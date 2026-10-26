"""Audit trail writer. Records who did what to which id; never stores images or patient fields."""
from ..models import AuditEvent
from ..repositories import AuditRepository


class AuditService:
    def __init__(self, audit: AuditRepository):
        self._audit = audit

    def record(self, actor_id: str | None, action: str, entity_type: str | None = None,
               entity_id: str | None = None) -> None:
        self._audit.add(AuditEvent(actor_id=actor_id, action=action, entity_type=entity_type,
                                   entity_id=entity_id))
