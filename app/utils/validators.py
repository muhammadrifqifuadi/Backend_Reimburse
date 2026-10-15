import re
from decimal import ROUND_HALF_UP, Decimal

ACCOUNT_RE = re.compile(r"^\d{8,20}$")


def clean_account_number(value: str) -> str:
    """Hapus spasi/tanda hubung, lalu pastikan hanya 8-20 digit."""
    cleaned = re.sub(r"[\s\-]", "", value or "")
    if not ACCOUNT_RE.match(cleaned):
        raise ValueError("Nomor rekening harus berupa angka 8-20 digit")
    return cleaned


def q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def rupiah(value) -> str:
    return "Rp " + f"{Decimal(value):,.0f}".replace(",", ".")


def check_password_strength(password: str) -> str:
    """Minimal 8 karakter (maks 72 byte, batas bcrypt), mengandung huruf dan angka."""
    if len(password) < 8 or len(password.encode()) > 72:
        raise ValueError("Password harus 8-72 karakter")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("Password harus mengandung huruf dan angka")
    return password


def generate_temp_password(length: int = 12) -> str:
    """Password acak (tanpa karakter yang mudah tertukar: 0/O, 1/l/I) yang selalu lolos check_password_strength."""
    import secrets

    letters = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    while True:
        pw = "".join(secrets.choice(letters + digits) for _ in range(length))
        if any(c in letters for c in pw) and any(c in digits for c in pw):
            return pw
