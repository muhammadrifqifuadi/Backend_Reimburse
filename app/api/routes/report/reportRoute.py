from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.controllers.report import report_controller as ctl
from app.controllers.reimbursement.reimbursement_controller import get_visible_claim
from app.core.constants import Role
from app.core.database import get_db
from app.core.dependencies import get_client_ip, get_current_user, require_role
from app.models.auth.user import User
from app.services.pdf_generator import build_claim_pdf

router = APIRouter(prefix="/reports", tags=["Report"])
reviewer = require_role(Role.HRD, Role.FINANCE, Role.ADMIN)


@router.get("/summary", summary="Ringkasan per status, kategori, departemen")
def summary(date_from: Optional[date] = None, date_to: Optional[date] = None, department_id: Optional[int] = None,
            db: Session = Depends(get_db), _: User = Depends(reviewer)):
    return ctl.summary(db, date_from, date_to, department_id)


@router.get("/export", summary="Rekap Excel untuk finance")
def export(status: Optional[str] = None, department_id: Optional[int] = None,
           date_from: Optional[date] = None, date_to: Optional[date] = None,
           db: Session = Depends(get_db), user: User = Depends(reviewer), ip=Depends(get_client_ip)):
    data = ctl.export_claims(db, user, status, department_id, date_from, date_to, ip)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="rekap-reimburse.xlsx"'},
    )


@router.get("/{claim_id}/pdf", summary="Bukti reimburse (PDF)")
def claim_pdf(claim_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    claim = get_visible_claim(db, claim_id, user)
    safe = claim.claim_number.replace("/", "-")
    return Response(
        content=build_claim_pdf(claim),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe}.pdf"'},
    )
