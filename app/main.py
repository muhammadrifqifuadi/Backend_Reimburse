import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.api.routes.approval.approvalRoute import router as approval_router
from app.api.routes.auth.authRoute import router as auth_router
from app.api.routes.bank_account.bankAccountRoute import router as bank_account_router
from app.api.routes.masterdata.masterdataRoute import router as masterdata_router
from app.api.routes.payment.paymentRoute import router as payment_router
from app.api.routes.reimbursement.reimbursementRoute import router as reimbursement_router
from app.api.routes.report.reportRoute import router as report_router
from app.core.config import settings
from app.core.startup import on_startup
from app.middleware.auth_logging import AuthAndLoggingMiddleware

logger = logging.getLogger("app")
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    on_startup()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="REST API aplikasi reimburse kantor. Alur: karyawan → HRD → finance → bayar.",
    lifespan=lifespan,
)

# Urutan: yang ditambahkan terakhir = terluar. CORS di luar agar respons 401 dari middleware tetap punya header CORS.
app.add_middleware(AuthAndLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

for r in (auth_router, masterdata_router, bank_account_router, reimbursement_router,
          approval_router, payment_router, report_router):
    app.include_router(r)


# ---------------- exception handlers ----------------
@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(x) for x in e["loc"] if x not in ("body", "query", "path")), "message": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": "Data yang dikirim tidak valid", "errors": errors})


@app.exception_handler(IntegrityError)
async def integrity_handler(_: Request, exc: IntegrityError):
    logger.warning("IntegrityError: %s", exc.orig)
    return JSONResponse(status_code=409, content={"detail": "Data bentrok dengan data yang sudah ada"})


@app.exception_handler(Exception)
async def unhandled_handler(_: Request, exc: Exception):
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Terjadi kesalahan pada server"})


# ---------------- util ----------------
@app.get("/", include_in_schema=False)
def root():
    return {"app": settings.APP_NAME, "docs": "/docs", "rapidoc": "/rapidoc"}


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/rapidoc", include_in_schema=False, response_class=HTMLResponse)
def rapidoc():
    local = STATIC_DIR / "rapidoc" / "rapidoc-min.js"
    src = "/static/rapidoc/rapidoc-min.js" if local.exists() else "https://unpkg.com/rapidoc/dist/rapidoc-min.js"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{settings.APP_NAME}</title>
<script type="module" src="{src}"></script></head><body>
<rapi-doc spec-url="/openapi.json" render-style="read" allow-try="true" theme="light"></rapi-doc></body></html>"""
