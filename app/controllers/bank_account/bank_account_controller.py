from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth.user import User
from app.models.bank_account.bank_account import BankAccount
from app.services.audit import log_audit
from app.utils.bank_list import BANK_MAP, OTHER_CODE
from app.utils.crypto_types import mask_account


def _bank_name(code: str, other: str | None) -> str:
    return (other or "").strip() if code == OTHER_CODE else BANK_MAP[code]


def _active_accounts(db: Session, user: User) -> list[BankAccount]:
    return list(
        db.scalars(
            select(BankAccount)
            .where(BankAccount.user_id == user.id, BankAccount.is_active.is_(True))
            .order_by(BankAccount.is_default.desc(), BankAccount.id)
        )
    )


def _get_own(db: Session, user: User, account_id: int) -> BankAccount:
    acc = db.get(BankAccount, account_id)
    if not acc or acc.user_id != user.id or not acc.is_active:
        raise HTTPException(404, "Rekening tidak ditemukan")
    return acc


def _make_default(db: Session, user: User, acc: BankAccount) -> None:
    for other in _active_accounts(db, user):
        other.is_default = other.id == acc.id


def list_accounts(db: Session, user: User):
    return _active_accounts(db, user)


def create_account(db: Session, user: User, data: dict, ip: str | None):
    existing = _active_accounts(db, user)
    if any(a.bank_code == data["bank_code"] and a.account_number == data["account_number"] for a in existing):
        raise HTTPException(409, "Rekening ini sudah terdaftar")
    acc = BankAccount(
        user_id=user.id,
        bank_code=data["bank_code"],
        bank_name=_bank_name(data["bank_code"], data.get("bank_name_other")),
        account_number=data["account_number"],
        account_holder_name=data["account_holder_name"],
        is_default=False,
    )
    db.add(acc)
    db.flush()
    if data.get("is_default") or not existing:  # rekening pertama otomatis jadi default
        _make_default(db, user, acc)
        acc.is_default = True
    log_audit(db, user.id, "bank_account_create", "bank_account", acc.id,
              {"bank": acc.bank_name, "account": mask_account(acc.account_number)}, ip)
    db.commit()
    return acc


def update_account(db: Session, user: User, account_id: int, data: dict, ip: str | None):
    acc = _get_own(db, user, account_id)
    before = {"bank": acc.bank_name, "account": mask_account(acc.account_number), "holder": acc.account_holder_name}
    acc.bank_code = data["bank_code"]
    acc.bank_name = _bank_name(data["bank_code"], data.get("bank_name_other"))
    acc.account_number = data["account_number"]
    acc.account_holder_name = data["account_holder_name"]
    if data.get("is_default"):
        _make_default(db, user, acc)
    after = {"bank": acc.bank_name, "account": mask_account(acc.account_number), "holder": acc.account_holder_name}
    log_audit(db, user.id, "bank_account_update", "bank_account", acc.id, {"before": before, "after": after}, ip)
    db.commit()
    return acc


def set_default(db: Session, user: User, account_id: int, ip: str | None):
    acc = _get_own(db, user, account_id)
    _make_default(db, user, acc)
    log_audit(db, user.id, "bank_account_set_default", "bank_account", acc.id, ip=ip)
    db.commit()
    return acc


def delete_account(db: Session, user: User, account_id: int, ip: str | None) -> None:
    acc = _get_own(db, user, account_id)
    was_default = acc.is_default
    acc.is_active = False  # soft delete: klaim lama tetap punya snapshot-nya sendiri
    acc.is_default = False
    if was_default:
        remaining = [a for a in _active_accounts(db, user) if a.id != acc.id]
        if remaining:
            remaining[0].is_default = True
    log_audit(db, user.id, "bank_account_delete", "bank_account", acc.id, {"account": mask_account(acc.account_number)}, ip)
    db.commit()
