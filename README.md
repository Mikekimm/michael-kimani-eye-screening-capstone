# Retinal Screening and Referral Support

An offline-first progressive web app that helps primary health centre workers screen fundus (retina)
photos for eye disease and refer uncertain or high-risk cases to a specialist.

> **Screening support only. Not a diagnostic device.** This is a research prototype trained and
> tested on public datasets. It has not been clinically validated and has no regulatory approval.

ALU BSc Software Engineering capstone, Michael Kimani (supervisor: Emmanuel Adjei).

| | |
|---|---|
| Walkthrough video | **TODO: add link** |
| Technical report (PDF) | **TODO: add link** (source in [docs/report/](docs/report/)) |
| MVP demo (earlier milestone) | https://youtu.be/5CVl1Cbt8A0 |

---

## 1. Problem and intended users

Diabetic retinopathy (DR), glaucoma and cataract are leading causes of preventable blindness. Primary
health centres in low-resource settings rarely have eye specialists or reliable internet. The intended
context is **primary health centres in low-resource settings in Africa**. This describes the target
setting only: no field deployment or clinical evaluation has taken place.

| Role | What they do in the app |
|---|---|
| **Health worker** (public sign-up) | Registers patients by clinic code, captures or uploads a fundus photo of the left or right eye, gets a screening result, refers cases, works offline and syncs later |
| **Specialist** (granted by an admin) | Reviews referred cases: approve, override with a reason, request a retake, comment. History is append-only |
| **Admin** | Manages users and roles, sees aggregate analytics (no images or identifiers) |

## 2. Conditions and real model availability

| Condition | Model | Status |
|---|---|---|
| Diabetic retinopathy | MobileNetV2 transfer learning, binary (no DR / DR present), TFLite run with LiteRT | **Available.** At threshold 0.5 on 47,234 validation images: accuracy 0.790, precision 0.920, sensitivity 0.542, specificity 0.97, F1 0.682 ([docs/metrics.json](docs/metrics.json)). These are validation results from the training notebook, not an independent hold-out; **the 85% sensitivity target is not met** |
| Glaucoma | MobileNetV2, binary, ODIR-5K, patient-separated split: [notebooks/odir_glaucoma_cataract.ipynb](notebooks/odir_glaucoma_cataract.ipynb) | **Model not available yet** until the notebook's output is added; the app then loads it with no code change. Binary result only |
| Cataract | as glaucoma | as glaucoma. **No 1-5 cataract grading**: ODIR-5K has no severity labels |

The 1-5 band shown for DR is an **estimated severity band** derived from the model score by a
configurable policy ([docs/risk_policy.md](docs/risk_policy.md)). It is not an ICDR grade. Adding a
trained glaucoma or cataract model needs no code change: drop `model.tflite` + `model_card.json` into
`models/glaucoma/` or `models/cataract/` and restart (the registry verifies the SHA-256).

## 3. Features

* Sign-up / sign-in with Argon2-hashed passwords, JWT access + refresh tokens, role-based access enforced by the API
* Patient registry using pseudonymous clinic codes (no names), patient screening history
* 3-step capture: patient, eye, photo (rear camera with a circular guide, or gallery), with on-device quality hints
* Server quality gate (blank, too small) with plain-language 422 errors; warnings for blur, darkness and non-fundus images
* One result card per condition: classification, model score explained, borderline flag, estimated severity band, model version, recommended action
* Automatic referral of positive and borderline results; manual "refer anyway"
* Specialist queue and case review with an append-only, timestamped review history
* Offline queue in IndexedDB: capture while offline, automatic sync with exponential backoff, per-item retry; specialist decisions pulled back to the device
* Admin user management and aggregate analytics; About screen built from the model card
* Installable PWA, mobile-first (bottom tabs) with a desktop sidebar

**Not included (honest limits):** offline *inference* (photos taken offline are analysed after they
sync), glaucoma and cataract models, a native Android app, a load balancer, field testing.

## 4. Architecture

```
React PWA (Vite, TypeScript)            FastAPI backend (Python)
  pages -> hooks -> typed API client  ->  api (routers) -> services -> repositories -> SQLAlchemy
  IndexedDB offline queue (SyncQueue)      ScreeningPipeline -> ModelRegistry -> TFLiteConditionModel (LiteRT)
                                           RiskPolicy (config/risk_policy.json)      SQLite / PostgreSQL
```

Design patterns you can find in the code:

| Pattern | Where |
|---|---|
| Strategy | `RiskPolicy` per condition: [backend/app/ml/risk_policy.py](backend/app/ml/risk_policy.py) |
| Interface + polymorphism | `ConditionModel` -> `TFLiteConditionModel`: [backend/app/ml/condition_model.py](backend/app/ml/condition_model.py) |
| Registry with integrity check | `ModelRegistry`: [backend/app/ml/registry.py](backend/app/ml/registry.py) |
| Repository | [backend/app/repositories/__init__.py](backend/app/repositories/__init__.py) (frontend: `QueueRepository` with IndexedDB and in-memory implementations) |
| Dependency injection | [backend/app/api/deps.py](backend/app/api/deps.py), [frontend/src/lib/services.tsx](frontend/src/lib/services.tsx) |
| Single access policy | `AccessPolicy`: [backend/app/services/access.py](backend/app/services/access.py) |

Algorithms: image quality gate (Laplacian variance, brightness, vignette test) in
[quality.py](backend/app/ml/quality.py); sensitivity-targeted threshold search (O(n log n)) in
[thresholding.py](backend/app/ml/thresholding.py); rank-sum AUC and bootstrap intervals in
[evaluation.py](backend/app/ml/evaluation.py); threshold-anchored severity bands in
[risk_policy.py](backend/app/ml/risk_policy.py); idempotent sync with bounded exponential backoff and
full jitter in [syncQueue.ts](frontend/src/offline/syncQueue.ts) and [backoff.ts](frontend/src/offline/backoff.ts);
SHA-256 model verification in [registry.py](backend/app/ml/registry.py).

## 5. Repository structure

```
backend/
  app/api/            FastAPI routers and dependency injection
  app/services/       use cases: auth, patients, screening pipeline, reviews, sync, analytics
  app/repositories/   database queries
  app/models/         SQLAlchemy entities and enums
  app/schemas/        Pydantic v2 request/response models
  app/ml/             preprocessing, quality gate, model registry, risk policy, evaluation
  app/core/           settings, database, security, error handling
  alembic/            database migrations
  config/             risk_policy.json
  tests/              pytest (api/, ml/)
frontend/
  src/pages/          screens        src/components/  UI building blocks
  src/hooks/          data hooks     src/lib/         API client, auth, utils
  src/offline/        IndexedDB queue, backoff, sync
  e2e/                Playwright journeys
models/dr/            model.tflite (served), model.h5 (source), model_card.json
notebooks/            training notebook, Kaggle hold-out evaluation notebook
scripts/              init_env, seed, benchmark, calibrate_threshold, export_tflite, e2e_server
docs/                 scope table, testing report, risk policy, benchmarks, diagrams, screenshots, report
```

## 6. Technical requirements (versions actually used)

| Component | Version |
|---|---|
| OS (development and tests) | Windows 11 Pro (10.0.26200) |
| Python | 3.14.6 (Docker image uses 3.12; not yet built) |
| Node.js / npm | 24.22.1 / 11.19.1 |
| Backend | FastAPI 0.162.0, Uvicorn 0.54.0, SQLAlchemy 2.1.6, Alembic 1.20.1, Pydantic 2.14.1, argon2-cffi 25.1.0, PyJWT 2.15.1, ai-edge-litert 2.3.0, NumPy 2.5.4, Pillow 13.0.0 |
| Frontend | React 18.3.1, Vite 5.4.10, TypeScript 5.6.3 (strict), Tailwind 3.4.14, TanStack Query 5.59.20, React Hook Form 7.53.2, Zod 3.23.8, vite-plugin-pwa 0.20.5, Recharts 2.13.3 |
| Testing | pytest 9.1.1, Vitest 2.1.4, Testing Library 16.0.1, Playwright 1.48.2, Lighthouse 12.2.1 |
| ML (dev only) | TensorFlow 2.22.0rc0, scikit-learn 1.9.1 |
| Database | SQLite (default); PostgreSQL 16 via `DATABASE_URL` (configured, not yet tested) |

Full pinned lists: [backend/requirements.txt](backend/requirements.txt), [backend/requirements-dev.txt](backend/requirements-dev.txt), [frontend/package.json](frontend/package.json).

## 7. Install and run (Windows PowerShell)

Prerequisites: Python 3.12+ and Node.js 22+ (LTS). No Docker or PostgreSQL needed.

```powershell
git clone https://github.com/Mikekimm/michael-kimani-eye-screening-capstone.git
cd michael-kimani-eye-screening-capstone

# Backend
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
.venv\Scripts\python scripts\init_env.py        # writes .env with a random JWT secret and demo passwords (printed once)
cd backend
..\.venv\Scripts\alembic upgrade head           # create the database (data\app.db)
cd ..
.venv\Scripts\python scripts\seed.py            # demo admin, specialist, health worker + 5 synthetic patients
cd backend
..\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

In a second terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev          # http://localhost:5173 (API calls are proxied to port 8000)
```

If PowerShell blocks `npm` scripts, use `npm.cmd` as shown. API documentation: http://localhost:8000/docs.

**Demo accounts** (synthetic data only): `admin@example.org`, `specialist@example.org`,
`nurse@example.org`. Their passwords are generated by `scripts/init_env.py` and stored in your local
`.env`; they are never committed. New health worker accounts can be created from the sign-up page.

**Switching to PostgreSQL:** set `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db` in `.env`,
`pip install "psycopg[binary]"`, then run `alembic upgrade head`.

**Docker (deployment):** `docker compose up --build` serves the app on http://localhost:8080 with
PostgreSQL. These files have not yet been built or run, because Docker is not installed on the
development machine.

## 8. Tests

```powershell
cd backend;  ..\.venv\Scripts\python -m pip install -r requirements-dev.txt;  ..\.venv\Scripts\python -m pytest -q
cd frontend; npm.cmd run typecheck; npm.cmd run lint; npm.cmd test
cd frontend; npx playwright install chromium firefox webkit; npx playwright test     # starts its own throwaway backend
```

Latest recorded results (26 Oct 2026, development laptop):

| Suite | Result |
|---|---|
| Backend pytest (unit, API integration, real-model tests) | 165 passed, 0 skipped |
| Frontend Vitest (algorithms, API client, components, forms, routes) | 48 passed |
| TypeScript strict type-check / ESLint | clean / clean |
| Playwright end-to-end (4 journeys x Chromium mobile + desktop, Firefox desktop, WebKit/iPhone) | 16 passed |
| Browser performance (upload to result, Chromium) | median 0.50 s; 3.17 s with emulated 6x slower CPU + slow 3G |
| Accessibility, axe-core WCAG 2.1 A/AA (15 screens, all roles, mobile + desktop) | 0 violations |
| Lighthouse, sign-in page (mobile / desktop) | 96/100/100/100 and 100/100/100/100 (performance/accessibility/best practices/SEO) |

Strategies, results and the improvements they led to: [docs/testing_report.md](docs/testing_report.md).
Server performance: [docs/benchmarks/](docs/benchmarks/) (200 runs on an Intel laptop CPU with 8 logical
cores: model 55 ms mean, full pipeline on a 1024px photo 74 ms mean; restricted to 1 thread: 60 ms and
77 ms; about 117 MB process memory). An earlier run on the same laptop under background load measured
110 ms / 166 ms, so timings vary with machine load.

## 9. Model provenance and evaluation

* Data: Kaggle `ascanipek/eyepacs-aptos-messidor-diabetic-retinopathy` (EyePACS, APTOS 2019,
  Messidor-2; pre-augmented; no patient identifiers). No images are stored in this repository.
* Training: [notebooks/model_notebook.ipynb](notebooks/model_notebook.ipynb) (MobileNetV2, frozen
  backbone, SEED 42, group-aware 5-fold split, 8 epochs).
* Model card: [models/dr/model_card.json](models/dr/model_card.json) (verified input spec, labels,
  checksum, threshold and its source, limitations).
* Reported metrics: validation results from the training notebook, not an independent hold-out, parsed from the notebook's saved outputs by
  `scripts/extract_notebook_metrics.py` into [docs/metrics.json](docs/metrics.json) and the model card.
  At 0.5 the model misses about 46% of DR cases in that fold (sensitivity 0.542), below the 85% target.
* Not completed: the independent hold-out run
  ([notebooks/kaggle_holdout_eval.ipynb](notebooks/kaggle_holdout_eval.ipynb)) and threshold calibration
  (`scripts/calibrate_threshold.py`), which would raise sensitivity at the cost of more referrals.
* Known limitations: image-level splits (no patient IDs), augmented near-duplicates, no external test
  set, no smartphone-lens images, probabilities not calibrated.

## 10. Security and privacy

Passwords hashed with Argon2id; short-lived access tokens with rotating refresh tokens revoked on
logout; RBAC enforced on every API route (tested as a role-by-route matrix); public sign-up cannot
choose a role; uploads checked for type, size and decodability; images stored under random names and
served only to authorised users; analytics and audit logs hold no images or patient fields; secrets
only in `.env`. Limits: tokens are kept in browser localStorage (readable by scripts on the page; the
app loads no third-party scripts); no TLS in local development; no penetration testing.

## 11. Use of AI assistance

This project was designed and directed by Michael Maina Kimani. I wrote the proposal, chose the scope and the honesty rules (real trained models only, no invented results), trained and evaluated the diabetic retinopathy model on Kaggle, and made the decisions on what to build and what to cut.

I used Claude (Anthropic), through Claude Code, to help write, refactor and test the backend and frontend code, the test suites and the documentation, working under my direction. I reviewed the results and I am responsible for the submitted work.

## 12. Known issues

* Glaucoma and cataract are not available until models are trained (e.g. on ODIR-5K).
* Offline mode queues photos but cannot analyse them on the device.
* The `.tflite` model is a quantized export; scores differ from the Keras model by up to about 0.03.
* PostgreSQL and Docker configurations are written but not yet run.
* No usability study with health workers has been completed yet.
