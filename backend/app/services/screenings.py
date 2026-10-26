"""Screening use cases: create (idempotent on client_uuid), read, list."""
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.errors import AppError, ConflictError
from ..models import DiagnosisResult, Referral, Screening, SyncLog, User
from ..models.enums import Eye, ReferralReason, Role, ScreeningStatus, SyncOutcome
from ..repositories import PatientRepository, ScreeningRepository
from .access import AccessPolicy
from .audit import AuditService
from .image_store import ImageStore
from .pipeline import PipelineOutcome, ScreeningPipeline
from .presenters import quality_out

CLOCK_SKEW = timedelta(minutes=5)


class ScreeningService:
    def __init__(self, session: Session, screenings: ScreeningRepository, patients: PatientRepository,
                 pipeline: ScreeningPipeline, images: ImageStore, access: AccessPolicy, audit: AuditService):
        self._session = session
        self._screenings = screenings
        self._patients = patients
        self._pipeline = pipeline
        self._images = images
        self._access = access
        self._audit = audit

    def create(self, user: User, *, patient_id: str, eye: Eye, client_uuid: str, captured_at: datetime,
               content_type: str | None, data: bytes, sync_attempt: int = 1) -> tuple[Screening, bool]:
        """Returns (screening, duplicate). Re-sending the same client_uuid never creates a second record."""
        AccessPolicy.require_role(user, Role.HEALTH_WORKER)
        existing = self._existing(user, client_uuid, sync_attempt)
        if existing is not None:
            return existing, True

        self._access.check_patient(user, self._patients.get(patient_id))
        captured_at = self._validate_captured_at(captured_at)
        outcome = self._pipeline.run(content_type, data)  # raises 413/422 for unusable uploads

        image_name = self._images.save(data, outcome.image_format)
        screening = self._build(user, patient_id, eye, client_uuid, captured_at, outcome, image_name)
        try:
            self._screenings.add(screening)
            self._session.add(SyncLog(user_id=user.id, client_uuid=client_uuid, entity_type="screening",
                                      outcome=SyncOutcome.ACCEPTED, attempt=sync_attempt))
            self._audit.record(user.id, "screening.created", "screening", screening.id)
            self._session.commit()
        except IntegrityError:
            # Two copies of the same upload raced each other; the first one won.
            self._session.rollback()
            self._images.delete(image_name)
            existing = self._existing(user, client_uuid, sync_attempt)
            if existing is None:
                raise
            return existing, True
        return self._screenings.get_full(screening.id), False

    def _existing(self, user: User, client_uuid: str, attempt: int) -> Screening | None:
        existing = self._screenings.by_client_uuid(client_uuid)
        if existing is None:
            return None
        if existing.created_by_id != user.id:
            raise ConflictError("This client_uuid is already used by another record.")
        self._session.add(SyncLog(user_id=user.id, client_uuid=client_uuid, entity_type="screening",
                                  outcome=SyncOutcome.DUPLICATE, attempt=attempt))
        self._session.commit()
        return existing

    @staticmethod
    def _validate_captured_at(captured_at: datetime) -> datetime:
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=timezone.utc)
        if captured_at > datetime.now(timezone.utc) + CLOCK_SKEW:
            raise AppError("captured_at cannot be in the future.")
        return captured_at

    def _build(self, user: User, patient_id: str, eye: Eye, client_uuid: str, captured_at: datetime,
               outcome: PipelineOutcome, image_name: str) -> Screening:
        results = [
            DiagnosisResult(
                condition=c.condition, model_available=c.model_available, model_version=c.model_version,
                probability=c.probability, threshold=c.threshold,
                positive=c.assessment.positive if c.assessment else None,
                uncertain=c.assessment.uncertain if c.assessment else None,
                severity_band=c.assessment.severity_band if c.assessment else None,
                risk_level=c.assessment.risk_level if c.assessment else None,
                recommendation=c.recommendation,
                auto_refer=bool(c.assessment and c.assessment.auto_refer),
            )
            for c in outcome.conditions
        ]
        referral = self._referral_for(results)
        screening = Screening(
            client_uuid=client_uuid, patient_id=patient_id, eye=eye, captured_at=captured_at,
            image_path=image_name,
            image_sha256=outcome.image_sha256, quality=quality_out(outcome.quality),
            status=ScreeningStatus.REFERRED if referral else ScreeningStatus.COMPLETED,
            created_by_id=user.id, results=results,
        )
        screening.referral = referral
        return screening

    @staticmethod
    def _referral_for(results: list[DiagnosisResult]) -> Referral | None:
        referring = [r for r in results if r.auto_refer]
        if not referring:
            return None
        reason = ReferralReason.POSITIVE if any(r.positive for r in referring) else ReferralReason.UNCERTAIN
        return Referral(reason=reason)

    def get(self, user: User, screening_id: str) -> Screening:
        return self._access.check_screening(user, self._screenings.get_full(screening_id))

    def list_mine(self, user: User, patient_id: str | None = None, limit: int = 50) -> Sequence[Screening]:
        AccessPolicy.require_role(user, Role.HEALTH_WORKER)
        return self._screenings.list(created_by_id=user.id, patient_id=patient_id, limit=limit)

    def image_path(self, user: User, screening_id: str):
        screening = self.get(user, screening_id)
        return self._images.path_for(screening.image_path)
