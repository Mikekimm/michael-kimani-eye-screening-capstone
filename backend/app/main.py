"""Application factory. ``uvicorn app.main:app`` from the backend/ folder."""
import logging
from datetime import timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.deps import AppContainer
from .api.routes import admin, auth, patients, reviews, screenings, sync, system
from .core.config import Settings, get_settings
from .core.database import Database
from .core.errors import register_error_handlers
from .core.security import PasswordHasher, TokenService
from .core.throttle import LoginThrottle
from .ml.registry import ModelRegistry
from .ml.risk_policy import RiskPolicyFactory
from .services.email import EmailSender, OutboxEmailSender, SmtpEmailSender
from .services.image_store import ImageStore
from .services.pipeline import ScreeningPipeline

API_PREFIX = "/api"


def build_container(settings: Settings, registry: ModelRegistry | None = None) -> AppContainer:
    registry = registry or ModelRegistry(settings.conditions).discover(settings.models_dir)
    policies = RiskPolicyFactory.from_file(settings.risk_policy_path)
    return AppContainer(
        settings=settings,
        database=Database(settings.database_url),
        registry=registry,
        policies=policies,
        pipeline=ScreeningPipeline(registry, policies, settings.max_upload_bytes, settings.allowed_image_types),
        images=ImageStore(settings.upload_dir),
        hasher=PasswordHasher(),
        tokens=TokenService(settings.jwt_secret, settings.jwt_algorithm,
                            timedelta(minutes=settings.access_token_minutes),
                            timedelta(days=settings.refresh_token_days)),
        login_throttle=LoginThrottle(settings.login_max_failures, settings.login_window_seconds),
        email=_email_sender(settings),
    )


def _email_sender(settings: Settings) -> EmailSender:
    """Real SMTP when configured; otherwise messages land in data/outbox (development and demos)."""
    if settings.smtp_host:
        return SmtpEmailSender(settings.smtp_host, settings.smtp_port, settings.smtp_username,
                               settings.smtp_password, settings.smtp_sender, settings.smtp_starttls)
    return OutboxEmailSender(settings.email_outbox_dir)


def create_app(container: AppContainer | None = None) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    container = container or build_container(get_settings())
    app = FastAPI(title=container.settings.app_name, version="1.0.0",
                  description="Retinal screening and referral support API. Not a diagnostic device.")
    app.state.container = container
    app.add_middleware(CORSMiddleware, allow_origins=container.settings.cors_origins, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])
    register_error_handlers(app)
    for router in (system.router, auth.router, patients.router, screenings.router, reviews.router,
                   sync.router, admin.router):
        app.include_router(router, prefix=API_PREFIX)
    return app


def __getattr__(name: str):
    # Lazily build the ASGI app so importing this module (e.g. in tests) needs no .env.
    if name == "app":
        return create_app()
    raise AttributeError(name)
