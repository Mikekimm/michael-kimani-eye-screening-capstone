"""ModelRegistry: discovers trained models on disk and registers only the valid ones.

Layout scanned:  models/<condition>/model.tflite + models/<condition>/model_card.json

A model is registered only if the card parses, the card's condition matches its folder, the
file's SHA-256 matches the card (catches a truncated download or a swapped file), and the
runtime loads it. Anything else is recorded as unavailable *with the reason*, so the API can
say "model not available yet" honestly instead of failing or inventing a result.
Dropping a valid folder into models/glaucoma/ or models/cataract/ needs no code change.
"""
import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .condition_model import ConditionModel, TFLiteConditionModel
from .exceptions import ModelNotAvailableError
from .model_card import ModelCard

logger = logging.getLogger(__name__)

CARD_FILE = "model_card.json"
ModelLoader = Callable[[ModelCard, Path], ConditionModel]


@dataclass(frozen=True)
class ModelStatus:
    condition: str
    available: bool
    reason: str
    card: ModelCard | None = None


def sha256_of(path: Path, chunk_size: int = 1 << 20) -> str:
    """Stream the file in 1 MiB chunks so large models never load fully into memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ModelRegistry:
    def __init__(self, conditions: tuple[str, ...], loader: ModelLoader = TFLiteConditionModel):
        self._conditions = tuple(conditions)
        self._loader = loader
        self._models: dict[str, ConditionModel] = {}
        self._statuses: dict[str, ModelStatus] = {
            c: ModelStatus(c, False, "No model folder found.") for c in self._conditions
        }

    @property
    def conditions(self) -> tuple[str, ...]:
        return self._conditions

    def discover(self, models_dir: Path) -> "ModelRegistry":
        for condition in self._conditions:
            self._statuses[condition] = self._try_register(condition, Path(models_dir) / condition)
        return self

    def _try_register(self, condition: str, folder: Path) -> ModelStatus:
        card_path = folder / CARD_FILE
        if not card_path.exists():
            return ModelStatus(condition, False, "Model not available yet (no trained model has been added).")
        try:
            card = ModelCard.load(card_path)
        except ValueError as exc:
            return self._reject(condition, f"Model card is invalid: {exc}")
        if card.condition != condition:
            return self._reject(condition, f"Model card says '{card.condition}' but folder is '{condition}'.", card)
        model_path = folder / card.file
        if not model_path.exists():
            return self._reject(condition, f"Model file {card.file} is missing.", card)
        actual = sha256_of(model_path)
        if actual != card.sha256:
            return self._reject(condition, "Model file checksum does not match its model card.", card)
        try:
            self._models[condition] = self._loader(card, model_path)
        except ModelNotAvailableError as exc:
            return self._reject(condition, str(exc), card)
        logger.info("Registered %s model %s", condition, card.version)
        return ModelStatus(condition, True, "Model loaded and checksum verified.", card)

    @staticmethod
    def _reject(condition: str, reason: str, card: ModelCard | None = None) -> ModelStatus:
        logger.warning("Model for %s not registered: %s", condition, reason)
        return ModelStatus(condition, False, reason, card)

    def get(self, condition: str) -> ConditionModel | None:
        return self._models.get(condition)

    def status(self, condition: str) -> ModelStatus:
        return self._statuses[condition]

    def statuses(self) -> list[ModelStatus]:
        return [self._statuses[c] for c in self._conditions]
