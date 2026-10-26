"""The DR metrics shown in the app are parsed from the training notebook's own outputs."""
import json
import sys

from app.core.config import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from extract_notebook_metrics import NOTEBOOK, notebook_output_text, parse  # noqa: E402


def test_values_come_from_the_notebook_outputs():
    m = parse(notebook_output_text(NOTEBOOK))
    assert (m["accuracy"], m["precision"], m["sensitivity"], m["f1"], m["specificity"]) == (0.790, 0.920, 0.542, 0.682, 0.97)
    assert m["negatives"] + m["positives"] == 47234


def test_model_card_and_metrics_file_agree_and_are_labelled_as_validation():
    card = json.loads((REPO_ROOT / "models" / "dr" / "model_card.json").read_text(encoding="utf-8"))
    report = json.loads((REPO_ROOT / "docs" / "metrics.json").read_text(encoding="utf-8"))
    assert card["metrics"]["sensitivity"] == report["metrics"]["sensitivity"]
    assert "not an independent hold-out" in card["metrics_status"]
    assert "test" not in card["metrics_status"].lower()
    assert report["targets"]["sensitivity_met"] is False
