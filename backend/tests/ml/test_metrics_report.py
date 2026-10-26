"""The metrics pipeline: CSV of predictions -> docs/metrics.json -> model card served by the API.

Uses SYNTHETIC predictions to exercise the code path only; they are not model results.
"""
import json
import shutil

import numpy as np

from app.core.config import REPO_ROOT
from app.ml.metrics_report import UNVERIFIED, VERIFIED, apply_to_model_card, build_report
from app.ml.registry import ModelRegistry


def _synthetic_predictions(tmp_path):
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 400)
    p = np.clip(0.35 * y + rng.uniform(0, 0.65, 400), 0, 1)
    path = tmp_path / "holdout_predictions.csv"
    path.write_text("y_true,y_prob\n" + "\n".join(f"{a},{b}" for a, b in zip(y, p)), encoding="utf-8")
    return y, p, path


def test_report_is_computed_from_predictions_and_labelled_unverified(tmp_path):
    y, p, path = _synthetic_predictions(tmp_path)
    report = build_report(y, p, target_sensitivity=0.85, target_specificity=0.80, seed=42,
                          source_file=path, row_order_verified=False)
    assert report["status"] == UNVERIFIED
    assert report["source"]["images"] == 400
    assert report["protocol"]["tuning_images"] + report["protocol"]["test_images"] == 400
    assert 0.0 < report["threshold"] < 1.0
    assert 0.0 <= report["auc"] <= 1.0
    ci = report["confidence_intervals"]["sensitivity"]
    assert ci["low"] <= ci["estimate"] <= ci["high"]
    assert json.loads(json.dumps(report)) == report  # JSON-serialisable


def test_verified_flag_changes_only_the_label(tmp_path):
    y, p, path = _synthetic_predictions(tmp_path)
    kwargs = dict(target_sensitivity=0.85, target_specificity=0.80, seed=42, source_file=path)
    unverified = build_report(y, p, row_order_verified=False, **kwargs)
    verified = build_report(y, p, row_order_verified=True, **kwargs)
    assert verified["status"] == VERIFIED
    assert verified["test_at_tuned_threshold"] == unverified["test_at_tuned_threshold"]


def test_card_update_keeps_the_model_loadable(tmp_path):
    y, p, path = _synthetic_predictions(tmp_path)
    models_dir = tmp_path / "models"
    shutil.copytree(REPO_ROOT / "models" / "dr", models_dir / "dr", ignore=shutil.ignore_patterns("*.h5"))
    report = build_report(y, p, target_sensitivity=0.85, target_specificity=0.80, seed=42,
                          source_file=path, row_order_verified=False)
    apply_to_model_card(models_dir / "dr" / "model_card.json", report)

    card = json.loads((models_dir / "dr" / "model_card.json").read_text(encoding="utf-8"))
    assert card["threshold"] == report["threshold"]
    assert card["metrics"]["sensitivity"] == report["test_at_tuned_threshold"]["sensitivity"]
    assert card["metrics_status"] == UNVERIFIED
    assert not any("not been measured" in line for line in card["limitations"])

    registry = ModelRegistry(("dr",)).discover(models_dir)
    assert registry.status("dr").available
    assert registry.get("dr").card.threshold == report["threshold"]


def test_calibrate_script_writes_metrics_and_updates_the_card(tmp_path):
    """Runs scripts/calibrate_threshold.py end to end (synthetic CSV, temp outputs)."""
    import subprocess
    import sys

    _, _, csv_path = _synthetic_predictions(tmp_path)
    card = tmp_path / "model_card.json"
    shutil.copy(REPO_ROOT / "models" / "dr" / "model_card.json", card)
    metrics = tmp_path / "metrics.json"
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "calibrate_threshold.py"), "--predictions", str(csv_path),
         "--metrics-out", str(metrics), "--model-card", str(card)],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    report = json.loads(metrics.read_text(encoding="utf-8"))
    assert report["status"] == UNVERIFIED
    assert json.loads(card.read_text(encoding="utf-8"))["threshold"] == report["threshold"]
