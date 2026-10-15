"""DATA DUMMY KHUSUS TES. Hanya dipakai pytest pada database sementara, tidak pernah dijalankan oleh aplikasi."""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import Role
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import registry  # noqa: F401
from app.models.auth.user import User
from app.models.bank_account.bank_account import BankAccount
from app.models.masterdata.department import Department
from app.models.masterdata.expense_category import ExpenseCategory
from app.models.masterdata.job_level import JobLevel
from app.models.masterdata.reimbursement_policy import ReimbursementPolicy

DEPARTMENTS = [("FIN", "Finance"), ("HR", "Human Resources"), ("IT", "Information Technology"),
               ("OPS", "Operations"), ("MKT", "Marketing")]

JOB_LEVELS = [("STAFF", "Staff", 1), ("SENIOR", "Senior Staff", 2), ("SPV", "Supervisor", 3),
              ("MGR", "Manager", 4), ("DIR", "Director", 5)]
LEVEL_MULTIPLIER = {1: 1, 2: 1.5, 3: 2, 4: 3, 5: 5}

# code, nama, wajib kwitansi (berapa pun), wajib unggah file
CATEGORIES = [
    ("TRANSPORT", "Transportasi", False, True),
    ("MEAL", "Makan & Jamuan", False, True),
    ("LODGING", "Akomodasi", True, True),
    ("HEALTH", "Kesehatan", True, True),
    ("COMM", "Komunikasi (pulsa/internet)", False, True),
    ("OFFICE", "Perlengkapan Kantor", True, True),
    ("TRAINING", "Pelatihan & Seminar", True, True),
    ("OTHER", "Lainnya", True, True),
]

# base limit level STAFF (dikali LEVEL_MULTIPLIER): per transaksi, per hari, per bulan, per tahun, kwitansi wajib di atas
BASE_LIMITS = {
    "TRANSPORT": (300_000, 600_000, 3_000_000, 30_000_000, 50_000),
    "MEAL": (150_000, 300_000, 2_000_000, 20_000_000, 50_000),
    "LODGING": (750_000, 750_000, 5_000_000, 40_000_000, 0),
    "HEALTH": (1_000_000, None, 3_000_000, 12_000_000, 0),
    "COMM": (300_000, None, 500_000, 6_000_000, 100_000),
    "OFFICE": (500_000, None, 2_000_000, 12_000_000, 0),
    "TRAINING": (3_000_000, None, 5_000_000, 20_000_000, 0),
    "OTHER": (250_000, None, 1_000_000, 6_000_000, 0),
}


def _get_or_create(db: Session, model, where: dict, values: dict | None = None):
    obj = db.scalar(select(model).filter_by(**where))
    if not obj:
        obj = model(**where, **(values or {}))
        db.add(obj)
        db.flush()
    return obj


def load_demo_data() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        depts = {c: _get_or_create(db, Department, {"code": c}, {"name": n}) for c, n in DEPARTMENTS}
        levels = {c: _get_or_create(db, JobLevel, {"code": c}, {"name": n, "rank_order": r}) for c, n, r in JOB_LEVELS}
        cats = {
            c: _get_or_create(db, ExpenseCategory, {"code": c},
                              {"name": n, "requires_receipt": rr, "requires_attachment": ra})
            for c, n, rr, ra in CATEGORIES
        }

        for lvl_code, _, rank in JOB_LEVELS:
            mult = LEVEL_MULTIPLIER[rank]
            for cat_code, (tx, day, month, year, receipt) in BASE_LIMITS.items():
                scale = lambda v: None if v is None else Decimal(str(round(v * mult)))
                _get_or_create(
                    db, ReimbursementPolicy,
                    {"job_level_id": levels[lvl_code].id, "category_id": cats[cat_code].id},
                    {"max_per_transaction": scale(tx), "max_per_day": scale(day), "max_per_month": scale(month),
                     "max_per_year": scale(year), "require_receipt_above": Decimal(str(receipt))},
                )

        pw = hash_password("Password123!")

        def user(emp, name, email, role, dept, level):
            return _get_or_create(
                db, User, {"email": email},
                {"employee_id": emp, "full_name": name, "hashed_password": pw, "role": role,
                 "department_id": depts[dept].id, "job_level_id": levels[level].id},
            )

        user("ADM-001", "Admin Sistem", "admin@kantor.test", Role.ADMIN, "IT", "MGR")
        # Dua HRD & dua finance: klaim milik HRD/finance sendiri harus diputuskan orang lain di role yang sama.
        user("HRD-001", "Rina Wulandari (HRD)", "hrd@kantor.test", Role.HRD, "HR", "SPV")
        user("HRD-002", "Teguh Prasetyo (HRD)", "hrd2@kantor.test", Role.HRD, "HR", "SENIOR")
        user("FIN-001", "Budi Santoso (Finance)", "finance@kantor.test", Role.FINANCE, "FIN", "SPV")
        user("FIN-002", "Maya Kusuma (Finance)", "finance2@kantor.test", Role.FINANCE, "FIN", "SENIOR")
        employee = user("EMP-001", "Andi Pratama", "employee@kantor.test", Role.KARYAWAN, "OPS", "STAFF")
        user("EMP-002", "Siti Aminah", "employee2@kantor.test", Role.KARYAWAN, "OPS", "SENIOR")

        if not db.scalar(select(BankAccount).where(BankAccount.user_id == employee.id)):
            db.add(BankAccount(user_id=employee.id, bank_code="BCA", bank_name="Bank Central Asia (BCA)",
                               account_number="1234567890", account_holder_name="Andi Pratama", is_default=True))
        db.commit()
        pass  # (tanpa output)
    finally:
        db.close()

