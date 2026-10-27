"""The served LiteRT model must agree with the Keras model it was exported from (DR v2, float32 export).

The notebook measured a maximum difference of 9.8e-06 on its validation images; on these synthetic
inputs the tolerance is 1e-3, far below anything that could change a screening decision.
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
        pytest.skip(f"{KERAS_MODEL_PATH.name} not present")
    keras_model = tf.keras.models.load_model(KERAS_MODEL_PATH, compile=False)
    served = ModelRegistry(("dr",)).discover(MODEL_DIR).get("dr")
    assert served is not None and served.runtime == "ai_edge_litert"

    preprocessor = ImagePreprocessor(interpolation=served.card.interpolation)
    for seed in range(5):
        batch = preprocessor.to_batch(make_fundus_like(seed=seed))
        keras_score = float(keras_model.predict(batch, verbose=0).reshape(-1)[0])
        assert abs(keras_score - served.predict_proba(batch)) < 1e-3
