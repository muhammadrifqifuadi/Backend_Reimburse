from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.controllers.approval import approval_controller as ctl
from app.core.constants import Role
from app.core.database import get_db
from app.core.dependencies import get_client_ip, require_role
from app.models.auth.user import User
from app.schemas.approval.approvalSchema import ApproveRequest, RejectRequest, RevisionRequest
from app.schemas.common import Page
from app.schemas.reimbursement.reimbursementSchema import ReimbursementListOut, ReimbursementOut

router = APIRouter(prefix="/approvals", tags=["Approval"])
approver_roles = require_role(Role.HRD, Role.FINANCE)


@router.get("/pending", response_model=Page[ReimbursementListOut], summary="Klaim menunggu keputusan saya (sesuai role)")
def pending(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
            db: Session = Depends(get_db), user: User = Depends(approver_roles)):
    return ctl.list_pending(db, user, skip, limit)


@router.get("/history", response_model=Page[ReimbursementListOut], summary="Klaim yang pernah saya putuskan")
def history(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
            db: Session = Depends(get_db), user: User = Depends(approver_roles)):
    return ctl.list_my_decisions(db, user, skip, limit)


@router.post("/{claim_id}/approve", response_model=ReimbursementOut,
             summary="Setujui (boleh sebagian: turunkan nominal per item)")
def approve(claim_id: int, payload: ApproveRequest = ApproveRequest(), db: Session = Depends(get_db),
            user: User = Depends(approver_roles), ip=Depends(get_client_ip)):
    return ctl.approve(db, claim_id, payload, user, ip)


@router.post("/{claim_id}/reject", response_model=ReimbursementOut, summary="Tolak (final)")
def reject(claim_id: int, payload: RejectRequest, db: Session = Depends(get_db),
           user: User = Depends(approver_roles), ip=Depends(get_client_ip)):
    return ctl.reject(db, claim_id, payload, user, ip)


@router.post("/{claim_id}/request-revision", response_model=ReimbursementOut, summary="Kembalikan ke pemohon untuk direvisi")
def request_revision(claim_id: int, payload: RevisionRequest, db: Session = Depends(get_db),
                     user: User = Depends(approver_roles), ip=Depends(get_client_ip)):
    return ctl.request_revision(db, claim_id, payload, user, ip)
