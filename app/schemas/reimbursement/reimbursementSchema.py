from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.constants import PAYMENT_METHODS
from app.schemas.common import Money, ORMModel
from app.schemas.masterdata.masterdataSchema import CategoryBrief, DepartmentOut, JobLevelOut, UserBrief


# ---------------- item ----------------
class ItemIn(BaseModel):
    category_id: int
    subcategory: Optional[str] = Field(default=None, max_length=100)
    expense_date: date
    description: str = Field(min_length=3, max_length=255)
    merchant_name: Optional[str] = Field(default=None, max_length=150)
    location: Optional[str] = Field(default=None, max_length=150)

    receipt_number: Optional[str] = Field(default=None, max_length=80)
    receipt_date: Optional[date] = None
    has_receipt: bool = True
    no_receipt_reason: Optional[str] = None

    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal = Field(gt=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    exchange_rate: Decimal = Field(default=Decimal("1"), gt=0)
    payment_method: str = "cash"

    extra_data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()

    @field_validator("payment_method")
    @classmethod
    def check_method(cls, v: str) -> str:
        if v not in PAYMENT_METHODS:
            raise ValueError(f"payment_method harus salah satu dari: {', '.join(PAYMENT_METHODS)}")
        return v

    @model_validator(mode="after")
    def check_receipt(self):
        if not self.has_receipt and not (self.no_receipt_reason and self.no_receipt_reason.strip()):
            raise ValueError("no_receipt_reason wajib diisi jika tidak ada kwitansi")
        if self.currency != "IDR" and self.exchange_rate == 1:
            raise ValueError("exchange_rate wajib diisi untuk mata uang selain IDR")
        return self


class AttachmentOut(ORMModel):
    id: int
    item_id: int
    file_name: str
    mime_type: str
    size: int
    checksum: str
    created_at: datetime


class ItemOut(ORMModel):
    id: int
    category: CategoryBrief
    subcategory: Optional[str] = None
    expense_date: date
    description: str
    merchant_name: Optional[str] = None
    location: Optional[str] = None
    receipt_number: Optional[str] = None
    receipt_date: Optional[date] = None
    has_receipt: bool
    no_receipt_reason: Optional[str] = None
    quantity: Money
    unit_price: Money
    amount: Money
    tax_amount: Money
    currency: str
    exchange_rate: Money
    amount_idr: Money
    payment_method: str
    extra_data: dict[str, Any]
    amount_approved: Optional[Money] = None
    item_status: str
    item_note: Optional[str] = None
    policy_flags: list[str]
    attachments: list[AttachmentOut] = []


# ---------------- header ----------------
class ReimbursementCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = None
    purpose: str = Field(min_length=5)
    cost_center: Optional[str] = Field(default=None, max_length=50)
    project_code: Optional[str] = Field(default=None, max_length=50)
    claim_period_start: date
    claim_period_end: date
    advance_deducted: Decimal = Field(default=Decimal("0"), ge=0)
    items: list[ItemIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_period(self):
        if self.claim_period_end < self.claim_period_start:
            raise ValueError("claim_period_end tidak boleh sebelum claim_period_start")
        return self


class ReimbursementUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    description: Optional[str] = None
    purpose: Optional[str] = Field(default=None, min_length=5)
    cost_center: Optional[str] = Field(default=None, max_length=50)
    project_code: Optional[str] = Field(default=None, max_length=50)
    claim_period_start: Optional[date] = None
    claim_period_end: Optional[date] = None
    advance_deducted: Optional[Decimal] = Field(default=None, ge=0)


class SubmitRequest(BaseModel):
    bank_account_id: Optional[int] = None  # kosong = pakai rekening default


class CancelRequest(BaseModel):
    reason: Optional[str] = None


class HistoryOut(ORMModel):
    id: int
    step: Optional[str] = None
    actor_id: int
    actor_name: Optional[str] = None
    actor_role: str
    decision: str
    note: Optional[str] = None
    amount_before: Optional[Money] = None
    amount_after: Optional[Money] = None
    created_at: datetime


class PaymentOut(ORMModel):
    id: int
    reimbursement_id: int
    paid_by: int
    paid_by_name: Optional[str] = None
    payment_date: date
    amount: Money
    bank_name: Optional[str] = None
    account_number_masked: Optional[str] = None
    bank_reference: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime


class ReimbursementOut(ORMModel):
    id: int
    claim_number: str
    user: UserBrief
    department: Optional[DepartmentOut] = None
    job_level: Optional[JobLevelOut] = None
    cost_center: Optional[str] = None
    project_code: Optional[str] = None
    title: str
    description: Optional[str] = None
    purpose: str
    claim_period_start: date
    claim_period_end: date
    currency: str
    subtotal: Money
    tax_total: Money
    total_claimed: Money
    total_approved: Money
    advance_deducted: Money
    total_payable: Money
    bank_name: Optional[str] = None
    account_number_masked: Optional[str] = None
    account_holder_name: Optional[str] = None
    status: str
    current_step: Optional[str] = None
    has_policy_flag: bool
    submitted_at: Optional[datetime] = None
    rejected_reason: Optional[str] = None
    revision_note: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    items: list[ItemOut] = []
    history: list[HistoryOut] = []
    payment: Optional[PaymentOut] = None


class ReimbursementListOut(ORMModel):
    id: int
    claim_number: str
    user: UserBrief
    title: str
    status: str
    current_step: Optional[str] = None
    total_claimed: Money
    total_approved: Money
    total_payable: Money
    has_policy_flag: bool
    submitted_at: Optional[datetime] = None
    created_at: datetime
