from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.controllers.bank_account import bank_account_controller as ctl
from app.core.database import get_db
from app.core.dependencies import get_client_ip, get_current_user
from app.models.auth.user import User
from app.schemas.bank_account.bankAccountSchema import BankAccountIn, BankAccountOut

router = APIRouter(prefix="/bank-accounts", tags=["Bank Account"])


@router.get("", response_model=list[BankAccountOut], summary="Rekening saya (nomor ditampilkan masked)")
def list_accounts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ctl.list_accounts(db, user)


@router.post("", response_model=BankAccountOut, status_code=201)
def create_account(payload: BankAccountIn, db: Session = Depends(get_db), user: User = Depends(get_current_user), ip=Depends(get_client_ip)):
    return ctl.create_account(db, user, payload.model_dump(), ip)


@router.put("/{account_id}", response_model=BankAccountOut)
def update_account(account_id: int, payload: BankAccountIn, db: Session = Depends(get_db), user: User = Depends(get_current_user), ip=Depends(get_client_ip)):
    return ctl.update_account(db, user, account_id, payload.model_dump(), ip)


@router.patch("/{account_id}/default", response_model=BankAccountOut)
def set_default(account_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user), ip=Depends(get_client_ip)):
    return ctl.set_default(db, user, account_id, ip)


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user), ip=Depends(get_client_ip)):
    ctl.delete_account(db, user, account_id, ip)
    return Response(status_code=204)
