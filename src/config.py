"""Central configuration: paths and constants shared across the project."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "models"


def _resolve_model_file(name: str) -> Path:
    """Prefer models/<name>; fall back to the repo root for older layouts."""
    preferred = MODEL_DIR / name
    legacy = PROJECT_ROOT / name
    if not preferred.exists() and legacy.exists():
        return legacy
    return preferred


KERAS_MODEL_PATH = _resolve_model_file("dr_screening_model.h5")
TFLITE_MODEL_PATH = _resolve_model_file("dr_screening_model.tflite")
THRESHOLD_PATH = MODEL_DIR / "threshold.json"

# Local, offline-first data (SQLite database + stored fundus images). Never committed.
DATA_DIR = Path(os.environ.get("SCREENING_DATA_DIR", PROJECT_ROOT / "data"))
LOCAL_DB_PATH = DATA_DIR / "screenings.db"
LOCAL_IMAGE_DIR = DATA_DIR / "images"

IMG_SIZE = (224, 224)       # must match the training pipeline
DEFAULT_THRESHOLD = 0.5
TARGET_SENSITIVITY = 0.85   # minimum sensitivity target from the proposal
# Scores within this distance of the threshold are "borderline": they are queued for
# specialist review even when below the threshold (the sequence diagram's "uncertain" case).
DEFAULT_UNCERTAINTY_MARGIN = 0.10
MODEL_VERSION = "mobilenetv2-dr-binary-0.3"
