"""ML constants shared by preprocessing, evaluation and the scripts.

Model files, thresholds and decision settings live in models/<condition>/model_card.json and
backend/config/risk_policy.json; API settings live in app/core/config.py.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # backend/app/ml/config.py -> repo root
MODEL_DIR = PROJECT_ROOT / "models"
KERAS_MODEL_PATH = MODEL_DIR / "dr" / "model.h5"
TFLITE_MODEL_PATH = MODEL_DIR / "dr" / "model.tflite"

IMG_SIZE = (224, 224)       # must match the training pipeline
TARGET_SENSITIVITY = 0.85   # minimum sensitivity target from the proposal
