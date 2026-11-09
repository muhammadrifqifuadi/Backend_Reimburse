from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class JobLevel(Base):
    __tablename__ = "job_levels"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    rank_order: Mapped[int] = mapped_column(Integer, unique=True, default=1)  # makin besar makin senior
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
