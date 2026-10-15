"""Kolom terenkripsi (Fernet) untuk data sensitif seperti nomor rekening."""
import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.core.config import settings


@lru_cache
def _fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    if not key:  # fallback dev: turunkan dari SECRET_KEY
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()).decode()
    return Fernet(key.encode())


class EncryptedString(TypeDecorator):
    impl = String(512)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else _fernet().encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        return None if value is None else _fernet().decrypt(value.encode()).decode()


def mask_account(number: str | None) -> str | None:
    if not number:
        return None
    return "*" * max(len(number) - 4, 0) + number[-4:]
