"""Centralised application settings, read from environment variables or a .env file.

Every tunable number the API relies on (token lifetimes, upload limits, paths) lives here,
so behaviour can be changed by configuration instead of code edits. ML decision numbers
(thresholds, uncertainty margins, severity bands) live in ``config/risk_policy.json``.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"


class DatabaseSettings(BaseSettings):
    """Just the database URL, so Alembic can run without the API's secrets."""
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SQLite locally; switch to PostgreSQL with e.g. postgresql+psycopg://user:pass@host/db
    database_url: str = f"sqlite:///{(REPO_ROOT / 'data' / 'app.db').as_posix()}"

    @field_validator("database_url")
    @classmethod
    def _normalise_database_url(cls, value: str) -> str:
        """sqlite:///data/app.db means <repo>/data/app.db no matter which folder a command runs from.
        Hosting providers hand out postgres:// or postgresql:// URLs; the app's driver is psycopg 3."""
        prefix = "sqlite:///"
        if value.startswith(prefix) and not Path(value.removeprefix(prefix)).is_absolute():
            return prefix + (REPO_ROOT / value.removeprefix(prefix)).as_posix()
        for scheme in ("postgres://", "postgresql://"):
            if value.startswith(scheme):
                return "postgresql+psycopg://" + value.removeprefix(scheme)
        return value


class Settings(DatabaseSettings):
    app_name: str = "Retinal Screening API"
    environment: str = "development"

    # Secrets have no default: the app refuses to start without them (see scripts/init_env.py).
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    login_max_failures: int = 5
    login_window_seconds: int = 15 * 60

    models_dir: Path = REPO_ROOT / "models"
    risk_policy_path: Path = BACKEND_ROOT / "config" / "risk_policy.json"
    upload_dir: Path = REPO_ROOT / "data" / "uploads"
    max_upload_bytes: int = 10 * 1024 * 1024
    allowed_image_types: tuple[str, ...] = ("image/jpeg", "image/png")

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173"]

    # Conditions the product is scoped to (approved proposal). A condition without a valid
    # model folder is reported as "model not available yet".
    conditions: tuple[str, ...] = ("dr", "glaucoma", "cataract")

    # Hosted deployment (render.yaml): the PWA's host name, e.g. retina-screening.onrender.com. When set, it is
    # allowed by CORS and used for links in emails.
    frontend_host: str | None = None

    # Password reset by email. Without SMTP_HOST, messages are written to email_outbox_dir instead.
    app_base_url: str = "http://localhost:5173"   # where the reset link points (the PWA)
    password_reset_minutes: int = 30
    email_outbox_dir: Path = REPO_ROOT / "data" / "outbox"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_sender: str = "Retinal Screening <no-reply@example.org>"
    smtp_starttls: bool = True

    @model_validator(mode="after")
    def _use_frontend_host(self) -> "Settings":
        if self.frontend_host:
            origin = f"https://{self.frontend_host.removeprefix('https://').rstrip('/')}"
            if origin not in self.cors_origins:
                self.cors_origins = [*self.cors_origins, origin]
            if self.app_base_url == "http://localhost:5173":
                self.app_base_url = origin
        return self

    @field_validator("jwt_secret")
    @classmethod
    def _reject_placeholder(cls, value: str) -> str:
        if "change-me" in value:
            raise ValueError("JWT_SECRET is still the placeholder; run scripts/init_env.py.")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
