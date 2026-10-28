"""Model card: the verified facts about one trained model, read from ``model_card.json``."""
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator

RESIZE_METHODS = ("nearest", "bilinear", "bicubic")


class ModelCard(BaseModel):
    condition: str
    display_name: str
    version: str
    file: str = "model.tflite"
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    task: str = "binary"
    labels: dict[str, str]
    input: dict[str, Any]
    output: dict[str, Any] = {}
    threshold: float = Field(gt=0.0, lt=1.0)
    threshold_source: str = ""
    architecture: str = ""
    training: dict[str, Any] = {}
    metrics: dict[str, Any] | None = None
    metrics_status: str = "not yet measured"
    limitations: list[str] = []

    @property
    def input_shape(self) -> list[int]:
        return list(self.input["shape"])

    @property
    def interpolation(self) -> str:
        """The resize the model was trained with: ``input.interpolation``, or the first method named in
        the free-text ``input.resize``. A card that names none is rejected rather than guessed."""
        explicit = self.input.get("interpolation")
        if explicit in RESIZE_METHODS:
            return explicit
        text = str(self.input.get("resize", "")).lower()
        found = [m for m in RESIZE_METHODS if m in text]
        if not found:
            raise ValueError(f"model card input must name a resize method {RESIZE_METHODS}")
        return min(found, key=text.index)

    @model_validator(mode="after")
    def _check_interpolation(self) -> "ModelCard":
        self.interpolation  # noqa: B018 - raises if the card does not say how to resize
        return self

    @classmethod
    def load(cls, path: Path) -> "ModelCard":
        try:
            return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"Invalid model card {path}: {exc}") from exc
