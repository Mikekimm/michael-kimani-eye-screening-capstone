"""Integration tests against the real trained model (skipped if unavailable)."""
import pytest

from src.config import KERAS_MODEL_PATH
from src.service import ScreeningService
from tests.conftest import encode, make_fundus_like

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def real_service():
    pytest.importorskip("tensorflow")
    if not KERAS_MODEL_PATH.exists():
        pytest.skip("trained model file not present")
    from src.classifier import KerasClassifier

    return ScreeningService(KerasClassifier())


def test_real_model_returns_probability_in_range(real_service):
    result = real_service.screen(encode(make_fundus_like(seed=1)))
    assert 0.0 <= result.probability <= 1.0


def test_real_model_is_deterministic(real_service):
    image = encode(make_fundus_like(seed=2))
    assert real_service.screen(image).probability == real_service.screen(image).probability


def test_tflite_agrees_with_keras_model():
    """The compact on-device model must give (almost) the same score as the full model."""
    pytest.importorskip("tensorflow")
    from src.config import TFLITE_MODEL_PATH

    if not (KERAS_MODEL_PATH.exists() and TFLITE_MODEL_PATH.exists()):
        pytest.skip("both model files are required")
    from src.classifier import KerasClassifier, TFLiteClassifier
    from src.preprocessing import ImagePreprocessor

    preprocessor = ImagePreprocessor()
    keras_model, tflite_model = KerasClassifier(), TFLiteClassifier()
    for seed in range(5):
        batch = preprocessor.to_batch(make_fundus_like(seed=seed))
        assert abs(keras_model.predict_proba(batch) - tflite_model.predict_proba(batch)) < 0.05
