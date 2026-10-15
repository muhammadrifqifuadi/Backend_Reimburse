import json
from datetime import datetime, time, timedelta

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.constants import (
    ITEM_APPROVED,
    ITEM_PENDING,
    Decision,
    Role,
    Status,
)
from app.core.database import utcnow
from app.models.auth.user import User
from app.models.bank_account.bank_account import BankAccount
from app.models.masterdata.expense_category import ExpenseCategory
from app.models.reimbursement.attachment import Attachment
from app.models.reimbursement.reimbursement import Reimbursement
from app.models.reimbursement.reimbursement_item import ReimbursementItem
from app.schemas.reimbursement.extraSchema import EXTRA_SCHEMAS
from app.services import approval_workflow as wf
from app.services import email_utils, file_storage, policy_validator
from app.services.audit import log_audit
from app.utils.pagination import paginate
from app.utils.validators import q2, rupiah

_LOAD = (
    selectinload(Reimbursement.items).selectinload(ReimbursementItem.attachments),
    selectinload(Reimbursement.items).selectinload(ReimbursementItem.category),
    selectinload(Reimbursement.history),
    selectinload(Reimbursement.payment),
)


# ---------------- helper akses ----------------
def get_claim(db: Session, claim_id: int) -> Reimbursement:
    claim = db.scalar(
        select(Reimbursement).where(Reimbursement.id == claim_id).options(*_LOAD).execution_options(populate_existing=True)
    )
    if not claim:
        raise HTTPException(404, "Klaim tidak ditemukan")
    return claim


def get_visible_claim(db: Session, claim_id: int, user: User) -> Reimbursement:
    claim = get_claim(db, claim_id)
    if not wf.can_view(db, user, claim):
        raise HTTPException(404, "Klaim tidak ditemukan")  # 404, bukan 403, agar tidak membocorkan keberadaan klaim
    return claim


def get_own_editable(db: Session, claim_id: int, user: User) -> Reimbursement:
    claim = get_claim(db, claim_id)
    if claim.user_id != user.id:
        raise HTTPException(404, "Klaim tidak ditemukan")
    if claim.status not in Status.EDITABLE:
        raise HTTPException(409, f"Klaim berstatus '{claim.status}' tidak dapat diubah")
    return claim


# ---------------- item ----------------
def _validate_extra(category: ExpenseCategory, extra: dict) -> dict:
    schema = EXTRA_SCHEMAS.get(category.code)
    if not schema:
        return extra or {}
    try:
        return schema.model_validate(extra or {}).model_dump(mode="json")
    except ValidationError as e:
        errors = [{"field": ".".join(str(x) for x in err["loc"]), "message": err["msg"]} for err in json.loads(e.json())]
        raise HTTPException(422, detail={"message": f"Data khusus kategori {category.name} tidak valid", "errors": errors})


def _apply_item(db: Session, item: ReimbursementItem, data: dict) -> None:
    category = db.get(ExpenseCategory, data["category_id"])
    if not category or not category.is_active:
        raise HTTPException(422, "Kategori tidak ditemukan atau nonaktif")
    policy_validator.check_expense_date(data["expense_date"])
    extra = _validate_extra(category, data.get("extra_data") or {})

    rate = data["exchange_rate"] if data["currency"] != "IDR" else 1
    amount = q2(data["quantity"] * data["unit_price"])
    for field in (
        "category_id", "subcategory", "expense_date", "description", "merchant_name", "location",
        "receipt_number", "receipt_date", "has_receipt", "no_receipt_reason", "quantity", "unit_price",
        "tax_amount", "currency", "payment_method",
    ):
        setattr(item, field, data.get(field))
    if item.has_receipt:
        item.no_receipt_reason = None
    item.exchange_rate = rate
    item.amount = amount
    item.amount_idr = q2((amount + data["tax_amount"]) * rate)
    item.extra_data = extra
    item.item_status = ITEM_PENDING
    item.amount_approved = None
    item.policy_flags = []


def add_item(db: Session, claim_id: int, data: dict, user: User) -> Reimbursement:
    claim = get_own_editable(db, claim_id, user)
    item = ReimbursementItem()
    _apply_item(db, item, data)
    claim.items.append(item)
    db.flush()
    wf.recompute_totals(claim)
    claim.updated_by = user.id
    db.commit()
    return get_claim(db, claim.id)


def update_item(db: Session, claim_id: int, item_id: int, data: dict, user: User) -> Reimbursement:
    claim = get_own_editable(db, claim_id, user)
    item = next((i for i in claim.items if i.id == item_id), None)
    if not item:
        raise HTTPException(404, "Item tidak ditemukan")
    _apply_item(db, item, data)
    wf.recompute_totals(claim)
    claim.updated_by = user.id
    db.commit()
    return get_claim(db, claim.id)


def delete_item(db: Session, claim_id: int, item_id: int, user: User) -> Reimbursement:
    claim = get_own_editable(db, claim_id, user)
    item = next((i for i in claim.items if i.id == item_id), None)
    if not item:
        raise HTTPException(404, "Item tidak ditemukan")
    paths = [a.file_path for a in item.attachments]
    claim.items.remove(item)
    db.flush()
    wf.recompute_totals(claim)
    claim.updated_by = user.id
    db.commit()
    for p in paths:
        file_storage.delete_file(p)
    return get_claim(db, claim.id)


# ---------------- header ----------------
def _new_claim_number(db: Session) -> str:
    now = utcnow()
    prefix = f"REM/{now:%Y}/{now:%m}/"
    from sqlalchemy import func

    last = db.scalar(select(func.max(Reimbursement.claim_number)).where(Reimbursement.claim_number.like(prefix + "%")))
    seq = int(last.rsplit("/", 1)[1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def create_claim(db: Session, data: dict, user: User) -> Reimbursement:
    items = data.pop("items", [])
    for attempt in range(3):  # retry jika nomor klaim bentrok (request bersamaan)
        claim = Reimbursement(
            claim_number=_new_claim_number(db),
            user_id=user.id,
            department_id=user.department_id,
            job_level_id=user.job_level_id,
            status=Status.DRAFT,
            created_by=user.id,
            updated_by=user.id,
            **data,
        )
        db.add(claim)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            if attempt == 2:
                raise HTTPException(409, "Gagal membuat nomor klaim, coba lagi")
    for it in items:
        item = ReimbursementItem()
        _apply_item(db, item, it)
        claim.items.append(item)
    db.flush()
    wf.recompute_totals(claim)
    db.commit()
    return get_claim(db, claim.id)


def update_header(db: Session, claim_id: int, data: dict, user: User) -> Reimbursement:
    claim = get_own_editable(db, claim_id, user)
    for k, v in data.items():
        setattr(claim, k, v)
    if claim.claim_period_end < claim.claim_period_start:
        raise HTTPException(422, "claim_period_end tidak boleh sebelum claim_period_start")
    wf.recompute_totals(claim)
    claim.updated_by = user.id
    db.commit()
    return get_claim(db, claim.id)


def list_mine(db: Session, user: User, status: str | None, q: str | None, skip: int, limit: int):
    stmt = select(Reimbursement).where(Reimbursement.user_id == user.id).order_by(Reimbursement.id.desc())
    if status:
        stmt = stmt.where(Reimbursement.status == status)
    if q:
        stmt = stmt.where(or_(Reimbursement.claim_number.ilike(f"%{q}%"), Reimbursement.title.ilike(f"%{q}%")))
    return paginate(db, stmt, skip, limit)


def list_all(db: Session, status: str | None, user_id: int | None, department_id: int | None,
             date_from, date_to, q: str | None, skip: int, limit: int):
    stmt = select(Reimbursement).where(Reimbursement.status != Status.DRAFT).order_by(Reimbursement.id.desc())
    stmt = apply_filters(stmt, status, user_id, department_id, date_from, date_to, q)
    return paginate(db, stmt, skip, limit)


def apply_filters(stmt, status=None, user_id=None, department_id=None, date_from=None, date_to=None, q=None):
    if status:
        stmt = stmt.where(Reimbursement.status == status)
    if user_id:
        stmt = stmt.where(Reimbursement.user_id == user_id)
    if department_id:
        stmt = stmt.where(Reimbursement.department_id == department_id)
    if date_from:
        stmt = stmt.where(Reimbursement.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        stmt = stmt.where(Reimbursement.created_at < datetime.combine(date_to + timedelta(days=1), time.min))
    if q:
        stmt = stmt.where(or_(Reimbursement.claim_number.ilike(f"%{q}%"), Reimbursement.title.ilike(f"%{q}%")))
    return stmt


# ---------------- lampiran ----------------
def add_attachment(db: Session, claim_id: int, item_id: int, filename: str, content: bytes, user: User) -> Attachment:
    claim = get_own_editable(db, claim_id, user)
    item = next((i for i in claim.items if i.id == item_id), None)
    if not item:
        raise HTTPException(404, "Item tidak ditemukan")
    meta = file_storage.save_receipt(claim.id, filename, content)

    dup = db.execute(
        select(Reimbursement.claim_number)
        .join(Attachment, Attachment.reimbursement_id == Reimbursement.id)
        .where(Attachment.checksum == meta["checksum"], Reimbursement.status.notin_((Status.CANCELLED, Status.REJECTED)))
    ).first()
    if dup:
        file_storage.delete_file(meta["file_path"])
        raise HTTPException(409, f"Kwitansi ini sudah pernah diunggah pada klaim {dup[0]}")

    att = Attachment(reimbursement_id=claim.id, item_id=item.id, uploaded_by=user.id, **meta)
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


def delete_attachment(db: Session, attachment_id: int, user: User) -> None:
    att = db.get(Attachment, attachment_id)
    if not att:
        raise HTTPException(404, "Lampiran tidak ditemukan")
    get_own_editable(db, att.reimbursement_id, user)
    path = att.file_path
    db.delete(att)
    db.commit()
    file_storage.delete_file(path)


def get_attachment_for_download(db: Session, attachment_id: int, user: User) -> Attachment:
    att = db.get(Attachment, attachment_id)
    if not att:
        raise HTTPException(404, "Lampiran tidak ditemukan")
    get_visible_claim(db, att.reimbursement_id, user)
    return att


# ---------------- submit & cancel ----------------
def submit(db: Session, claim_id: int, bank_account_id: int | None, user: User, ip: str | None) -> Reimbursement:
    claim = get_own_editable(db, claim_id, user)

    # rekening tujuan
    q = select(BankAccount).where(BankAccount.user_id == user.id, BankAccount.is_active.is_(True))
    q = q.where(BankAccount.id == bank_account_id) if bank_account_id else q.where(BankAccount.is_default.is_(True))
    account = db.scalar(q)
    if not account:
        raise HTTPException(422, "Rekening belum dipilih. Tambahkan rekening dan jadikan default sebelum mengajukan klaim.")

    wf.recompute_totals(claim)
    policy_validator.validate_for_submit(db, claim)

    # snapshot rekening: perubahan rekening di kemudian hari tidak memengaruhi klaim ini
    claim.bank_code, claim.bank_name = account.bank_code, account.bank_name
    claim.account_number, claim.account_holder_name = account.account_number, account.account_holder_name

    for it in claim.items:
        it.amount_approved, it.item_status, it.item_note = it.amount_idr, ITEM_PENDING, None
    claim.status = Status.SUBMITTED
    claim.current_step = wf.first_step()
    claim.submitted_at = utcnow()
    claim.rejected_reason = claim.revision_note = None
    claim.updated_by = user.id
    wf.recompute_totals(claim)
    wf.record(db, claim, user, Decision.SUBMITTED, after=claim.total_claimed, ip=ip, step="karyawan")
    log_audit(db, user.id, "claim_submit", "reimbursement", claim.id, {"claim": claim.claim_number}, ip)
    db.commit()

    email_utils.send_email(
        wf.recipients_for_current_step(db, claim),
        f"[Reimburse] Menunggu persetujuan: {claim.claim_number}",
        f"{user.full_name} mengajukan klaim '{claim.title}' sebesar {rupiah(claim.total_claimed)}.\n"
        f"Silakan tinjau di aplikasi (menu Persetujuan).",
    )
    return get_claim(db, claim.id)


def cancel(db: Session, claim_id: int, reason: str | None, user: User, ip: str | None) -> Reimbursement:
    claim = get_claim(db, claim_id)
    if claim.user_id != user.id:
        raise HTTPException(404, "Klaim tidak ditemukan")
    if claim.status not in Status.CANCELABLE:
        raise HTTPException(409, "Klaim yang sudah diproses tidak dapat dibatalkan")
    claim.status, claim.current_step, claim.cancelled_at = Status.CANCELLED, None, utcnow()
    claim.updated_by = user.id
    if claim.status != Status.DRAFT:
        wf.record(db, claim, user, Decision.CANCELLED, note=reason, ip=ip)
    db.commit()
    return get_claim(db, claim.id)
