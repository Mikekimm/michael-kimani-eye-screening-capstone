# Benchmark: dev-laptop-hp

Windows-11-10.0.26200-SP0 | Intel64 Family 6 Model 142 Stepping 12, GenuineIntel | 8 CPUs | Python 3.14.6 | 2026-10-26T09:09:57+00:00

| Measurement | Mean (ms) | p50 (ms) | p95 (ms) | Max (ms) |
|---|---|---|---|---|
| Model only (LiteRT, 224x224) | 110.43 | 107.06 | 141.75 | 155.97 |
| Full pipeline (1024px JPEG) | 165.72 | 156.55 | 231.78 | 247.99 |

Model file 2.6 MB, registry load 0.066 s, process memory 89.4 -> 116.8 MB, 50 runs after one warm-up. Input is a synthetic benchmark image.
