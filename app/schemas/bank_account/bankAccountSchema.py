from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ORMModel
from app.utils.bank_list import BANK_MAP, OTHER_CODE
from app.utils.validators import clean_account_number


class BankAccountIn(BaseModel):
    bank_code: str  # dari GET /masterdata/banks, atau OTHER
    bank_name_other: Optional[str] = Field(default=None, max_length=100)
    account_number: str  # diketik sendiri
    account_holder_name: str = Field(min_length=3, max_length=100)
    is_default: bool = False

    @field_validator("bank_code")
    @classmethod
    def upper_code(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("account_number")
    @classmethod
    def check_number(cls, v: str) -> str:
        return clean_account_number(v)

    @field_validator("account_holder_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def check_bank(self):
        if self.bank_code == OTHER_CODE:
            if not (self.bank_name_other and self.bank_name_other.strip()):
                raise ValueError("Nama bank wajib diisi jika memilih Lainnya")
        elif self.bank_code not in BANK_MAP:
            raise ValueError("Kode bank tidak dikenal. Ambil daftar dari GET /masterdata/banks")
        return self


class BankAccountOut(ORMModel):
    id: int
    bank_code: str
    bank_name: str
    account_number_masked: str
    account_holder_name: str
    is_default: bool
    created_at: datetime
