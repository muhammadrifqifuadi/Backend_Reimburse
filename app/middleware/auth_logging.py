import time

import jwt
from fastapi.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.database import SessionLocal
from app.core.security import decode_token
from app.models.log.request_log import RequestLog

PUBLIC_PATHS = {"/", "/health", "/auth/login", "/auth/refresh", "/auth/forgot-password", "/auth/reset-password", "/docs", "/redoc", "/rapidoc", "/openapi.json"}
PUBLIC_PREFIXES = ("/static",)
NO_LOG_PATHS = {"/health", "/docs", "/redoc", "/rapidoc", "/openapi.json"}


def _write_log(user_id, request: Request, status_code: int, duration_ms: float) -> None:
    db = SessionLocal()
    try:
        db.add(RequestLog(
            user_id=user_id, method=request.method, path=request.url.path[:300], status_code=status_code,
            ip_address=(request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                        or (request.client.host if request.client else None)),
            user_agent=(request.headers.get("user-agent") or "")[:300], duration_ms=round(duration_ms, 2),
        ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


class AuthAndLoggingMiddleware(BaseHTTPMiddleware):
    """Cek Bearer token untuk semua endpoint non-publik + catat setiap request ke request_logs."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        path = request.url.path
        user_id = None
        is_public = request.method == "OPTIONS" or path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)

        response = None
        if not is_public:
            scheme, _, token = request.headers.get("Authorization", "").partition(" ")
            if scheme.lower() != "bearer" or not token:
                response = JSONResponse({"detail": "Token tidak ditemukan"}, 401, {"WWW-Authenticate": "Bearer"})
            else:
                try:
                    user_id = int(decode_token(token, "access")["sub"])
                except (jwt.PyJWTError, ValueError, KeyError):
                    response = JSONResponse({"detail": "Token tidak valid atau kedaluwarsa"}, 401, {"WWW-Authenticate": "Bearer"})
        if response is None:
            response = await call_next(request)

        if path not in NO_LOG_PATHS and not path.startswith(PUBLIC_PREFIXES):
            await run_in_threadpool(_write_log, user_id, request, response.status_code, (time.perf_counter() - start) * 1000)
        return response
