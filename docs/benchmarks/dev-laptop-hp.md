# Benchmark: dev-laptop-hp

Windows-11-10.0.26200-SP0 | Intel64 Family 6 Model 142 Stepping 12, GenuineIntel | 8 CPUs | Python 3.14.6 | 2026-10-26T10:45:34+00:00

| Measurement | Mean (ms) | p50 (ms) | p95 (ms) | Max (ms) |
|---|---|---|---|---|
| Model only (LiteRT, 224x224) | 55.03 | 52.55 | 67.77 | 101.9 |
| Full pipeline (1024px JPEG) | 73.54 | 69.84 | 89.99 | 148.31 |

Model file 2.6 MB, registry load 0.033 s, process memory 89.6 -> 117.3 MB, 200 runs after one warm-up. Input is a synthetic benchmark image.
