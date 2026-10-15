from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.controllers.masterdata import masterdata_controller as ctl
from app.core.constants import Role
from app.core.database import get_db
from app.core.dependencies import get_client_ip, get_current_user, require_role
from app.models.auth.user import User
from app.models.masterdata.department import Department
from app.models.masterdata.expense_category import ExpenseCategory
from app.models.masterdata.job_level import JobLevel
from app.schemas.common import Message, Page
from app.schemas.masterdata.masterdataSchema import (
    BankOption, CategoryIn, CategoryOut, CategoryUpdate, DepartmentIn, DepartmentOut, DepartmentUpdate,
    JobLevelIn, JobLevelOut, JobLevelUpdate, PolicyIn, PolicyOut, PolicyUpdate, UserCreate, UserOut, UserUpdate,
)
from app.utils.bank_list import all_banks

router = APIRouter(prefix="/masterdata", tags=["Master Data"])
admin_only = require_role(Role.ADMIN)
admin_hrd = require_role(Role.ADMIN, Role.HRD)


# ---- dropdown bank ----
@router.get("/banks", response_model=list[BankOption], summary="Daftar bank untuk dropdown")
def banks(_: User = Depends(get_current_user)):
    return all_banks()


# ---- departemen ----
@router.get("/departments", response_model=list[DepartmentOut])
def departments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ctl.list_items(db, Department, only_active=user.role != Role.ADMIN)


@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(payload: DepartmentIn, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return ctl.create_item(db, Department, payload.model_dump())


@router.put("/departments/{dept_id}", response_model=DepartmentOut)
def update_department(dept_id: int, payload: DepartmentUpdate, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return ctl.update_item(db, Department, dept_id, payload.model_dump(exclude_unset=True), "Departemen")


# ---- level jabatan ----
@router.get("/job-levels", response_model=list[JobLevelOut])
def job_levels(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ctl.list_items(db, JobLevel, only_active=user.role != Role.ADMIN)


@router.post("/job-levels", response_model=JobLevelOut, status_code=201)
def create_job_level(payload: JobLevelIn, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return ctl.create_item(db, JobLevel, payload.model_dump())


@router.put("/job-levels/{level_id}", response_model=JobLevelOut)
def update_job_level(level_id: int, payload: JobLevelUpdate, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return ctl.update_item(db, JobLevel, level_id, payload.model_dump(exclude_unset=True), "Level jabatan")


# ---- kategori klaim ----
@router.get("/categories", response_model=list[CategoryOut])
def categories(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ctl.list_items(db, ExpenseCategory, only_active=user.role != Role.ADMIN)


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(payload: CategoryIn, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return ctl.create_item(db, ExpenseCategory, payload.model_dump())


@router.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return ctl.update_item(db, ExpenseCategory, category_id, payload.model_dump(exclude_unset=True), "Kategori")


# ---- kebijakan limit (HRD & admin) ----
@router.get("/policies", response_model=list[PolicyOut])
def policies(
    job_level_id: Optional[int] = None,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return ctl.list_policies(db, job_level_id, category_id)


@router.post("/policies", response_model=PolicyOut, status_code=201)
def create_policy(payload: PolicyIn, db: Session = Depends(get_db), _: User = Depends(admin_hrd)):
    return ctl.create_policy(db, payload.model_dump())


@router.put("/policies/{policy_id}", response_model=PolicyOut)
def update_policy(policy_id: int, payload: PolicyUpdate, db: Session = Depends(get_db), _: User = Depends(admin_hrd)):
    return ctl.update_policy(db, policy_id, payload.model_dump(exclude_unset=True))


# ---- user (admin) ----
@router.get("/users", response_model=Page[UserOut])
def users(
    q: Optional[str] = None,
    role: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(admin_hrd),
):
    return ctl.list_users(db, q, role, skip, limit)


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db), admin: User = Depends(admin_only), ip=Depends(get_client_ip)):
    return ctl.create_user(db, payload.model_dump(), admin, ip)


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_only), ip=Depends(get_client_ip)):
    return ctl.update_user(db, user_id, payload.model_dump(exclude_unset=True), admin, ip)


@router.post("/users/{user_id}/reset-password", response_model=Message,
             summary="Reset password user: password sementara baru dikirim ke email user (admin tidak melihatnya)")
def reset_user_password(user_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_only), ip=Depends(get_client_ip)):
    ctl.reset_user_password(db, user_id, admin, ip)
    return {"message": "Password sementara baru telah dikirim ke email user"}
