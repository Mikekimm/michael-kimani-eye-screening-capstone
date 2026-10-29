"""Copy the DR v1 validation metrics printed by its training notebook into docs/models/evaluation/dr_v1_metrics.json,
parsing the notebook's saved outputs so no number is typed by hand. v1 is retired (DR v2 replaced it, see
scripts/dr_v2_metrics.py); this file keeps its figures as history and does not touch the model card.

These are VALIDATION results from the training notebook (the fold also used for early stopping),
not an independent hold-out or test set. The independent hold-out run did not finish.

Usage (repo root):  .venv\\Scripts\\python scripts\\extract_notebook_metrics.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "notebooks" / "model_notebook.ipynb"
METRICS = ROOT / "docs" / "models" / "evaluation" / "dr_v1_metrics.json"
TARGET_SENSITIVITY, TARGET_SPECIFICITY = 0.85, 0.80
LABEL = "validation results from the training notebook, not an independent hold-out"


def notebook_output_text(path: Path) -> str:
    nb = json.loads(path.read_text(encoding="utf-8"))
    chunks = []
    for cell in nb["cells"]:
        for out in cell.get("outputs", []):
            chunks.append("".join(out.get("text", "")) or "".join(out.get("data", {}).get("text/plain", "")))
    return "\n".join(chunks)


def parse(text: str) -> dict:
    def number(pattern):
        match = re.search(pattern, text)
        if not match:
            raise SystemExit(f"Could not find {pattern!r} in the notebook outputs.")
        return match.group(1)
    no_dr = re.search(r"No DR\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)", text)
    dr = re.search(r"DR present\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)", text)
    if not (no_dr and dr):
        raise SystemExit("Could not find the classification report in the notebook outputs.")
    return {
        "accuracy": float(number(r"Accuracy:\s+([\d.]+)")),
        "precision": float(number(r"Precision:\s+([\d.]+)")),
        "sensitivity": float(number(r"Recall \(sensitivity\):\s+([\d.]+)")),
        "f1": float(number(r"F1 score:\s+([\d.]+)")),
        "specificity": float(no_dr.group(2)),  # recall of the No DR class, printed to 2 decimals
        "negatives": int(no_dr.group(4)), "positives": int(dr.group(4)),
    }


def main() -> int:
    m = parse(notebook_output_text(NOTEBOOK))
    images = m["negatives"] + m["positives"]
    met_sens, met_spec = m["sensitivity"] >= TARGET_SENSITIVITY, m["specificity"] >= TARGET_SPECIFICITY
    status = (f"{LABEL}: {images:,} images, threshold 0.5; "
              + ("meets" if met_sens else "does NOT meet") + " the 85% sensitivity target"
              + f" (sensitivity {m['sensitivity']:.3f})")
    report = {
        "status": status,
        "source": "notebooks/model_notebook.ipynb, saved outputs of the evaluation cell (classification_report)",
        "evaluation_set": "validation fold of the training run (StratifiedGroupKFold, seed 42), also used for early stopping",
        "threshold": 0.5,
        "metrics": {k: m[k] for k in ("accuracy", "precision", "sensitivity", "specificity", "f1")},
        "precision_of_values": "accuracy, precision, sensitivity and F1 to 3 decimals; specificity to 2 decimals (from the classification report)",
        "auc": None,
        "class_counts": {"no_dr": m["negatives"], "dr_present": m["positives"], "total": images},
        "targets": {"sensitivity": TARGET_SENSITIVITY, "specificity": TARGET_SPECIFICITY,
                    "sensitivity_met": met_sens, "specificity_met": met_spec},
        "caveats": [
            "Not an independent hold-out or test set: the same fold guided early stopping.",
            "The independent hold-out evaluation did not finish (its notebook was removed from the repo; it is in the git history).",
            "Image-level data with no patient identifiers and augmented near-duplicates: optimistic.",
            "Measured with the Keras model in the training session; the served .tflite is a quantized export that differs by up to about 0.03 in score.",
            "No threshold calibration was performed; the app uses the default 0.5.",
        ],
        "reference_only": "Gulshan et al. (2016): 90.3% sensitivity / 98.1% specificity on different data, model and operating point.",
    }
    METRICS.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"]), "|", status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
