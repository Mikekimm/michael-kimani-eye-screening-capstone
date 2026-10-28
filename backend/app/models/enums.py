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
    COMPLETED = "completed"                # result available; the health worker decides whether to ask a specialist
    REFERRED = "referred"                  # sent by the health worker; waiting in the specialist queue
    REVIEWED = "reviewed"                  # a specialist approved or overrode the result
    RETAKE_REQUESTED = "retake_requested"  # a specialist asked for a new photo


class ReviewAction(str, Enum):
    APPROVE = "approve"
    OVERRIDE = "override"
    REQUEST_RETAKE = "request_retake"
    COMMENT = "comment"


class Specialty(str, Enum):
    """What a specialist reviews. GENERAL matches every case. An extension beyond the proposal, which has a
    single Specialist role."""
    DR = "dr"
    GLAUCOMA = "glaucoma"
    CATARACT = "cataract"
    GENERAL = "general"


class ReviewPriority(str, Enum):
    """Chosen by the health worker when asking a specialist; sets the review target (24 h / 72 h)."""
    URGENT = "urgent"
    ROUTINE = "routine"


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


class ReferralAdvice(str, Enum):
    """What the app recommends after a result; the risk policy says which of these are queued automatically."""
    NONE = "none"                # "No referral needed"
    CONSIDER = "consider"        # "Uncertain, consider asking a specialist" (borderline or low-quality photo)
    RECOMMENDED = "recommended"  # "Refer recommended" (a model detected signs)
