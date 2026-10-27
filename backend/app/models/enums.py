"""Enumerations shared by the ORM models, schemas and services."""
from enum import Enum


class Role(str, Enum):
    HEALTH_WORKER = "health_worker"
    SPECIALIST = "specialist"
    ADMIN = "admin"


class AccountStatus(str, Enum):
    """Public sign-ups start as PENDING until a clinic administrator checks them."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Eye(str, Enum):
    LEFT = "left"
    RIGHT = "right"


class Sex(str, Enum):
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ScreeningStatus(str, Enum):
    COMPLETED = "completed"                # result available, no referral needed
    REFERRED = "referred"                  # waiting in the specialist queue
    REVIEWED = "reviewed"                  # a specialist approved or overrode the result
    RETAKE_REQUESTED = "retake_requested"  # a specialist asked for a new photo


class ReviewAction(str, Enum):
    APPROVE = "approve"
    OVERRIDE = "override"
    REQUEST_RETAKE = "request_retake"
    COMMENT = "comment"


class ReferralReason(str, Enum):
    POSITIVE = "positive"
    UNCERTAIN = "uncertain"
    MANUAL = "manual"


class SyncOutcome(str, Enum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


def values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]
