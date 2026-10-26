"""ScreeningPipeline: upload validation -> decode -> quality gate -> every available model -> RiskPolicy.

Pure ML orchestration with no database access, so it is unit-testable with the real model and
reusable from scripts (e.g. the benchmark). Conditions without a registered model produce an
explicit "model not available yet" outcome instead of a guessed score.
"""
import hashlib
import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from ..core.errors import PayloadTooLargeError, UnprocessableImageError
from ..ml.exceptions import InvalidImageError
from ..ml.preprocessing import ImagePreprocessor
from ..ml.quality import ImageQualityChecker, QualityReport
from ..ml.registry import ModelRegistry
from ..ml.risk_policy import RiskAssessment, RiskPolicyFactory

NOT_AVAILABLE = "Model not available yet. No result is given for this condition."
_FORMAT_TO_TYPE = {"JPEG": "image/jpeg", "PNG": "image/png"}


@dataclass(frozen=True)
class ConditionOutcome:
    condition: str
    display_name: str
    model_available: bool
    model_version: str | None = None
    probability: float | None = None
    threshold: float | None = None
    assessment: RiskAssessment | None = None

    @property
    def recommendation(self) -> str:
        return self.assessment.recommendation if self.assessment else NOT_AVAILABLE


@dataclass(frozen=True)
class PipelineOutcome:
    image_sha256: str
    image_format: str
    quality: QualityReport
    conditions: list[ConditionOutcome]


DISPLAY_NAMES = {"dr": "Diabetic retinopathy", "glaucoma": "Glaucoma", "cataract": "Cataract"}


class ScreeningPipeline:
    def __init__(self, registry: ModelRegistry, policies: RiskPolicyFactory, max_upload_bytes: int,
                 allowed_types: tuple[str, ...], quality_checker: ImageQualityChecker | None = None):
        self._registry = registry
        self._policies = policies
        self._max_upload_bytes = max_upload_bytes
        self._allowed_types = allowed_types
        self._quality_checker = quality_checker or ImageQualityChecker()
        self._preprocessors: dict[tuple[int, int], ImagePreprocessor] = {}

    def validate_upload(self, content_type: str | None, data: bytes) -> Image.Image:
        """Checks the declared type, the size, and that the bytes really decode as JPEG/PNG."""
        if not data:
            raise UnprocessableImageError("The uploaded file is empty.")
        if len(data) > self._max_upload_bytes:
            limit_mb = self._max_upload_bytes // (1024 * 1024)
            raise PayloadTooLargeError(f"The image is larger than the {limit_mb} MB limit.")
        if content_type not in self._allowed_types:
            raise UnprocessableImageError("Only JPEG or PNG photos are accepted.")
        try:
            with Image.open(io.BytesIO(data)) as probe:
                actual_format = probe.format
        except (UnidentifiedImageError, OSError):
            raise UnprocessableImageError("The file could not be read as an image.") from None
        if _FORMAT_TO_TYPE.get(actual_format) not in self._allowed_types:
            raise UnprocessableImageError("The file content is not a JPEG or PNG image.")
        try:
            return ImagePreprocessor().load(data)
        except InvalidImageError as exc:
            raise UnprocessableImageError(str(exc)) from None

    def run(self, content_type: str | None, data: bytes) -> PipelineOutcome:
        image = self.validate_upload(content_type, data)
        quality = self._quality_checker.assess(image)
        if not quality.is_usable:
            raise UnprocessableImageError(
                "This photo cannot be screened: " + " ".join(quality.blocking_issues) + " Please retake it.",
                details={"blocking_issues": list(quality.blocking_issues)},
            )
        outcomes = [self._score(condition, image) for condition in self._registry.conditions]
        with Image.open(io.BytesIO(data)) as probe:
            image_format = probe.format or "JPEG"
        return PipelineOutcome(hashlib.sha256(data).hexdigest(), image_format, quality, outcomes)

    def _score(self, condition: str, image: Image.Image) -> ConditionOutcome:
        display = DISPLAY_NAMES.get(condition, condition.title())
        model = self._registry.get(condition)
        if model is None:
            return ConditionOutcome(condition, display, model_available=False)
        size = getattr(model, "input_size", (224, 224))
        preprocessor = self._preprocessors.setdefault(size, ImagePreprocessor(target_size=size))
        probability = model.predict_proba(preprocessor.to_batch(image))
        if not 0.0 <= probability <= 1.0:
            raise RuntimeError(f"{condition} model returned an invalid score {probability!r}")
        threshold = model.card.threshold
        assessment = self._policies.for_condition(condition, threshold).assess(probability)
        return ConditionOutcome(condition, model.card.display_name or display, True,
                                model.version, probability, threshold, assessment)
