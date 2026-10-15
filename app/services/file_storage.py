import hashlib
import uuid
from pathlib import Path

from fastapi import HTTPException

from app.core.config import settings

ALLOWED = {
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".pdf": ("application/pdf", (b"%PDF",)),
}


def save_receipt(claim_id: int, filename: str, content: bytes) -> dict:
    """Validasi (ekstensi, ukuran, isi file) lalu simpan. Mengembalikan metadata file."""
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if not content:
        raise HTTPException(422, "File kosong")
    if len(content) > max_bytes:
        raise HTTPException(413, f"Ukuran file maksimal {settings.MAX_UPLOAD_MB} MB")

    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(422, "Format file harus JPG, PNG, atau PDF")
    mime, magics = ALLOWED[ext]
    if not any(content.startswith(m) for m in magics):
        raise HTTPException(422, "Isi file tidak sesuai dengan ekstensinya")

    folder = Path(settings.UPLOAD_DIR) / str(claim_id)
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{uuid.uuid4().hex}{ext}"  # nama asli tidak dipakai di disk (cegah path traversal)
    stored.write_bytes(content)
    return {
        "file_name": Path(filename).name[:255],
        "file_path": str(stored),
        "mime_type": mime,
        "size": len(content),
        "checksum": hashlib.sha256(content).hexdigest(),
    }


def delete_file(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass
