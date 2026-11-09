from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.core.constants import Role
from app.schemas.common import Money, ORMModel


class BankOption(BaseModel):
    code: str
    name: str


# ---- departemen ----
class DepartmentIn(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=100)
    is_active: bool = True


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    is_active: Optional[bool] = None


class DepartmentOut(ORMModel):
    id: int
    code: str
    name: str
    is_active: bool


# ---- level jabatan ----
class JobLevelIn(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=100)
    rank_order: int = Field(ge=1, default=1)
    is_active: bool = True


class JobLevelUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    rank_order: Optional[int] = Field(default=None, ge=1)
    is_active: Optional[bool] = None


class JobLevelOut(ORMModel):
    id: int
    code: str
    name: str
    rank_order: int
    is_active: bool


# ---- kategori klaim ----
class CategoryIn(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = None
    requires_receipt: bool = True
    requires_attachment: bool = True
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = None
    requires_receipt: Optional[bool] = None
    requires_attachment: Optional[bool] = None
    is_active: Optional[bool] = None


class CategoryOut(ORMModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    requires_receipt: bool
    requires_attachment: bool
    is_active: bool


class CategoryBrief(ORMModel):
    id: int
    code: str
    name: str


# ---- kebijakan limit ----
class PolicyIn(BaseModel):
    job_level_id: int
    category_id: int
    max_per_transaction: Optional[Decimal] = Field(default=None, ge=0)
    max_per_day: Optional[Decimal] = Field(default=None, ge=0)
    max_per_month: Optional[Decimal] = Field(default=None, ge=0)
    max_per_year: Optional[Decimal] = Field(default=None, ge=0)
    require_receipt_above: Optional[Decimal] = Field(default=None, ge=0)
    is_active: bool = True


class PolicyUpdate(BaseModel):
    max_per_transaction: Optional[Decimal] = Field(default=None, ge=0)
    max_per_day: Optional[Decimal] = Field(default=None, ge=0)
    max_per_month: Optional[Decimal] = Field(default=None, ge=0)
    max_per_year: Optional[Decimal] = Field(default=None, ge=0)
    require_receipt_above: Optional[Decimal] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


class PolicyOut(ORMModel):
    id: int
    job_level_id: int
    category_id: int
    max_per_transaction: Optional[Money] = None
    max_per_day: Optional[Money] = None
    max_per_month: Optional[Money] = None
    max_per_year: Optional[Money] = None
    require_receipt_above: Optional[Money] = None
    is_active: bool


# ---- user ----
class UserCreate(BaseModel):
    # employee_id: str = Field(min_length=2, max_length=30)
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=30)
    role: str = Role.KARYAWAN
    department_id: Optional[int] = None
    job_level_id: Optional[int] = None

    @model_validator(mode="after")
    def check_role(self):
        if self.role not in Role.ALL:
            raise ValueError(f"Role harus salah satu dari: {', '.join(Role.ALL)}")
        return self


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=30)
    role: Optional[str] = None
    department_id: Optional[int] = None
    job_level_id: Optional[int] = None
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def check_role(self):
        if self.role is not None and self.role not in Role.ALL:
            raise ValueError(f"Role harus salah satu dari: {', '.join(Role.ALL)}")
        return self


class UserOut(ORMModel):
    id: int
    employee_id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    role: str
    is_active: bool
    must_change_password: bool = False
    department: Optional[DepartmentOut] = None
    job_level: Optional[JobLevelOut] = None


class UserBrief(ORMModel):
    id: int
    employee_id: str
    full_name: str
