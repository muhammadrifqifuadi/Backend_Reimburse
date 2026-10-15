from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import Money


class PayRequest(BaseModel):
    payment_date: date
    bank_reference: str = Field(min_length=3, max_length=100)
    note: Optional[str] = None


class DestinationAccountOut(BaseModel):
    claim_number: str
    bank_name: str
    account_number: str
    account_holder_name: str
    amount_payable: Money
