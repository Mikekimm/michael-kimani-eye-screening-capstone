"""Screening use cases: create (idempotent on client_uuid), read, list, ask a specialist, discard, daily counts."""
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.errors import AppError, ConflictError, ConsentRequiredError
from ..models import DiagnosisResult, Referral, Screening, SyncLog, User
from ..ml.risk_policy import ReferralAdvisor
from ..models.enums import Eye, ReferralAdvice, ReferralReason, Role, ScreeningStatus, SyncOutcome
from ..repositories import PatientRepository, ScreeningRepository
from .access import AccessPolicy
from .audit import AuditService
from .image_store import ImageStore
from .pipeline import PipelineOutcome, ScreeningPipeline
from .daily_counts import count_by_day, local_day, start_of_window
from .presenters import quality_out

CLOCK_SKEW = timedelta(minutes=5)
# The recommendation at the moment of asking decides the review priority (urgent for a clear positive).
_REASON_FOR = {ReferralAdvice.RECOMMENDED: ReferralReason.POSITIVE,
               ReferralAdvice.CONSIDER: ReferralReason.UNCERTAIN,
               ReferralAdvice.NONE: ReferralReason.MANUAL}


class ScreeningService:
    def __init__(self, session: Session, screenings: ScreeningRepository, patients: PatientRepository,
                 pipeline: ScreeningPipeline, images: ImageStore, access: AccessPolicy, audit: AuditService,
                 advisor: ReferralAdvisor | None = None, zone: ZoneInfo | None = None):
        self._session = session
        self._screenings = screenings
        self._patients = patients
        self._pipeline = pipeline
        self._images = images
        self._access = access
        self._audit = audit
        self._advisor = advisor or ReferralAdvisor()
        self._zone = zone or ZoneInfo("UTC")

    @property
    def time_zone(self) -> str:
        return self._zone.key

    def create(self, user: User, *, patient_id: str, eye: Eye, client_uuid: str, captured_at: datetime,
               content_type: str | None, data: bytes, sync_attempt: int = 1,
               patient_consent: bool = False) -> tuple[Screening, bool]:
        """Returns (screening, duplicate). Re-sending the same client_uuid never creates a second record.
        Nothing is analysed or stored unless the health worker confirmed the patient's consent."""
        AccessPolicy.require_role(user, Role.HEALTH_WORKER)
        existing = self._existing(user, client_uuid, sync_attempt)
        if existing is not None:
            return existing, True
        if not patient_consent:
            raise ConsentRequiredError("Confirm that the patient agreed to the photo and the screening.")

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
                refer_suggested=bool(c.assessment and c.assessment.refer_suggested),
            )
            for c in outcome.conditions
        ]
        # Nothing is sent to a specialist here: the health worker sees the recommendation and decides.
        screening = Screening(
            client_uuid=client_uuid, patient_id=patient_id, eye=eye, captured_at=captured_at, patient_consent=True,
            image_path=image_name,
            image_sha256=outcome.image_sha256, quality=quality_out(outcome.quality),
            status=ScreeningStatus.COMPLETED, created_by_id=user.id, results=results,
        )
        return screening

    def ask_specialist(self, user: User, screening_id: str, question: str) -> Screening:
        """The health worker sends the case to the specialist queue with a question. Only sent cases are
        "Awaiting specialist"; a screening can be sent once."""
        AccessPolicy.require_role(user, Role.HEALTH_WORKER)
        screening = self.get(user, screening_id)
        if screening.referral is not None:
            raise ConflictError("This screening has already been sent to a specialist.")
        advice = self._advisor.advise(screening.results, bool(screening.quality.get("warnings")))
        screening.referral = Referral(reason=_REASON_FOR[advice], question=question)
        screening.status = ScreeningStatus.REFERRED
        screening.updated_at = datetime.now(timezone.utc)
        self._audit.record(user.id, "screening.sent_to_specialist", "screening", screening.id)
        self._session.commit()
        self._session.expire(screening)
        return self._screenings.get_full(screening.id)

    def discard(self, user: User, screening_id: str, reason: str) -> None:
        """Soft delete by the health worker who made it: hidden from every list, queue and count; the row,
        its review history and the audit entry stay, and the photo file is deleted."""
        AccessPolicy.require_role(user, Role.HEALTH_WORKER)
        screening = self.get(user, screening_id)
        now = datetime.now(timezone.utc)
        screening.discarded_at, screening.discarded_by_id, screening.discard_reason = now, user.id, reason
        if screening.referral is not None and screening.referral.is_open:
            screening.referral.is_open, screening.referral.closed_at = False, now
        screening.updated_at = now
        self._audit.record(user.id, "screening.discarded", "screening", screening.id)
        self._session.commit()
        self._images.delete(screening.image_path)

    def daily_counts(self, user: User, days: int, now: datetime | None = None) -> tuple[str, list]:
        """This health worker's screenings per local day, last ``days`` days ending today."""
        AccessPolicy.require_role(user, Role.HEALTH_WORKER)
        now = now or datetime.now(timezone.utc)
        times = self._screenings.created_times(user.id, start_of_window(self._zone, days, now))
        return local_day(now, self._zone).isoformat(), count_by_day(times, self._zone, days, now)

    def get(self, user: User, screening_id: str) -> Screening:
        return self._access.check_screening(user, self._screenings.get_full(screening_id))

    def list_mine(self, user: User, patient_id: str | None = None, limit: int = 50,
                  on_day: date | None = None) -> Sequence[Screening]:
        """Newest first. ``on_day`` keeps one calendar day in the clinic's time zone."""
        AccessPolicy.require_role(user, Role.HEALTH_WORKER)
        if on_day is None:
            return self._screenings.list(created_by_id=user.id, patient_id=patient_id, limit=limit)
        start = datetime(on_day.year, on_day.month, on_day.day, tzinfo=self._zone)
        return self._screenings.list(created_by_id=user.id, patient_id=patient_id, limit=limit,
                                     day_start=start.astimezone(timezone.utc),
                                     day_end=(start + timedelta(days=1)).astimezone(timezone.utc))

    def image_path(self, user: User, screening_id: str):
        screening = self.get(user, screening_id)
        return self._images.path_for(screening.image_path)
