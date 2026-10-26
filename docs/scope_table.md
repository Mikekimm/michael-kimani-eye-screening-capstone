# Scope alignment and feature validation

Planned features come from the approved proposal (objectives 1.3.1, scope 1.5, ML approach 3.3,
architecture 3.4, use cases 3.5, tools 3.6) and the supervisor's feedback of 6 October.
Statuses: **Completed**, **Partial**, **Not implemented**, **Changed** (delivered differently, with the reason).
Evidence paths are relative to the repository root. Last updated 26 October 2026.

## Planned features

| # | Planned feature | Intended purpose | Current status | Evidence |
|---|---|---|---|---|
| 1 | DR classifier (MobileNetV2 transfer learning) | Detect diabetic retinopathy from a fundus photo | **Completed** (binary: no DR / DR present) | `notebooks/model_notebook.ipynb`, `models/dr/model_card.json`, `backend/app/ml/condition_model.py`; real-model tests in `backend/tests/api/test_screenings.py` |
| 2 | Glaucoma classifier (ODIR-5K) | Multi-disease screening | **Not implemented** | No model trained. The app shows "Model not available yet" with no score (`backend/app/ml/registry.py`, screenshot `docs/screenshots/e2e/mobile-chromium-05-result.png`). Adding one is a drop-in folder (`test_dropping_a_valid_model_folder_registers_it_without_code_changes`) |
| 3 | Cataract classifier (ODIR-5K) | Multi-disease screening | **Not implemented** | As row 2 |
| 4 | Preliminary risk / severity classification | Tell the worker how urgent a case is | **Completed (changed)**: five-band *estimated* severity from the binary score, labelled as an estimate | `backend/app/ml/risk_policy.py`, `backend/config/risk_policy.json`, `docs/risk_policy.md`, 26 tests in `test_risk_policy.py` |
| 5 | Meet >= 85% sensitivity and >= 80% specificity; compare with Gulshan et al. (2016) | Safe screening trade-off, research question 3 | **Partial**: protocol and tooling complete, hold-out run pending | `notebooks/kaggle_holdout_eval.ipynb`, `scripts/calibrate_threshold.py`, `backend/app/ml/metrics_report.py`, `docs/testing_report.md` section 6 |
| 6 | On-device TFLite inference | Screen without internet | **Changed**: TFLite (LiteRT) runs on the server; offline captures are queued and analysed after sync | `backend/app/ml/condition_model.py`; reason in `docs/architecture.md` (deviations) |
| 7 | Android app (React Native) | Mobile client for health workers | **Changed**: installable PWA, mobile-first, tested on Android (Pixel 5) and iPhone (WebKit) emulation | `frontend/`, `frontend/vite.config.ts` (PWA manifest), `frontend/e2e/` |
| 8 | Offline local storage of records | Keep working with no connectivity | **Completed** (captures and new patients) | `frontend/src/offline/repository.ts` (IndexedDB), `syncQueue.test.ts` |
| 9 | Register patient | Identify who was screened | **Completed** (pseudonymous clinic code, minimal fields) | `backend/app/services/patients.py`, `POST /api/patients`, E2E journey 1 |
| 10 | Capture retinal image | Get the photo into the system | **Completed** (camera with circular guide or gallery; left/right eye; no fundus lens hardware, per proposal 1.7) | `frontend/src/components/ImageCaptureGuide.tsx`, screenshot `*-04-capture.png` |
| 11 | Run screening | Preliminary result in seconds | **Completed** online (0.5 s median round trip); offline = queued | `backend/app/services/pipeline.py`, `docs/benchmarks/` |
| 12 | View screening result | Act on the result | **Completed** (per-condition card, band, model version, action, disclaimer) | `frontend/src/components/ScreeningResultCard.tsx`, `results.test.tsx` |
| 13 | Automatic two-way sync | Push records, pull specialist decisions | **Completed** (idempotent push, backoff with jitter, pull since last sync) | `frontend/src/offline/syncQueue.ts`, `backend/app/services/sync.py`, `test_sync_pull_returns_only_new_decisions` |
| 14 | Flag uncertain / high-risk cases for referral | Structured referral pathway | **Completed** (automatic for positive and borderline; manual "refer anyway") | `RiskPolicy.auto_refer`, `POST /api/screenings/{id}/refer`, `test_workflow.py` |
| 15 | Specialist dashboard: review referred cases | Close the referral loop | **Completed** | `frontend/src/pages/specialist.tsx`, `GET /api/reviews/queue`, E2E journey 2 |
| 16 | Approve or override diagnosis | Specialist confirmation | **Completed** (+ request retake, comment; override needs a reason) | `backend/app/services/reviews.py`, `test_override_requires_condition_result_and_reason` |
| 17 | Admin: manage user accounts | Control access | **Completed** (roles, activation; admins cannot change themselves) | `frontend/src/pages/admin.tsx`, `PATCH /api/admin/users/{id}`, `test_rbac.py` |
| 18 | Admin: analytics dashboard | See screening and referral patterns | **Completed** (aggregates only) | `GET /api/admin/analytics`, `test_analytics_are_aggregates_only` |
| 19 | Cloud backend: FastAPI + PostgreSQL | Central store and API | **Completed** with SQLite; **Partial** for PostgreSQL (configured via `DATABASE_URL`, Docker stack written, not yet run) | `backend/`, `backend/alembic/`, `docker-compose.yml` |
| 20 | Load balancer | Scale to many clinics | **Not implemented** | Stateless JWT API allows horizontal scaling; not meaningful for a single-instance prototype |
| 21 | Test sync under connectivity interruptions | Prove reliability (objective 4) | **Completed** | `syncQueue.test.ts` (reply lost after save, offline mid-queue, backoff, retry limit) |
| 22 | Informal usability testing with health workers | Check the interface is usable | **Not implemented yet** | Planned SUS questionnaire; no participants tested at the time of writing |
| 23 | UML design (use case, class, ERD, sequence, architecture) | Specify the system | **Completed**, regenerated from the code | `docs/architecture.md`, `docs/diagrams/` |

## Added after the proposal (supervisor feedback and engineering needs)

| Feature | Purpose | Evidence |
|---|---|---|
| Authentication and RBAC (Argon2, JWT refresh rotation) | Protect patient data; reconcile offline use with authentication (supervisor) | `backend/app/core/security.py`, `services/auth.py`, 45-case RBAC matrix |
| Image quality gate | Refuse unusable photos with a plain reason | `backend/app/ml/quality.py`, `test_blank_image_is_rejected_with_reason` |
| Model registry with SHA-256 check and model card | Serve only verified models; honest "not available" state | `backend/app/ml/registry.py`, `models/dr/model_card.json` |
| Eye laterality, model version per result, append-only review history | Supervisor's data-model corrections | `backend/app/models/entities.py`, `test_review_history_is_append_only` |
| Audit log | Accountability for logins, screenings, reviews, user changes | `AuditEvent`, `test_audit_log_records_key_actions` |
| About-the-model screen | Show provenance, threshold source, limitations, metric status | `frontend/src/pages/AboutPage.tsx`, `GET /api/models` |
| Reproducible hold-out protocol | Separate research evaluation from software testing (supervisor) | `notebooks/kaggle_holdout_eval.ipynb` |

## Traceability: requirement -> implementation -> test -> evidence

| Requirement | Implementation | Endpoint / screen | Test | Status |
|---|---|---|---|---|
| Health worker can register and screen a patient | `PatientService`, `ScreeningService`, `ScreeningPipeline` | `POST /api/patients`, `POST /api/screenings`; Screen page | `test_real_model_returns_one_result_per_condition`; E2E journey 1 | Completed |
| Only real models produce results | `ModelRegistry` (checksum), `NOT_AVAILABLE` outcome | `GET /api/models`; result cards | `test_registry.py`; `results.test.tsx` (no score for missing model) | Completed |
| Unusable images are refused | `ScreeningPipeline.validate_upload`, `ImageQualityChecker` | 413 / 422 | 9 invalid-input tests in `test_screenings.py`; E2E journey 4 | Completed |
| Uncertain / positive cases reach a specialist | `RiskPolicy`, `Referral` | `GET /api/reviews/queue` | `test_positive_result_is_referred_and_queued`, `test_borderline_negative_is_referred_as_uncertain` | Completed |
| Specialist decisions are never lost or rewritten | `ReviewEvent` ORM guards, `ReviewRepository` (add/read only) | `POST /api/reviews/{id}` | `test_review_history_is_append_only`; E2E journey 2 | Completed |
| Work continues offline, no duplicates on retry | `SyncQueue`, idempotent `client_uuid` | `POST /api/sync/push`, `GET /api/sync/pull` | `syncQueue.test.ts`; `test_resubmitting_same_client_uuid_is_idempotent` | Completed |
| Each role sees only what it should | `require_roles`, `AccessPolicy` | all routes | `test_rbac.py` (45); E2E journey 3 | Completed |
| Admin sees aggregates without identifiers | `AnalyticsService` | `GET /api/admin/analytics` | `test_analytics_are_aggregates_only` | Completed |
| Sensitivity >= 85%, specificity >= 80% | calibration and metrics report | `docs/metrics.json`, About screen | `test_metrics_report.py` (pipeline only) | Pending hold-out run |
| Usable on low-end phones and several browsers | PWA, code splitting | all screens | Playwright on Chromium/Firefox/WebKit; throttled round trip; Lighthouse | Completed (emulated devices) |

## Why the scope changed

The supervisor asked for a feasible offline prototype with a named user and one demonstrable
workflow, for offline inference to be reconciled with sync and authentication, and for research
evaluation to be separated from software development. Depth was therefore put into one complete,
tested workflow for diabetic retinopathy (capture, screen, refer, review, decision returned, offline
queue) rather than three shallow classifiers. Glaucoma and cataract are kept visible as "not available
yet" so the multi-disease design is real and honest, and the registry makes adding them a data task
rather than a code change.
