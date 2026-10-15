from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    reimbursement_id: Mapped[int] = mapped_column(ForeignKey("reimbursements.id"), unique=True)
    paid_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    payment_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    bank_name: Mapped[Optional[str]] = mapped_column(String(100))
    account_number_masked: Mapped[Optional[str]] = mapped_column(String(30))
    bank_reference: Mapped[Optional[str]] = mapped_column(String(100))  # no. referensi transfer
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    reimbursement = relationship("Reimbursement", back_populates="payment")
    payer = relationship("User", foreign_keys=[paid_by])

    @property
    def paid_by_name(self) -> Optional[str]:
        return self.payer.full_name if self.payer else None
