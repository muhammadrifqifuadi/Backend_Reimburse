"""Alur status: karyawan -> HRD (approve) -> finance (verifikasi) -> finance (bayar)."""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import APPROVAL_STEPS, ITEM_REJECTED, STEP_PAYMENT, Role, Status
from app.models.approval.approval_history import ApprovalHistory
from app.models.auth.user import User
from app.models.reimbursement.reimbursement import Reimbursement
from app.utils.validators import q2


def first_step() -> str:
    return APPROVAL_STEPS[0]


def next_step(step: str) -> str:
    idx = APPROVAL_STEPS.index(step)
    return APPROVAL_STEPS[idx + 1] if idx + 1 < len(APPROVAL_STEPS) else STEP_PAYMENT


def can_act(user: User, claim: Reimbursement) -> bool:
    """Apakah `user` berhak memutuskan klaim ini pada tahap saat ini?"""
    step = claim.current_step
    if step not in APPROVAL_STEPS or not user.is_active:
        return False
    if user.id == claim.user_id:  # tidak boleh menyetujui klaim sendiri
        return False
    return user.role == step  # nama tahap = role yang berhak (hrd / finance)


def can_view(db: Session, user: User, claim: Reimbursement) -> bool:
    return claim.user_id == user.id or user.role in (Role.HRD, Role.FINANCE, Role.ADMIN)


def record(
    db: Session,
    claim: Reimbursement,
    user: User,
    decision: str,
    note: str | None = None,
    before: Decimal | None = None,
    after: Decimal | None = None,
    ip: str | None = None,
    step: str | None = None,
) -> None:
    claim.history.append(
        ApprovalHistory(
            step=step,
            actor_id=user.id,
            actor_role=user.role,
            decision=decision,
            note=note,
            amount_before=before,
            amount_after=after,
            ip_address=ip,
        )
    )


def recompute_totals(claim: Reimbursement) -> None:
    sub = tax = claimed = approved = Decimal(0)
    for it in claim.items:
        rate = it.exchange_rate or Decimal(1)
        sub += q2(it.amount * rate)
        tax += q2(it.tax_amount * rate)
        claimed += it.amount_idr
        if it.amount_approved is not None and it.item_status != ITEM_REJECTED:
            approved += it.amount_approved
    claim.subtotal, claim.tax_total, claim.total_claimed, claim.total_approved = sub, tax, claimed, approved
    base = claimed if (claim.status in Status.EDITABLE or not claim.submitted_at) else approved
    claim.total_payable = max(base - (claim.advance_deducted or Decimal(0)), Decimal(0))


def recipients_for_current_step(db: Session, claim: Reimbursement) -> list[str]:
    """Email penerima notifikasi untuk langkah yang sedang menunggu (selain pemohon sendiri)."""
    step = claim.current_step
    if step not in (*APPROVAL_STEPS, STEP_PAYMENT):
        return []
    role = Role.FINANCE if step == STEP_PAYMENT else step
    users = db.scalars(select(User).where(User.role == role, User.is_active.is_(True), User.id != claim.user_id))
    return [u.email for u in users]
