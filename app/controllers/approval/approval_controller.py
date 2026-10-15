from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import (
    ITEM_APPROVED,
    ITEM_PARTIAL,
    ITEM_REJECTED,
    STATUS_AFTER_STEP,
    Decision,
    Role,
    Status,
)
from app.models.approval.approval_history import ApprovalHistory
from app.models.auth.user import User
from app.models.reimbursement.reimbursement import Reimbursement
from app.controllers.reimbursement.reimbursement_controller import get_claim
from app.services import approval_workflow as wf
from app.services import email_utils
from app.utils.pagination import paginate
from app.utils.validators import rupiah


def list_pending(db: Session, user: User, skip: int, limit: int):
    """Klaim yang sedang menunggu keputusan `user`: tahap = role (hrd / finance), bukan klaim sendiri."""
    stmt = (
        select(Reimbursement)
        .where(Reimbursement.current_step == user.role, Reimbursement.user_id != user.id)
        .order_by(Reimbursement.submitted_at)
    )
    return paginate(db, stmt, skip, limit)


def list_my_decisions(db: Session, user: User, skip: int, limit: int):
    ids = select(ApprovalHistory.reimbursement_id).where(
        ApprovalHistory.actor_id == user.id, ApprovalHistory.decision != Decision.SUBMITTED
    )
    stmt = select(Reimbursement).where(Reimbursement.id.in_(ids)).order_by(Reimbursement.updated_at.desc())
    return paginate(db, stmt, skip, limit)


def _apply_item_decisions(claim: Reimbursement, decisions: list) -> None:
    by_id = {i.id: i for i in claim.items}
    for d in decisions:
        item = by_id.get(d.item_id)
        if not item:
            raise HTTPException(422, f"Item {d.item_id} bukan bagian dari klaim ini")
        current = item.amount_approved if item.amount_approved is not None else item.amount_idr
        if d.amount_approved > current:
            raise HTTPException(422, f"Item {d.item_id}: nominal disetujui tidak boleh melebihi {rupiah(current)}")
        item.amount_approved = d.amount_approved
        item.item_note = d.note or item.item_note
        if d.amount_approved == 0:
            item.item_status = ITEM_REJECTED
        elif d.amount_approved < item.amount_idr:
            item.item_status = ITEM_PARTIAL
        else:
            item.item_status = ITEM_APPROVED


def _load_for_decision(db: Session, claim_id: int, user: User) -> Reimbursement:
    claim = get_claim(db, claim_id)
    if not wf.can_act(user, claim):
        # sengaja pesan umum: tidak membocorkan alasan (klaim sendiri / bukan bawahan / bukan giliran)
        raise HTTPException(403, "Anda tidak berhak memutuskan klaim ini pada tahap saat ini")
    return claim


def approve(db: Session, claim_id: int, payload, user: User, ip: str | None) -> Reimbursement:
    claim = _load_for_decision(db, claim_id, user)
    before = claim.total_approved
    step = claim.current_step

    _apply_item_decisions(claim, payload.items)
    wf.recompute_totals(claim)
    if claim.total_approved <= 0:
        raise HTTPException(422, "Semua item bernilai 0. Gunakan Tolak jika klaim tidak disetujui.")

    # item yang belum disentuh dianggap disetujui penuh pada tahap ini
    for it in claim.items:
        if it.item_status == "pending":
            it.item_status = ITEM_APPROVED

    claim.status = STATUS_AFTER_STEP[step]
    claim.current_step = wf.next_step(step)
    wf.recompute_totals(claim)
    wf.record(db, claim, user, Decision.APPROVED, payload.note, before, claim.total_approved, ip, step)
    db.commit()

    email_utils.send_email(
        wf.recipients_for_current_step(db, claim),
        f"[Reimburse] Menunggu tindakan: {claim.claim_number}",
        f"Klaim '{claim.title}' dari {claim.user.full_name} disetujui pada tahap {step} "
        f"dan kini menunggu tahap berikutnya ({claim.current_step}).",
    )
    return get_claim(db, claim.id)


def reject(db: Session, claim_id: int, payload, user: User, ip: str | None) -> Reimbursement:
    claim = _load_for_decision(db, claim_id, user)
    step = claim.current_step
    wf.record(db, claim, user, Decision.REJECTED, payload.note, claim.total_approved, Decimal(0), ip, step)
    claim.status, claim.current_step, claim.rejected_reason = Status.REJECTED, None, payload.note
    db.commit()
    email_utils.send_email(
        [claim.user.email],
        f"[Reimburse] Klaim ditolak: {claim.claim_number}",
        f"Klaim '{claim.title}' ditolak oleh {user.full_name} ({user.role}).\nAlasan: {payload.note}",
    )
    return get_claim(db, claim.id)


def request_revision(db: Session, claim_id: int, payload, user: User, ip: str | None) -> Reimbursement:
    claim = _load_for_decision(db, claim_id, user)
    step = claim.current_step
    wf.record(db, claim, user, Decision.REVISION, payload.note, claim.total_approved, None, ip, step)
    claim.status, claim.current_step, claim.revision_note = Status.REVISION, None, payload.note
    for it in claim.items:  # hasil penilaian lama dibuang, dinilai ulang setelah submit ulang
        it.amount_approved, it.item_status = None, "pending"
    wf.recompute_totals(claim)
    db.commit()
    email_utils.send_email(
        [claim.user.email],
        f"[Reimburse] Klaim perlu revisi: {claim.claim_number}",
        f"Klaim '{claim.title}' dikembalikan oleh {user.full_name} ({user.role}).\nCatatan: {payload.note}",
    )
    return get_claim(db, claim.id)
