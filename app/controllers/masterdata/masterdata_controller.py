from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.auth.user import User
from app.models.masterdata.department import Department
from app.models.masterdata.expense_category import ExpenseCategory
from app.models.masterdata.job_level import JobLevel
from app.models.masterdata.reimbursement_policy import ReimbursementPolicy
from app.services import email_utils
from app.services.audit import log_audit
from app.utils.pagination import paginate
from app.utils.validators import generate_temp_password


def _save(db: Session, obj, duplicate_msg: str = "Data duplikat (kode sudah dipakai)"):
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, duplicate_msg)
    db.refresh(obj)
    return obj


def _get(db: Session, model, obj_id: int, name: str):
    obj = db.get(model, obj_id)
    if not obj:
        raise HTTPException(404, f"{name} tidak ditemukan")
    return obj


# ---------- CRUD sederhana: departemen, level jabatan, kategori ----------
def list_items(db: Session, model, only_active: bool = False):
    stmt = select(model).order_by(model.id)
    if only_active:
        stmt = stmt.where(model.is_active.is_(True))
    return db.scalars(stmt).all()


def create_item(db: Session, model, data: dict):
    return _save(db, model(**data))


def update_item(db: Session, model, obj_id: int, data: dict, name: str):
    obj = _get(db, model, obj_id, name)
    for k, v in data.items():
        setattr(obj, k, v)
    return _save(db, obj)


# ---------- kebijakan limit ----------
def list_policies(db: Session, job_level_id: int | None, category_id: int | None):
    stmt = select(ReimbursementPolicy).order_by(ReimbursementPolicy.job_level_id, ReimbursementPolicy.category_id)
    if job_level_id:
        stmt = stmt.where(ReimbursementPolicy.job_level_id == job_level_id)
    if category_id:
        stmt = stmt.where(ReimbursementPolicy.category_id == category_id)
    return db.scalars(stmt).all()


def create_policy(db: Session, data: dict):
    _get(db, JobLevel, data["job_level_id"], "Level jabatan")
    _get(db, ExpenseCategory, data["category_id"], "Kategori")
    return _save(db, ReimbursementPolicy(**data), "Kebijakan untuk level & kategori ini sudah ada, gunakan PUT")


def update_policy(db: Session, policy_id: int, data: dict):
    return update_item(db, ReimbursementPolicy, policy_id, data, "Kebijakan")


# ---------- user ----------
def _check_user_refs(db: Session, data: dict) -> None:
    if data.get("department_id") is not None:
        _get(db, Department, data["department_id"], "Departemen")
    if data.get("job_level_id") is not None:
        _get(db, JobLevel, data["job_level_id"], "Level jabatan")


def list_users(db: Session, q: str | None, role: str | None, skip: int, limit: int):
    stmt = select(User).order_by(User.id)
    if q:
        like = f"%{q.lower()}%"
        from sqlalchemy import func, or_

        stmt = stmt.where(or_(func.lower(User.full_name).like(like), func.lower(User.email).like(like), User.employee_id.like(f"%{q}%")))
    if role:
        stmt = stmt.where(User.role == role)
    return paginate(db, stmt, skip, limit)


def _welcome_mail(user: User, temp_password: str, reset: bool) -> tuple[str, str]:
    login = f"Login: {settings.FRONTEND_LOGIN_URL}\n" if settings.FRONTEND_LOGIN_URL else ""
    intro = "Password akun Reimburse Anda telah direset oleh admin." if reset else "Akun aplikasi Reimburse Anda sudah dibuat."
    return (
        "[Reimburse] Password sementara akun Anda" if reset else "[Reimburse] Akun Anda sudah dibuat",
        f"Halo {user.full_name},\n\n{intro}\n\n"
        f"Email login: {user.email}\n"
        f"Password sementara: {temp_password}\n"
        f"{login}\n"
        "Saat login pertama Anda WAJIB mengganti password. Jangan bagikan password ini kepada siapa pun,\n"
        "termasuk admin.",
    )


def _deliver_credentials(db: Session, user: User, temp_password: str, reset: bool) -> None:
    """Kirim password sementara. Gagal kirim -> batalkan semua perubahan agar tidak ada akun yang password-nya tak diketahui siapa pun."""
    if not email_utils.can_deliver():
        db.rollback()
        raise HTTPException(503, "Pengiriman email belum dikonfigurasi (SMTP_HOST). Password sementara tidak dapat dikirim ke karyawan.")
    subject, body = _welcome_mail(user, temp_password, reset)
    try:
        email_utils.send_now([user.email], subject, body)
    except email_utils.EmailError:
        db.rollback()
        raise HTTPException(502, f"Gagal mengirim email ke {user.email}. Perubahan dibatalkan, silakan coba lagi.")


def create_user(db: Session, data: dict, actor: User, ip: str | None):
    """Buat user. Password sementara dibuat acak oleh sistem dan dikirim ke email user; admin tidak melihatnya."""
    data = dict(data)
    _check_user_refs(db, data)
    data["email"] = data["email"].lower()
    temp = generate_temp_password()
    user = User(**data, hashed_password=hash_password(temp), must_change_password=True)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email atau NIK sudah terdaftar")
    log_audit(db, actor.id, "create_user", "user", user.id, {"email": user.email, "role": user.role}, ip)
    _deliver_credentials(db, user, temp, reset=False)
    db.commit()
    return user


def reset_user_password(db: Session, user_id: int, actor: User, ip: str | None) -> None:
    """Admin mereset akun: password sementara baru dikirim ke email user, sesi lama diputus."""
    user = _get(db, User, user_id, "User")
    if user.id == actor.id:
        raise HTTPException(400, "Untuk akun sendiri gunakan Ganti Password")
    if not user.is_active:
        raise HTTPException(409, "Akun nonaktif")
    temp = generate_temp_password()
    user.hashed_password = hash_password(temp)
    user.must_change_password = True
    user.token_version += 1
    log_audit(db, actor.id, "admin_reset_password", "user", user.id, ip=ip)
    _deliver_credentials(db, user, temp, reset=True)
    db.commit()


def update_user(db: Session, user_id: int, data: dict, actor: User, ip: str | None):
    user = _get(db, User, user_id, "User")
    data = dict(data)
    _check_user_refs(db, data)
    if user.id == actor.id and (data.get("is_active") is False or ("role" in data and data["role"] != user.role)):
        raise HTTPException(400, "Anda tidak dapat menonaktifkan atau mengubah role akun sendiri")
    changes = {k: v for k, v in data.items() if getattr(user, k) != v}
    for k, v in data.items():
        setattr(user, k, v)
    if data.get("is_active") is False:
        user.token_version += 1  # putus semua sesi yang masih berjalan
    log_audit(db, actor.id, "update_user", "user", user.id, changes, ip)
    db.commit()
    return user
