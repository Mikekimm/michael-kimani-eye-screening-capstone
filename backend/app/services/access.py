"""AccessPolicy: the single place that decides who may see which clinical record.

health_worker -> patients and screenings they created
specialist    -> patients and screenings that were referred for review
admin         -> user management and aggregate analytics only, no patient-level data
"""
from ..core.errors import NotFoundError, PermissionDeniedError
from ..models import Patient, Screening, User
from ..models.enums import Role
from ..repositories import PatientRepository


class AccessPolicy:
    def __init__(self, patients: PatientRepository):
        self._patients = patients

    def check_patient(self, user: User, patient: Patient | None) -> Patient:
        if patient is None:
            raise NotFoundError("Patient not found.")
        if user.role == Role.HEALTH_WORKER and patient.created_by_id == user.id:
            return patient
        if user.role == Role.SPECIALIST and self._patients.has_referred_screening(patient.id):
            return patient
        # Same message as "not found" so record ids cannot be probed.
        raise NotFoundError("Patient not found.")

    def check_screening(self, user: User, screening: Screening | None) -> Screening:
        if screening is None or screening.discarded_at is not None:
            raise NotFoundError("Screening not found.")
        if user.role == Role.HEALTH_WORKER and screening.created_by_id == user.id:
            return screening
        if user.role == Role.SPECIALIST and screening.referral is not None:
            return screening
        raise NotFoundError("Screening not found.")

    @staticmethod
    def require_role(user: User, *roles: Role) -> None:
        if user.role not in roles:
            raise PermissionDeniedError("Your role does not allow this action.")
