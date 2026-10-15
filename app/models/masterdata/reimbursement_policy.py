from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReimbursementPolicy(Base):
    """Limit per level jabatan x kategori. NULL = tidak dibatasi."""

    __tablename__ = "reimbursement_policies"
    __table_args__ = (UniqueConstraint("job_level_id", "category_id", name="uq_policy_level_category"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_level_id: Mapped[int] = mapped_column(ForeignKey("job_levels.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("expense_categories.id"), index=True)
    max_per_transaction: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    max_per_day: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    max_per_month: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    max_per_year: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    require_receipt_above: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    job_level = relationship("JobLevel")
    category = relationship("ExpenseCategory")
