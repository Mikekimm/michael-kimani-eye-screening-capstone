"""Maps ORM entities to API schemas in one place, so every endpoint shows records the same way."""
from datetime import datetime, timezone

from ..ml.quality import QualityReport
from ..models import Patient, Screening
from ..schemas import ConditionResultOut, PatientOut, QualityOut, ReviewEventOut, ScreeningOut
from .pipeline import DISPLAY_NAMES
from ..ml.risk_policy import ReferralAdvisor
from .review_targets import ReviewTargets

DISCLAIMER = (
    "Screening support only, not a diagnosis. Results come from a research prototype that has not "
    "been clinically validated. A qualified eye-care professional must confirm any finding."
)


def quality_out(report: QualityReport) -> dict:
    return QualityOut(usable=report.is_usable, warnings=list(report.warnings), sharpness=report.sharpness,
                      brightness=report.brightness, contrast=report.contrast).model_dump()


def _result_order(condition: str) -> tuple[int, str]:
    """Product order (DR, glaucoma, cataract), not alphabetical; unknown conditions go last."""
    order = list(DISPLAY_NAMES)
    return (order.index(condition) if condition in order else len(order), condition)


def _review_timing(screening: Screening, targets: ReviewTargets) -> dict:
    """While a referral is open: when it was referred, its priority, when review is due and whether it is late."""
    referral = screening.referral
    if referral is None:
        return {}
    timing = {"referred_at": referral.created_at, "referral_conditions": list(referral.conditions or []),
              "assigned_to_name": referral.assigned_to.full_name if referral.assigned_to else None,
              "assigned_to_id": referral.assigned_to_id, "queued_automatically": referral.queued_automatically}
    if referral.is_open:
        timing |= {"review_priority": referral.priority.value,
                   "review_due_at": targets.due_at(referral.created_at, referral.priority),
                   "review_overdue": targets.is_overdue(referral.created_at, referral.priority, datetime.now(timezone.utc))}
    return timing


class ScreeningPresenter:
    """Turns a screening into its API shape, adding the referral advice and the review timing, which
    depend on configuration (risk policy, review targets) rather than on stored data."""

    def __init__(self, targets: ReviewTargets | None = None, advisor: ReferralAdvisor | None = None):
        self._targets = targets or ReviewTargets()
        self._advisor = advisor or ReferralAdvisor()

    def screening(self, screening: Screening, schema: type[ScreeningOut] = ScreeningOut, **extra) -> ScreeningOut:
        advice = self._advisor.advise(screening.results, bool(screening.quality.get("warnings")))
        return screening_out(screening, schema, targets=self._targets, referral_advice=advice,
                             suggested_priority=self._advisor.default_priority(screening.results).value, **extra)


def screening_out(screening: Screening, schema: type[ScreeningOut] = ScreeningOut, *,
                  targets: ReviewTargets | None = None, **extra) -> ScreeningOut:
    extra.setdefault("referral_advice", ReferralAdvisor().advise(screening.results, bool(screening.quality.get("warnings"))))
    return schema(
        id=screening.id, client_uuid=screening.client_uuid, patient_id=screening.patient_id,
        patient_code=screening.patient.code, eye=screening.eye, status=screening.status,
        patient_consent=screening.patient_consent,
        captured_at=screening.captured_at, created_at=screening.created_at, updated_at=screening.updated_at,
        created_by_name=screening.created_by.full_name,
        quality=QualityOut.model_validate(screening.quality),
        results=[ConditionResultOut.model_validate(r).model_copy(
            update={"display_name": DISPLAY_NAMES.get(r.condition, r.condition)})
            for r in sorted(screening.results, key=lambda r: _result_order(r.condition))],
        referral_reason=screening.referral.reason if screening.referral else None,
        referral_question=screening.referral.question if screening.referral else None,
        reviews=[ReviewEventOut(id=e.id, action=e.action, condition=e.condition,
                                override_positive=e.override_positive, note=e.note,
                                reviewer_name=e.reviewer.full_name, created_at=e.created_at)
                 for e in screening.reviews],
        disclaimer=DISCLAIMER,
        new_decision=screening.new_decision,
        **_review_timing(screening, targets or ReviewTargets()),
        **extra,
    )


def patient_out(patient: Patient) -> PatientOut:
    last = max((s.created_at for s in patient.screenings), default=None)
    return PatientOut.model_validate(patient).model_copy(
        update={"screening_count": len(patient.screenings), "last_screened_at": last})
