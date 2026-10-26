"""The served LiteRT model must agree with the full Keras model it was exported from.

The .tflite file is about 2.6 MB versus roughly 9 MB for a float32 MobileNetV2, which indicates a
quantized export, so scores differ slightly. Measured on these synthetic inputs: up to 0.034.
The tolerance (0.05) is the one used since the MVP; the Kaggle hold-out run reports the maximum
difference over the full validation fold (docs/evaluation/holdout_run_info.json).
"""
import pytest

from app.ml.config import KERAS_MODEL_PATH, MODEL_DIR
from app.ml.preprocessing import ImagePreprocessor
from app.ml.registry import ModelRegistry
from tests.conftest import make_fundus_like

pytestmark = pytest.mark.integration


def test_litert_model_agrees_with_keras_model():
    tf = pytest.importorskip("tensorflow")
    if not KERAS_MODEL_PATH.exists():
        pytest.skip("models/dr/model.h5 not present")
    keras_model = tf.keras.models.load_model(KERAS_MODEL_PATH, compile=False)
    served = ModelRegistry(("dr",)).discover(MODEL_DIR).get("dr")
    assert served is not None and served.runtime == "ai_edge_litert"

    preprocessor = ImagePreprocessor()
    for seed in range(5):
        batch = preprocessor.to_batch(make_fundus_like(seed=seed))
        keras_score = float(keras_model.predict(batch, verbose=0).reshape(-1)[0])
        assert abs(keras_score - served.predict_proba(batch)) < 0.05
