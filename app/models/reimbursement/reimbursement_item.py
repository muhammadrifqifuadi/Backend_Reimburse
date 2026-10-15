from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, JSONType, utcnow


class ReimbursementItem(Base):
    __tablename__ = "reimbursement_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    reimbursement_id: Mapped[int] = mapped_column(ForeignKey("reimbursements.id"), index=True)

    # dasar
    category_id: Mapped[int] = mapped_column(ForeignKey("expense_categories.id"), index=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100))
    expense_date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(255))
    merchant_name: Mapped[Optional[str]] = mapped_column(String(150))
    location: Mapped[Optional[str]] = mapped_column(String(150))

    # bukti
    receipt_number: Mapped[Optional[str]] = mapped_column(String(80))
    receipt_date: Mapped[Optional[date]] = mapped_column(Date)
    has_receipt: Mapped[bool] = mapped_column(Boolean, default=True)
    no_receipt_reason: Mapped[Optional[str]] = mapped_column(Text)

    # nominal
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2))  # quantity x unit_price (belum pajak)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="IDR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=1)
    amount_idr: Mapped[Decimal] = mapped_column(Numeric(15, 2))  # (amount + tax) x kurs
    payment_method: Mapped[str] = mapped_column(String(20), default="cash")

    # khusus kategori (transport, makan, akomodasi, kesehatan)
    extra_data: Mapped[dict] = mapped_column(JSONType, default=dict)

    # penilaian approver/HRD/finance
    amount_approved: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    item_status: Mapped[str] = mapped_column(String(15), default="pending")
    item_note: Mapped[Optional[str]] = mapped_column(Text)
    policy_flags: Mapped[list] = mapped_column(JSONType, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    reimbursement = relationship("Reimbursement", back_populates="items")
    category = relationship("ExpenseCategory")
    attachments = relationship(
        "Attachment", back_populates="item", cascade="all, delete-orphan", order_by="Attachment.id"
    )
