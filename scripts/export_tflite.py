"""Convert the trained Keras model to TensorFlow Lite for on-device inference.

Usage:
    python scripts/export_tflite.py
Reads models/dr/model.h5 and writes models/dr/model.tflite.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import tensorflow as tf  # noqa: E402

from app.ml.config import KERAS_MODEL_PATH, MODEL_DIR  # noqa: E402


def main():
    model = tf.keras.models.load_model(KERAS_MODEL_PATH, compile=False)
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]  # dynamic-range quantisation
    tflite_bytes = converter.convert()
    out_path = MODEL_DIR / "dr" / "model.tflite"
    out_path.write_bytes(tflite_bytes)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
