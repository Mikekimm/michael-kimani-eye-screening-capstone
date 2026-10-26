"""Model card: the verified facts about one trained model, read from ``model_card.json``."""
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError


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

    @classmethod
    def load(cls, path: Path) -> "ModelCard":
        try:
            return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"Invalid model card {path}: {exc}") from exc
