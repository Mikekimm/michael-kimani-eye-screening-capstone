"""Measure inference latency, model size and memory on the current machine.

Usage:
    python scripts/benchmark.py --runs 50
Run it on each device you want to compare and paste the Markdown table into the report.
"""
import argparse
import os
import platform
import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.ml.classifier import KerasClassifier, TFLiteClassifier  # noqa: E402
from app.ml.config import IMG_SIZE, KERAS_MODEL_PATH, TFLITE_MODEL_PATH  # noqa: E402
from app.ml.exceptions import ModelNotAvailableError  # noqa: E402


def time_backend(backend, runs):
    batch = np.random.default_rng(0).uniform(-1, 1, (1, *IMG_SIZE, 3)).astype(np.float32)
    start = time.perf_counter()
    backend.warm_up()
    load_s = time.perf_counter() - start
    backend.predict_proba(batch)  # warm-up inference
    samples = []
    for _ in range(runs):
        tick = time.perf_counter()
        backend.predict_proba(batch)
        samples.append((time.perf_counter() - tick) * 1000)
    samples.sort()
    return load_s, statistics.mean(samples), samples[int(0.95 * (len(samples) - 1))]


def rss_mb():
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / 1e6
    except ImportError:
        return float("nan")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=50)
    args = parser.parse_args()

    print(f"Machine: {platform.platform()} | Python {platform.python_version()} "
          f"| CPU count: {os.cpu_count()}\n")
    print("| Back-end | File size (MB) | Load (s) | Mean latency (ms) | p95 latency (ms) | RSS after (MB) |")
    print("|---|---|---|---|---|---|")
    for backend, path in ((KerasClassifier(), KERAS_MODEL_PATH), (TFLiteClassifier(), TFLITE_MODEL_PATH)):
        try:
            load_s, mean_ms, p95_ms = time_backend(backend, args.runs)
        except ModelNotAvailableError as exc:
            print(f"| {backend.name} | - | - | - | - | skipped: {exc} |")
            continue
        size_mb = Path(path).stat().st_size / 1e6
        print(f"| {backend.name} | {size_mb:.1f} | {load_s:.2f} | {mean_ms:.1f} | {p95_ms:.1f} | {rss_mb():.0f} |")


if __name__ == "__main__":
    main()
