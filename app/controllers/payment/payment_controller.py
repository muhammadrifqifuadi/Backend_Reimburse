from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import STEP_PAYMENT, Decision, Status
from app.models.auth.user import User
from app.models.payment.payment import Payment
from app.models.reimbursement.reimbursement import Reimbursement
from app.controllers.reimbursement.reimbursement_controller import get_claim
from app.services import approval_workflow as wf
from app.services import email_utils
from app.services.audit import log_audit
from app.utils.pagination import paginate
from app.utils.validators import rupiah


def list_awaiting_payment(db: Session, user: User, skip: int, limit: int):
    stmt = (
        select(Reimbursement)
        .where(Reimbursement.status == Status.APPROVED_FINANCE, Reimbursement.user_id != user.id)
        .order_by(Reimbursement.submitted_at)
    )
    return paginate(db, stmt, skip, limit)


def list_payments(db: Session, skip: int, limit: int):
    return paginate(db, select(Payment).order_by(Payment.id.desc()), skip, limit)


def _payable_claim(db: Session, claim_id: int, user: User) -> Reimbursement:
    claim = get_claim(db, claim_id)
    if claim.user_id == user.id:
        raise HTTPException(403, "Anda tidak dapat memproses pembayaran klaim sendiri")
    if claim.status != Status.APPROVED_FINANCE or claim.current_step != STEP_PAYMENT:
        raise HTTPException(409, "Klaim belum siap dibayar (semua persetujuan harus selesai)")
    return claim


def destination_account(db: Session, claim_id: int, user: User, ip: str | None) -> dict:
    """Nomor rekening penuh: hanya finance, hanya saat siap dibayar, dan selalu dicatat di audit log."""
    claim = _payable_claim(db, claim_id, user)
    log_audit(db, user.id, "reveal_account_number", "reimbursement", claim.id, {"claim": claim.claim_number}, ip)
    db.commit()
    return {
        "claim_number": claim.claim_number,
        "bank_name": claim.bank_name,
        "account_number": claim.account_number,
        "account_holder_name": claim.account_holder_name,
        "amount_payable": claim.total_payable,
    }


def pay(db: Session, claim_id: int, payload, user: User, ip: str | None) -> Reimbursement:
    claim = _payable_claim(db, claim_id, user)
    if claim.total_payable <= 0:
        raise HTTPException(422, "Total yang dibayarkan 0 (tertutup uang muka). Tidak ada transfer yang perlu dilakukan.")
    claim.payment = (
        Payment(
            paid_by=user.id,
            payment_date=payload.payment_date,
            amount=claim.total_payable,
            bank_name=claim.bank_name,
            account_number_masked=claim.account_number_masked,
            bank_reference=payload.bank_reference,
            note=payload.note,
        )
    )
    claim.status, claim.current_step = Status.PAID, None
    wf.record(db, claim, user, Decision.PAID, payload.note, claim.total_payable, claim.total_payable, ip, STEP_PAYMENT)
    log_audit(db, user.id, "claim_paid", "reimbursement", claim.id,
              {"amount": float(claim.total_payable), "ref": payload.bank_reference}, ip)
    db.commit()
    email_utils.send_email(
        [claim.user.email],
        f"[Reimburse] Klaim dibayar: {claim.claim_number}",
        f"Klaim '{claim.title}' telah dibayar sebesar {rupiah(claim.total_payable)} "
        f"ke {claim.bank_name} {claim.account_number_masked}. Ref: {payload.bank_reference}.",
    )
    return get_claim(db, claim.id)
