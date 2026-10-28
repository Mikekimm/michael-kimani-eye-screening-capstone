"""Specialist review workflow. Every decision is appended to review_events; nothing is overwritten.

The screening's ``status`` is a convenience summary of the latest decisive event; the full,
immutable history is always available alongside it.
"""
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..core.errors import AppError, ConflictError, NotFoundError
from ..models import ReviewEvent, Screening, User
from ..models.enums import ReviewAction, Role, ScreeningStatus, Specialty
from ..repositories import ReviewRepository, ScreeningRepository
from ..schemas import QueueItemOut, ReviewRequest
from .access import AccessPolicy
from .audit import AuditService
from .review_targets import ReviewTargets

_STATUS_AFTER = {
    ReviewAction.APPROVE: ScreeningStatus.REVIEWED,
    ReviewAction.OVERRIDE: ScreeningStatus.REVIEWED,
    ReviewAction.REQUEST_RETAKE: ScreeningStatus.RETAKE_REQUESTED,
}


class ReviewService:
    def __init__(self, session: Session, screenings: ScreeningRepository, reviews: ReviewRepository,
                 audit: AuditService, targets: ReviewTargets | None = None):
        self._session = session
        self._screenings = screenings
        self._reviews = reviews
        self._audit = audit
        self._targets = targets or ReviewTargets()

    def queue(self, user: User) -> list[QueueItemOut]:
        """Every open case, those matching the specialist's specialties first; within each group overdue
        first, then the longest waiting. The UI shows the matching ones under "My specialties" and all of
        them under "All cases"."""
        AccessPolicy.require_role(user, Role.SPECIALIST)
        now = datetime.now(timezone.utc)
        items = [self._queue_item(s, now, user) for s in self._screenings.review_queue()]
        return sorted(items, key=lambda item: (not item.matches_my_specialties, not item.overdue, item.waiting_since))

    @staticmethod
    def matches(specialties: list[str] | None, conditions: list[str]) -> bool:
        """"general" matches every case; otherwise any shared condition."""
        mine = set(specialties or [])
        return Specialty.GENERAL.value in mine or bool(mine & set(conditions))

    def take(self, user: User, screening_id: str) -> Screening:
        """Assigns a queued case to this specialist; others then see it as taken. Only open cases in the
        queue can be taken, and a case taken by someone else cannot be taken over."""
        AccessPolicy.require_role(user, Role.SPECIALIST)
        screening = self._open_case(screening_id)
        referral = screening.referral
        if referral.assigned_to_id not in (None, user.id):
            raise ConflictError(f"This case is already being reviewed by {referral.assigned_to.full_name}.")
        if referral.assigned_to_id is None:
            referral.assigned_to_id, referral.assigned_at = user.id, datetime.now(timezone.utc)
            screening.updated_at = referral.assigned_at  # the health worker's next sync shows who took it
            self._audit.record(user.id, "review.taken", "screening", screening.id)
            self._session.commit()
            self._session.expire_all()  # reload the referral with its new assignee
        return self._screenings.get_full(screening.id)

    def _open_case(self, screening_id: str) -> Screening:
        screening = self._screenings.get_full(screening_id)
        if screening is None or screening.referral is None or screening.discarded_at is not None:
            raise NotFoundError("Referred screening not found.")
        if not screening.referral.is_open:
            raise ConflictError("This case is no longer in the review queue.")
        return screening

    def _queue_item(self, screening: Screening, now: datetime, user: User) -> QueueItemOut:
        bands = [r.severity_band for r in screening.results if r.severity_band is not None]
        flagged = [r.condition for r in screening.results if r.refer_suggested]
        referral = screening.referral
        conditions = list(referral.conditions or []) or flagged
        return QueueItemOut(screening_id=screening.id, patient_code=screening.patient.code, eye=screening.eye,
                            referral_reason=referral.reason, flagged_conditions=flagged,
                            highest_band=max(bands, default=None),
                            created_at=screening.created_at, created_by_name=screening.created_by.full_name,
                            created_by_facility=screening.created_by.facility, question=referral.question,
                            waiting_since=referral.created_at, priority=referral.priority.value,
                            due_at=self._targets.due_at(referral.created_at, referral.priority),
                            overdue=self._targets.is_overdue(referral.created_at, referral.priority, now),
                            conditions=conditions, matches_my_specialties=self.matches(user.specialties, conditions),
                            assigned_to_name=referral.assigned_to.full_name if referral.assigned_to else None,
                            assigned_to_me=referral.assigned_to_id == user.id)

    def review(self, user: User, screening_id: str, request: ReviewRequest) -> Screening:
        AccessPolicy.require_role(user, Role.SPECIALIST)
        screening = self._screenings.get_full(screening_id)
        if screening is None or screening.referral is None or screening.discarded_at is not None:
            raise NotFoundError("Referred screening not found.")
        referral = screening.referral
        if referral.is_open and referral.assigned_to_id not in (None, user.id):
            raise ConflictError(f"This case is being reviewed by {referral.assigned_to.full_name}.")
        if referral.is_open and referral.assigned_to_id is None:  # deciding without "Take" also takes it
            referral.assigned_to_id, referral.assigned_at = user.id, datetime.now(timezone.utc)
            self._audit.record(user.id, "review.taken", "screening", screening.id)
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
        screening.new_decision = True  # "New decisions" on the health worker's home until they open it
        self._audit.record(user.id, f"review.{request.action.value}", "screening", screening.id)
        self._session.commit()
        self._session.expire_all()
        return self._screenings.get_full(screening.id)

    def history(self, screening_id: str) -> Sequence[ReviewEvent]:
        return self._reviews.for_screening(screening_id)
