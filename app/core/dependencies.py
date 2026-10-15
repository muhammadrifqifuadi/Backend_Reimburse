import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.auth.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user_any(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """User dari token, TANPA memeriksa kewajiban ganti password. Hanya untuk /auth/me dan /auth/change-password."""
    try:
        payload = decode_token(token, "access")
        user_id = int(payload["sub"])
        token_version = int(payload.get("tv", 0))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token tidak valid atau kedaluwarsa",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, user_id)
    # token_version berubah saat password diganti/direset -> sesi lama otomatis ditolak
    if not user or not user.is_active or user.token_version != token_version:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Sesi tidak valid. Silakan login ulang.", headers={"WWW-Authenticate": "Bearer"}
        )
    return user


def get_current_user(user: User = Depends(get_current_user_any)) -> User:
    """User yang sudah boleh memakai aplikasi (bukan lagi memakai password sementara)."""
    if user.must_change_password:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PASSWORD_CHANGE_REQUIRED",
                "message": "Anda harus mengganti password sementara terlebih dahulu (POST /auth/change-password).",
            },
        )
    return user


def require_role(*roles: str):
    """Role guard: hanya role yang disebutkan yang boleh mengakses endpoint."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Anda tidak memiliki akses ke fitur ini")
        return user

    return checker


def get_client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None
