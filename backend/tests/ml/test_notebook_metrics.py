"""The DR metrics shown in the app come from the notebooks' own outputs, recomputed with the app's code."""
import csv
import json
import sys

import numpy as np

from app.core.config import REPO_ROOT
from app.ml.thresholding import metrics_at_threshold, select_threshold

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from extract_notebook_metrics import NOTEBOOK, notebook_output_text, parse  # noqa: E402

EVIDENCE = REPO_ROOT / "docs" / "models" / "evaluation" / "dr_v2"


def _read(name):
    with open(EVIDENCE / name, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return np.array([int(r["label"]) for r in rows]), np.array([float(r["prob"]) for r in rows])


def test_v1_history_values_come_from_the_v1_notebook_outputs():
    m = parse(notebook_output_text(NOTEBOOK))
    assert (m["accuracy"], m["precision"], m["sensitivity"], m["f1"], m["specificity"]) == (0.790, 0.920, 0.542, 0.682, 0.97)
    assert m["negatives"] + m["positives"] == 47234


def test_v2_threshold_is_chosen_on_validation_and_metrics_recompute_from_test_predictions():
    card = json.loads((REPO_ROOT / "models" / "dr" / "model_card.json").read_text(encoding="utf-8"))
    threshold = select_threshold(*_read("val_predictions.csv"), 0.85).threshold
    assert threshold == card["threshold"]
    point = metrics_at_threshold(*_read("test_predictions.csv"), threshold)
    assert (point.sensitivity, point.specificity, point.precision) == (
        card["metrics"]["sensitivity"], card["metrics"]["specificity"], card["metrics"]["precision"])


def test_card_and_metrics_file_agree_and_carry_the_honesty_label():
    card = json.loads((REPO_ROOT / "models" / "dr" / "model_card.json").read_text(encoding="utf-8"))
    report = json.loads((REPO_ROOT / "docs" / "models" / "metrics.json").read_text(encoding="utf-8"))
    assert card["version"] == report["model_version"]
    assert card["metrics"]["sensitivity"] == report["metrics"]["sensitivity"]
    for phrase in ("held-out test split by image", "near-duplicates could not be excluded",
                   "not external validation", "not clinically validated", "below the 80% specificity target"):
        assert phrase in card["metrics_status"]
    assert report["targets"] == {"sensitivity": 0.85, "specificity": 0.8, "sensitivity_met": True, "specificity_met": False}
