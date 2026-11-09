from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.controllers.auth import auth_controller
from app.core.database import get_db
from app.core.dependencies import get_client_ip, get_current_user_any
from app.models.auth.user import User
from app.schemas.auth.authSchema import (
    ChangePasswordRequest, ForgotPasswordRequest, LoginResponse, RefreshRequest, ResetPasswordRequest, TokenResponse,
)
from app.schemas.common import Message
from app.schemas.masterdata.masterdataSchema import UserOut

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse, summary="Login (username = email)")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return auth_controller.login(db, form.username, form.password)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    return auth_controller.refresh(db, payload.refresh_token)


@router.get("/me", response_model=UserOut, summary="Profil saya (boleh diakses walau masih memakai password sementara)")
def me(user: User = Depends(get_current_user_any)):
    return user


@router.post("/change-password", response_model=TokenResponse,
             summary="Ganti password (wajib saat login pertama). Mengembalikan token baru.")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_any),
    ip: str | None = Depends(get_client_ip),
):
    return auth_controller.change_password(db, user, payload.current_password, payload.new_password, ip)


@router.post("/forgot-password", response_model=Message, summary="Lupa password: kirim token reset ke email")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db), ip: str | None = Depends(get_client_ip)):
    return auth_controller.forgot_password(db, payload.email, ip)


@router.post("/reset-password", response_model=Message, summary="Atur password baru memakai token dari email")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db), ip: str | None = Depends(get_client_ip)):
    auth_controller.reset_password(db, payload.token, payload.new_password, ip)
    return {"message": "Password berhasil diubah. Silakan login dengan password baru."}



@router.post("/logout", response_model=Message, summary="Logout: putus semua sesi aktif")
def logout(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_any),
    ip: str | None = Depends(get_client_ip),
):
    auth_controller.logout(db, user, ip)
    return {"message": "Logout berhasil"}