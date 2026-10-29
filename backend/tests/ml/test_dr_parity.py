"""The app's own pipeline must reproduce the scores the training notebook gave 24 test photos.

Scores: docs/models/evaluation/dr_v2/parity.csv (committed). Photos: dr_v2_results.zip -> incoming/dr_v2/parity/
(dataset images are never committed, so this test skips when they are absent, e.g. in CI).
Tolerance: 0.03 on the score and no change in any screening decision. TensorFlow and Pillow decode
JPEGs slightly differently, so exact equality is not expected; measured max difference 0.021.
"""
import csv

import pytest

from app.core.config import REPO_ROOT
from app.ml.preprocessing import ImagePreprocessor
from app.ml.registry import ModelRegistry

PHOTOS = REPO_ROOT / "incoming" / "dr_v2" / "parity"
SCORES = REPO_ROOT / "docs" / "models" / "evaluation" / "dr_v2" / "parity.csv"
TOLERANCE = 0.03


@pytest.mark.skipif(not PHOTOS.exists(), reason="parity photos not present (unzip dr_v2_results.zip into incoming/dr_v2)")
def test_app_pipeline_reproduces_notebook_scores():
    model = ModelRegistry(("dr",)).discover(REPO_ROOT / "models").get("dr")
    preprocessor = ImagePreprocessor(interpolation=model.card.interpolation)
    with open(SCORES, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 24
    for row in rows:
        image = preprocessor.load((PHOTOS / row["file"]).read_bytes())
        ours, notebook = model.predict_proba(preprocessor.to_batch(image)), float(row["tflite_score"])
        assert abs(ours - notebook) < TOLERANCE, row["file"]
        assert (ours >= model.card.threshold) == (notebook >= model.card.threshold), row["file"]
