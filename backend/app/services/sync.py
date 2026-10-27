"""Two-way sync for devices that work offline.

push: patients registered offline arrive in a batch; each carries a client_uuid, so replaying a
      batch after a dropped connection is safe (duplicates are reported, never re-created).
      Screenings captured offline are replayed one by one through POST /screenings, which is
      idempotent on the same key.
pull: returns specialist decisions on the caller's screenings changed after ``since``.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..core.errors import AppError
from ..models import SyncLog, User
from ..models.enums import Role, SyncOutcome
from ..repositories import ScreeningRepository
from ..schemas import SyncDecision, SyncItemResult, SyncPullResponse, SyncPushRequest
from .access import AccessPolicy
from .patients import PatientService


class SyncService:
    def __init__(self, session: Session, patients: PatientService, screenings: ScreeningRepository):
        self._session = session
        self._patients = patients
        self._screenings = screenings

    def push(self, user: User, request: SyncPushRequest, attempt: int = 1) -> list[SyncItemResult]:
        AccessPolicy.require_role(user, Role.HEALTH_WORKER)
        results = []
        for item in request.patients:
            if not item.client_uuid:
                results.append(SyncItemResult(client_uuid="", outcome=SyncOutcome.REJECTED,
                                              error="client_uuid is required for synced records."))
                continue
            try:
                patient, duplicate = self._patients.register(user, item)
                outcome = SyncOutcome.DUPLICATE if duplicate else SyncOutcome.ACCEPTED
                result = SyncItemResult(client_uuid=item.client_uuid, outcome=outcome, server_id=patient.id,
                                        code=patient.code)
            except AppError as exc:
                self._session.rollback()
                result = SyncItemResult(client_uuid=item.client_uuid, outcome=SyncOutcome.REJECTED,
                                        error=exc.message)
            self._session.add(SyncLog(user_id=user.id, client_uuid=item.client_uuid, entity_type="patient",
                                      outcome=result.outcome, attempt=attempt, error=result.error))
            self._session.commit()
            results.append(result)
        return results

    def pull(self, user: User, since: datetime | None) -> SyncPullResponse:
        AccessPolicy.require_role(user, Role.HEALTH_WORKER)
        server_time = datetime.now(timezone.utc)
        since = (since or datetime(1970, 1, 1, tzinfo=timezone.utc))
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        decisions = []
        for screening in self._screenings.changed_since(user.id, since):
            if not screening.reviews:
                continue  # nothing new from a specialist yet
            latest = screening.reviews[-1]
            decisions.append(SyncDecision(screening_id=screening.id, client_uuid=screening.client_uuid,
                                          status=screening.status, latest_action=latest.action,
                                          latest_note=latest.note, updated_at=screening.updated_at))
        return SyncPullResponse(server_time=server_time, decisions=decisions)
