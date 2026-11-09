import argparse
import getpass
import sys

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import Role
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import registry  # noqa: F401
from app.models.auth.user import User
from app.utils.validators import check_password_strength


def create_first_admin(db: Session, email: str, full_name: str, password: str, employee_id: str = "ADM-001") -> User | None:
    """Buat admin pertama. Mengembalikan None jika sudah ada admin."""
    if db.scalar(select(User).where(User.role == Role.ADMIN)):
        return None
    try:
        email = validate_email(email, check_deliverability=False).normalized.lower()
    except EmailNotValidError as e:
        raise ValueError(f"Email tidak valid: {e}")
    if len(full_name.strip()) < 2:
        raise ValueError("Nama minimal 2 karakter")
    check_password_strength(password)

    user = User(employee_id=employee_id, full_name=full_name.strip(), email=email,
                hashed_password=hash_password(password), role=Role.ADMIN)
    db.add(user)
    db.commit()
    return user


def main() -> int:
    parser = argparse.ArgumentParser(description="Buat admin pertama")
    parser.add_argument("--email", default=settings.ADMIN_EMAIL)
    parser.add_argument("--name", default=settings.ADMIN_NAME)
    parser.add_argument("--employee-id", default="ADM-001")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.role == Role.ADMIN)):
            print("Admin sudah ada, tidak ada yang dibuat.")
            return 0

        email = args.email or input("Email admin: ").strip()
        name = args.name or input("Nama lengkap admin: ").strip()
        password = settings.ADMIN_PASSWORD
        if not password:
            password = getpass.getpass("Password (min. 8 karakter, huruf + angka): ")
            if password != getpass.getpass("Ulangi password: "):
                print("Password tidak sama.", file=sys.stderr)
                return 1
        try:
            user = create_first_admin(db, email, name, password, args.employee_id)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
        print(f"Admin dibuat: {user.email}")
        print("Login lewat POST /auth/login, lalu isi data lewat /masterdata/... (lihat README: 'Pertama kali pakai').")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
