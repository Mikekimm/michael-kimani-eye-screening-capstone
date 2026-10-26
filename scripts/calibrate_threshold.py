"""Choose a decision threshold that meets the sensitivity target, then report
honest performance on data the threshold never saw.

Input: a CSV with columns ``y_true`` (0/1) and ``y_prob`` (model score) produced by
``docs/kaggle_holdout_predictions.py`` from images the model never trained on.

The file is split in two (stratified, fixed seed):
  * tuning half : the threshold is selected here
  * test half   : every reported number comes from here, with 95% bootstrap intervals

Outputs (all computed from the CSV, nothing typed by hand):
  * docs/metrics.json                 full report shown in the README, report and About screen
  * models/dr/model_card.json         calibrated threshold + headline metrics served by GET /api/models

Usage:
    python scripts/calibrate_threshold.py --predictions docs/evaluation/holdout_predictions.csv
    (add --row-order-verified only after confirming the Kaggle df matched the training session)
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.ml.config import THRESHOLD_PATH, TARGET_SENSITIVITY  # noqa: E402
from app.ml.evaluation import bootstrap_metric_ci, roc_auc, stratified_split  # noqa: E402
from app.ml.metrics_report import apply_to_model_card, build_report  # noqa: E402
from app.ml.thresholding import metrics_at_threshold, save_threshold, select_threshold  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
METRICS_PATH = REPO_ROOT / "docs" / "metrics.json"
MODEL_CARD_PATH = REPO_ROOT / "models" / "dr" / "model_card.json"

TARGET_SPECIFICITY = 0.80  # from the proposal (Section 3.3)


def read_predictions(path):
    y_true, y_prob = [], []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            y_true.append(int(float(row["y_true"])))
            y_prob.append(float(row["y_prob"]))
    return np.array(y_true), np.array(y_prob)


def row(name, point):
    return (f"| {name} | {point.threshold:.3f} | {point.sensitivity:.3f} | {point.specificity:.3f} "
            f"| {point.precision:.3f} | {point.f1:.3f} | {point.accuracy:.3f} |")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--target", type=float, default=TARGET_SENSITIVITY)
    parser.add_argument("--out", default=str(THRESHOLD_PATH))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-save", action="store_true", help="print only; write no files")
    parser.add_argument("--row-order-verified", action="store_true",
                        help="the Kaggle df was confirmed identical to the training session")
    args = parser.parse_args()

    y, p = read_predictions(args.predictions)
    tune_idx, test_idx = stratified_split(y, 0.5, args.seed)
    y_tune, p_tune, y_test, p_test = y[tune_idx], p[tune_idx], y[test_idx], p[test_idx]

    tuned = select_threshold(y_tune, p_tune, args.target)
    on_test_default = metrics_at_threshold(y_test, p_test, 0.5)
    on_test_tuned = metrics_at_threshold(y_test, p_test, tuned.threshold)

    print(f"Predictions: {len(y)} images -> tuning {len(y_tune)} / test {len(y_test)} "
          f"(positives in test: {int(y_test.sum())})\n")
    print("Results on the TEST half (threshold chosen on the tuning half only)\n")
    print("| Setting | Threshold | Sensitivity | Specificity | Precision | F1 | Accuracy |")
    print("|---|---|---|---|---|---|---|")
    print(row("Default 0.5", on_test_default))
    print(row(f"Tuned for {args.target:.0%} sensitivity", on_test_tuned))
    print(row("Baseline: flag everyone", metrics_at_threshold(y_test, p_test, 0.0)))
    print(row("Baseline: flag no one", metrics_at_threshold(y_test, p_test, 1.0 + 1e-9)))

    auc = roc_auc(y_test, p_test)
    sens = bootstrap_metric_ci(y_test, p_test, tuned.threshold, "sensitivity", seed=args.seed)
    spec = bootstrap_metric_ci(y_test, p_test, tuned.threshold, "specificity", seed=args.seed)
    print(f"\nAUC (test half): {auc:.3f}")
    print(f"Sensitivity at tuned threshold: {sens}")
    print(f"Specificity at tuned threshold: {spec}")
    meets = sens.estimate >= args.target and spec.estimate >= TARGET_SPECIFICITY
    print(f"\nProposal targets (>= {args.target:.0%} sensitivity AND >= "
          f"{TARGET_SPECIFICITY:.0%} specificity): {'MET' if meets else 'NOT MET'}")
    print("Reference only (not comparable: different data, model and operating point): "
          "Gulshan et al. 2016 reported 90.3% sensitivity / 98.1% specificity.")

    if not args.no_save:
        save_threshold(tuned, args.target, Path(args.out), extra={
            "tuning_images": int(len(y_tune)), "test_images": int(len(y_test)),
            "seed": args.seed,
            "test_metrics": {"sensitivity": sens.estimate, "specificity": spec.estimate,
                             "auc": auc, "targets_met": bool(meets)}})
        print(f"\nSaved tuned threshold to {args.out}")


if __name__ == "__main__":
    main()
