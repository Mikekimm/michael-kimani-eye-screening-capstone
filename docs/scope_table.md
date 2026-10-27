# Scope alignment and feature validation

Planned features come from the approved proposal (objectives 1.3.1, scope 1.5, ML approach 3.3,
architecture 3.4, use cases 3.5, tools 3.6) and the supervisor's feedback of 6 October.
Statuses: **Completed**, **Partial**, **Not implemented**, **Changed** (delivered differently, with the reason).
Evidence paths are relative to the repository root. Last updated 27 October 2026.

A classifier row is **Completed** when a trained model is served by the app and was measured on a held-out
test split. Whether it meets the proposal's performance targets is a separate row (5), so a weak model is
never hidden behind a "completed" label.

## Planned features

| # | Planned feature | Intended purpose | Current status | Evidence |
|---|---|---|---|---|
| 1 | DR classifier (MobileNetV2 transfer learning) | Detect diabetic retinopathy from a fundus photo | **Completed** (binary: no DR / DR present; v2.0 fine-tuned, threshold 0.418 chosen on validation) | `notebooks/dr_v2_finetune.ipynb` (with outputs), `models/dr/model_card.json`, `docs/evaluation/dr_v2/`, `scripts/dr_v2_metrics.py`; `test_notebook_metrics.py`, `test_dr_parity.py`, `test_classifier_integration.py` |
| 2 | Glaucoma classifier (ODIR-5K) | Multi-disease screening | **Completed, below target**: served and measured on a patient-separated test split (1,040 eyes, 42 positive): sensitivity 0.762, specificity 0.721, precision 0.103 | `notebooks/odir_glaucoma_cataract.ipynb`, `models/glaucoma/model_card.json`, `docs/odir_metrics.json`; `test_real_models_folder_registers_all_three_conditions` |
| 3 | Cataract classifier (ODIR-5K) | Multi-disease screening | **Completed, limited evidence**: sensitivity 0.978, specificity 0.962, precision 0.542 on 1,044 test eyes with only 46 positives | as row 2, `models/cataract/model_card.json` |
| 3b | Five-band cataract severity grading (1-5) | Grade how advanced a cataract is | **Not implemented** | ODIR-5K labels say only whether cataract is present in an eye; it has no severity grades, so a graded model cannot be trained or validated from it. Glaucoma and cataract are binary only (`severity_bands: false` in `backend/config/risk_policy.json`; the result card says "binary result only") |
| 4 | Preliminary risk / severity classification | Tell the worker how urgent a case is | **Completed (changed)**: for DR, a five-band *estimated* severity from the binary score, labelled as an estimate; glaucoma and cataract are binary (see 3b) | `backend/app/ml/risk_policy.py`, `backend/config/risk_policy.json`, `docs/risk_policy.md`, `test_risk_policy.py` |
| 5 | Meet >= 85% sensitivity and >= 80% specificity on a held-out test set; compare with Gulshan et al. (2016) | Safe screening trade-off, research question 3 | **Partial.** DR: sensitivity 0.851 **met**, specificity 0.748 **not met** (35,426 test images; held-out test split by image, no patient IDs available, near-duplicates could not be excluded; not external validation; not clinically validated). Glaucoma: both **not met**. Cataract: both met (46 positives). Gulshan et al. compared as a reference only (different data, model and operating point) | `docs/metrics.json`, `docs/odir_metrics.json`, `docs/data_and_evaluation.md`, `docs/testing_report.md` section 6 |
| 6 | On-device TFLite inference | Screen without internet | **Changed**: the same TFLite files run on the server (LiteRT). Offline, the app captures and queues photos; they are scored after sync. Reason: one runtime for three models, model updates without app releases, and the checksum-verified registry; browser inference of three ~9 MB models was not built in the time available | `backend/app/ml/condition_model.py`, `frontend/src/offline/`; `docs/architecture.md` (deviations) |
| 7 | Android app (React Native) | Mobile client for health workers | **Changed**: installable PWA, mobile-first, one code base for Android and iPhone; tested on Android (Pixel 5) and iPhone (WebKit) emulation and on Chromium, Firefox and WebKit. Reason: no app-store build or device-specific code needed, and the proposal's iOS "future work" comes for free | `frontend/`, `frontend/vite.config.ts` (PWA manifest), `frontend/e2e/` |
| 8 | Offline local storage of records | Keep working with no connectivity | **Completed** (captures and new patients) | `frontend/src/offline/repository.ts` (IndexedDB), `syncQueue.test.ts` |
| 9 | Register patient | Identify who was screened | **Completed** (app-generated pseudonymous code with a check character, also offline; minimal fields; patients have no accounts) | `backend/app/core/patient_codes.py`, `POST /api/patients`, E2E journey 1 |
| 10 | Capture retinal image | Get the photo into the system | **Completed** (camera with circular guide or gallery; left/right eye; patient consent required; no fundus lens hardware, per proposal 1.7) | `frontend/src/components/ImageCaptureGuide.tsx`, screenshot `*-04-capture.png` |
| 11 | Run screening | Preliminary result in seconds | **Completed** online (0.5 s median round trip); offline = queued | `backend/app/services/pipeline.py`, `docs/benchmarks/` |
| 12 | View screening result | Act on the result | **Completed** (per-condition card, band, model version, action, measured model limits, disclaimer, emergency guidance, notice on results from earlier models) | `ScreeningResultCard.tsx`, `ScreeningView.tsx`, `results.test.tsx` |
| 13 | Automatic two-way sync | Push records, pull specialist decisions | **Completed** (idempotent push, backoff with jitter, pull since last sync) | `frontend/src/offline/syncQueue.ts`, `backend/app/services/sync.py`, `test_sync_pull_returns_only_new_decisions` |
| 14 | Flag uncertain / high-risk cases for referral | Structured referral pathway | **Completed** (automatic for positive and borderline; manual "refer anyway"; waiting time and review target shown) | `RiskPolicy.auto_refer`, `ReviewTargets`, `POST /api/screenings/{id}/refer`, `test_workflow.py` |
| 15 | Specialist dashboard: review referred cases | Close the referral loop | **Completed** (queue shows flagged conditions, who referred and from which facility, waiting time, overdue first) | `frontend/src/pages/specialist.tsx`, `GET /api/reviews/queue`, E2E journey 2 |
| 16 | Approve or override diagnosis | Specialist confirmation | **Completed** (+ request retake, comment; override of any scored condition needs a reason) | `backend/app/services/reviews.py`, `test_specialist_can_override_a_glaucoma_result`, E2E journey 2 |
| 17 | Admin: manage user accounts | Control access | **Completed** (approve or reject sign-ups with a reason, create staff accounts, roles, activation; admins cannot change themselves) | `frontend/src/pages/admin.tsx`, `PATCH /api/admin/users/{id}`, `test_rbac.py`, `approval.spec.ts` |
| 18 | Admin: analytics dashboard | See screening and referral patterns | **Completed** (aggregates only, including overdue reviews) | `GET /api/admin/analytics`, `test_analytics_are_aggregates_only` |
| 19 | Cloud backend: FastAPI + PostgreSQL | Central store and API | **Completed**: SQLite locally; the backend test suite runs against PostgreSQL 16 in CI ([run #1](https://github.com/Mikekimm/michael-kimani-eye-screening-capstone/actions/runs/40503709691), [run #2](https://github.com/Mikekimm/michael-kimani-eye-screening-capstone/actions/runs/40503744036)); Docker images built in CI, full stack not started locally | `backend/`, `backend/alembic/`, `docker-compose.yml`, `.github/workflows/ci.yml` |
| 20 | Load balancer | Scale to many clinics | **Not implemented** | The API is stateless (JWT), so instances can be added behind one; the in-memory rate limits would then need a shared store |
| 21 | Test sync under connectivity interruptions | Prove reliability (objective 4) | **Completed** | `syncQueue.test.ts` (reply lost after save, offline mid-queue, backoff, retry limit) |
| 22 | Informal usability testing with health workers | Check the interface is usable | **Not implemented yet** | SUS kit in `docs/usability/`; no participants tested at the time of writing |
| 23 | UML design (use case, class, ERD, sequence, architecture) | Specify the system | **Completed**, regenerated from the code | `docs/architecture.md`, `docs/diagrams/` |

## Added after the proposal (supervisor feedback and engineering needs)

| Feature | Purpose | Evidence |
|---|---|---|
| Sign-up with admin approval | A stranger can ask for an account but cannot use it until an admin approves it; rejected accounts cannot sign in | `services/auth.py`, `test_pending_account_cannot_sign_in_until_an_admin_approves_it`, `approval.spec.ts` |
| Admin-managed facility list | Sign-up picks a facility from the list; free text is refused by the server | `services/facilities.py`, `test_facilities.py`, `test_free_text_or_inactive_facility_is_refused` |
| Registration number recorded for review | The admin checks it offline; the app never claims it is verified | sign-up and Users screens, admin email text |
| Authentication and RBAC (Argon2, JWT refresh rotation, sign-in and sign-up rate limits, password rules) | Protect patient data; reconcile offline use with authentication (supervisor) | `backend/app/core/security.py`, `services/auth.py`, `core/throttle.py`, RBAC matrix (42 role-by-route cases + 14 signed-out checks) |
| Review targets and overdue flag | Specialist review is asynchronous; urgent (signs detected) 24 h and routine 72 h targets, configurable. A design decision: the proposal sets no time limit | `services/review_targets.py`, `docs/risk_policy.md`, `test_review_targets.py`, `test_queue_and_screening_show_waiting_time_priority_and_overdue` |
| Image quality gate | Refuse unusable photos with a plain reason | `backend/app/ml/quality.py`, `test_blank_image_is_rejected_with_reason` |
| Model registry with SHA-256 check, model card and per-model preprocessing | Serve only verified models fed exactly as they were trained | `backend/app/ml/registry.py`, `model_card.py`, `test_each_model_card_names_the_resize_it_was_trained_with` |
| Eye laterality, model version per result, append-only review history | Supervisor's data-model corrections | `backend/app/models/entities.py`, `test_review_history_is_append_only` |
| Audit log | Accountability for logins, screenings, reviews, approvals, facility and user changes | `AuditEvent`, `test_audit_log_records_key_actions`, `test_rejecting_needs_a_reason_and_every_decision_is_audited` |
| About-the-model screen and per-result limits | Show provenance, threshold source, limitations and measured performance | `frontend/src/pages/AboutPage.tsx`, `ScreeningResultCard.tsx`, `GET /api/models` |

## Traceability: requirement -> implementation -> test -> evidence

| Requirement | Implementation | Endpoint / screen | Test | Status |
|---|---|---|---|---|
| Health worker can register and screen a patient | `PatientService`, `ScreeningService`, `ScreeningPipeline` | `POST /api/patients`, `POST /api/screenings`; Screen page | `test_real_models_return_one_result_per_condition`; E2E journey 1 | Completed |
| Only real, verified models produce results | `ModelRegistry` (checksum, resize from card) | `GET /api/models`; result cards | `test_registry.py`, `test_dr_parity.py`; `results.test.tsx` | Completed |
| Unusable images are refused | `ScreeningPipeline.validate_upload`, `ImageQualityChecker` | 413 / 422 | invalid-input tests in `test_screenings.py`; E2E journey 4 | Completed |
| Uncertain / positive cases reach a specialist | `RiskPolicy`, `Referral`, `ReviewTargets` | `GET /api/reviews/queue` | `test_positive_result_is_referred_and_queued`, `test_borderline_negative_is_referred_as_uncertain` | Completed |
| Specialist decisions are never lost or rewritten | `ReviewEvent` ORM guards, `ReviewRepository` (add/read only) | `POST /api/reviews/{id}` | `test_review_history_is_append_only`; E2E journey 2 | Completed |
| Work continues offline, no duplicates on retry | `SyncQueue`, idempotent `client_uuid` | `POST /api/sync/push`, `GET /api/sync/pull` | `syncQueue.test.ts`; `test_resubmitting_same_client_uuid_is_idempotent` | Completed |
| Only approved accounts sign in | `AuthService.login`, `UserService.update` | `POST /api/auth/login`, Users screen | `test_auth.py`; `approval.spec.ts` | Completed |
| Each role sees only what it should | `require_roles`, `AccessPolicy` | all routes | `test_rbac.py`; E2E journey 3 | Completed |
| Admin sees aggregates without identifiers | `AnalyticsService` | `GET /api/admin/analytics` | `test_analytics_are_aggregates_only` | Completed |
| Sensitivity >= 85%, specificity >= 80% | DR v2 notebook; `scripts/dr_v2_metrics.py` | `docs/metrics.json`, About screen, result cards | `test_notebook_metrics.py` | Partial (DR sensitivity met, specificity not; glaucoma not met) |
| Usable on low-end phones and several browsers | PWA, code splitting | all screens | Playwright on Chromium/Firefox/WebKit; throttled round trip; Lighthouse | Completed (emulated devices; physical-phone test pending) |

## Why the scope changed

The supervisor asked for a feasible offline prototype with a named user and one demonstrable
workflow, for offline inference to be reconciled with sync and authentication, and for research
evaluation to be separated from software development. Depth went first into one complete, tested
workflow (capture, screen, refer, review, decision returned, offline queue); the registry then made
adding the glaucoma and cataract models a data task with no code change. The platform moved from a
React Native Android app with on-device TensorFlow Lite to an installable PWA with server-side
inference: one code base for Android and iPhone, and models that can be replaced and verified on the
server. The cost is that a photo taken offline is scored only after it syncs.
