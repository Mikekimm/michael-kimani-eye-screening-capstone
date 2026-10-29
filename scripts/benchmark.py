"""Measure inference latency and memory on this machine and save the results.

Times two things, each over --runs repetitions after one warm-up:
  * model only:     LiteRT interpreter on a preprocessed batch (what the server runs per condition)
  * full pipeline:  decode -> quality gate -> preprocess -> every available model -> RiskPolicy
                    (the work done for one POST /api/screenings, excluding network and database)

Results are written to docs/testing/benchmarks/<machine-label>.json and .md. Run it on each device you
want to compare (e.g. a high-end laptop and a low-end machine) and cite the files in the report.

Usage (repo root):
    .venv\\Scripts\\python scripts\\benchmark.py --runs 50 --label my-laptop
"""
import argparse
import io
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import BACKEND_ROOT  # noqa: E402
from app.ml.condition_model import TFLiteConditionModel  # noqa: E402
from app.ml.preprocessing import ImagePreprocessor  # noqa: E402
from app.ml.registry import ModelRegistry  # noqa: E402
from app.ml.risk_policy import RiskPolicyFactory  # noqa: E402
from app.services.pipeline import ScreeningPipeline  # noqa: E402

OUT_DIR = ROOT / "docs" / "testing" / "benchmarks"


def synthetic_fundus(size: int = 1024) -> bytes:
    """Benchmark input only: a textured disc the size of a typical phone fundus photo (not a retinal image)."""
    rng = np.random.default_rng(0)
    yy, xx = np.mgrid[0:size, 0:size]
    disc = np.hypot(xx - size / 2, yy - size / 2) < size * 0.45
    pixels = np.zeros((size, size, 3), dtype=np.float32)
    pixels[disc] = np.array([200, 90, 30]) + rng.normal(0, 12, (int(disc.sum()), 1))
    buffer = io.BytesIO()
    Image.fromarray(pixels.clip(0, 255).astype(np.uint8)).save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def time_ms(fn, runs: int) -> dict:
    fn()  # warm-up
    samples = []
    for _ in range(runs):
        tick = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - tick) * 1000)
    samples.sort()
    return {"mean_ms": round(statistics.mean(samples), 2), "p50_ms": round(samples[len(samples) // 2], 2),
            "p95_ms": round(samples[int(0.95 * (len(samples) - 1))], 2), "max_ms": round(samples[-1], 2)}


def rss_mb() -> float | None:
    try:
        import psutil
        return round(psutil.Process(os.getpid()).memory_info().rss / 1e6, 1)
    except ImportError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--label", default=platform.node() or "machine")
    parser.add_argument("--threads", type=int, default=None,
                        help="limit the interpreter to N CPU threads (1 approximates a low-end CPU)")
    args = parser.parse_args()

    rss_before = rss_mb()
    start = time.perf_counter()
    loader = lambda card, path: TFLiteConditionModel(card, path, num_threads=args.threads)  # noqa: E731
    registry = ModelRegistry(("dr", "glaucoma", "cataract"), loader=loader).discover(ROOT / "models")
    load_s = time.perf_counter() - start
    model = registry.get("dr")
    if model is None:
        print("DR model not available:", registry.status("dr").reason)
        return 1
    pipeline = ScreeningPipeline(registry, RiskPolicyFactory.from_file(BACKEND_ROOT / "config" / "risk_policy.json"),
                                 max_upload_bytes=10 * 1024 * 1024, allowed_types=("image/jpeg", "image/png"))
    image_bytes = synthetic_fundus()
    batch = ImagePreprocessor().to_batch(Image.open(io.BytesIO(image_bytes)).convert("RGB"))

    result = {
        "label": args.label,
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "machine": {"os": platform.platform(), "processor": platform.processor() or platform.machine(),
                    "cpu_count": os.cpu_count(), "python": platform.python_version()},
        "model": {"version": model.version, "file_mb": round((ROOT / "models" / "dr" / "model.tflite").stat().st_size / 1e6, 2),
                  "runtime": model.runtime},
        "interpreter_threads": args.threads or "default (all cores)",
        "runs": args.runs,
        "registry_load_s": round(load_s, 3),
        "model_only": time_ms(lambda: model.predict_proba(batch), args.runs),
        "full_pipeline_1024px_jpeg": time_ms(lambda: pipeline.run("image/jpeg", image_bytes), args.runs),
        "rss_mb": {"before_load": rss_before, "after_runs": rss_mb()},
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in args.label)
    (OUT_DIR / f"{stem}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    m, f = result["model_only"], result["full_pipeline_1024px_jpeg"]
    table = (f"# Benchmark: {args.label}\n\n{result['machine']['os']} | {result['machine']['processor']} | "
             f"{result['machine']['cpu_count']} CPUs | Python {result['machine']['python']} | {result['measured_at']}\n\n"
             "| Measurement | Mean (ms) | p50 (ms) | p95 (ms) | Max (ms) |\n|---|---|---|---|---|\n"
             f"| Model only (LiteRT, 224x224) | {m['mean_ms']} | {m['p50_ms']} | {m['p95_ms']} | {m['max_ms']} |\n"
             f"| Full pipeline (1024px JPEG) | {f['mean_ms']} | {f['p50_ms']} | {f['p95_ms']} | {f['max_ms']} |\n\n"
             f"Model file {result['model']['file_mb']} MB, registry load {result['registry_load_s']} s, "
             f"process memory {result['rss_mb']['before_load']} -> {result['rss_mb']['after_runs']} MB, "
             f"{args.runs} runs after one warm-up. Input is a synthetic benchmark image.\n")
    (OUT_DIR / f"{stem}.md").write_text(table, encoding="utf-8")
    print(table)
    print(f"Saved {OUT_DIR / (stem + '.json')} and .md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
