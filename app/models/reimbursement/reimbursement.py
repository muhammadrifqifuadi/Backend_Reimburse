from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow
from app.utils.crypto_types import EncryptedString, mask_account


class Reimbursement(Base):
    __tablename__ = "reimbursements"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)  # REM/2026/10/0001

    # identitas pemohon (snapshot saat klaim dibuat)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"))
    job_level_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_levels.id"))
    cost_center: Mapped[Optional[str]] = mapped_column(String(50))
    project_code: Mapped[Optional[str]] = mapped_column(String(50))

    # isi klaim
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(Text)
    claim_period_start: Mapped[date] = mapped_column(Date)
    claim_period_end: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), default="IDR")

    # nominal (semua dalam IDR)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    total_claimed: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    total_approved: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    advance_deducted: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)  # uang muka
    total_payable: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)

    # rekening tujuan (snapshot saat submit)
    bank_code: Mapped[Optional[str]] = mapped_column(String(20))
    bank_name: Mapped[Optional[str]] = mapped_column(String(100))
    account_number: Mapped[Optional[str]] = mapped_column(EncryptedString())
    account_holder_name: Mapped[Optional[str]] = mapped_column(String(100))

    # status & alur
    status: Mapped[str] = mapped_column(String(25), default="draft", index=True)
    current_step: Mapped[Optional[str]] = mapped_column(String(20), index=True)  # approver/hrd/finance/payment
    has_policy_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    rejected_reason: Mapped[Optional[str]] = mapped_column(Text)
    revision_note: Mapped[Optional[str]] = mapped_column(Text)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # audit
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    created_by: Mapped[Optional[int]] = mapped_column(Integer)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer)

    user = relationship("User", foreign_keys=[user_id])
    department = relationship("Department")
    job_level = relationship("JobLevel")
    items = relationship(
        "ReimbursementItem",
        back_populates="reimbursement",
        cascade="all, delete-orphan",
        order_by="ReimbursementItem.id",
    )
    history = relationship(
        "ApprovalHistory",
        back_populates="reimbursement",
        cascade="all, delete-orphan",
        order_by="ApprovalHistory.id",
    )
    payment = relationship("Payment", back_populates="reimbursement", uselist=False)

    @property
    def account_number_masked(self) -> Optional[str]:
        return mask_account(self.account_number)
