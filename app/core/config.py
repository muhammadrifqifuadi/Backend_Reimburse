from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Reimburse API"
    DEBUG: bool = False
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/reimburse"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    SECRET_KEY: str = "ganti-dengan-string-acak-minimal-32-karakter"
    ENCRYPTION_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 5

    RESET_TOKEN_EXPIRE_MINUTES: int = 30
    # Tautan di email. {token} diganti token reset. Kosong = email hanya berisi token.
    FRONTEND_RESET_URL: str = ""
    FRONTEND_LOGIN_URL: str = ""

    CLAIM_MAX_AGE_DAYS: int = 30
    RECEIPT_REQUIRED_ABOVE: float = 50000

    AUTO_CREATE_TABLES: bool = True

    # Hanya dipakai `python -m app.seed` untuk membuat admin pertama (boleh dikosongkan, akan ditanya interaktif)
    ADMIN_EMAIL: str = ""
    ADMIN_NAME: str = ""
    ADMIN_PASSWORD: str = ""

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@perusahaan.com"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
