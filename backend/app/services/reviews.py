"""Specialist review workflow. Every decision is appended to review_events; nothing is overwritten.

The screening's ``status`` is a convenience summary of the latest decisive event; the full,
immutable history is always available alongside it.
"""
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..core.errors import AppError, NotFoundError
from ..models import ReviewEvent, Screening, User
from ..models.enums import ReviewAction, Role, ScreeningStatus
from ..repositories import ReviewRepository, ScreeningRepository
from ..schemas import QueueItemOut, ReviewRequest
from .access import AccessPolicy
from .audit import AuditService

_STATUS_AFTER = {
    ReviewAction.APPROVE: ScreeningStatus.REVIEWED,
    ReviewAction.OVERRIDE: ScreeningStatus.REVIEWED,
    ReviewAction.REQUEST_RETAKE: ScreeningStatus.RETAKE_REQUESTED,
}


class ReviewService:
    def __init__(self, session: Session, screenings: ScreeningRepository, reviews: ReviewRepository,
                 audit: AuditService):
        self._session = session
        self._screenings = screenings
        self._reviews = reviews
        self._audit = audit

    def queue(self, user: User) -> list[QueueItemOut]:
        AccessPolicy.require_role(user, Role.SPECIALIST)
        return [self._queue_item(s) for s in self._screenings.review_queue()]

    @staticmethod
    def _queue_item(screening: Screening) -> QueueItemOut:
        bands = [r.severity_band for r in screening.results if r.severity_band is not None]
        return QueueItemOut(screening_id=screening.id, patient_code=screening.patient.code, eye=screening.eye,
                            referral_reason=screening.referral.reason, highest_band=max(bands, default=None),
                            created_at=screening.created_at, created_by_name=screening.created_by.full_name)

    def review(self, user: User, screening_id: str, request: ReviewRequest) -> Screening:
        AccessPolicy.require_role(user, Role.SPECIALIST)
        screening = self._screenings.get_full(screening_id)
        if screening is None or screening.referral is None:
            raise NotFoundError("Referred screening not found.")
        if request.condition is not None:
            evaluated = {r.condition for r in screening.results if r.model_available}
            if request.condition not in evaluated:
                raise AppError(f"'{request.condition}' was not evaluated by a model in this screening.")

        self._reviews.add(ReviewEvent(screening_id=screening.id, reviewer_id=user.id, action=request.action,
                                      condition=request.condition, override_positive=request.override_positive,
                                      note=request.note))
        now = datetime.now(timezone.utc)
        if request.action in _STATUS_AFTER:
            screening.status = _STATUS_AFTER[request.action]
            screening.referral.is_open = False
            screening.referral.closed_at = now
        screening.updated_at = now  # lets the health worker's next sync pull pick up the decision
        self._audit.record(user.id, f"review.{request.action.value}", "screening", screening.id)
        self._session.commit()
        self._session.expire(screening)
        return self._screenings.get_full(screening.id)

    def history(self, screening_id: str) -> Sequence[ReviewEvent]:
        return self._reviews.for_screening(screening_id)
