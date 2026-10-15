"""Uji pengiriman email SEBELUM mulai membuat user.

    python -m app.test_email alamat.tujuan@gmail.com

Memakai SMTP_* dari .env dan menampilkan penyebab yang jelas jika gagal.
"""
import smtplib
import socket
import sys

from app.core.config import settings
from app.services.email_utils import _smtp_send


def main() -> int:
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        print("Pemakaian: python -m app.test_email alamat.tujuan@gmail.com", file=sys.stderr)
        return 2
    if not settings.SMTP_HOST:
        print("SMTP_HOST di .env masih kosong.", file=sys.stderr)
        return 1
    to = sys.argv[1]
    print(f"Mengirim via {settings.SMTP_HOST}:{settings.SMTP_PORT} sebagai {settings.SMTP_USER or '(tanpa login)'} ...")
    try:
        _smtp_send([to], "[Reimburse] Tes pengiriman email",
                   "Jika email ini sampai, pengaturan SMTP aplikasi Reimburse sudah benar.\n"
                   "Password sementara dan token reset password akan dikirim dengan cara yang sama.")
    except smtplib.SMTPAuthenticationError:
        print("GAGAL: login ditolak. Gmail: gunakan App Password 16 karakter (bukan password akun), "
              "dan SMTP_USER harus alamat Gmail lengkap.", file=sys.stderr)
        return 1
    except smtplib.SMTPRecipientsRefused:
        print(f"GAGAL: alamat tujuan {to} ditolak server.", file=sys.stderr)
        return 1
    except (socket.timeout, TimeoutError, ConnectionError, socket.gaierror) as e:
        print(f"GAGAL: tidak bisa terhubung ke {settings.SMTP_HOST}:{settings.SMTP_PORT} ({e}). "
              "Periksa host/port dan koneksi internet/firewall server.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"GAGAL: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(f"Berhasil. Cek inbox {to} (juga folder Spam).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
