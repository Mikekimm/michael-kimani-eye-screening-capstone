"""Repositories: the only layer that builds SQL queries. Services depend on these, not on SQLAlchemy."""
from collections.abc import Sequence
from datetime import datetime
from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..core.database import Base
from ..models import (
    AuditEvent, DiagnosisResult, PasswordResetToken, Patient, Referral, RefreshToken, ReviewEvent, Screening,
    SyncLog, User,
)
from ..models.enums import Role, ScreeningStatus

T = TypeVar("T", bound=Base)


class Repository(Generic[T]):
    """Shared persistence operations; subclasses add the queries their aggregate needs."""
    model: type[T]

    def __init__(self, session: Session):
        self.session = session

    def get(self, entity_id) -> T | None:
        return self.session.get(self.model, entity_id)

    def add(self, entity: T) -> T:
        self.session.add(entity)
        self.session.flush()
        return entity


class UserRepository(Repository[User]):
    model = User

    def by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(func.lower(User.email) == email.lower()))

    def list(self) -> Sequence[User]:
        return self.session.scalars(select(User).order_by(User.created_at)).all()

    def count_by_role(self) -> dict[str, int]:
        rows = self.session.execute(select(User.role, func.count()).group_by(User.role)).all()
        return {role.value: count for role, count in rows}


class RefreshTokenRepository(Repository[RefreshToken]):
    model = RefreshToken

    def revoke_all_for(self, user_id: str, when: datetime) -> None:
        """Ends every session of a user, e.g. after a password reset."""
        for token in self.session.scalars(select(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))):
            token.revoked_at = when


class PasswordResetRepository(Repository[PasswordResetToken]):
    model = PasswordResetToken

    def by_hash(self, token_hash: str) -> PasswordResetToken | None:
        return self.session.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))


class PatientRepository(Repository[Patient]):
    model = Patient

    def by_code(self, code: str) -> Patient | None:
        return self.session.scalar(select(Patient).where(func.lower(Patient.code) == code.lower()))

    def by_client_uuid(self, client_uuid: str) -> Patient | None:
        return self.session.scalar(select(Patient).where(Patient.client_uuid == client_uuid))

    def search(self, query: str | None, created_by_id: str | None, limit: int = 100) -> Sequence[Patient]:
        stmt = select(Patient).options(selectinload(Patient.screenings)).order_by(Patient.created_at.desc())
        if created_by_id:
            stmt = stmt.where(Patient.created_by_id == created_by_id)
        if query:
            stmt = stmt.where(Patient.code.ilike(f"%{query}%"))
        return self.session.scalars(stmt.limit(limit)).all()

    def has_referred_screening(self, patient_id: str) -> bool:
        stmt = select(Referral.id).join(Screening).where(Screening.patient_id == patient_id).limit(1)
        return self.session.scalar(stmt) is not None


_SCREENING_GRAPH = (
    selectinload(Screening.results), selectinload(Screening.patient),
    selectinload(Screening.created_by), selectinload(Screening.referral),
    selectinload(Screening.reviews).selectinload(ReviewEvent.reviewer),
)


class ScreeningRepository(Repository[Screening]):
    model = Screening

    def get_full(self, screening_id: str) -> Screening | None:
        return self.session.scalar(select(Screening).options(*_SCREENING_GRAPH).where(Screening.id == screening_id))

    def by_client_uuid(self, client_uuid: str) -> Screening | None:
        return self.session.scalar(
            select(Screening).options(*_SCREENING_GRAPH).where(Screening.client_uuid == client_uuid))

    def list(self, created_by_id: str | None = None, patient_id: str | None = None,
             limit: int = 50) -> Sequence[Screening]:
        stmt = select(Screening).options(*_SCREENING_GRAPH).order_by(Screening.created_at.desc())
        if created_by_id:
            stmt = stmt.where(Screening.created_by_id == created_by_id)
        if patient_id:
            stmt = stmt.where(Screening.patient_id == patient_id)
        return self.session.scalars(stmt.limit(limit)).all()

    def review_queue(self) -> Sequence[Screening]:
        """Open referrals, oldest first, so nobody waits longest by accident."""
        stmt = (select(Screening).options(*_SCREENING_GRAPH).join(Referral)
                .where(Referral.is_open.is_(True)).order_by(Screening.created_at.asc()))
        return self.session.scalars(stmt).all()

    def changed_since(self, created_by_id: str, since: datetime) -> Sequence[Screening]:
        stmt = (select(Screening).options(*_SCREENING_GRAPH)
                .where(Screening.created_by_id == created_by_id, Screening.updated_at > since)
                .order_by(Screening.updated_at.asc()))
        return self.session.scalars(stmt).all()


class ReviewRepository(Repository[ReviewEvent]):
    """Append-only: exposes add and read, never update or delete."""
    model = ReviewEvent

    def for_screening(self, screening_id: str) -> Sequence[ReviewEvent]:
        return self.session.scalars(
            select(ReviewEvent).where(ReviewEvent.screening_id == screening_id).order_by(ReviewEvent.created_at)
        ).all()


class SyncLogRepository(Repository[SyncLog]):
    model = SyncLog


class AuditRepository(Repository[AuditEvent]):
    model = AuditEvent

    def list(self, limit: int = 100) -> Sequence[AuditEvent]:
        return self.session.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all()


class AnalyticsRepository:
    """Read-only aggregate queries. Returns counts only: no images, codes or names."""

    def __init__(self, session: Session):
        self.session = session

    def total_screenings(self) -> int:
        return self.session.scalar(select(func.count()).select_from(Screening)) or 0

    def screenings_per_day(self, limit_days: int = 30) -> list[tuple[str, int]]:
        day = func.date(Screening.created_at)
        rows = self.session.execute(
            select(day, func.count()).group_by(day).order_by(day.desc()).limit(limit_days)).all()
        return [(str(d), c) for d, c in reversed(rows)]

    def positives_per_condition(self) -> dict[str, int]:
        rows = self.session.execute(
            select(DiagnosisResult.condition, func.count())
            .where(DiagnosisResult.positive.is_(True)).group_by(DiagnosisResult.condition)).all()
        return dict(rows)

    def referral_count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(Referral)) or 0

    def open_referral_count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(Referral).where(Referral.is_open.is_(True))) or 0

    def first_review_delays(self) -> list[tuple[datetime, datetime]]:
        """(referral created, first decisive review) pairs for closed referrals."""
        first_review = (select(ReviewEvent.screening_id, func.min(ReviewEvent.created_at).label("at"))
                        .where(ReviewEvent.action != "comment").group_by(ReviewEvent.screening_id).subquery())
        rows = self.session.execute(
            select(Referral.created_at, first_review.c.at)
            .join(first_review, first_review.c.screening_id == Referral.screening_id)).all()
        return [(a, b) for a, b in rows]

    def model_versions_in_use(self) -> dict[str, int]:
        rows = self.session.execute(
            select(DiagnosisResult.model_version, func.count())
            .where(DiagnosisResult.model_available.is_(True)).group_by(DiagnosisResult.model_version)).all()
        return {version: count for version, count in rows}

    def status_counts(self) -> dict[ScreeningStatus, int]:
        rows = self.session.execute(select(Screening.status, func.count()).group_by(Screening.status)).all()
        return dict(rows)


__all__ = [
    "AnalyticsRepository", "AuditRepository", "PatientRepository", "RefreshTokenRepository",
    "Repository", "ReviewRepository", "Role", "ScreeningRepository", "SyncLogRepository", "UserRepository",
]
