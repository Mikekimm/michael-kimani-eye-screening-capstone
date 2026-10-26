# Benchmark: dev-laptop-hp-1-thread

Windows-11-10.0.26200-SP0 | Intel64 Family 6 Model 142 Stepping 12, GenuineIntel | 8 CPUs | Python 3.14.6 | 2026-10-26T10:46:09+00:00

| Measurement | Mean (ms) | p50 (ms) | p95 (ms) | Max (ms) |
|---|---|---|---|---|
| Model only (LiteRT, 224x224) | 59.88 | 54.47 | 84.23 | 112.76 |
| Full pipeline (1024px JPEG) | 76.7 | 73.52 | 103.08 | 135.74 |

Model file 2.6 MB, registry load 0.036 s, process memory 89.2 -> 117.0 MB, 200 runs after one warm-up. Input is a synthetic benchmark image.
