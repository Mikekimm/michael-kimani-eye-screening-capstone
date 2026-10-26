# Testing strategy and evidence

Software verification is kept separate from model evaluation (see [DATA_AND_EVALUATION.md](DATA_AND_EVALUATION.md)).

## Strategies used

| Strategy | Why chosen | How | Where |
|---|---|---|---|
| **Unit tests** | Cheap, fast checks of each class in isolation | pytest; a stub classifier replaces the model so no TensorFlow is needed | `tests/test_preprocessing.py`, `test_quality.py`, `test_thresholding.py`, `test_evaluation.py`, `test_storage.py`, `test_result_review_flag.py` |
| **Integration tests** | The risk is in how parts work together: HTTP, auth, SQLite, sync | A real backend on a free local port, real clients, real database | `tests/test_api_integration.py`, `tests/test_classifier_integration.py` (real model) |
| **Failure / connectivity testing** | The product's reason to exist is working offline | Dead port, dropped connection mid-sync, wrong token, rejected record, oversized body | `tests/test_sync.py`, `tests/test_api_integration.py` |
| **UI smoke tests** | The Streamlit pages must start and render | Streamlit `AppTest` | `tests/test_app_smoke.py` |
| **Performance testing** | Offline use on modest hardware | `scripts/benchmark.py` (model), `scripts/benchmark_pipeline.py` (everything else) | below |
| **Compatibility testing** | Clinics use different browsers and machines | Manual run of the same workflow in each browser | below |

Run everything: `pytest` (tests that need TensorFlow or the model skip cleanly if absent).

## Input and error handling (what the tests assert)

| Input | Expected behaviour |
|---|---|
| Valid JPG / PNG / grayscale / RGBA fundus-like image | Screened, saved as PENDING |
| Corrupt or truncated bytes | `InvalidImageError`; nothing saved |
| Blank or too-small image | `ImageQualityError`; nothing saved |
| Blurry, dark or not-fundus-like image | Screened with a warning |
| Patient code that looks like a name | Rejected; nothing saved |
| Score within 0.10 of the threshold | Saved and queued for specialist review |
| Server unreachable | Records stay on the device; one attempt per cycle; no failed-attempt count |
| Wrong token / wrong role | 401 / 403; records stay pending |
| Tampered image checksum, bad JSON, oversized body | 400 / 400 / 413 |
| Same record uploaded twice | Stored once |
| Same review pulled twice | Stored once |

## Bugs found and fixed through testing

1. **Train/serve preprocessing mismatch:** training resized with nearest-neighbour, the first app version used PIL's default.
   The `ImagePreprocessor` now matches training.
2. **Image loss on a duplicate-id race** (found while writing `test_duplicate_id_never_destroys_the_existing_image`): the cleanup could delete an existing image.
   Images are now written to a temp file and moved into place only after the database insert succeeds.
3. **Sync kept trying a dead connection once per queued record.** A mutation check showed the original tests did not detect this;
   `test_offline_cycle_stops_after_the_first_failed_attempt` now pins the behaviour.

## Results to fill in (from your own runs)

> RESULTS-TO-FILL: paste the final line of `pytest` here, e.g. `NNN passed`.

### Performance (run on each device, paste the tables)

```
python scripts/benchmark.py --runs 50
python scripts/benchmark_pipeline.py --runs 30 --records 50
```

| Device | CPU / RAM | OS | Python / TF | Keras mean (ms) | TFLite mean (ms) | Pipeline total (ms) |
|---|---|---|---|---|---|---|
| Laptop (high-end) | | | | | | |
| Second, lower-spec device | | | | | | |

### Compatibility (same workflow: screen, save, sync, review)

| Environment | Clinic app | Specialist portal | Notes |
|---|---|---|---|
| Chrome (version) on Windows | | | |
| Edge (version) | | | |
| Firefox (version) | | | |
| Phone browser over the "Network URL" | | | |

### Improvements made after testing

Record here what you changed because of what you saw (for example a message you reworded after a confusing error).
