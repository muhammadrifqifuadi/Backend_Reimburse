from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ItemDecision(BaseModel):
    """Setujui sebagian: turunkan nominal disetujui per item (0 = item ditolak)."""

    item_id: int
    amount_approved: Decimal = Field(ge=0)
    note: Optional[str] = None


class ApproveRequest(BaseModel):
    note: Optional[str] = None
    items: list[ItemDecision] = Field(default_factory=list)


class RejectRequest(BaseModel):
    note: str = Field(min_length=5, description="Alasan penolakan (wajib)")


class RevisionRequest(BaseModel):
    note: str = Field(min_length=5, description="Apa yang harus diperbaiki (wajib)")
