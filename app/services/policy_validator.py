"""Validasi kebijakan reimburse.

Aturan KERAS (klaim ditolak sistem, harus diperbaiki pemohon):
  - tanggal pengeluaran di masa depan / lebih tua dari CLAIM_MAX_AGE_DAYS
  - item di atas batas tanpa kwitansi
  - item wajib kwitansi tapi belum ada file
  - klaim tanpa item / uang muka melebihi total
Aturan LUNAK (klaim lanjut, ditandai `policy_flags` agar HRD memeriksa):
  - melebihi limit per transaksi / hari / bulan / tahun
  - tanggal pengeluaran di luar periode klaim
"""
import calendar
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import Status
from app.models.masterdata.reimbursement_policy import ReimbursementPolicy
from app.models.reimbursement.reimbursement import Reimbursement
from app.models.reimbursement.reimbursement_item import ReimbursementItem
from app.utils.validators import rupiah


def check_expense_date(expense_date: date) -> None:
    today = date.today()
    if expense_date > today:
        raise HTTPException(422, "Tanggal pengeluaran tidak boleh di masa depan")
    if (today - expense_date).days > settings.CLAIM_MAX_AGE_DAYS:
        raise HTTPException(
            422, f"Pengeluaran lebih dari {settings.CLAIM_MAX_AGE_DAYS} hari yang lalu tidak dapat diklaim"
        )


def get_policy(db: Session, job_level_id: int | None, category_id: int) -> ReimbursementPolicy | None:
    if not job_level_id:
        return None
    return db.scalar(
        select(ReimbursementPolicy).where(
            ReimbursementPolicy.job_level_id == job_level_id,
            ReimbursementPolicy.category_id == category_id,
            ReimbursementPolicy.is_active.is_(True),
        )
    )


def _used_in_window(db: Session, claim: Reimbursement, category_id: int, start: date, end: date) -> Decimal:
    """Total yang sudah dipakai pemohon (klaim lain yang aktif) + item klaim ini pada rentang tanggal."""
    stmt = (
        select(func.coalesce(func.sum(ReimbursementItem.amount_idr), 0))
        .join(Reimbursement, Reimbursement.id == ReimbursementItem.reimbursement_id)
        .where(
            Reimbursement.user_id == claim.user_id,
            Reimbursement.id != claim.id,
            Reimbursement.status.in_(Status.ACTIVE),
            ReimbursementItem.category_id == category_id,
            ReimbursementItem.expense_date.between(start, end),
        )
    )
    others = Decimal(str(db.scalar(stmt) or 0))
    own = sum(
        (i.amount_idr for i in claim.items if i.category_id == category_id and start <= i.expense_date <= end),
        Decimal(0),
    )
    return others + own


def _limit_flags(db: Session, claim: Reimbursement, item: ReimbursementItem, policy: ReimbursementPolicy | None):
    if not policy:
        return []
    flags: list[str] = []
    d = item.expense_date
    if policy.max_per_transaction is not None and item.amount_idr > policy.max_per_transaction:
        flags.append(
            f"Melebihi limit per transaksi: {rupiah(item.amount_idr)} (limit {rupiah(policy.max_per_transaction)})"
        )
    windows = (
        ("hari", policy.max_per_day, d, d),
        ("bulan", policy.max_per_month, d.replace(day=1), d.replace(day=calendar.monthrange(d.year, d.month)[1])),
        ("tahun", policy.max_per_year, date(d.year, 1, 1), date(d.year, 12, 31)),
    )
    for label, limit, start, end in windows:
        if limit is None:
            continue
        used = _used_in_window(db, claim, item.category_id, start, end)
        if used > limit:
            flags.append(f"Total kategori ini dalam satu {label} {rupiah(used)} melebihi limit {rupiah(limit)}")
    return flags


def _receipt_threshold(item: ReimbursementItem, policy: ReimbursementPolicy | None) -> Decimal:
    if policy and policy.require_receipt_above is not None:
        return policy.require_receipt_above
    if item.category.requires_receipt:
        return Decimal(0)
    return Decimal(str(settings.RECEIPT_REQUIRED_ABOVE))


def validate_for_submit(db: Session, claim: Reimbursement) -> None:
    """Jalankan semua aturan. Raise 422 berisi daftar masalah; set policy_flags untuk aturan lunak."""
    errors: list[str] = []
    if not claim.items:
        errors.append("Klaim belum memiliki item pengeluaran")
    if claim.advance_deducted > claim.total_claimed:
        errors.append("Uang muka yang dipotong melebihi total klaim")

    for idx, item in enumerate(claim.items, 1):
        label = f"Item #{idx} ({item.description[:40]})"
        try:
            check_expense_date(item.expense_date)
        except HTTPException as e:
            errors.append(f"{label}: {e.detail}")

        policy = get_policy(db, claim.job_level_id, item.category_id)
        if not item.has_receipt and item.amount_idr > _receipt_threshold(item, policy):
            errors.append(f"{label}: nominal {rupiah(item.amount_idr)} wajib disertai kwitansi")
        if item.has_receipt and item.category.requires_attachment and not item.attachments:
            errors.append(f"{label}: file kwitansi belum diunggah")

        flags = _limit_flags(db, claim, item, policy)
        if not (claim.claim_period_start <= item.expense_date <= claim.claim_period_end):
            flags.append("Tanggal pengeluaran di luar periode klaim")
        item.policy_flags = flags  # assign list baru agar perubahan terdeteksi

    if errors:
        raise HTTPException(422, detail={"message": "Klaim belum memenuhi syarat untuk diajukan", "errors": errors})
    claim.has_policy_flag = any(i.policy_flags for i in claim.items)
