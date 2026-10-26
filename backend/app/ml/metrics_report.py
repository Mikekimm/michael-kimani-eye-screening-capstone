"""Builds the metrics report (docs/metrics.json) from hold-out predictions, and applies the
calibrated threshold and metrics to a model card.

Every number is computed from the predictions file; nothing is typed in by hand. The threshold
is chosen on the tuning half and every reported metric comes from the test half.
"""
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .evaluation import bootstrap_metric_ci, roc_auc, stratified_split
from .thresholding import metrics_at_threshold, select_threshold

UNVERIFIED = ("unverified, optimistic estimate: row-order equivalence of the Kaggle hold-out with the "
              "training session has not been confirmed, and the dataset has no patient identifiers")
VERIFIED = ("optimistic estimate: hold-out reproduced with the training seed, but the dataset has no "
            "patient identifiers and contains augmented near-duplicates")


def build_report(y_true: np.ndarray, y_prob: np.ndarray, *, target_sensitivity: float, target_specificity: float,
                 seed: int, source_file: Path, row_order_verified: bool) -> dict:
    tune_idx, test_idx = stratified_split(y_true, 0.5, seed)
    y_tune, p_tune, y_test, p_test = y_true[tune_idx], y_prob[tune_idx], y_true[test_idx], y_prob[test_idx]

    tuned = select_threshold(y_tune, p_tune, target_sensitivity)
    at_tuned = metrics_at_threshold(y_test, p_test, tuned.threshold)
    at_default = metrics_at_threshold(y_test, p_test, 0.5)
    intervals = {name: asdict(bootstrap_metric_ci(y_test, p_test, tuned.threshold, name, seed=seed))
                 for name in ("sensitivity", "specificity", "precision")}
    sensitivity, specificity = at_tuned.sensitivity, at_tuned.specificity
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {"file": source_file.name, "sha256": hashlib.sha256(source_file.read_bytes()).hexdigest(),
                   "images": int(len(y_true)), "positives": int(y_true.sum())},
        "status": VERIFIED if row_order_verified else UNVERIFIED,
        "protocol": {"split": "stratified 50/50 tuning/test", "seed": seed,
                     "threshold_rule": f"highest threshold with sensitivity >= {target_sensitivity:.0%} on the tuning half",
                     "tuning_images": int(len(y_tune)), "test_images": int(len(y_test)),
                     "bootstrap": "1000 resamples of the test half, 95% percentile interval"},
        "threshold": tuned.threshold,
        "test_at_tuned_threshold": asdict(at_tuned),
        "test_at_default_0_5": asdict(at_default),
        "confidence_intervals": intervals,
        "auc": roc_auc(y_test, p_test),
        "targets": {"sensitivity": target_sensitivity, "specificity": target_specificity,
                    "sensitivity_met": bool(sensitivity >= target_sensitivity),
                    "specificity_met": bool(specificity >= target_specificity)},
        "reference_only": "Gulshan et al. (2016) reported 90.3% sensitivity / 98.1% specificity on different "
                          "data, model and operating point; not a like-for-like comparison.",
    }


def apply_to_model_card(card_path: Path, report: dict) -> None:
    card = json.loads(card_path.read_text(encoding="utf-8"))
    tuned = report["test_at_tuned_threshold"]
    card["threshold"] = report["threshold"]
    card["threshold_source"] = (f"calibrated by scripts/calibrate_threshold.py on {report['generated_at'][:10]}: "
                                f"{report['protocol']['threshold_rule']}")
    card["metrics"] = {
        "sensitivity": tuned["sensitivity"], "specificity": tuned["specificity"],
        "precision": tuned["precision"], "f1": tuned["f1"], "accuracy": tuned["accuracy"], "auc": report["auc"],
        "test_images": report["protocol"]["test_images"], "confidence_intervals": report["confidence_intervals"],
        "source": "docs/metrics.json",
    }
    card["metrics_status"] = report["status"]
    card["limitations"] = [line for line in card.get("limitations", [])
                           if "has not been measured yet" not in line]
    card_path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
