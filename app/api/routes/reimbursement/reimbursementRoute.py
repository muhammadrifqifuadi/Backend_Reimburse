from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.controllers.reimbursement import reimbursement_controller as ctl
from app.core.config import settings
from app.core.constants import Role
from app.core.database import get_db
from app.core.dependencies import get_client_ip, get_current_user, require_role
from app.models.auth.user import User
from app.schemas.common import Page
from app.schemas.reimbursement.reimbursementSchema import (
    AttachmentOut, CancelRequest, ItemIn, ReimbursementCreate, ReimbursementListOut, ReimbursementOut,
    ReimbursementUpdate, SubmitRequest,
)

router = APIRouter(prefix="/reimbursements", tags=["Reimbursement"])
# admin tidak mengajukan klaim; karyawan, HRD, dan finance boleh (mereka juga karyawan)
claimant = require_role(Role.KARYAWAN, Role.HRD, Role.FINANCE)
reviewer = require_role(Role.HRD, Role.FINANCE, Role.ADMIN)


@router.post("", response_model=ReimbursementOut, status_code=201, summary="Buat klaim (draft), item boleh sekalian")
def create(payload: ReimbursementCreate, db: Session = Depends(get_db), user: User = Depends(claimant)):
    return ctl.create_claim(db, payload.model_dump(), user)


@router.get("", response_model=Page[ReimbursementListOut], summary="Klaim saya")
def list_mine(
    status: Optional[str] = None,
    q: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(claimant),
):
    return ctl.list_mine(db, user, status, q, skip, limit)


@router.get("/all", response_model=Page[ReimbursementListOut], summary="Semua klaim yang sudah diajukan (HRD/finance/admin)")
def list_all(
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    department_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    q: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(reviewer),
):
    return ctl.list_all(db, status, user_id, department_id, date_from, date_to, q, skip, limit)


# ---- lampiran (path statis harus di atas path /{claim_id}) ----
@router.get("/attachments/{attachment_id}/download", summary="Unduh file kwitansi")
def download_attachment(attachment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    att = ctl.get_attachment_for_download(db, attachment_id, user)
    return FileResponse(att.file_path, media_type=att.mime_type, filename=att.file_name)


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_attachment(attachment_id: int, db: Session = Depends(get_db), user: User = Depends(claimant)):
    ctl.delete_attachment(db, attachment_id, user)
    return Response(status_code=204)


@router.get("/{claim_id}", response_model=ReimbursementOut)
def detail(claim_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ctl.get_visible_claim(db, claim_id, user)


@router.put("/{claim_id}", response_model=ReimbursementOut, summary="Ubah header klaim (draft/revisi)")
def update_header(claim_id: int, payload: ReimbursementUpdate, db: Session = Depends(get_db), user: User = Depends(claimant)):
    return ctl.update_header(db, claim_id, payload.model_dump(exclude_unset=True), user)


@router.post("/{claim_id}/items", response_model=ReimbursementOut, status_code=201)
def add_item(claim_id: int, payload: ItemIn, db: Session = Depends(get_db), user: User = Depends(claimant)):
    return ctl.add_item(db, claim_id, payload.model_dump(), user)


@router.put("/{claim_id}/items/{item_id}", response_model=ReimbursementOut)
def update_item(claim_id: int, item_id: int, payload: ItemIn, db: Session = Depends(get_db), user: User = Depends(claimant)):
    return ctl.update_item(db, claim_id, item_id, payload.model_dump(), user)


@router.delete("/{claim_id}/items/{item_id}", response_model=ReimbursementOut)
def delete_item(claim_id: int, item_id: int, db: Session = Depends(get_db), user: User = Depends(claimant)):
    return ctl.delete_item(db, claim_id, item_id, user)


@router.post("/{claim_id}/items/{item_id}/attachments", response_model=AttachmentOut, status_code=201,
             summary="Unggah kwitansi (JPG/PNG/PDF)")
async def upload_attachment(
    claim_id: int, item_id: int, file: UploadFile = File(...),
    db: Session = Depends(get_db), user: User = Depends(claimant),
):
    content = await file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)  # baca maksimal batas + 1 byte
    return ctl.add_attachment(db, claim_id, item_id, file.filename or "", content, user)


@router.post("/{claim_id}/submit", response_model=ReimbursementOut, summary="Ajukan klaim")
def submit(claim_id: int, payload: SubmitRequest = SubmitRequest(), db: Session = Depends(get_db),
           user: User = Depends(claimant), ip=Depends(get_client_ip)):
    return ctl.submit(db, claim_id, payload.bank_account_id, user, ip)


@router.post("/{claim_id}/cancel", response_model=ReimbursementOut)
def cancel(claim_id: int, payload: CancelRequest = CancelRequest(), db: Session = Depends(get_db),
           user: User = Depends(claimant), ip=Depends(get_client_ip)):
    return ctl.cancel(db, claim_id, payload.reason, user, ip)
