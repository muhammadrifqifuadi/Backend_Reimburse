from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(30), unique=True, index=True)  # NIK
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="karyawan", index=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"))
    job_level_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_levels.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # True = password sementara dari sistem; user wajib menggantinya sebelum memakai fitur lain
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # dinaikkan saat password diganti/direset atau akun dinonaktifkan -> semua token lama otomatis tidak berlaku
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    department = relationship("Department")
    job_level = relationship("JobLevel")
