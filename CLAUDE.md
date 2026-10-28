# CLAUDE.md: Eye Disease Screening Capstone (spec and working rules)

Read this fully before any change. If an instruction conflicts with this file, stop and ask.

## 1. Project summary
Offline-first retinal screening app for primary health centres (ALU BSc Software Engineering capstone,
Michael Kimani, supervisor Emmanuel Adjei). A health worker uploads/captures a fundus image of a patient's
left or right eye; the system checks image quality, runs every available trained model, and returns a
structured screening result with a recommended action and, when needed, a referral to a specialist.
**Screening and referral support only. Not a diagnostic device. Never present it as one.**
Intended deployment context: primary health centres in low-resource settings in Africa. This is the intended
context only. Do not name a country; only public datasets were used and there was no field validation.

## 2. Scope (from the approved proposal)
- Conditions: diabetic retinopathy (DR), glaucoma, cataract.
- Actors: health worker, specialist, admin (proposal use-case diagram).
- Planned stack in proposal: React Native, SQLite, on-device TFLite, FastAPI + PostgreSQL, React dashboard.
- Delivered direction (documented deviation): React + Vite PWA instead of React Native; server-side TFLite
  inference; offline = capture + queue + sync, not offline inference (stretch goal only).
- Every deviation must be listed with its reason in `docs/scope_table.md`.

## 3. ML models and honesty rules
- DR v2.0 (served): binary MobileNetV2 (0 = no DR, 1 = DR present, ICDR grades 1-4) fine-tuned from
  `block_13_expand`, Kaggle `ascanipek/eyepacs-aptos-messidor-diabetic-retinopathy`,
  `notebooks/dr_v2_finetune.ipynb`. Input 224x224, BILINEAR anti-aliased resize, pixel / 127.5 - 1. The
  resize comes from each model card (`input.interpolation` / `input.resize`); never hard-code it.
- **DR metrics** (`docs/metrics.json`, written by `scripts/dr_v2_metrics.py`, which recomputes them from the
  notebook's predictions with the app's code): threshold 0.418 chosen on validation; test split of 35,426
  images: sensitivity 0.851, specificity 0.748, precision 0.706, AUC 0.900. Sensitivity target met,
  **specificity target not met**. Always label them: "held-out test split by image (no patient IDs available;
  near-duplicates could not be excluded); not external validation; not clinically validated".
  Never estimate numbers; only use values in results.json, the model cards or the metrics files.
- DR v0.3 (retired): validation-fold results only (sensitivity 0.542, threshold 0.5), kept as history in
  `docs/evaluation/dr_v1_metrics.json`. Its independent hold-out run never finished; never call those figures a test set.
- Glaucoma and cataract (served): ODIR-5K, binary only (no severity labels), patient-separated split.
  Glaucoma: sensitivity 0.762, specificity 0.721, precision 0.103 on 1,040 eyes (42 positive): below both
  targets, limited evidence; always show its precision. Cataract: 0.978 / 0.962 / 0.542 on 1,044 eyes
  (46 positive): meets targets, limited evidence. ODIR labels are free-text keywords and may be noisy.
- A condition without a valid model folder still shows `model_available=false` / "Model not available yet".
- Severity band 1-5 for a binary model is an **estimate** from a documented, configurable `RiskPolicy`,
  labelled "Estimated severity band". It is not a clinical grade. Never claim calibration not measured.
- No random, dummy, mocked or hard-coded probabilities outside clearly labelled test fixtures.
- Known limitations to state: no patient IDs in dataset (image-level split only, optimistic metrics),
  augmented near-duplicates, no external evaluation, images are not from low-cost smartphone lenses.

Design patterns that must be visible in code:
- `ConditionModel` interface -> `TFLiteConditionModel`.
- `ModelRegistry`: discovers `models/<condition>/model.tflite` + `model_card.json`, verifies sha256,
  registers only valid models. Dropping a model folder in must work with zero code change.
- `RiskPolicy` strategy per condition: probability -> positive / uncertain / severity band / risk level /
  recommendation / refer-suggested; `ReferralAdvisor` turns them into one screening-level recommendation
  ("No referral needed" / "Refer recommended" / "Uncertain, consider asking a specialist"). Referral policy
  (`referral_advice` in risk_policy.json, as in the proposal's sequence diagram): uncertain cases are queued
  automatically; clear positives are sent by the health worker with "Ask a specialist"; severe (band 4-5) = urgent.
  All numbers in one config file, reasoning in `docs/risk_policy.md`.

## 4. Roles
- `health_worker`: patients, screenings, results, history, ask a specialist, remove own screening (reason),
  offline queue + sync.
- Public sign-up is a pending request (name, email, password, requested role `health_worker` or `specialist`, never
  admin); it grants nothing until an admin approves it (with that role or another, optionally setting the facility)
  or rejects it with a reason. One account per email: a duplicate sign-up is refused (409) and changes nothing.
  The app verifies nobody's identity or qualifications. Never claim it does.
- `specialist`: review queue; approve / override (reason required) / request retake / comment. Specialty routing
  (extension beyond the proposal): specialties per specialist (dr/glaucoma/cataract/general), "My specialties" and
  "All cases" tabs, "Take this case"; the health worker's ask names conditions and routine/urgent.
- `admin`: user and role management, aggregate analytics (no images, no identifiers).

## 5. Data model
users, patients, screenings (patient, eye laterality, image path, client_uuid unique, captured_at,
created_by), diagnosis_results (one per condition per screening, model_version, probability, band,
uncertain, model_available), review_events (append-only: never UPDATE or DELETE), referrals,
sync_logs (attempts, errors), audit_events. Constraints and indexes on FKs and client_uuid.

## 6. Auth and security
Argon2 password hashing; JWT access + refresh; logout invalidates refresh; RBAC enforced on the backend
(never only in the UI); users cannot change their own role; secrets only from env (`.env`, never committed);
uploads validated (content type, max size, decodable image); no images or identifiers in logs or analytics.

## 7. Screening pipeline and API
- Quality gate (reuse `quality.py`): blur (Laplacian variance), brightness, blank, fundus-field coverage.
  Unusable image -> HTTP 422 with a plain-language reason.
- `POST /screenings` (multipart: image, patient_id, eye, client_uuid, captured_at): run every available
  condition, store one diagnosis_result per condition, idempotent on client_uuid.
- `GET /models`: versions, availability, thresholds, limitations, metrics (or "not yet measured").
- Runtime: `ai-edge-litert` (installed, v2.3.0 on Python 3.14). TensorFlow stays a dev-only dependency for the
  Keras-vs-TFLite agreement test. Validate equivalence before switching runtimes.

## 8. Review, sync, analytics
- `GET /reviews/queue`, `POST /reviews/{screening_id}` (appends review_event).
- `POST /sync/push` (batch, idempotent per client_uuid), `GET /sync/pull?since=`.
- `GET /admin/analytics`: screenings per day, positives per condition, referral rate, review turnaround,
  model versions in use. Aggregates only.
- Audit events for login, screening, review, user changes.

## 9. Patients and RBAC
Health workers see patients they registered; specialists see patients with referred screenings; admins see
aggregates and users. Patients identified by a pseudonymous code plus minimal fields (synthetic data only).

## 10. Frontend
Vite + React + TypeScript strict + Tailwind + shadcn/ui + vite-plugin-pwa + React Hook Form + Zod + Vitest.
Mobile-first (390px): bottom tabs on mobile, sidebar on desktop. Typed API client and hooks; no fetch in
components. IndexedDB offline queue with client UUIDs, states pending/syncing/synced/failed, bounded
exponential backoff with jitter. Medical disclaimers visible on result screens. No mock data in the UI.

## 11. Testing and evidence
pytest (backend, real model for ML tests), Vitest (frontend), Playwright and Lighthouse if time allows,
`scripts/benchmark.py` -> `docs/benchmarks/`. Report real command output only. A passing build is not proof.
At least two testing strategies documented in `docs/testing_report.md` with real results.

## 12. Repository structure
```
backend/app/{api,services,repositories,models,schemas,core,ml}/   # ml/ = former src/ code
backend/tests/   backend/alembic/   scripts/   models/<condition>/
frontend/   docs/{diagrams,evaluation,benchmarks,report}/   notebooks/
```

## 12b. Current state (28 Oct 2026)
Backend, frontend, E2E, docs, diagrams and the technical report PDF are done (see `docs/scope_table.md`);
`final-app` is merged into `main`. The Streamlit prototype was retired (git tag `legacy-streamlit-prototype`).
All three models are installed (DR v2.0, glaucoma, cataract); metrics as in section 3. CI (backend on
PostgreSQL 16, frontend checks, Docker build) ran green on GitHub for runs #1, #2 and #4 (#4 = wip-final-fixes, 28 Oct).
Sign-up is a pending request (requested role health worker or specialist; no facility field, the admin may set
it on approval) until an admin approves; demo passwords documented in docs/video_script.md; the facility list and the old professional-ID field were removed (migration `7a3c5e9b1d20`). Fundus check is a
hard stop (3/25 real fundus photos wrongly refused, 0/77 non-eye accepted; tuned on the same images, optimistic).
Referral only via "Ask a specialist". Soft delete with reason; `scripts/reset_demo_data.py`; daily counts in
`TIME_ZONE` (Africa/Kigali). Review targets (urgent 24 h, routine 72 h) are a design decision.
Work since 27 Oct is on branch `wip-final-fixes` (not yet merged into `main`).
Latest test run and counts: see README section 8 and docs/testing_report.md.
Pending: walkthrough video, usability test (SUS), physical-device test (iPhone 13 Pro after an HTTPS deploy),
on-device inference and load balancer (proposal items not built).

## 13. Environment
Windows + PowerShell. Python in project `.venv` only (never global). Pinned requirements.
Node at `C:\Program Files\nodejs`; call `npm.cmd` / `npx.cmd` (PowerShell blocks npm.ps1).
`DATABASE_URL` setting: SQLite locally by default, PostgreSQL by config switch. Docker / docker-compose
provided for deployment only, not required locally.

## 14. Working rules
- Plan first, wait for approval, then implement in small steps.
- Conventional commits (feat/fix/test/docs/refactor/chore). Branch `final-app`; merge to `main` at the end.
  No force-push, no history rewrites. One approved exception: on 26 Oct 2026 commit-message trailers were
  removed with a history rewrite (file contents unchanged; backups kept). Michael decides when to push:
  never push until he types exactly "OK, push". No Co-Authored-By trailers; AI use is disclosed in README §11.
- Preserve working code and existing tests. Never commit datasets, venvs, secrets, `$Recycle.Bin/`.
- End each phase with: files changed, commands run + real results, failures/blocked items,
  evidence to capture, scope-table rows updated. Then stop.
