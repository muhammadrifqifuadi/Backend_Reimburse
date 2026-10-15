from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExpenseCategory(Base):
    __tablename__ = "expense_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(String(255))
    requires_receipt: Mapped[bool] = mapped_column(Boolean, default=True)  # kwitansi wajib berapa pun nominalnya
    requires_attachment: Mapped[bool] = mapped_column(Boolean, default=True)  # kwitansi harus diunggah
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
