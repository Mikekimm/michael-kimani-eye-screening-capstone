"""Settings needed by the hosted deployment (render.yaml): database URL schemes and the PWA's host."""
import secrets

from app.core.config import Settings


def _settings(**overrides) -> Settings:
    return Settings(jwt_secret=secrets.token_hex(32), **overrides)


def test_hosting_provider_postgres_urls_use_the_psycopg3_driver():
    for given in ("postgres://u:p@db:5432/screening", "postgresql://u:p@db:5432/screening"):
        assert _settings(database_url=given).database_url == "postgresql+psycopg://u:p@db:5432/screening"
    explicit = "postgresql+psycopg://u:p@db:5432/screening"
    assert _settings(database_url=explicit).database_url == explicit


def test_frontend_host_is_allowed_by_cors_and_used_for_email_links():
    settings = _settings(frontend_host="retina-screening.onrender.com")
    assert "https://retina-screening.onrender.com" in settings.cors_origins
    assert "http://localhost:5173" in settings.cors_origins  # local development keeps working
    assert settings.app_base_url == "https://retina-screening.onrender.com"


def test_without_frontend_host_local_defaults_are_unchanged():
    settings = _settings()
    assert settings.app_base_url == "http://localhost:5173"
    assert not any("onrender" in origin for origin in settings.cors_origins)
