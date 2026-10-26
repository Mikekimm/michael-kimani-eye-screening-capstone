"""Application service: orchestrates load -> quality check -> predict -> decide."""
from typing import Optional

from .classifier import BaseClassifier
from .config import DEFAULT_THRESHOLD, DEFAULT_UNCERTAINTY_MARGIN, MODEL_VERSION
from .exceptions import ImageQualityError, ScreeningError
from .preprocessing import ImagePreprocessor, ImageSource
from .quality import ImageQualityChecker
from .result import ScreeningResult


class ScreeningService:
    """Depends on abstractions, so any BaseClassifier can be injected (and stubbed in tests)."""

    def __init__(
        self,
        classifier: BaseClassifier,
        preprocessor: Optional[ImagePreprocessor] = None,
        quality_checker: Optional[ImageQualityChecker] = None,
        threshold: float = DEFAULT_THRESHOLD,
        model_version: str = MODEL_VERSION,
        uncertainty_margin: float = DEFAULT_UNCERTAINTY_MARGIN,
    ):
        if not 0.0 < threshold < 1.0:
            raise ValueError("threshold must be strictly between 0 and 1.")
        self._classifier = classifier
        self._preprocessor = preprocessor or ImagePreprocessor()
        self._quality_checker = quality_checker or ImageQualityChecker()
        self._threshold = threshold
        self._model_version = model_version
        self._uncertainty_margin = uncertainty_margin

    @property
    def threshold(self) -> float:
        return self._threshold

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def classifier_name(self) -> str:
        return self._classifier.name

    def screen(self, source: ImageSource) -> ScreeningResult:
        image = self._preprocessor.load(source)
        quality = self._quality_checker.assess(image)
        if not quality.is_usable:
            raise ImageQualityError(" ".join(quality.blocking_issues), quality)

        batch = self._preprocessor.to_batch(image)
        probability = self._classifier.predict_proba(batch)
        if not 0.0 <= probability <= 1.0:
            raise ScreeningError(f"Model returned an invalid probability: {probability!r}")

        return ScreeningResult(
            probability, self._threshold, self._model_version, quality,
            self._uncertainty_margin,
        )
