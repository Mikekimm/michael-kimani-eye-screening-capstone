"""Patient registration and lookup, scoped by role through AccessPolicy."""
from collections.abc import Sequence

from sqlalchemy.orm import Session

from ..core.errors import ConflictError
from ..models import Patient, User
from ..models.enums import Role
from ..repositories import PatientRepository
from ..schemas import PatientCreate
from .access import AccessPolicy
from .audit import AuditService


class PatientService:
    def __init__(self, session: Session, patients: PatientRepository, access: AccessPolicy, audit: AuditService):
        self._session = session
        self._patients = patients
        self._access = access
        self._audit = audit

    def register(self, user: User, request: PatientCreate) -> tuple[Patient, bool]:
        """Returns (patient, duplicate). Idempotent when the device supplies a client_uuid."""
        AccessPolicy.require_role(user, Role.HEALTH_WORKER)
        if request.client_uuid:
            existing = self._patients.by_client_uuid(request.client_uuid)
            if existing is not None:
                if existing.created_by_id != user.id:
                    raise ConflictError("This client_uuid is already used by another record.")
                return existing, True
        if self._patients.by_code(request.code):
            raise ConflictError(f"Patient code '{request.code}' is already registered.")
        patient = self._patients.add(Patient(**request.model_dump(), created_by_id=user.id))
        self._audit.record(user.id, "patient.created", "patient", patient.id)
        self._session.commit()
        self._session.refresh(patient)
        return patient, False

    def search(self, user: User, query: str | None) -> Sequence[Patient]:
        AccessPolicy.require_role(user, Role.HEALTH_WORKER)
        return self._patients.search(query, created_by_id=user.id)

    def get(self, user: User, patient_id: str) -> Patient:
        return self._access.check_patient(user, self._patients.get(patient_id))
