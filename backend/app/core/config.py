"""Centralised application settings, read from environment variables or a .env file.

Every tunable number the API relies on (token lifetimes, upload limits, paths) lives here,
so behaviour can be changed by configuration instead of code edits. ML decision numbers
(thresholds, uncertainty margins, severity bands) live in ``config/risk_policy.json``.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
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
    def _anchor_relative_sqlite_path(cls, value: str) -> str:
        """sqlite:///data/app.db means <repo>/data/app.db no matter which folder a command runs from."""
        prefix = "sqlite:///"
        if value.startswith(prefix) and not Path(value.removeprefix(prefix)).is_absolute():
            return prefix + (REPO_ROOT / value.removeprefix(prefix)).as_posix()
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

    @field_validator("jwt_secret")
    @classmethod
    def _reject_placeholder(cls, value: str) -> str:
        if "change-me" in value:
            raise ValueError("JWT_SECRET is still the placeholder; run scripts/init_env.py.")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
