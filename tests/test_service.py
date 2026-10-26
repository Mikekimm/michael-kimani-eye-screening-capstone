import pytest
from PIL import Image

from src.classifier import BaseClassifier
from src.exceptions import ImageQualityError, InvalidImageError, ScreeningError
from src.service import ScreeningService
from tests.conftest import encode


class StubClassifier(BaseClassifier):
    """Returns a fixed probability and records the batch it received."""

    def __init__(self, probability):
        self.probability = probability
        self.last_batch = None

    @property
    def name(self):
        return "stub"

    def predict_proba(self, batch):
        self.last_batch = batch
        return self.probability


def test_flagged_when_probability_above_threshold(fundus_png):
    result = ScreeningService(StubClassifier(0.8), threshold=0.5).screen(fundus_png)
    assert result.dr_detected
    assert "refer" in result.recommendation.lower()


def test_clear_when_probability_below_threshold(fundus_png):
    result = ScreeningService(StubClassifier(0.2), threshold=0.5).screen(fundus_png)
    assert not result.dr_detected
    assert "routine" in result.recommendation.lower()


def test_probability_equal_to_threshold_is_flagged(fundus_png):
    assert ScreeningService(StubClassifier(0.3), threshold=0.3).screen(fundus_png).dr_detected


def test_lower_threshold_flags_more_cases(fundus_png):
    strict = ScreeningService(StubClassifier(0.4), threshold=0.5).screen(fundus_png)
    sensitive = ScreeningService(StubClassifier(0.4), threshold=0.3).screen(fundus_png)
    assert not strict.dr_detected and sensitive.dr_detected


def test_classifier_receives_correctly_shaped_batch(fundus_png):
    stub = StubClassifier(0.5)
    ScreeningService(stub).screen(fundus_png)
    assert stub.last_batch.shape == (1, 224, 224, 3)


@pytest.mark.parametrize("fmt", ["PNG", "JPEG"])
def test_accepts_png_and_jpeg(fundus_image, fmt):
    assert ScreeningService(StubClassifier(0.5)).screen(encode(fundus_image, fmt)) is not None


def test_accepts_grayscale_and_rgba(fundus_image):
    service = ScreeningService(StubClassifier(0.5))
    assert service.screen(encode(fundus_image.convert("L"))) is not None
    assert service.screen(encode(fundus_image.convert("RGBA"))) is not None


def test_corrupt_bytes_raise_invalid_image_error():
    with pytest.raises(InvalidImageError):
        ScreeningService(StubClassifier(0.5)).screen(b"definitely not an image")


def test_blank_image_raises_quality_error_with_report():
    blank = encode(Image.new("RGB", (300, 300), (90, 90, 90)))
    with pytest.raises(ImageQualityError) as info:
        ScreeningService(StubClassifier(0.5)).screen(blank)
    assert info.value.report is not None and not info.value.report.is_usable


def test_classifier_not_called_for_unusable_image():
    stub = StubClassifier(0.5)
    with pytest.raises(ImageQualityError):
        ScreeningService(stub).screen(encode(Image.new("RGB", (300, 300), (90, 90, 90))))
    assert stub.last_batch is None


@pytest.mark.parametrize("bad_probability", [-0.1, 1.2, float("nan")])
def test_invalid_model_output_is_rejected(fundus_png, bad_probability):
    with pytest.raises(ScreeningError):
        ScreeningService(StubClassifier(bad_probability)).screen(fundus_png)


@pytest.mark.parametrize("threshold", [0.0, 1.0, -1, 2])
def test_invalid_threshold_rejected(threshold):
    with pytest.raises(ValueError):
        ScreeningService(StubClassifier(0.5), threshold=threshold)


def test_result_carries_model_version_and_threshold(fundus_png):
    result = ScreeningService(StubClassifier(0.5), threshold=0.4, model_version="v-test").screen(fundus_png)
    assert result.model_version == "v-test" and result.threshold == 0.4
