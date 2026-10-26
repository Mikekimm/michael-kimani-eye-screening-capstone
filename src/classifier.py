"""Model back-ends behind one interface (polymorphism).

TensorFlow is imported lazily so that the rest of the package, and its unit
tests, work without TensorFlow installed.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

import numpy as np

from .config import KERAS_MODEL_PATH, TFLITE_MODEL_PATH
from .exceptions import ModelNotAvailableError


class BaseClassifier(ABC):
    """Contract every model back-end must satisfy."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier shown in the UI and logs."""

    def warm_up(self) -> None:
        """Load the model eagerly. Raises ModelNotAvailableError on failure."""

    @abstractmethod
    def predict_proba(self, batch: np.ndarray) -> float:
        """Return P(DR present) in [0, 1] for a batch of shape (1, H, W, 3)."""


def _import_tensorflow():
    try:
        import tensorflow as tf  # noqa: WPS433 (deliberately lazy)
    except ImportError as exc:
        raise ModelNotAvailableError("TensorFlow is not installed.") from exc
    return tf


class KerasClassifier(BaseClassifier):
    """Runs the full Keras (.h5) model."""

    def __init__(self, model_path: Path = KERAS_MODEL_PATH):
        self._path = Path(model_path)
        self._model = None

    @property
    def name(self) -> str:
        return f"keras:{self._path.name}"

    def warm_up(self) -> None:
        if self._model is not None:
            return
        if not self._path.exists():
            raise ModelNotAvailableError(f"Model file not found: {self._path}")
        tf = _import_tensorflow()
        try:
            self._model = tf.keras.models.load_model(self._path, compile=False)
        except Exception as exc:  # corrupt or incompatible file
            raise ModelNotAvailableError(f"Could not load {self._path.name}: {exc}") from exc

    def predict_proba(self, batch: np.ndarray) -> float:
        self.warm_up()
        output = self._model.predict(batch, verbose=0)
        return float(np.asarray(output).reshape(-1)[0])


class TFLiteClassifier(BaseClassifier):
    """Runs the compact TensorFlow Lite model used for on-device inference."""

    def __init__(self, model_path: Path = TFLITE_MODEL_PATH):
        self._path = Path(model_path)
        self._interpreter = None
        self._input_index = None
        self._output_index = None

    @property
    def name(self) -> str:
        return f"tflite:{self._path.name}"

    def warm_up(self) -> None:
        if self._interpreter is not None:
            return
        if not self._path.exists():
            raise ModelNotAvailableError(f"Model file not found: {self._path}")
        tf = _import_tensorflow()
        try:
            interpreter = tf.lite.Interpreter(model_path=str(self._path))
            interpreter.allocate_tensors()
        except Exception as exc:
            raise ModelNotAvailableError(f"Could not load {self._path.name}: {exc}") from exc
        self._input_index = interpreter.get_input_details()[0]["index"]
        self._output_index = interpreter.get_output_details()[0]["index"]
        self._interpreter = interpreter

    def predict_proba(self, batch: np.ndarray) -> float:
        self.warm_up()
        self._interpreter.set_tensor(self._input_index, batch.astype(np.float32))
        self._interpreter.invoke()
        output = self._interpreter.get_tensor(self._output_index)
        return float(np.asarray(output).reshape(-1)[0])


_BACKENDS = {"keras": KerasClassifier, "tflite": TFLiteClassifier}


def load_classifier(preference: Sequence[str] = ("keras", "tflite")) -> BaseClassifier:
    """Factory: return the first back-end in ``preference`` that loads."""
    errors = []
    for key in preference:
        try:
            backend = _BACKENDS[key]()
        except KeyError:
            raise ValueError(f"Unknown back-end: {key!r}") from None
        try:
            backend.warm_up()
            return backend
        except ModelNotAvailableError as exc:
            errors.append(f"{key}: {exc}")
    raise ModelNotAvailableError("No model could be loaded. " + " | ".join(errors))
