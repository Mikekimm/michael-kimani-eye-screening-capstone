from fastapi import APIRouter

from ...schemas import ModelInfoOut
from ...services.pipeline import DISPLAY_NAMES
from ..deps import Container, CurrentUser

router = APIRouter(tags=["system"])


@router.get("/health")
def health(container: Container):
    return {"status": "ok", "models_available": [s.condition for s in container.registry.statuses() if s.available]}


@router.get("/models", response_model=list[ModelInfoOut])
def models(_user: CurrentUser, container: Container):
    """What each condition model is, whether it is loaded, and its verified facts and limits."""
    infos = []
    for status in container.registry.statuses():
        card = status.card
        info = ModelInfoOut(condition=status.condition, display_name=DISPLAY_NAMES.get(status.condition, status.condition),
                            available=status.available, status_reason=status.reason)
        if card is not None:
            policy = container.policies.for_condition(status.condition, card.threshold)
            info = info.model_copy(update={
                "display_name": card.display_name, "version": card.version, "threshold": card.threshold,
                "threshold_source": card.threshold_source, "uncertainty_margin": policy.uncertainty_margin,
                "input": card.input, "labels": card.labels, "architecture": card.architecture,
                "training": card.training, "metrics": card.metrics, "metrics_status": card.metrics_status,
                "limitations": card.limitations,
            })
        infos.append(info)
    return infos
