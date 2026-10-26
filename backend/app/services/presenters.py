"""Maps ORM entities to API schemas in one place, so every endpoint shows records the same way."""
from ..ml.quality import QualityReport
from ..models import Patient, Screening
from ..schemas import ConditionResultOut, PatientOut, QualityOut, ReviewEventOut, ScreeningOut
from .pipeline import DISPLAY_NAMES

DISCLAIMER = (
    "Screening support only, not a diagnosis. Results come from a research prototype that has not "
    "been clinically validated. A qualified eye-care professional must confirm any finding."
)


def quality_out(report: QualityReport) -> dict:
    return QualityOut(usable=report.is_usable, warnings=list(report.warnings), sharpness=report.sharpness,
                      brightness=report.brightness, contrast=report.contrast).model_dump()


def screening_out(screening: Screening, schema: type[ScreeningOut] = ScreeningOut, **extra) -> ScreeningOut:
    return schema(
        id=screening.id, client_uuid=screening.client_uuid, patient_id=screening.patient_id,
        patient_code=screening.patient.code, eye=screening.eye, status=screening.status,
        captured_at=screening.captured_at, created_at=screening.created_at, updated_at=screening.updated_at,
        created_by_name=screening.created_by.full_name,
        quality=QualityOut.model_validate(screening.quality),
        results=[ConditionResultOut.model_validate(r).model_copy(
            update={"display_name": DISPLAY_NAMES.get(r.condition, r.condition)}) for r in screening.results],
        referral_reason=screening.referral.reason if screening.referral else None,
        reviews=[ReviewEventOut(id=e.id, action=e.action, condition=e.condition,
                                override_positive=e.override_positive, note=e.note,
                                reviewer_name=e.reviewer.full_name, created_at=e.created_at)
                 for e in screening.reviews],
        disclaimer=DISCLAIMER,
        **extra,
    )


def patient_out(patient: Patient) -> PatientOut:
    last = max((s.created_at for s in patient.screenings), default=None)
    return PatientOut.model_validate(patient).model_copy(
        update={"screening_count": len(patient.screenings), "last_screened_at": last})
