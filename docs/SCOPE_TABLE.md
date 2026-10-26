# Scope alignment: planned vs delivered

Planned features come from the approved proposal (sections 1.3, 3.3, 3.4, 3.5, 3.6) and the three
supervisor revisions. **Evidence** points to files in this repository.

| # | Planned feature | Intended purpose | Status | Evidence / justification |
|---|---|---|---|---|
| 1 | DR classification (transfer learning, MobileNetV2) | Detect referable diabetic retinopathy from a fundus photo | **Completed** (model); targets **pending** hold-out run | `models/dr_screening_model.h5`, `notebooks/model_notebook.ipynb`, `scripts/calibrate_threshold.py` |
| 2 | Meet 85% sensitivity / 80% specificity | Safe screening trade-off | **Partial** | Threshold selection algorithm implemented and tested (`src/thresholding.py`); the final figures come from the hold-out run (see DATA_AND_EVALUATION.md). If the targets are not met this is reported as not met, with the sensitivity/specificity trade-off shown. |
| 3 | Glaucoma classifier (ODIR-5K) | Multi-disease screening | **Not implemented** | Out of reach in the available time; the classifier interface (`BaseClassifier`) lets further conditions be added without changing the app. Listed as future work. |
| 4 | Cataract classifier (ODIR-5K) | Multi-disease screening | **Not implemented** | As above. |
| 5 | On-device inference with TensorFlow Lite | Screening with no internet | **Partial** | `TFLiteClassifier` and `models/dr_screening_model.tflite` run locally and agree with the Keras model within 0.05 (`tests/test_classifier_integration.py`). Runs on a laptop, not yet packaged for Android. |
| 6 | Android app (React Native) | Mobile client for health workers | **Not implemented (changed)** | Replaced by a Streamlit clinic app (`app.py`) so the full workflow could be built and tested in one semester. All logic is in `src/`, so a mobile front end could call the same code or REST contract. |
| 7 | Offline local storage of patient records | Keep working with no connectivity | **Completed** | `src/storage.py` (SQLite). Retains image, laterality, model version, threshold, score and review history. `tests/test_storage.py` |
| 8 | Image capture / register patient | Identify who was screened | **Completed (changed)** | Images are uploaded rather than captured live (no fundus lens hardware, per proposal 1.7). Patients are identified by a pseudonymous code only (no name or date of birth) to minimise personal data. |
| 9 | Automatic offline-to-online sync (two-way) | Push queued records, pull specialist decisions | **Completed** | `src/sync.py`, `src/api_client.py`; idempotent, stops cleanly when offline. Tested with connection drops. `tests/test_sync.py`, `tests/test_api_integration.py` |
| 10 | Flag uncertain / high-risk cases and queue them | Structured referral | **Completed** | `ScreeningResult.needs_review` (flagged or within +/-0.10 of the threshold). `tests/test_result_review_flag.py` |
| 11 | Specialist dashboard: review, approve or override | Close the referral loop | **Completed (changed)** | Streamlit portal `specialist_app.py` instead of a React web app. Decisions are append-only history (`reviews` table). |
| 12 | Cloud backend (FastAPI + PostgreSQL) | Central store and API | **Partial (changed)** | REST backend on the Python standard library with SQLite (`src/server.py`) keeping the same REST contract. Chosen so the project runs with no extra services; the `ScreeningRepository` boundary is where PostgreSQL would plug in. |
| 13 | Authentication and roles | Protect patient data | **Partial** | Bearer tokens with clinician / specialist / admin roles, constant-time comparison, reviewer identity taken from the token (`src/server.py`). No user accounts, passwords, token expiry or TLS in the prototype. |
| 14 | Admin: manage accounts, analytics | Observe prevalence and referral patterns | **Partial** | Aggregate statistics endpoint and metrics (`/api/stats`). Account management not implemented. |
| 15 | Load balancer in front of the API | Scale to many clinics | **Not implemented** | Not meaningful for a single-process prototype; documented as production work. |
| 16 | Test sync under simulated connectivity interruptions | Prove reliability | **Completed** | `test_connection_drop_mid_cycle_resumes_where_it_stopped`, `test_offline_then_online_full_loop`, `test_server_going_down_mid_session_keeps_new_data_pending` |
| 17 | Compare with published baseline (Gulshan et al.) | Context for results | **Partial** | Reported as a reference only, with the reasons the comparison is not like-for-like (DATA_AND_EVALUATION.md section 3). |
| 18 | Informal usability testing with primary health workers | Check the interface is usable | **Not done** | No participants were available in the time; stated as a limitation. |
| + | Image quality check (not in proposal) | Refuse blank or tiny images, warn on blur / darkness / not-a-fundus | **Added** | `src/quality.py`, `tests/test_quality.py` |
| + | Sensitivity-targeted threshold, AUC, bootstrap intervals, tune/test split (not in proposal) | Make the evaluation honest | **Added** | `src/thresholding.py`, `src/evaluation.py` |

## Why the scope changed

The proposal described a three-disease Android system. After the supervisor's review (a feasible offline
research prototype with one named user and one demonstrable workflow), the delivered scope is a
**single-disease (DR) offline-first prototype with a complete, tested screen -> save -> sync -> specialist
review -> decision-returned loop**. Depth on one condition and on the offline/sync architecture was chosen over
breadth, because the supervisor asked for the architecture to be reconciled (offline inference with cloud
synchronisation and authentication) and for an evaluation that can be defended.
