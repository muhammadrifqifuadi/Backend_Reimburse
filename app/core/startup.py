import logging
from pathlib import Path

from app.core.config import settings
from app.core.database import Base, engine

logger = logging.getLogger("startup")


def on_startup() -> None:
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    from app.models import registry  # noqa: F401  (pastikan semua tabel terdaftar)

    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
    if settings.SECRET_KEY.startswith("ganti-dengan"):
        logger.warning("SECRET_KEY masih default. Ganti sebelum production!")
