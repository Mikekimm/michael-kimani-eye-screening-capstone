"""Benchmark the parts of the pipeline that do not need TensorFlow.

Measures: image decode + preprocessing, quality check, saving a record locally,
and a full offline-to-online sync round trip against a local backend.

Usage:
    python scripts/benchmark_pipeline.py --runs 30 --records 50
Run it on each device you test and paste the table into the report.
(Model inference time is measured separately by scripts/benchmark.py.)
"""
import argparse
import io
import os
import platform
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.ml.api_client import ClinicClient  # noqa: E402
from app.ml.domain import Role  # noqa: E402
from app.ml.preprocessing import ImagePreprocessor  # noqa: E402
from app.ml.quality import ImageQualityChecker  # noqa: E402
from app.ml.result import ScreeningResult  # noqa: E402
from app.ml.server import Principal, make_server  # noqa: E402
from app.ml.storage import ScreeningRepository  # noqa: E402
from app.ml.sync import SyncService  # noqa: E402


def synthetic_fundus(size=1024, seed=0) -> bytes:
    """Synthetic disc used only to time the code path; it is not a medical image."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size]
    disc = np.hypot(xx - size / 2, yy - size / 2) < size * 0.45
    pixels = np.zeros((size, size, 3), dtype=np.float32)
    pixels[disc] = (np.array([200, 90, 30]) + rng.normal(0, 12, (size, size, 1))[disc]).clip(0, 255)
    buffer = io.BytesIO()
    Image.fromarray(pixels.astype(np.uint8), "RGB").save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


def timed(fn, runs):
    fn()  # warm-up
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    samples.sort()
    return statistics.mean(samples), samples[int(0.95 * (len(samples) - 1))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--records", type=int, default=50)
    args = parser.parse_args()

    image = synthetic_fundus()
    preprocessor, checker = ImagePreprocessor(), ImageQualityChecker()
    print(f"Machine: {platform.platform()} | Python {platform.python_version()} | CPU count: {os.cpu_count()}")
    print(f"Test image: 1024x1024 JPEG, {len(image) / 1024:.0f} KB\n")
    print("| Step | Mean (ms) | p95 (ms) |")
    print("|---|---|---|")
    decoded = preprocessor.load(image)
    rows = [
        ("Decode + convert to RGB", lambda: preprocessor.load(image)),
        ("Resize + scale to model input", lambda: preprocessor.to_batch(decoded)),
        ("Quality check", lambda: checker.assess(decoded)),
    ]
    for name, fn in rows:
        mean_ms, p95_ms = timed(fn, args.runs)
        print(f"| {name} | {mean_ms:.1f} | {p95_ms:.1f} |")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        local = ScreeningRepository(tmp / "local.db", tmp / "local_img")
        result = ScreeningResult(0.8, 0.5, "bench", checker.assess(decoded))
        counter = iter(range(10**6))
        mean_ms, p95_ms = timed(lambda: local.add_screening(
            result, image, f"PT-{next(counter):05d}", "left", "bench", "stub"), args.runs)
        print(f"| Save record locally (SQLite + image file) | {mean_ms:.1f} | {p95_ms:.1f} |")

        for _ in range(args.records):
            local.add_screening(result, image, f"PT-{next(counter):05d}", "right", "bench", "stub")
        pending = len(local.pending())
        server_repo = ScreeningRepository(tmp / "srv.db", tmp / "srv_img")
        server = make_server(server_repo, {"t": Principal("bench", Role.CLINICIAN)}, port=0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        client = ClinicClient(f"http://127.0.0.1:{server.server_address[1]}", "t", timeout=30)
        start = time.perf_counter()
        report = SyncService(local, client).sync()
        elapsed = time.perf_counter() - start
        server.shutdown()
        server.server_close()
        print(f"\nSync round trip (local server): {report.pushed}/{pending} records uploaded in "
              f"{elapsed:.2f} s ({elapsed / max(report.pushed, 1) * 1000:.0f} ms per record, "
              f"{len(image) / 1024:.0f} KB image each)")


if __name__ == "__main__":
    main()
