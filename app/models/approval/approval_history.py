from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow


class ApprovalHistory(Base):
    __tablename__ = "approval_histories"

    id: Mapped[int] = mapped_column(primary_key=True)
    reimbursement_id: Mapped[int] = mapped_column(ForeignKey("reimbursements.id"), index=True)
    step: Mapped[Optional[str]] = mapped_column(String(20))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    actor_role: Mapped[str] = mapped_column(String(20))
    decision: Mapped[str] = mapped_column(String(25))
    note: Mapped[Optional[str]] = mapped_column(Text)
    amount_before: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    amount_after: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    ip_address: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    reimbursement = relationship("Reimbursement", back_populates="history")
    actor = relationship("User")

    @property
    def actor_name(self) -> Optional[str]:
        return self.actor.full_name if self.actor else None
