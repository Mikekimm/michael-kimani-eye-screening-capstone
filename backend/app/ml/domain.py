"""Domain types and validation shared by storage, sync and the API.

The records deliberately keep the fields the supervisor asked for: which eye
(laterality), which model version produced the score, and the full review history.
Patients are identified only by a pseudonymous reference, never by name or date of
birth, which keeps the prototype's data minimal.
"""
import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional

from .exceptions import RecordValidationError


class Laterality(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    UNKNOWN = "unknown"


class SyncStatus(str, Enum):
    PENDING = "pending"   # saved on the device, not yet accepted by the server
    SYNCED = "synced"
    FAILED = "failed"     # the server permanently rejected it


class ReviewDecision(str, Enum):
    APPROVE = "approve"                      # agrees with the screening outcome
    OVERRIDE_DR_PRESENT = "override_dr_present"
    OVERRIDE_NO_DR = "override_no_dr"
    UNGRADABLE = "ungradable"                # image unusable: retake the photo


class Role(str, Enum):
    CLINICIAN = "clinician"   # primary health centre worker
    SPECIALIST = "specialist"  # ophthalmologist reviewing referred cases
    ADMIN = "admin"           # views aggregate statistics


_PATIENT_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,39}$")
MAX_NOTES_LENGTH = 2000


def validate_patient_ref(value: str) -> str:
    """Accept only short pseudonymous codes (letters, digits, - and _)."""
    if not isinstance(value, str) or not _PATIENT_REF.match(value):
        raise RecordValidationError(
            "Patient reference must be 3-40 characters: letters, digits, '-' or '_' "
            "(use a code, not the patient's name)."
        )
    return value


def parse_enum(enum_cls, value, field: str):
    try:
        return enum_cls(value)
    except ValueError:
        allowed = ", ".join(member.value for member in enum_cls)
        raise RecordValidationError(f"{field} must be one of: {allowed}.") from None


@dataclass(frozen=True)
class ScreeningRecord:
    id: str
    created_at: str
    patient_ref: str
    laterality: Laterality
    image_sha256: str
    image_path: str
    model_version: str
    classifier_name: str
    threshold: float
    probability: float
    dr_detected: bool
    needs_review: bool
    quality_json: str
    created_by: str
    sync_status: SyncStatus
    sync_attempts: int = 0
    last_sync_error: Optional[str] = None
    synced_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["laterality"] = self.laterality.value
        data["sync_status"] = self.sync_status.value
        return data


@dataclass(frozen=True)
class ReviewRecord:
    id: int
    screening_id: str
    reviewer: str
    decision: ReviewDecision
    notes: str
    reviewed_at: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["decision"] = self.decision.value
        return data
