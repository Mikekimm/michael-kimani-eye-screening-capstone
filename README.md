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
| **Health worker** (public sign-up, then admin approval) | Registers patients by app-generated code, captures or uploads a fundus photo of the left or right eye, gets a screening result, refers cases, works offline and syncs later |
| **Specialist** (created or promoted by an admin) | Reviews referred cases: approve, override any condition with a reason, request a retake, comment. History is append-only |
| **Admin** (created at install) | Approves or rejects sign-ups (rejection needs a reason), creates staff accounts, assigns roles, maintains the facility list, sees aggregate analytics (no images or identifiers) |

Patients have no accounts: they are records with an app-generated code. A new sign-up is **pending** and
cannot sign in until an admin approves it. The facility comes from the admin's list (no free text) and
the professional registration number is **recorded for the admin to check** (for example by phoning
the facility); the app cannot verify it. The server checks the role on every request (`AccessPolicy`
and route guards), so a health worker calling a specialist or admin endpoint gets HTTP 403.

## 2. Conditions and real model availability

| Condition | Model | Status |
|---|---|---|
| Diabetic retinopathy | v2.0: MobileNetV2 fine-tuned from `block_13_expand`, binary (no DR / DR present), bilinear resize, TFLite run with LiteRT ([notebooks/dr_v2_finetune.ipynb](notebooks/dr_v2_finetune.ipynb)) | **Available.** Threshold 0.418 chosen on the validation split. On 35,426 test images: sensitivity **0.851** (95% CI 0.845-0.857), specificity **0.748** (0.743-0.754), precision 0.706, AUC 0.900 ([docs/metrics.json](docs/metrics.json)). **Sensitivity target met; specificity target (80%) not met.** Held-out test split by image (no patient IDs available; near-duplicates could not be excluded); not external validation; not clinically validated |
| Glaucoma | MobileNetV2, binary, ODIR-5K, patient-separated split ([notebooks/odir_glaucoma_cataract.ipynb](notebooks/odir_glaucoma_cataract.ipynb)) | **Available, below target, limited evidence.** Threshold 0.320. On 1,040 test eyes (42 positive): sensitivity 0.762, specificity 0.721, **precision 0.103** (about 9 in 10 positive flags are false alarms), AUC 0.818 ([docs/odir_metrics.json](docs/odir_metrics.json)). Binary result only |
| Cataract | as glaucoma | **Available, limited evidence.** Threshold 0.541. On 1,044 test eyes (46 positive): sensitivity 0.978, specificity 0.962, precision 0.542, AUC 0.991; meets both targets, but with only 46 positives the intervals are wide. Binary result only: **no 1-5 cataract grading**, because ODIR-5K has no severity labels |

ODIR-5K labels come from free-text diagnostic keywords per eye and may be noisy. The earlier DR model
(v0.3, sensitivity 0.542 on its validation fold) is kept only as history in
[docs/evaluation/dr_v1_metrics.json](docs/evaluation/dr_v1_metrics.json); results it produced keep its
version label and the app says so on those screens.

The 1-5 band shown for DR is an **estimated severity band** derived from the model score by a
configurable policy ([docs/risk_policy.md](docs/risk_policy.md)). It is not an ICDR grade. Adding or
replacing a model needs no code change: drop `model.tflite` + `model_card.json` into `models/<condition>/`
and restart. The registry verifies the SHA-256, and the card says which resize the model was trained with
(the app feeds each model exactly that; a card that does not say is refused).

## 3. Features

* Sign-up with admin approval (pending until approved; facility from an admin-managed list; rejection with a reason, emailed to the person), sign-in with Argon2-hashed passwords, JWT access + refresh tokens, sign-in and sign-up rate limits, role-based access enforced by the API
* Forgot password by emailed one-time link; required patient consent per screening
* Patient registry using pseudonymous clinic codes (no names), patient screening history
* 3-step capture: patient, eye, photo (rear camera with a circular guide, or gallery), with on-device quality hints
* Server quality gate (blank, too small) with plain-language 422 errors; warnings for blur, darkness and non-fundus images
* One result card per condition: classification, model score explained, borderline flag, estimated severity band (DR), model version, recommended action, and the model's measured limits ("How reliable is this model?")
* Results made by an earlier model are kept unchanged and labelled, with "Screen again" for current results
* Automatic referral of positive and borderline results; manual "refer anyway"
* Specialist queue (overdue first; flagged conditions; waiting time; urgent 24 h / routine 72 h review targets, configurable) and case review with an append-only, timestamped review history; override any condition with a reason
* Offline queue in IndexedDB: capture while offline, automatic sync with exponential backoff, per-item retry; specialist decisions pulled back to the device
* Admin user management, staff account creation, facility list, aggregate analytics with overdue reviews; About screen built from the model cards
* Installable PWA, mobile-first (bottom tabs) with a desktop sidebar

**Not included (honest limits):** offline *inference* (photos taken offline are analysed after they
sync), a native Android app (the PWA installs on Android and iPhone instead), a load balancer, field testing.

**Deviations from the proposal** (reasons in [docs/scope_table.md](docs/scope_table.md)): React Native on
Android with on-device TensorFlow Lite became an installable PWA with server-side TFLite inference. Offline
works for capture and queueing only: a photo taken offline is scored after it syncs.

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
models/<condition>/   model.tflite (served), model_card.json; models/dr/model.keras (source for the agreement test)
notebooks/            DR v2 and ODIR training notebooks (with outputs), DR v1 notebook, hold-out notebook
scripts/              init_env, seed, benchmark, dr_v2_metrics, extract_notebook_metrics, export_tflite, e2e_server
docs/                 scope table, testing report, risk policy, metrics, evaluation evidence, benchmarks, diagrams, screenshots, report
.github/workflows/     CI: backend tests on PostgreSQL, frontend checks, Docker build
```

## 6. Technical requirements (versions actually used)

| Component | Version |
|---|---|
| OS (development and tests) | Windows 11 Pro (10.0.26200) |
| Python | 3.14.6 (Docker image uses 3.12, built in CI) |
| Node.js / npm | 24.22.1 / 11.19.1 |
| Backend | FastAPI 0.162.0, Uvicorn 0.54.0, SQLAlchemy 2.1.6, Alembic 1.20.1, Pydantic 2.14.1, argon2-cffi 25.1.0, PyJWT 2.15.1, ai-edge-litert 2.3.0, NumPy 2.5.4, Pillow 13.0.0 |
| Frontend | React 18.3.1, Vite 5.4.10, TypeScript 5.6.3 (strict), Tailwind 3.4.14, TanStack Query 5.59.20, React Hook Form 7.53.2, Zod 3.23.8, vite-plugin-pwa 0.20.5, Recharts 2.13.3 |
| Testing | pytest 9.1.1, Vitest 2.1.4, Testing Library 16.0.1, Playwright 1.48.2, Lighthouse 12.2.1 |
| ML (dev only) | TensorFlow 2.22.0rc0, scikit-learn 1.9.1 |
| Database | SQLite (default); PostgreSQL 16 via `DATABASE_URL` (backend test suite run against it in CI) |

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
`.env`; they are never committed. The seed also creates three fictional facilities (Demo Health Centre A,
Demo Health Centre B, Demo District Hospital). New health worker accounts come from the sign-up page and
stay pending until the admin approves them on the Users page.

**Switching to PostgreSQL:** set `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db` in `.env`,
`pip install "psycopg[binary]"`, then run `alembic upgrade head`.

**Docker (deployment):** `docker compose up --build` serves the app on http://localhost:8080 with
PostgreSQL. CI builds both images on every push; the full stack has not been started locally because
Docker is not installed on the development machine.

**Hosted demo (Render, free plan):** [render.yaml](render.yaml) describes the whole deployment: PostgreSQL,
the API (built from `backend/Dockerfile`) and the PWA as a static HTTPS site. In the Render dashboard choose
**New -> Blueprint**, pick this repository, then type the six `SEED_*` values (demo accounts) and, for real
emails, the `SMTP_*` values (e.g. Gmail with an App Password). Secrets are entered in the dashboard and never
stored in git. Open the static site's URL on a phone and use **Add to Home Screen** to install the app.

## 8. Tests

```powershell
cd backend;  ..\.venv\Scripts\python -m pip install -r requirements-dev.txt;  ..\.venv\Scripts\python -m pytest -q
cd frontend; npm.cmd run typecheck; npm.cmd run lint; npm.cmd test
cd frontend; npx playwright install chromium firefox webkit; npx playwright test     # starts its own throwaway backend
```

Continuous integration ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs on every push: the backend suite
against PostgreSQL 16 (after `alembic upgrade head`), frontend type-check, lint and Vitest, and `docker compose build`.
First runs, all three jobs green:
[run #1 (final-app)](https://github.com/Mikekimm/michael-kimani-eye-screening-capstone/actions/runs/40503709691),
[run #2 (main)](https://github.com/Mikekimm/michael-kimani-eye-screening-capstone/actions/runs/40503744036).

Latest recorded results (27 Oct 2026, development laptop):

| Suite | Result |
|---|---|
| Backend pytest (119 unit/algorithm + 136 API integration, real models incl. parity and Keras-vs-TFLite agreement) | 255 passed, 0 skipped |
| Frontend Vitest (algorithms, API client, components, forms, routes) | 69 passed |
| TypeScript strict type-check / ESLint | clean / clean |
| Playwright end-to-end (6 journeys incl. fake sign-up -> pending -> refused -> approved, x Chromium mobile + desktop, Firefox desktop, WebKit/iPhone; plus axe-core and throttled-performance checks on Chromium) | 27 passed (24 journeys + 2 accessibility + 1 performance), 3 skipped by design (those checks run on Chromium only) |
| Browser performance (upload to result, Chromium; measured 26 Oct with the DR v1 model) | median 0.50 s; 3.17 s with emulated 6x slower CPU + slow 3G |
| Accessibility, axe-core WCAG 2.1 A/AA (20 pages, all roles, mobile + desktop) | 0 violations |
| Lighthouse, sign-in page (mobile / desktop) | 96/100/100/100 and 100/100/100/100 (performance/accessibility/best practices/SEO) |

Strategies, results and the improvements they led to: [docs/testing_report.md](docs/testing_report.md).
Server performance: [docs/benchmarks/](docs/benchmarks/) (200 runs on an Intel laptop CPU with 8 logical
cores: model 55 ms mean, full pipeline on a 1024px photo 74 ms mean; restricted to 1 thread: 60 ms and
77 ms; about 117 MB process memory). An earlier run on the same laptop under background load measured
110 ms / 166 ms, so timings vary with machine load.

## 9. Model provenance and evaluation

* DR data: Kaggle `ascanipek/eyepacs-aptos-messidor-diabetic-retinopathy` (EyePACS, APTOS 2019,
  Messidor-2; pre-augmented; no patient identifiers). Glaucoma and cataract: Kaggle
  `andrewmvd/ocular-disease-recognition-odir5k`. No images are stored in this repository.
* DR v2 training: [notebooks/dr_v2_finetune.ipynb](notebooks/dr_v2_finetune.ipynb) (run on Kaggle, 2 x T4,
  224 min; 70/15/15 split by image group, train 165,319 / validation 35,425 / test 35,426). Its outputs are in
  [docs/evaluation/dr_v2/](docs/evaluation/dr_v2/) (results, validation and test predictions, parity scores).
* Every DR figure is recomputed from those predictions with the app's own code by
  `scripts/dr_v2_metrics.py`, which stops if anything differs from the notebook; a pytest test repeats it.
* The served `model.tflite` has the SHA-256 the notebook recorded
  (`eb2603ab5b8ed412ac4462fc7fcad3cc6b8b84a7a7bf5d711ba24b673f05eb30`). On 24 of the notebook's test photos
  the app's own pipeline reproduces the notebook's scores within 0.021 (tolerance 0.03), with no decision changed.
* Glaucoma/cataract: [notebooks/odir_glaucoma_cataract.ipynb](notebooks/odir_glaucoma_cataract.ipynb), split by
  patient (no patient in two splits), thresholds chosen on validation, test scored once with the exported file.
* Known limitations: DR split by image (the notebook found as many groups as images, so augmented copies and a
  patient's two eyes could not be grouped; the DR figures may be optimistic), no external test set, no
  smartphone-lens images, scores are not calibrated probabilities, ODIR labels may be noisy and its positive
  classes are small.
* Reference only: Gulshan et al. (2016) reported 90.3% sensitivity / 98.1% specificity for referable DR on
  different data, a much larger model and a high-specificity operating point; not a like-for-like comparison.
  Our referable-DR (grade 2+) sensitivity on the test split is 0.869.

## 10. Security and privacy

Passwords hashed with Argon2id; short-lived access tokens with rotating refresh tokens revoked on
logout; RBAC enforced on every API route (tested as a role-by-route matrix); public sign-up cannot
choose a role; uploads checked for type, size and decodability; images stored under random names and
served only to authorised users; analytics and audit logs hold no images or patient fields; secrets
only in `.env`. Limits: tokens are kept in browser localStorage (readable by scripts on the page; the
app loads no third-party scripts); no TLS in local development; no penetration testing.

## 11. Use of AI assistance

I used Claude to help me build this project.

This project was designed and directed by Michael Maina Kimani. I wrote the proposal, chose the scope and the honesty rules (real trained models only, no invented results), trained and evaluated the diabetic retinopathy model on Kaggle, and made the decisions on what to build and what to cut.

I used Claude (Anthropic), through Claude Code, to help write, refactor and test the backend and frontend code, the test suites and the documentation, working under my direction. I reviewed the results and I am responsible for the submitted work.

## 12. Known issues

* DR specificity (0.748) and both glaucoma targets are below the proposal's targets; glaucoma precision is
  about 0.10. The result screens show these limits next to each result.
* Offline mode queues photos but cannot analyse them on the device.
* PostgreSQL runs in CI (backend tests) and Docker images are built in CI; the full Docker stack has not been
  started locally.
* Rate limits are in memory per process; behind several API instances they would need a shared store.
* No usability study with health workers has been completed yet.
* On the free Render plan the API sleeps after 15 minutes without use (the next request takes about a
  minute), its disk is wiped on restart (records and results stay in PostgreSQL, but older photos stop
  displaying), and the free database expires after 30 days.
