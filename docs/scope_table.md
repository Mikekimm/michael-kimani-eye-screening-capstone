# Scope alignment and feature validation

Planned features come from the approved proposal (objectives 1.3.1, scope 1.5, ML approach 3.3,
architecture 3.4, use cases 3.5, tools 3.6) and the supervisor's feedback of 6 October.
Statuses: **Completed**, **Partial**, **Not implemented**, **Changed** (delivered differently, with the reason).
Evidence paths are relative to the repository root. Last updated 28 October 2026.

A classifier row is **Completed** when a trained model is served by the app and was measured on a held-out
test split. Whether it meets the proposal's performance targets is a separate row (5), so a weak model is
never hidden behind a "completed" label.

## Planned features

| # | Planned feature | Intended purpose | Current status | Evidence |
|---|---|---|---|---|
| 1 | DR classifier (MobileNetV2 transfer learning) | Detect diabetic retinopathy from a fundus photo | **Completed** (binary: no DR / DR present; v2.0 fine-tuned, threshold 0.418 chosen on validation) | `notebooks/dr_v2_finetune.ipynb` (with outputs), `models/dr/model_card.json`, `docs/models/evaluation/dr_v2/`, `scripts/dr_v2_metrics.py`; `test_notebook_metrics.py`, `test_dr_parity.py`, `test_classifier_integration.py` |
| 2 | Glaucoma classifier (ODIR-5K) | Multi-disease screening | **Completed, below target**: served and measured on a patient-separated test split (1,040 eyes, 42 positive): sensitivity 0.762, specificity 0.721, precision 0.103 | `notebooks/odir_glaucoma_cataract.ipynb`, `models/glaucoma/model_card.json`, `docs/models/odir_metrics.json`; `test_real_models_folder_registers_all_three_conditions` |
| 3 | Cataract classifier (ODIR-5K) | Multi-disease screening | **Completed, limited evidence**: sensitivity 0.978, specificity 0.962, precision 0.542 on 1,044 test eyes with only 46 positives | as row 2, `models/cataract/model_card.json` |
| 3b | Five-band cataract severity grading (1-5) | Grade how advanced a cataract is | **Not implemented** | ODIR-5K labels say only whether cataract is present in an eye; it has no severity grades, so a graded model cannot be trained or validated from it. Glaucoma and cataract are binary only (`severity_bands: false` in `backend/config/risk_policy.json`; the result card says "binary result only") |
| 4 | Preliminary risk / severity classification | Tell the worker how urgent a case is | **Completed (changed)**: for DR, a five-band *estimated* severity from the binary score, labelled as an estimate; glaucoma and cataract are binary (see 3b) | `backend/app/ml/risk_policy.py`, `backend/config/risk_policy.json`, `docs/models/risk_policy.md`, `test_risk_policy.py` |
| 5 | Meet >= 85% sensitivity and >= 80% specificity on a held-out test set; compare with Gulshan et al. (2016) | Safe screening trade-off, research question 3 | **Partial.** DR: sensitivity 0.851 **met**, specificity 0.748 **not met** (35,426 test images; held-out test split by image, no patient IDs available, near-duplicates could not be excluded; not external validation; not clinically validated). Glaucoma: both **not met**. Cataract: both met (46 positives). Gulshan et al. compared as a reference only (different data, model and operating point) | `docs/models/metrics.json`, `docs/models/odir_metrics.json`, `docs/models/data_and_evaluation.md`, `docs/testing/testing_report.md` section 6 |
| 6 | On-device TFLite inference | Screen without internet | **Changed**: the same TFLite files run on the server (LiteRT). Offline, the app captures and queues photos; they are scored after sync. Reason: one runtime for three models, model updates without app releases, and the checksum-verified registry; browser inference of three ~9 MB models was not built in the time available | `backend/app/ml/condition_model.py`, `frontend/src/offline/`; `docs/architecture.md` (deviations) |
| 7 | Android app (React Native) | Mobile client for health workers | **Changed**: installable PWA, mobile-first, one code base for Android and iPhone; tested on Android (Pixel 5) and iPhone (WebKit) emulation and on Chromium, Firefox and WebKit. Reason: no app-store build or device-specific code needed, and the proposal's iOS "future work" comes for free | `frontend/`, `frontend/vite.config.ts` (PWA manifest), `frontend/e2e/` |
| 8 | Offline local storage of records | Keep working with no connectivity | **Completed** (captures and new patients) | `frontend/src/offline/repository.ts` (IndexedDB), `syncQueue.test.ts` |
| 9 | Register patient | Identify who was screened | **Completed (changed)**: the proposal's class diagram stores name and date of birth; the app uses an app-generated pseudonymous code with a check character and year of birth only (privacy; synthetic data). Works offline; patients have no accounts | `backend/app/core/patient_codes.py`, `POST /api/patients`, E2E journey 1 |
| 10 | Capture retinal image | Get the photo into the system | **Completed** (camera with circular guide or gallery; left/right eye; patient consent required; no fundus lens hardware, per proposal 1.7) | `frontend/src/components/ImageCaptureGuide.tsx`, screenshot `*-04-capture.png` |
| 11 | Run screening | Preliminary result in seconds | **Completed** online (0.5 s median round trip); offline = queued | `backend/app/services/pipeline.py`, `docs/testing/benchmarks/` |
| 12 | View screening result | Act on the result | **Completed** (per-condition card, band, model version, action, measured model limits, disclaimer, emergency guidance, notice on results from earlier models) | `ScreeningResultCard.tsx`, `ScreeningView.tsx`, `results.test.tsx` |
| 13 | Automatic two-way sync | Push records, pull specialist decisions | **Completed** (idempotent push, backoff with jitter, pull since last sync) | `frontend/src/offline/syncQueue.ts`, `backend/app/services/sync.py`, `test_sync_pull_returns_only_new_decisions` |
| 14 | Flag uncertain / high-risk cases for referral | Structured referral pathway | **Completed**: as in the proposal, uncertain cases (borderline results, usable photos with quality warnings) are flagged and queued automatically; clear positives show "Refer recommended" and the health worker sends them with "Ask a specialist"; clear negatives are not queued (all configurable in `risk_policy.json`). The health worker can add a question or send any case; severe results (DR band 4-5) default to urgent. Specialty routing (an extension) adds conditions and priority | `ReferralAdvisor` in `backend/app/ml/risk_policy.py`, `ScreeningService._build`, `POST /api/screenings/{id}/ask-specialist`, `test_recommendation_and_automatic_queueing_follow_the_policy`, `test_uncertain_case_is_queued_routine_and_the_health_worker_can_add_a_question`, `test_nothing_is_sent_to_a_specialist_automatically` (clear positives), E2E `journeys.spec.ts` |
| 15 | Specialist dashboard: review referred cases | Close the referral loop | **Completed**, asynchronous as in the proposal: a later confirmation, not a gate on the same-visit advice (queue shows the health worker's question, flagged conditions, who sent it, waiting time, overdue first; the decision returns at the next sync) | `frontend/src/pages/specialist.tsx`, `GET /api/reviews/queue`, E2E journey 2 |
| 16 | Approve or override diagnosis | Specialist confirmation | **Completed** (+ request retake, shown to the health worker as "Retake needed"; comment; override of any scored condition needs a reason) | `backend/app/services/reviews.py`, `test_specialist_can_override_a_glaucoma_result`, E2E journey 2 |
| 17 | Admin: manage user accounts | Control access | **Completed** (approve sign-up requests with the requested or another role, reject with a reason, create staff accounts, roles, activation; admins cannot change themselves) | `frontend/src/pages/admin.tsx`, `PATCH /api/admin/users/{id}`, `test_rbac.py`, `approval.spec.ts` |
| 18 | Admin: analytics dashboard | See screening and referral patterns | **Completed** (aggregates only, including overdue reviews) | `GET /api/admin/analytics`, `test_analytics_are_aggregates_only` |
| 19 | Cloud backend: FastAPI + PostgreSQL | Central store and API | **Completed**: SQLite locally; the backend test suite runs against PostgreSQL 16 in CI ([run #1](https://github.com/Mikekimm/michael-kimani-eye-screening-capstone/actions/runs/40503709691), [run #2](https://github.com/Mikekimm/michael-kimani-eye-screening-capstone/actions/runs/40503744036)); Docker images built in CI, full stack not started locally | `backend/`, `backend/alembic/`, `docker-compose.yml`, `.github/workflows/ci.yml` |
| 20 | Load balancer | Scale to many clinics | **Not implemented** | The API is stateless (JWT), so instances can be added behind one; the in-memory rate limits would then need a shared store |
| 21 | Test sync under connectivity interruptions | Prove reliability (objective 4) | **Completed** | `syncQueue.test.ts` (reply lost after save, offline mid-queue, backoff, retry limit) |
| 22 | Informal usability testing with health workers | Check the interface is usable | **Not implemented yet** | SUS kit in `docs/usability/`; no participants tested at the time of writing |
| 23 | UML design (use case, class, ERD, sequence, architecture) | Specify the system | **Completed**, regenerated from the code | `docs/architecture.md`, `docs/diagrams/` |

## Proposal compliance (checked against the approved proposal, 28 October 2026)

Every requirement in the proposal (objectives 1.3.1, research questions 1.4, scope 1.5, ML approach 3.3,
architecture 3.4, UML 3.5, tools 3.6, budget 1.7), with an honest status. The main deviation: the proposal
specifies React Native with on-device TensorFlow Lite; the app is a PWA with server-side inference, and offline
covers capture and queueing only.

| Proposal section | Requirement | Status | Evidence |
|---|---|---|---|
| 1.3.1 O1 | Review literature and existing AI retinal-screening and offline-first mHealth tools | **Met** | Proposal chapter 2 (nine sources); gap: no tool combines three conditions, offline use and referral |
| 1.3.1 O2 | Design architecture, database schema and user workflows (offline-first, referral pathway) | **Met** | `docs/architecture.md`, `docs/diagrams/` (use case, class, ERD, sequence, architecture), Alembic migrations |
| 1.3.1 O3 | Prototype with an on-device classification model, a mobile screening app and a specialist dashboard | **Partial** | Mobile-first installable PWA and specialist dashboard built; the TFLite models run on the server, not on the device (deviation below) |
| 1.3.1 O4 | Evaluate against >= 85% sensitivity and >= 80% specificity, compare with Gulshan et al. (2016), test sync under simulated interruptions | **Partial** | DR sensitivity 0.851 met, specificity 0.748 not met; glaucoma below both; cataract met (46 positive test eyes); Gulshan compared as reference only; sync interruption tests pass (`syncQueue.test.ts`) |
| 1.4 RQ1 | Gaps in mobile retinal screening tools | **Met** | Answered by the literature review in the proposal |
| 1.4 RQ2 | Architecture and sync design for reliable offline-first use | **Met (emulated)** | IndexedDB queue, idempotent push on client UUID, backoff with jitter, decision pull; tested with lost replies and offline mid-queue; no field test |
| 1.4 RQ3 | How accurately can an on-device model classify DR, glaucoma and cataract from low-cost fundus-attachment images | **Partial** | Measured on public-dataset test splits, not on smartphone-lens images, and run on the server; figures above with their caveats |
| 1.4 RQ4 | How effectively does the referral workflow connect health workers to specialists once connectivity returns | **Partial** | Workflow built and tested end to end (E2E on four browser profiles); effectiveness with real users not measured (no usability study) |
| 1.5 | Prototype, not a regulator-approved product; public labelled datasets only | **Met** | Disclaimers on every result screen; Kaggle datasets only |
| 1.5 | Small informal user test with primary health workers | **Not met** | SUS kit in `docs/usability/`; no participants yet |
| 1.5 / 3.6 | Android app in React Native, iOS as future work | **Changed** | Installable PWA (React + Vite) for Android and iPhone; tested in emulation on Chromium, Firefox and WebKit |
| 1.5 | Scope limited to DR, glaucoma and cataract; refractive errors excluded | **Met** | Three models; no refraction features |
| Abstract | Preliminary risk classification in about a second | **Met online** | 0.44 s median upload-to-result; 2.73 s on an emulated slow phone and slow 3G; offline photos are scored after sync |
| Abstract / 3.4 | Screening runs on the device while offline | **Not met** | Offline covers capture and queueing only; scoring happens on the server after sync |
| 3.3 | Transfer learning (MobileNetV2 or EfficientNet-Lite), one fine-tuned model per condition, TFLite | **Met** | Three MobileNetV2 models, TFLite files with checksums (`models/<condition>/`) |
| 3.3 | APTOS 2019 for DR severity | **Changed** | DR trained on the Kaggle EyePACS + APTOS + Messidor set as binary (no DR / DR); the 1-5 band is an estimate from the score, not a grade |
| 3.3 | ODIR-5K for glaucoma and cataract presence | **Met** | Patient-separated split; `docs/models/odir_metrics.json` |
| 3.3 | Sensitivity prioritised as the primary metric | **Met** | Thresholds chosen on validation for >= 85% sensitivity |
| 3.4 | Local data store for offline patient records | **Met (changed tool)** | IndexedDB instead of SQLite (WatermelonDB/Realm), because the client is a PWA |
| 3.4 | Cloud backend (FastAPI + PostgreSQL), two-way sync: push records, pull specialist decisions | **Met** | `POST /api/sync/push`, `GET /api/sync/pull`; backend suite on PostgreSQL 16 in CI; SQLite locally |
| 3.4 | Load balancer in front of the API | **Not met** | Not built; the API is stateless (JWT) so it could scale behind one |
| 3.5 use cases | Health worker: register patient, capture image, run screening, view result, sync | **Met except offline screening** | Patient stored as a pseudonymous code and year of birth instead of name and date of birth (privacy) |
| 3.5 use cases | Specialist: review referred case, approve or override; admin: manage users, analytics | **Met** | Plus request retake and comment; admin approves sign-up requests; analytics are aggregates only |
| 3.5 sequence | An uncertain case is flagged and queued automatically for the specialist | **Met** | Borderline results and usable low-quality photos are queued by the risk policy ("Queued automatically"); clear positives show "Refer recommended" for the health worker to send; configurable in `risk_policy.json`; `test_recommendation_and_automatic_queueing_follow_the_policy`. Queued when the server scores the photo (after sync if captured offline), not on the device |
| 3.5 sequence | Specialist decision is pulled back to the health worker | **Met** | Decision shown on the screening and in History ("Reviewed" / "Retake needed"), "New decisions" count on the home screen until opened; `GET /api/sync/pull`, `GET /api/screenings/new-decisions`; `test_sync_pull_returns_only_new_decisions`, `test_new_decision_shows_until_the_health_worker_opens_the_screening`; review is a later confirmation, not a gate on same-visit advice |
| 3.6 | Diagrams in draw.io / PlantUML | **Changed** | Mermaid sources rendered by a script (`docs/diagrams/src/`) |
| 1.7 | Budget $0 (open-source tools, free datasets, free-tier hosting; no fundus lens hardware) | **Met** | Render free plan blueprint (`render.yaml`); no hardware bought |

## Proposal sequence diagram, step by step (for the presentation)

| # | Step in the proposal's sequence diagram | Where it happens in the app | Code and test evidence |
|---|---|---|---|
| 1 | Health worker captures a retinal image | Screen -> patient -> eye -> camera or gallery -> Cancel / Analyse | `ScreenPage.tsx`, `ImageCaptureGuide.tsx`; `capture.spec.ts` |
| 2 | The app runs the screening (proposal: offline, on the device) | **Deviation:** the server scores it with every checksum-verified model; offline, the photo is queued on the device and scored after sync | `ScreeningPipeline`, `ModelRegistry`, `frontend/src/offline/syncQueue.ts`; `test_real_models_return_one_result_per_condition`, `syncQueue.test.ts` |
| 3 | The result is shown to the health worker | Result page: one card per condition, recommendation, disclaimer | `ScreeningView.tsx`, `ScreeningResultCard.tsx`; `results.test.tsx`, `journeys.spec.ts` |
| 4 | If the case is uncertain, the app flags it and queues it | The risk policy flags borderline results and low-quality photos and queues them automatically ("Queued automatically"); clear positives: "Refer recommended" + Ask a specialist | `ReferralAdvisor.queues_automatically`, `ScreeningService._build`, `config/risk_policy.json`; `test_recommendation_and_automatic_queueing_follow_the_policy`, `test_uncertain_case_is_queued_routine_and_the_health_worker_can_add_a_question` |
| 5 | Once connected, the queued case is synced to the specialist | Offline captures are pushed with backoff and scored; queued cases appear in the specialist's shared queue (My specialties / All cases), refreshing every 30 s | `SyncQueue`, `GET /api/reviews/queue`, `ReviewQueuePage`; `test_queue_puts_cases_matching_the_specialty_first`, `refresh.test.tsx` |
| 6 | The specialist reviews it | Take this case -> Case review: approve, override with a reason, request a retake, comment (append-only) | `ReviewService.take`, `ReviewService.review`; `test_take_assigns_the_case_and_others_see_it_as_taken`, `test_review_history_is_append_only` |
| 7 | The specialist sends the confirmed decision back | The decision is stored as a review event; the screening becomes Reviewed or Retake needed | `POST /api/reviews/{id}`; `test_approve_closes_the_referral`, `test_retake_request_comes_back_as_retake_needed` |
| 8 | The app pulls the decision back to the health worker | `GET /api/sync/pull`; the screening and History show it; home shows "New decisions" until opened | `useSync`, `GET /api/screenings/new-decisions`; `test_sync_pull_returns_only_new_decisions`, `test_new_decision_shows_until_the_health_worker_opens_the_screening`, `routing.spec.ts` |

## Added after the proposal (supervisor feedback and engineering needs)

| Feature | Purpose | Evidence |
|---|---|---|
| Sign-up request with admin approval | A stranger can ask for an account (name, email, password, requested role: health worker or specialist; admin cannot be requested) but cannot use it until an admin approves it; the requested role grants nothing; rejected accounts cannot sign in; a registered email cannot sign up again and the existing account is never changed. The admin may record the facility when approving; the app does not verify identity or qualifications | `services/auth.py`, `services/users.py`, `test_auth.py`, `approval.spec.ts` (incl. specialist request) |
| Fundus check (hard stop) | Refuse photos that are not retinal fundus photographs before any model runs; nothing saved | `FundusCheck` in `backend/app/ml/quality.py`, `scripts/evaluate_fundus_check.py` (3 of 25 real fundus photos wrongly refused, 0 of 77 non-eye images accepted; tuned on the same images, no face photos: optimistic), `test_non_eye_image_is_refused_and_nothing_is_saved`, E2E `capture.spec.ts` |
| Capture flow and remove screening | Cancel / Analyse, Retake / Upload another, Save / Discard; soft delete with a reason, photo file deleted, audit kept | `ScreenPage.tsx`, `ScreeningDetailPage.tsx`, `POST /api/screenings/{id}/discard`, `test_discard_hides_the_screening_keeps_the_audit_and_deletes_the_photo`, `capture.spec.ts` |
| Daily counts in the clinic time zone | Correct "screened today" around midnight | `services/daily_counts.py` (`TIME_ZONE`, default Africa/Kigali), `test_daily_counts.py` |
| Demo reset command | Clean data for the demo and video | `scripts/reset_demo_data.py`, `test_reset_demo_data.py` |
| Authentication and RBAC (Argon2, JWT refresh rotation, sign-in and sign-up rate limits, password rules) | Protect patient data; reconcile offline use with authentication (supervisor) | `backend/app/core/security.py`, `services/auth.py`, `core/throttle.py`, RBAC matrix (39 role-by-route cases + 13 signed-out checks) |
| Specialty routing (**extension beyond the proposal**, which lists only a single Specialist role) | Route each question to a specialist who covers that condition and show who is reviewing it. Ask form: conditions (pre-ticked from borderline or positive results), question, routine or urgent. Specialties per specialist (DR, glaucoma, cataract, general = all cases) set by the admin on approval or in user management. Queue: "My specialties" first, "All cases" tab; "Take this case" assigns it, others see "Taken by"; the health worker sees "Being reviewed by". Server checks: a health worker cannot take or decide; only open queued cases can be taken; a case taken by someone else cannot be decided. Overdue counts per priority for the admin | migration `c4e8a2f61b37`, `ReviewService.take`, `POST /api/reviews/{id}/take`, `test_routing.py`, `routing.test.tsx`, E2E `routing.spec.ts` |
| Shared asynchronous queue, auto-refresh | One shared queue (a "general" specialist sees all cases; a district specialist can serve several clinics); queue, home and history refresh every 30 s (`VITE_REFRESH_SECONDS`), paused while the tab is hidden; SMS / email notifications are future work. Specialists do not prescribe: approve, override with a reason, request a retake, comment | `frontend/src/lib/refresh.ts`, `refresh.test.tsx` |
| Review targets and overdue flag | Specialist review is asynchronous (proposal); for sent cases, urgent (signs detected) 24 h and routine 72 h targets, configurable. A design decision: the proposal sets no time limit | `services/review_targets.py`, `docs/models/risk_policy.md`, `test_review_targets.py`, `test_queue_and_screening_show_waiting_time_priority_and_overdue` |
| Image quality gate | Refuse unusable photos (blank, tiny, not a fundus photo) with a plain reason | `backend/app/ml/quality.py`, `test_blank_image_is_rejected_with_reason` |
| Model registry with SHA-256 check, model card and per-model preprocessing | Serve only verified models fed exactly as they were trained | `backend/app/ml/registry.py`, `model_card.py`, `test_each_model_card_names_the_resize_it_was_trained_with` |
| Eye laterality, model version per result, append-only review history | Supervisor's data-model corrections | `backend/app/models/entities.py`, `test_review_history_is_append_only` |
| Audit log | Accountability for logins, screenings, reviews, sign-up decisions, sent cases, removed screenings and user changes | `AuditEvent`, `test_audit_log_records_key_actions`, `test_rejecting_needs_a_reason_and_every_decision_is_audited` |
| About-the-model screen and per-result limits | Show provenance, threshold source, limitations and measured performance | `frontend/src/pages/AboutPage.tsx`, `ScreeningResultCard.tsx`, `GET /api/models` |

## Traceability: requirement -> implementation -> test -> evidence

| Requirement | Implementation | Endpoint / screen | Test | Status |
|---|---|---|---|---|
| Health worker can register and screen a patient | `PatientService`, `ScreeningService`, `ScreeningPipeline` | `POST /api/patients`, `POST /api/screenings`; Screen page | `test_real_models_return_one_result_per_condition`; E2E journey 1 | Completed |
| Only real, verified models produce results | `ModelRegistry` (checksum, resize from card) | `GET /api/models`; result cards | `test_registry.py`, `test_dr_parity.py`; `results.test.tsx` | Completed |
| Unusable and non-eye images are refused | `ScreeningPipeline.validate_upload`, `ImageQualityChecker`, `FundusCheck` | 413 / 422 | invalid-input tests in `test_screenings.py`, `test_non_eye_image_is_refused_and_nothing_is_saved`; `capture.spec.ts` | Completed |
| Cases the health worker sends reach a specialist | `ReferralAdvisor`, `ScreeningService.ask_specialist`, `ReviewTargets` | `POST /api/screenings/{id}/ask-specialist`, `GET /api/reviews/queue` | `test_asked_case_reaches_the_queue_with_the_question`, `test_nothing_is_sent_to_a_specialist_automatically` | Completed |
| Specialist decisions are never lost or rewritten | `ReviewEvent` ORM guards, `ReviewRepository` (add/read only) | `POST /api/reviews/{id}` | `test_review_history_is_append_only`; E2E journey 2 | Completed |
| Work continues offline, no duplicates on retry | `SyncQueue`, idempotent `client_uuid` | `POST /api/sync/push`, `GET /api/sync/pull` | `syncQueue.test.ts`; `test_resubmitting_same_client_uuid_is_idempotent` | Completed |
| Only approved accounts sign in | `AuthService.login`, `UserService.update` | `POST /api/auth/login`, Users screen | `test_auth.py`; `approval.spec.ts` | Completed |
| Each role sees only what it should | `require_roles`, `AccessPolicy` | all routes | `test_rbac.py`; E2E journey 3 | Completed |
| Admin sees aggregates without identifiers | `AnalyticsService` | `GET /api/admin/analytics` | `test_analytics_are_aggregates_only` | Completed |
| Sensitivity >= 85%, specificity >= 80% | DR v2 notebook; `scripts/dr_v2_metrics.py` | `docs/models/metrics.json`, About screen, result cards | `test_notebook_metrics.py` | Partial (DR sensitivity met, specificity not; glaucoma not met) |
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
