from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.controllers.payment import payment_controller as ctl
from app.core.constants import Role
from app.core.database import get_db
from app.core.dependencies import get_client_ip, require_role
from app.models.auth.user import User
from app.schemas.common import Page
from app.schemas.payment.paymentSchema import DestinationAccountOut, PayRequest
from app.schemas.reimbursement.reimbursementSchema import PaymentOut, ReimbursementListOut, ReimbursementOut

router = APIRouter(prefix="/payments", tags=["Payment (Finance)"])
finance_only = require_role(Role.FINANCE)


@router.get("/pending", response_model=Page[ReimbursementListOut], summary="Klaim siap dibayar")
def pending(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
            db: Session = Depends(get_db), user: User = Depends(finance_only)):
    return ctl.list_awaiting_payment(db, user, skip, limit)


@router.get("", response_model=Page[PaymentOut], summary="Riwayat pembayaran")
def list_payments(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                  db: Session = Depends(get_db), _: User = Depends(require_role(Role.FINANCE, Role.ADMIN))):
    return ctl.list_payments(db, skip, limit)


@router.get("/{claim_id}/destination", response_model=DestinationAccountOut,
            summary="Rekening tujuan transfer (nomor penuh, dicatat di audit log)")
def destination(claim_id: int, db: Session = Depends(get_db), user: User = Depends(finance_only), ip=Depends(get_client_ip)):
    return ctl.destination_account(db, claim_id, user, ip)


@router.post("/{claim_id}/pay", response_model=ReimbursementOut, summary="Tandai sudah dibayar")
def pay(claim_id: int, payload: PayRequest, db: Session = Depends(get_db),
        user: User = Depends(finance_only), ip=Depends(get_client_ip)):
    return ctl.pay(db, claim_id, payload, user, ip)
