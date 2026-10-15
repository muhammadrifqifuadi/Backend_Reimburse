import hashlib
import secrets
from datetime import timedelta

import jwt
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import utcnow
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.auth.password_reset_token import PasswordResetToken
from app.models.auth.user import User
from app.services import email_utils
from app.services.audit import log_audit

GENERIC_FORGOT = {"message": "Jika email terdaftar, instruksi reset password telah dikirim ke email tersebut."}
MAX_RESET_REQUESTS_PER_HOUR = 3


def _tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id, user.role, user.token_version),
        "refresh_token": create_refresh_token(user.id, user.token_version),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def login(db: Session, email: str, password: str) -> dict:
    user = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    # pesan sama untuk email salah / password salah / akun nonaktif (cegah user enumeration)
    if not user or not user.is_active or not verify_password(password, user.hashed_password):
        raise HTTPException(401, "Email atau password salah")
    user.last_login_at = utcnow()
    db.commit()
    return {**_tokens(user), "user": user}


def refresh(db: Session, refresh_token: str) -> dict:
    try:
        payload = decode_token(refresh_token, "refresh")
        user = db.get(User, int(payload["sub"]))
        tv = int(payload.get("tv", 0))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "Refresh token tidak valid atau kedaluwarsa")
    if not user or not user.is_active or user.token_version != tv:
        raise HTTPException(401, "Sesi tidak valid. Silakan login ulang.")
    return _tokens(user)


def _set_password(user: User, new_password: str) -> None:
    user.hashed_password = hash_password(new_password)
    user.must_change_password = False
    user.password_changed_at = utcnow()
    user.token_version += 1  # semua token/sesi lama langsung tidak berlaku


def change_password(db: Session, user: User, current: str, new: str, ip: str | None) -> dict:
    """Ganti password. Mengembalikan token baru (token lama otomatis tidak berlaku)."""
    if not verify_password(current, user.hashed_password):
        raise HTTPException(400, "Password saat ini salah")
    if verify_password(new, user.hashed_password):
        raise HTTPException(400, "Password baru harus berbeda dari password saat ini")
    _set_password(user, new)
    log_audit(db, user.id, "change_password", "user", user.id, ip=ip)
    db.commit()
    return _tokens(user)


def forgot_password(db: Session, email: str, ip: str | None) -> dict:
    """Kirim token reset ke email. Respons SELALU sama, baik email terdaftar maupun tidak."""
    user = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if not user or not user.is_active:
        return GENERIC_FORGOT

    now = utcnow()
    recent = db.scalar(
        select(func.count(PasswordResetToken.id)).where(
            PasswordResetToken.user_id == user.id, PasswordResetToken.created_at > now - timedelta(hours=1)
        )
    )
    if recent >= MAX_RESET_REQUESTS_PER_HOUR:  # batasi spam ke inbox pemilik akun
        return GENERIC_FORGOT

    for old in db.scalars(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))):
        old.used_at = now  # permintaan baru membatalkan token lama

    raw = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(
        user_id=user.id, token_hash=_hash_token(raw), ip_address=ip,
        expires_at=now + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
    ))
    log_audit(db, user.id, "forgot_password_request", "user", user.id, ip=ip)
    db.commit()

    link = settings.FRONTEND_RESET_URL.replace("{token}", raw) if settings.FRONTEND_RESET_URL else None
    email_utils.send_secret_async(
        [user.email],
        "[Reimburse] Reset password",
        f"Halo {user.full_name},\n\n"
        "Kami menerima permintaan reset password untuk akun Anda.\n\n"
        + (f"Buka tautan ini: {link}\n\n" if link else "")
        + f"Token reset: {raw}\n\n"
        f"Token berlaku {settings.RESET_TOKEN_EXPIRE_MINUTES} menit dan hanya bisa dipakai sekali.\n"
        "Jika Anda tidak memintanya, abaikan email ini; password Anda tidak berubah.",
    )
    return GENERIC_FORGOT


def reset_password(db: Session, token: str, new_password: str, ip: str | None) -> None:
    invalid = HTTPException(400, "Token reset tidak valid atau sudah kedaluwarsa")  # pesan sama untuk semua kasus
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(token.strip())))
    now = utcnow()
    if not row or row.used_at is not None or row.expires_at < now:
        raise invalid
    user = db.get(User, row.user_id)
    if not user or not user.is_active:
        raise invalid
    row.used_at = now
    _set_password(user, new_password)
    log_audit(db, user.id, "reset_password", "user", user.id, ip=ip)
    db.commit()
