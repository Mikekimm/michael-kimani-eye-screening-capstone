# Retinal Screening Assistant: offline-first diabetic retinopathy screening prototype

A research prototype that lets a primary health centre worker screen a retinal fundus photograph for
**diabetic retinopathy (DR)** with **no internet connection**, keep the record safely on the device, and
**send flagged or borderline cases to a specialist** when a connection is available. It is preliminary
screening support, **not a diagnosis**, and it is not clinically validated.

| | |
|---|---|
| **Video walkthrough** | TODO-paste-video-link |
| **Technical report (PDF, 5 pages)** | TODO-paste-report-link |
| **Repository** | https://github.com/Mikekimm/michael-kimani-eye-screening-capstone |

## Who it is for and the demonstration workflow

**User:** a clinical officer at a rural primary health centre with an intermittent internet connection and no
ophthalmologist on site. **Reviewer:** an ophthalmologist at a regional hospital.

1. The clinical officer enters a **patient code** (not a name), chooses the **eye**, and uploads a fundus photo.
2. The app checks image quality, runs the model **locally**, and shows the result and advice. The record
   (image, eye, model version, score, threshold) is saved on the device immediately.
3. Flagged or **borderline** scores are marked for specialist review. Nothing is lost while offline.
4. When connected, **Sync now** uploads pending records and pulls back specialist decisions.
5. The specialist opens the **review portal**, sees the image, eye and model version, and approves or overrides.
   Every decision is kept in the case history; the clinic receives it at its next sync.

Research evaluation (how good is the model?) is documented separately from software verification
(does the system behave?): see [docs/DATA_AND_EVALUATION.md](docs/DATA_AND_EVALUATION.md) and [docs/TESTING.md](docs/TESTING.md).

## Features and scope

See [docs/SCOPE_TABLE.md](docs/SCOPE_TABLE.md) for the full planned-versus-delivered table. In short:
DR classification, offline inference (Keras and TensorFlow Lite), local SQLite storage, two-way sync,
token-authenticated REST backend, specialist review portal with history, and quality checks are implemented.
**Glaucoma, cataract and the Android app are not implemented** (future work).

## Architecture

![Architecture](docs/diagrams/architecture.png)

Diagrams for the use cases and data model are in [docs/diagrams](docs/diagrams) and explained in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Repository structure

```
app.py                     Clinic app UI (offline-first): screen, save, sync
specialist_app.py          Specialist review portal UI
src/
  config.py                paths and constants
  domain.py                records, enums, validation (laterality, patient code, review decisions)
  preprocessing.py         ImagePreprocessor: decode, convert, resize, scale (matches training)
  quality.py               ImageQualityChecker: blank, size, blur, brightness, fundus-likeness
  classifier.py            BaseClassifier + KerasClassifier + TFLiteClassifier + factory
  thresholding.py          sensitivity-targeted threshold selection
  evaluation.py            tune/test split, AUC, bootstrap confidence intervals
  result.py                ScreeningResult (flagged / borderline / needs_review)
  service.py               ScreeningService: load -> quality -> predict -> decide
  storage.py               ScreeningRepository: SQLite store, review history, sync bookkeeping
  workflow.py              ScreeningWorkflow: screen + save in one step
  sync.py                  SyncService + RemoteClient interface
  api_client.py            ApiClient, ClinicClient, SpecialistClient (HTTP, error translation)
  server.py                REST backend with token authentication and roles
  exceptions.py            domain-specific errors
scripts/
  run_server.py            start the backend
  calibrate_threshold.py   choose threshold on one half, report on the other, with intervals
  benchmark.py             model latency, size, memory
  benchmark_pipeline.py    preprocessing, quality, storage and sync timings
  export_tflite.py         convert the Keras model to TensorFlow Lite
tests/                     pytest suite (unit, integration, connectivity, UI smoke)
notebooks/                 model_notebook.ipynb (training and evaluation, run on Kaggle)
models/                    dr_screening_model.h5, dr_screening_model.tflite (+ threshold.json once calibrated)
docs/                      data and evaluation, scope table, testing, architecture, diagrams, video script
```

## Installation

Requirements: Python 3.10 or newer (TensorFlow does not yet support every newest Python; use the version in the table below).

```bash
git clone https://github.com/Mikekimm/michael-kimani-eye-screening-capstone.git
cd michael-kimani-eye-screening-capstone
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

### Run the demo (three terminals, same folder, virtual environment active)

```bash
# 1. backend (prints access tokens; --demo-tokens uses fixed INSECURE tokens for demos only)
python scripts/run_server.py --demo-tokens

# 2. clinic app: set the token in the sidebar (demo: demo-clinician-token)
streamlit run app.py

# 3. specialist portal: token demo-specialist-token
streamlit run specialist_app.py --server.port 8502
```

To demonstrate offline use, screen a few patients **before** starting the backend, then start it and press **Sync now**.

## Technical requirements

| Item | Version used |
|---|---|
| OS | TODO |
| Python | TODO (`python --version`) |
| TensorFlow / Keras | TODO (`pip show tensorflow keras`) |
| Streamlit | TODO (`pip show streamlit`) |
| NumPy / Pillow | TODO (`pip show numpy pillow`) |
| Hardware | TODO (CPU, RAM) |
| Training | Kaggle notebook, GPU T4 x2 |

## Testing

```bash
pip install -r requirements-dev.txt
pytest                         # everything (tests needing TensorFlow skip if it is absent)
pytest -m "not integration"    # skip the tests that load the real model
python scripts/benchmark.py --runs 50
python scripts/benchmark_pipeline.py --runs 30 --records 50
```

Strategy, input cases and results: [docs/TESTING.md](docs/TESTING.md).

## Model, data and metrics (read this)

* **Model:** MobileNetV2 (ImageNet weights, frozen backbone) with a small classification head; binary output (DR present or absent).
* **Data:** a public Kaggle collection (EyePACS + APTOS + Messidor-2). It has **no patient identifiers** and contains augmented
  copies, so a patient-separated split was not possible and **all metrics are optimistic estimates**.
  Full details: [docs/DATA_AND_EVALUATION.md](docs/DATA_AND_EVALUATION.md).
* **Metrics for the deployed model:** TODO-paste-the-table-from `scripts/calibrate_threshold.py`.
  Earlier training-run figures (0.790 accuracy, 0.542 recall) belong to a previous run whose weights were not saved, so they
  must not be read as this model's performance.
* **Threshold:** chosen on a tuning half of the hold-out to reach 85% sensitivity; every reported number comes from the test half.
  A higher sensitivity means more false alarms, an accepted trade-off for a screening tool.

## Known limitations

* DR only; no glaucoma or cataract; no Android app.
* Not clinically validated; retrospective public data; no external evaluation set; no patient-level split.
* Prototype security: bearer tokens without expiry, plain HTTP (use TLS in production), no user accounts.
* The clinic app runs on a laptop; offline inference on a phone would need the TFLite model packaged in a mobile app.
* No usability study with health workers was possible.
