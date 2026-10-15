import logging
import smtplib
import threading
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("email")


class EmailError(Exception):
    pass


def can_deliver() -> bool:
    """Email bisa dikirim? (SMTP terisi, atau mode DEBUG yang hanya menulis ke log)."""
    return bool(settings.SMTP_HOST) or settings.DEBUG


def _smtp_send(to: list[str], subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.SMTP_FROM, ", ".join(to), subject
    msg.set_content(body)
    if settings.SMTP_PORT == 465:  # SSL langsung
        smtp_ctx = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
    else:  # 587 (STARTTLS), yang direkomendasikan
        smtp_ctx = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
    with smtp_ctx as smtp:
        if settings.SMTP_PORT != 465:
            smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


def send_now(to: list[str], subject: str, body: str) -> None:
    """Kirim SEKARANG dan laporkan kegagalan (raise EmailError). Untuk email berisi kredensial/token.

    Tanpa SMTP_HOST: hanya jika DEBUG=true isi email ditulis ke log (khusus development).
    Di production tanpa SMTP, email berisi password/token TIDAK pernah ditulis ke log.
    """
    to = [t for t in to if t]
    if not to:
        return
    if not settings.SMTP_HOST:
        if settings.DEBUG:
            logger.warning("[EMAIL-DEV, hanya DEBUG] to=%s subject=%s\n%s", to, subject, body)
            return
        raise EmailError("SMTP belum dikonfigurasi")
    try:
        _smtp_send(to, subject, body)
    except Exception as e:
        logger.exception("Gagal mengirim email ke %s", to)
        raise EmailError("Gagal mengirim email") from e


def send_secret_async(to: list[str], subject: str, body: str) -> None:
    """Seperti send_now tetapi di thread terpisah dan kegagalan hanya dilog.
    Dipakai untuk 'lupa password' agar waktu respons tidak membocorkan apakah email terdaftar."""

    def run():
        try:
            send_now(to, subject, body)
        except EmailError as e:
            logger.error("Email sensitif tidak terkirim ke %s: %s", to, e)

    threading.Thread(target=run, daemon=True).start()


def send_email(to: list[str], subject: str, body: str) -> None:
    """Notifikasi biasa (tanpa data rahasia), best-effort di thread terpisah. Tanpa SMTP_HOST hanya ditulis ke log."""
    to = [t for t in to if t]
    if not to:
        return
    if not settings.SMTP_HOST:
        logger.info("[EMAIL-DEV] to=%s subject=%s\n%s", to, subject, body)
        return

    def run():
        try:
            _smtp_send(to, subject, body)
        except Exception:  # notifikasi tidak boleh menggagalkan proses bisnis
            logger.exception("Gagal mengirim email ke %s", to)

    threading.Thread(target=run, daemon=True).start()
