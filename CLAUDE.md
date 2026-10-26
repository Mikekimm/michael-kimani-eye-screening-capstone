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
- DR: real binary MobileNetV2 classifier (0 = no DR, 1 = DR present, ICDR grades 1-4), Kaggle
  `ascanipek/eyepacs-aptos-messidor-diabetic-retinopathy`. The committed notebook trained 8 epochs on a
  StratifiedGroupKFold fold and saved the model files; whether the shipped files are that run is checked by
  `notebooks/kaggle_holdout_eval.ipynb` (the author earlier believed it was a 2-epoch / 15k-image run).
  Input 224x224, MobileNetV2 `preprocess_input`, nearest-neighbour resize (matches training).
- **DR metrics** are validation results from the training notebook, not an independent hold-out (accuracy
  0.790, precision 0.920, sensitivity 0.542, specificity 0.97, F1 0.682, 47,234 images, threshold 0.5), parsed by
  `scripts/extract_notebook_metrics.py` into `docs/metrics.json` and the model card. Never call them a test set.
  The 85% sensitivity target is not met. The hold-out run did not finish. Never estimate numbers.
- Glaucoma and cataract: no trained models. They show `model_available=false` / "Model not available yet".
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
  recommendation / auto-refer. All numbers in one config file, reasoning in `docs/risk_policy.md`.

## 4. Roles
- `health_worker`: patients, screenings, results, history, offline queue + sync. Public sign-up = this role only.
- `specialist`: review queue; approve / override (reason required) / request retake / comment.
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

## 12b. Current state (26 Oct 2026)
Backend, frontend, E2E, docs and diagrams are done (see `docs/scope_table.md`). The Streamlit prototype was
retired (git tag `legacy-streamlit-prototype`). DR metrics = validation results from the training notebook, not an independent hold-out (docs/metrics.json). Pending: ODIR notebook run,
technical report PDF, video, usability test, merge `final-app` into `main`.

## 13. Environment
Windows + PowerShell. Python in project `.venv` only (never global). Pinned requirements.
Node at `C:\Program Files\nodejs`; call `npm.cmd` / `npx.cmd` (PowerShell blocks npm.ps1).
`DATABASE_URL` setting: SQLite locally by default, PostgreSQL by config switch. Docker / docker-compose
provided for deployment only, not required locally.

## 14. Working rules
- Plan first, wait for approval, then implement in small steps.
- Conventional commits (feat/fix/test/docs/refactor/chore). Branch `final-app`; merge to `main` at the end.
  No force-push, no history rewrites. Michael decides when to push.
- Preserve working code and existing tests. Never commit datasets, venvs, secrets, `$Recycle.Bin/`.
- End each phase with: files changed, commands run + real results, failures/blocked items,
  evidence to capture, scope-table rows updated. Then stop.
