"""Dependency injection: builds services per request from application-wide singletons.

Long-lived objects (settings, database, model registry, pipeline, token service) are created
once in ``create_app`` and stored on ``app.state``. Request-scoped services receive a session
and repositories here, so routes stay thin and tests can swap any piece.
"""
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..core.config import Settings
from ..core.database import Database
from ..core.errors import AuthenticationError, PermissionDeniedError
from ..core.security import PasswordHasher, TokenService
from ..core.throttle import LoginThrottle
from ..ml.registry import ModelRegistry
from ..ml.risk_policy import RiskPolicyFactory
from ..models import User
from ..models.enums import Role
from ..repositories import (
    AnalyticsRepository, AuditRepository, PasswordResetRepository, PatientRepository, RefreshTokenRepository,
    ReviewRepository,
    ScreeningRepository, UserRepository,
)
from ..services.access import AccessPolicy
from ..services.analytics import AnalyticsService
from ..services.audit import AuditService
from ..services.auth import AuthService, PasswordResetConfig
from ..services.email import EmailSender
from ..services.image_store import ImageStore
from ..services.patients import PatientService
from ..services.pipeline import ScreeningPipeline
from ..services.presenters import ScreeningPresenter
from ..services.review_targets import ReviewTargets
from ..services.reviews import ReviewService
from ..services.screenings import ScreeningService
from ..services.sync import SyncService
from ..services.users import UserService


@dataclass
class AppContainer:
    settings: Settings
    database: Database
    registry: ModelRegistry
    policies: RiskPolicyFactory
    pipeline: ScreeningPipeline
    images: ImageStore
    hasher: PasswordHasher
    tokens: TokenService
    login_throttle: LoginThrottle
    signup_throttle: LoginThrottle
    review_targets: ReviewTargets
    email: EmailSender


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


Container = Annotated[AppContainer, Depends(get_container)]


def get_presenter(container: Container) -> ScreeningPresenter:
    return ScreeningPresenter(container.review_targets, container.policies.advisor())


Presenter = Annotated[ScreeningPresenter, Depends(get_presenter)]


def get_session(container: Container) -> Iterator[Session]:
    yield from container.database.session()


DbSession = Annotated[Session, Depends(get_session)]


def _audit(session: Session) -> AuditService:
    return AuditService(AuditRepository(session))


def _access(session: Session) -> AccessPolicy:
    return AccessPolicy(PatientRepository(session))


def get_auth_service(session: DbSession, container: Container) -> AuthService:
    return AuthService(session, UserRepository(session), RefreshTokenRepository(session), container.hasher,
                       container.tokens, _audit(session), container.settings.access_token_minutes * 60,
                       container.login_throttle, PasswordResetRepository(session),
                       PasswordResetConfig(container.email, container.settings.app_base_url,
                                           container.settings.password_reset_minutes),
                       signup_throttle=container.signup_throttle)


def get_user_service(session: DbSession, container: Container) -> UserService:
    return UserService(session, UserRepository(session), container.hasher, _audit(session),
                       container.email, container.settings.app_base_url)


def get_patient_service(session: DbSession) -> PatientService:
    return PatientService(session, PatientRepository(session), _access(session), _audit(session))


def get_screening_service(session: DbSession, container: Container) -> ScreeningService:
    return ScreeningService(session, ScreeningRepository(session), PatientRepository(session),
                            container.pipeline, container.images, _access(session), _audit(session),
                            container.policies.advisor(), ZoneInfo(container.settings.time_zone))


def get_review_service(session: DbSession, container: Container) -> ReviewService:
    return ReviewService(session, ScreeningRepository(session), ReviewRepository(session), _audit(session),
                         container.review_targets)


def get_sync_service(session: DbSession, patients: Annotated[PatientService, Depends(get_patient_service)]) -> SyncService:
    return SyncService(session, patients, ScreeningRepository(session))


def get_analytics_service(session: DbSession, container: Container) -> AnalyticsService:
    return AnalyticsService(AnalyticsRepository(session), UserRepository(session), ScreeningRepository(session),
                            container.review_targets, ZoneInfo(container.settings.time_zone))


_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    if credentials is None:
        raise AuthenticationError("Sign in to continue.")
    return auth.user_from_access_token(credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role):
    """Route-level RBAC guard; services repeat the check so they are safe outside HTTP too."""
    def _guard(user: CurrentUser) -> User:
        if user.role not in roles:
            raise PermissionDeniedError("Your role does not allow this action.")
        return user
    return _guard


HealthWorker = Annotated[User, Depends(require_roles(Role.HEALTH_WORKER))]
Specialist = Annotated[User, Depends(require_roles(Role.SPECIALIST))]
Admin = Annotated[User, Depends(require_roles(Role.ADMIN))]
ClinicalUser = Annotated[User, Depends(require_roles(Role.HEALTH_WORKER, Role.SPECIALIST))]
