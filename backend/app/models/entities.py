"""SQLAlchemy ORM entities. One table per concept in the proposal's ERD, extended with the
fields the supervisor asked for: eye laterality, model version per result and an append-only
review history.
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Enum as SAEnum, Float, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base, UTCDateTime, utcnow
from .enums import (
    AccountStatus, Eye, ReferralReason, ReviewAction, RiskLevel, Role, ScreeningStatus, Sex, SyncOutcome,
)


def _uuid() -> str:
    return uuid.uuid4().hex


def _enum(enum_cls) -> SAEnum:
    # Store the value ("health_worker"), not the member name, and use a portable CHECK constraint.
    return SAEnum(enum_cls, values_callable=lambda e: [m.value for m in e], native_enum=False,
                  length=32, validate_strings=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(_enum(Role), default=Role.HEALTH_WORKER, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Self-registered health workers wait for an admin; accounts an admin creates are approved at once.
    status: Mapped[AccountStatus] = mapped_column(_enum(AccountStatus), default=AccountStatus.APPROVED,
                                                  server_default=AccountStatus.APPROVED.value, index=True)
    facility: Mapped[str | None] = mapped_column(String(120), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class PasswordResetToken(Base):
    """One-time password reset link. Only a SHA-256 hash of the token is stored, never the token."""
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class RefreshToken(Base):
    """Server-side record of issued refresh tokens so logout and rotation can revoke them."""
    __tablename__ = "refresh_tokens"

    jti: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Patient(Base):
    """Pseudonymous patient record: a clinic code plus minimal, non-identifying fields."""
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    year_of_birth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sex: Mapped[Sex] = mapped_column(_enum(Sex), default=Sex.UNKNOWN)
    has_diabetes: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    client_uuid: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    screenings: Mapped[list["Screening"]] = relationship(
        back_populates="patient", order_by="Screening.created_at.desc()")

    __table_args__ = (
        CheckConstraint("year_of_birth IS NULL OR (year_of_birth BETWEEN 1900 AND 2100)",
                        name="ck_patients_year_of_birth"),
    )


class Screening(Base):
    """One fundus image of one eye, screened by every available condition model."""
    __tablename__ = "screenings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    client_uuid: Mapped[str] = mapped_column(String(36), unique=True)  # idempotency key
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    eye: Mapped[Eye] = mapped_column(_enum(Eye))
    image_path: Mapped[str] = mapped_column(String(255))
    image_sha256: Mapped[str] = mapped_column(String(64))
    quality: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[ScreeningStatus] = mapped_column(_enum(ScreeningStatus), index=True)
    captured_at: Mapped[datetime] = mapped_column(UTCDateTime)
    # The health worker confirmed the patient agreed to the photo and the screening (NULL = recorded
    # before consent capture existed).
    patient_consent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow,
                                                 onupdate=utcnow, index=True)

    patient: Mapped[Patient] = relationship(back_populates="screenings")
    created_by: Mapped[User] = relationship()
    results: Mapped[list["DiagnosisResult"]] = relationship(
        back_populates="screening", cascade="all, delete-orphan", order_by="DiagnosisResult.condition")
    reviews: Mapped[list["ReviewEvent"]] = relationship(
        back_populates="screening", order_by="ReviewEvent.created_at")
    referral: Mapped["Referral | None"] = relationship(back_populates="screening", uselist=False)


class DiagnosisResult(Base):
    """Outcome for one condition. Unavailable models are stored too, so history shows what ran."""
    __tablename__ = "diagnosis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screening_id: Mapped[str] = mapped_column(ForeignKey("screenings.id", ondelete="CASCADE"))
    condition: Mapped[str] = mapped_column(String(32))
    model_available: Mapped[bool] = mapped_column(Boolean)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    positive: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    uncertain: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    severity_band: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_level: Mapped[RiskLevel | None] = mapped_column(_enum(RiskLevel), nullable=True)
    recommendation: Mapped[str] = mapped_column(Text)
    auto_refer: Mapped[bool] = mapped_column(Boolean, default=False)

    screening: Mapped[Screening] = relationship(back_populates="results")

    __table_args__ = (
        UniqueConstraint("screening_id", "condition", name="uq_result_screening_condition"),
        CheckConstraint("probability IS NULL OR (probability >= 0 AND probability <= 1)",
                        name="ck_result_probability_range"),
        CheckConstraint("severity_band IS NULL OR (severity_band BETWEEN 1 AND 5)",
                        name="ck_result_band_range"),
    )


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screening_id: Mapped[str] = mapped_column(ForeignKey("screenings.id", ondelete="CASCADE"), unique=True)
    reason: Mapped[ReferralReason] = mapped_column(_enum(ReferralReason))
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    screening: Mapped[Screening] = relationship(back_populates="referral")


class ReviewEvent(Base):
    """Append-only specialist review history. Rows are never updated or deleted (see listeners)."""
    __tablename__ = "review_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screening_id: Mapped[str] = mapped_column(ForeignKey("screenings.id"), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[ReviewAction] = mapped_column(_enum(ReviewAction))
    condition: Mapped[str | None] = mapped_column(String(32), nullable=True)
    override_positive: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)

    screening: Mapped[Screening] = relationship(back_populates="reviews")
    reviewer: Mapped[User] = relationship()


class SyncLog(Base):
    """One row per item a device tried to sync: what happened, on which attempt, and why."""
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    client_uuid: Mapped[str] = mapped_column(String(36), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    outcome: Mapped[SyncOutcome] = mapped_column(_enum(SyncOutcome))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AuditEvent(Base):
    """Security audit trail. Stores ids and action names only, never images or patient data."""
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)

    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)


class AppendOnlyViolation(RuntimeError):
    """Raised when code tries to modify or delete review history."""


@event.listens_for(ReviewEvent, "before_update")
def _forbid_review_update(_mapper, _connection, target: ReviewEvent) -> None:
    raise AppendOnlyViolation(f"Review event {target.id} is append-only and cannot be edited.")


@event.listens_for(ReviewEvent, "before_delete")
def _forbid_review_delete(_mapper, _connection, target: ReviewEvent) -> None:
    raise AppendOnlyViolation(f"Review event {target.id} is append-only and cannot be deleted.")
