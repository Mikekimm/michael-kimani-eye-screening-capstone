"""Write docs/metrics.json and models/dr/model_card.json for DR model v2 from the notebook's own files.

Inputs (copied from dr_v2_results.zip into docs/evaluation/dr_v2/):
  results.json          what notebooks/dr_v2_finetune.ipynb measured
  val_predictions.csv   validation split scores (the threshold is chosen here)
  test_predictions.csv  held-out test split scores (every reported number comes from here)

The threshold and every metric are recomputed with the app's own code (thresholding.py, evaluation.py)
and checked against results.json; the script stops if they disagree. No number is typed by hand.

Usage (repo root):  .venv\\Scripts\\python scripts\\dr_v2_metrics.py
"""
import csv
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.ml.config import TARGET_SENSITIVITY  # noqa: E402
from app.ml.evaluation import bootstrap_metric_ci, roc_auc  # noqa: E402
from app.ml.thresholding import metrics_at_threshold, select_threshold  # noqa: E402

EVIDENCE = ROOT / "docs" / "evaluation" / "dr_v2"
METRICS = ROOT / "docs" / "metrics.json"
V1_METRICS = ROOT / "docs" / "evaluation" / "dr_v1_metrics.json"
CARD = ROOT / "models" / "dr" / "model_card.json"
MODEL = ROOT / "models" / "dr" / "model.tflite"
TARGET_SPECIFICITY = 0.80
VERSION = "mobilenetv2-dr-binary-2.0"
LABEL = ("held-out test split by image (no patient IDs available; near-duplicates could not be excluded); "
         "not external validation; not clinically validated")


def read(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return np.array([int(r["label"]) for r in rows]), np.array([float(r["prob"]) for r in rows])


def check(name: str, ours: float, notebook: float) -> None:
    if abs(ours - notebook) > 1e-9:
        raise SystemExit(f"{name}: recomputed {ours} but the notebook reported {notebook}; not writing anything.")


def main() -> None:
    results = json.loads((EVIDENCE / "results.json").read_text(encoding="utf-8"))
    y_val, p_val = read(EVIDENCE / "val_predictions.csv")
    y_test, p_test = read(EVIDENCE / "test_predictions.csv")

    threshold = select_threshold(y_val, p_val, TARGET_SENSITIVITY).threshold
    check("threshold", threshold, results["threshold"]["value"])
    tuned = metrics_at_threshold(y_test, p_test, threshold)
    default = metrics_at_threshold(y_test, p_test, 0.5)
    auc = roc_auc(y_test, p_test)
    for key in ("sensitivity", "specificity", "precision", "accuracy", "f1"):
        check(f"test {key}", getattr(tuned, key), results["test"]["at_threshold"][key])
    check("test AUC", auc, results["test"]["auc"])
    sha = hashlib.sha256(MODEL.read_bytes()).hexdigest()
    if sha != results["export"]["tflite_sha256"]:
        raise SystemExit("models/dr/model.tflite is not the file the notebook measured.")

    intervals = {k: asdict(bootstrap_metric_ci(y_test, p_test, threshold, k, seed=42))
                 for k in ("sensitivity", "specificity", "precision")}
    meets_sens, meets_spec = tuned.sensitivity >= TARGET_SENSITIVITY, tuned.specificity >= TARGET_SPECIFICITY
    targets = (f"meets the {TARGET_SENSITIVITY:.0%} sensitivity target; "
               f"{'meets' if meets_spec else 'below'} the {TARGET_SPECIFICITY:.0%} specificity target")
    status = f"{LABEL}; {len(y_test):,} test images; {targets}"
    split = results["split"]

    report = {
        "status": status,
        "model_version": VERSION,
        "source": "notebooks/dr_v2_finetune.ipynb -> docs/evaluation/dr_v2/ (recomputed by scripts/dr_v2_metrics.py)",
        "evaluation_set": "held-out test split by image group (seed 42); the threshold was chosen on the validation split only",
        "split": {k: split[k] for k in ("method", "train", "validation", "test", "groups", "group_overlap")},
        "threshold": threshold,
        "threshold_rule": results["threshold"]["rule"],
        "metrics": {"sensitivity": tuned.sensitivity, "specificity": tuned.specificity, "precision": tuned.precision,
                    "f1": tuned.f1, "accuracy": tuned.accuracy, "auc": auc,
                    "tp": tuned.tp, "fp": tuned.fp, "tn": tuned.tn, "fn": tuned.fn},
        "confidence_intervals": intervals,
        "test_at_default_0_5": asdict(default),
        "referable_dr_grade_2_plus": results["test"]["referable_dr"],
        "share_flagged_per_icdr_grade": results["test"]["per_grade_flagged"],
        "class_counts": {"no_dr": int((y_test == 0).sum()), "dr_present": int(y_test.sum()), "total": int(len(y_test))},
        "targets": {"sensitivity": TARGET_SENSITIVITY, "specificity": TARGET_SPECIFICITY,
                    "sensitivity_met": bool(meets_sens), "specificity_met": bool(meets_spec)},
        "caveats": [
            f"The notebook found {split['groups']:,} image groups for {split['groups']:,} images: augmented copies and "
            "the two eyes of one patient could not be grouped, so near-duplicates may sit in both train and test and "
            "these figures may be optimistic.",
            "No patient identifiers in the dataset; no external validation; not clinically validated.",
            "Images are from clinic fundus cameras, not low-cost smartphone lenses.",
        ],
        "reference_only": "Gulshan et al. (2016) reported 90.3% sensitivity / 98.1% specificity on different data, "
                          "model and operating point; not a like-for-like comparison.",
        "previous_model": {"version": "mobilenetv2-dr-binary-0.3", "file": "docs/evaluation/dr_v1_metrics.json",
                           "summary": "validation fold only, threshold 0.5: sensitivity 0.542, specificity 0.97"},
    }
    METRICS.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    card = {
        "condition": "dr",
        "display_name": "Diabetic retinopathy",
        "version": VERSION,
        "file": "model.tflite",
        "sha256": sha,
        "task": "binary",
        "labels": {"0": "No DR", "1": "DR present (ICDR grades 1-4)"},
        "input": {"shape": [1, 224, 224, 3], "dtype": "float32", "color": "RGB", "interpolation": "bilinear",
                  "resize": "bilinear, anti-aliased, to 224x224 (tf.image.resize antialias=True in training)",
                  "normalisation": results["input"]["normalisation"]},
        "output": {"shape": [1, 1], "meaning": "sigmoid score for DR present, in [0, 1]"},
        "threshold": threshold,
        "threshold_source": f"{results['threshold']['rule']}; the test split was not used for any choice",
        "architecture": results["model"] + "; class weights; early stopping on validation AUC; seed 42",
        "training": {
            "dataset": results["dataset"] + " (EyePACS + APTOS 2019 + Messidor-2 redistribution, pre-augmented, "
                                            "no patient identifiers)",
            "split": f"{split['method']}: train {split['train']:,} / validation {split['validation']:,} / "
                     f"test {split['test']:,}",
            "epochs_run": results["training"]["epochs_run"],
            "notebook": "notebooks/dr_v2_finetune.ipynb",
            "export": f"float32 TFLite; max |Keras - TFLite| {results['export']['max_abs_keras_tflite_diff']:.1e}",
            "licence_note": "Underlying data is for non-commercial / academic use; no images are stored in this repository.",
        },
        "metrics": {"sensitivity": tuned.sensitivity, "specificity": tuned.specificity, "precision": tuned.precision,
                    "f1": tuned.f1, "accuracy": tuned.accuracy, "auc": auc, "test_images": int(len(y_test)),
                    "evaluation_set": "held-out test split by image", "confidence_intervals": intervals,
                    "source": "docs/metrics.json"},
        "metrics_status": status,
        "limitations": [
            "Screening support only. Not a diagnosis and not clinically validated.",
            f"Specificity {tuned.specificity:.3f} is below the 80% target: {1 - tuned.specificity:.0%} of eyes without DR "
            "are flagged for specialist review.",
            report["caveats"][0],
            "No external evaluation; images from low-cost smartphone fundus lenses were never tested.",
            "The 1-5 severity band is estimated from a binary score by a configurable policy; it is not an ICDR grade.",
        ],
    }
    CARD.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    print(f"threshold {threshold:.6f} (validation) | test: sensitivity {tuned.sensitivity:.4f}, specificity "
          f"{tuned.specificity:.4f}, precision {tuned.precision:.4f}, AUC {auc:.4f} on {len(y_test):,} images")
    print(f"all values match results.json; wrote {METRICS.relative_to(ROOT)} and {CARD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
