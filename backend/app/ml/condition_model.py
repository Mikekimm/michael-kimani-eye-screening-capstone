"""ConditionModel abstraction: one trained model that scores one eye condition.

The API depends on this interface only, so a new condition (glaucoma, cataract) or a new
runtime can be added without touching the screening service (open/closed principle).
"""
from abc import ABC, abstractmethod
from pathlib import Path
from threading import Lock

import numpy as np

from .exceptions import ModelNotAvailableError
from .model_card import ModelCard


class ConditionModel(ABC):
    """Contract for a per-condition classifier returning P(condition present)."""

    def __init__(self, card: ModelCard):
        self._card = card

    @property
    def card(self) -> ModelCard:
        return self._card

    @property
    def condition(self) -> str:
        return self._card.condition

    @property
    def version(self) -> str:
        return self._card.version

    @abstractmethod
    def predict_proba(self, batch: np.ndarray) -> float:
        """Score a preprocessed batch of shape (1, H, W, 3)."""


def _load_interpreter_class():
    """Prefer Google's LiteRT runtime; fall back to TensorFlow's bundled interpreter."""
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:  # pragma: no cover - only when ai-edge-litert is missing
        try:
            from tensorflow.lite import Interpreter  # type: ignore[no-redef]
        except ImportError as exc:
            raise ModelNotAvailableError("No TFLite runtime installed (ai-edge-litert).") from exc
    return Interpreter


class TFLiteConditionModel(ConditionModel):
    """Runs a .tflite file. The interpreter is not thread-safe, so calls are serialised."""

    def __init__(self, card: ModelCard, model_path: Path):
        super().__init__(card)
        try:
            self._interpreter = _load_interpreter_class()(model_path=str(model_path))
            self._interpreter.allocate_tensors()
        except ModelNotAvailableError:
            raise
        except Exception as exc:
            raise ModelNotAvailableError(f"Could not load {model_path.name}: {exc}") from exc
        input_detail = self._interpreter.get_input_details()[0]
        self._input_index = input_detail["index"]
        self._input_shape = tuple(int(dim) for dim in input_detail["shape"])
        self._output_index = self._interpreter.get_output_details()[0]["index"]
        self._lock = Lock()
        if list(self._input_shape) != list(card.input_shape):
            raise ModelNotAvailableError(
                f"Model input {self._input_shape} does not match model card {tuple(card.input_shape)}.")

    @property
    def runtime(self) -> str:
        """Which interpreter is in use (ai_edge_litert or the TensorFlow fallback)."""
        return type(self._interpreter).__module__.split(".")[0]

    @property
    def input_size(self) -> tuple[int, int]:
        return self._input_shape[2], self._input_shape[1]  # (width, height) for PIL

    def predict_proba(self, batch: np.ndarray) -> float:
        with self._lock:
            self._interpreter.set_tensor(self._input_index, batch.astype(np.float32))
            self._interpreter.invoke()
            output = self._interpreter.get_tensor(self._output_index)
        return float(np.asarray(output).reshape(-1)[0])
