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
| **Health worker** (sign-up request, then admin approval) | Registers patients by app-generated code, captures or uploads a fundus photo of the left or right eye, gets a screening result with a recommendation, decides whether to ask a specialist, works offline and syncs later |
| **Specialist** (sign-up request approved as specialist, or created by an admin) | Reviews the cases health workers sent, starting with those matching their specialties; takes a case, then approves, overrides any condition with a reason, requests a retake or comments. History is append-only |
| **Admin** (created at install) | Approves or rejects sign-up requests (choosing the role to grant; rejection needs a reason), creates staff accounts, changes roles, sees aggregate analytics (no images or identifiers) |

Patients have no accounts: they are records with an app-generated code.

### How access is controlled

* **Sign-up is a request, not an account.** The form asks only for name, email, password and the role being
  requested (health worker or specialist; admin cannot be requested). The request is **pending**: with the
  correct password, signing in returns "Your account is waiting for administrator approval" until an admin
  acts; a wrong password gets the generic "Incorrect email or password". The requested role grants nothing.
* **One account per email.** Signing up again with a registered email (any letter case) is refused with "This
  email is already registered. Sign in, or use Forgot password ..." and changes nothing: no second account,
  and the existing name, password, role and status stay as they were. The clear message is a deliberate
  choice (it reveals that the email is registered; sign-up is rate-limited).
* **An admin decides.** On the Users page the admin approves the request with the requested role or another
  one, optionally recording the person's facility, or rejects it with a reason (emailed to the person). Every
  decision is in the audit log. Admins can also create staff accounts directly.
* **The app does not verify anyone's identity or qualifications.** The admin is expected to check who the
  person is outside the app (for example by phoning the facility).
* **Every request is checked on the server.** Route guards and one `AccessPolicy` check the role and record
  ownership, so a health worker calling a specialist or admin endpoint gets HTTP 403, and health workers see
  only their own patients. Users cannot change their own role. Sign-in and sign-up are rate-limited.

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

* Sign-up request with a requested role, pending until an admin approves (see "How access is controlled"); sign-in with Argon2-hashed passwords, JWT access + refresh tokens, sign-in and sign-up rate limits, role-based access enforced by the API
* Forgot password by emailed one-time link; required patient consent per screening
* Patient registry using pseudonymous clinic codes (no names), patient screening history
* 3-step capture: patient, eye, photo (rear camera with a circular guide, or gallery), with on-device quality hints. After choosing a photo: **Cancel** or **Analyse**; a refused photo offers **Retake** or **Upload another**; after a result: **Save** or **Discard** (with a reason)
* Server quality gate with plain-language 422 errors and nothing saved: blank, too small, and **photos that do not look like a retinal fundus photograph** (a heuristic check; see section 8); warnings for blur and darkness
* One result card per condition: classification, model score explained, borderline flag, estimated severity band (DR), model version, the model's measured limits ("How reliable is this model?"), and one recommendation for the screening: "No referral needed", "Refer recommended" or "Uncertain, consider asking a specialist"
* **Specialist review is a later confirmation, not a gate.** The health worker gives the patient the recommended action from the result straight away, at the same visit; the specialist's review (asynchronous, as in the proposal) confirms or corrects it later and comes back at the next sync. The review targets (urgent 24 h, routine 72 h, configurable) are my own design decision so that no sent case waits unnoticed; the proposal sets no time limit.
* **Specialty routing (an extension beyond the proposal, which lists only a single Specialist role):** when asking a specialist, the health worker ticks which conditions the question is about (pre-ticked from borderline or positive results) and chooses routine or urgent. Each specialist has specialties (DR, glaucoma, cataract, general = all cases), set by the admin on the approval screen or in user management. The queue shows matching cases under "My specialties" and everything under "All cases"; "Take this case" assigns it, other specialists see it as taken, and the health worker sees "Being reviewed by <name>". Decisions come back as before; overdue cases (past 24 h urgent / 72 h routine) are counted per priority in the admin analytics. The server enforces it: a health worker cannot take or decide a case, a specialist can take only open cases in the queue and cannot decide a case another specialist has taken.
* **Referral policy (configurable, as in the proposal's sequence diagram):** an uncertain case is flagged and queued for specialist review automatically: borderline results, and usable photos with quality warnings. A clear positive shows "Refer recommended" and the health worker sends it with "Ask a specialist"; a clear negative is not queued. The health worker can add a question to a queued case or send any case manually. Severe results (DR band 4-5) default to urgent, everything else to routine. Settings: `referral_advice` in `backend/config/risk_policy.json`
* **Asynchronous review from a shared queue.** The specialist works from one shared queue: a single specialist with the "general" specialty sees every case, and one district specialist can serve several clinics. Specialists do not prescribe medication: they approve, override with a reason, request a retake or comment; the app supports screening and referral only. Notifications by SMS or email are future work: health workers and specialists see new cases and decisions when the screens refresh (every 30 seconds by default, `VITE_REFRESH_SECONDS`) or at the next sync
* **New decisions:** the health worker's home shows how many specialist decisions have arrived and not been opened; History marks them "New decision" next to "Reviewed" (or "Retake needed"); opening the screening clears it
* Results made by an earlier model are kept unchanged and labelled, with "Screen again" for current results
* Asynchronous specialist review, as in the proposal: the queue shows the health worker's question, flagged conditions, waiting time and review target (urgent 24 h / routine 72 h, configurable; overdue first); approve, override any condition with a reason, request a retake or comment; append-only, timestamped history
* Remove screening (soft delete by the health worker who made it, reason required): hidden everywhere, the photo file is deleted, the audit entry stays
* Daily screening counts and a History day filter in the clinic's time zone (setting `TIME_ZONE`, default Africa/Kigali)
* Offline queue in IndexedDB: capture while offline, automatic sync with exponential backoff, per-item retry; specialist decisions pulled back to the device
* Admin user management (approve / reject requests, staff accounts, roles), aggregate analytics with overdue reviews; About screen built from the model cards
* Installable PWA, mobile-first (bottom tabs) with a desktop sidebar

**Not included (honest limits):** offline *inference* (photos taken offline are analysed after they
sync), a native Android app (the PWA installs on Android and iPhone instead), a load balancer, field testing.

**Planned vs implemented** (same rows as [docs/scope_table.md](docs/scope_table.md) and the report):

| Planned feature (proposal) | Status | Evidence (scope table row) |
|---|---|---|
| DR classifier (MobileNetV2, TFLite) | **Completed** | v2.0 fine-tuned, served; recomputation and parity tests (1) |
| Glaucoma classifier (ODIR-5K) | **Completed, below target** | sensitivity 0.762, specificity 0.721, precision 0.103 (1,040 eyes, 42 positive) (2) |
| Cataract classifier (ODIR-5K) | **Completed, limited evidence** | 0.978 / 0.962 / precision 0.542; only 46 positive test eyes (3) |
| Five-band cataract grading | **Not implemented** | ODIR-5K has no severity labels; binary result only (3b) |
| Risk / severity output | **Completed (changed)** | DR: five-band *estimated* band from the binary score; others binary (4) |
| Sensitivity >= 85%, specificity >= 80% on a held-out test set | **Partial** | DR sensitivity 0.851 met, specificity 0.748 not met; glaucoma not met; cataract met (5) |
| On-device TFLite inference | **Changed** | server-side LiteRT; offline = capture and queue, scored after sync (6) |
| Android app (React Native) | **Changed** | installable PWA for Android and iPhone (7) |
| Offline storage and two-way sync | **Completed** | IndexedDB queue, idempotent push, decision pull, interruption tests (8, 13, 21) |
| Register patient, capture image, run screening, view result | **Completed (changed)** | patient stored as a code and year of birth (no name); E2E journeys on four browser profiles (9-12) |
| Flag uncertain / high-risk cases for referral | **Completed** | uncertain cases flagged and queued automatically (configurable); clear positives sent by the health worker; decision pulled back (14) |
| Specialist review: approve or override | **Completed** | asynchronous queue with the question, review targets; override, retake, comment (15-16) |
| Admin: user accounts and analytics | **Completed** | approve / reject sign-up requests, roles, aggregate analytics (17-18) |
| FastAPI + PostgreSQL backend | **Completed** | SQLite locally; backend suite on PostgreSQL 16 in GitHub Actions (19) |
| Load balancer | **Not implemented** | stateless JWT API could scale behind one (20) |
| Usability testing with health workers | **Not implemented yet** | SUS kit ready, no participants yet (22) |
| UML design | **Completed** | use case, class, ERD, sequence, architecture diagrams (23) |
| Specialty routing (not in the proposal) | **Added (extension)** | conditions and priority on "Ask a specialist", specialist specialties, "Take this case"; `test_routing.py`, `routing.spec.ts` |

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

Algorithms: image quality gate (Laplacian variance, brightness, vignette test) and the fundus check
(dark corners, bright centre, red/green ratio, lit-field fraction) in [quality.py](backend/app/ml/quality.py);
one screening-level referral recommendation (`ReferralAdvisor`) in [risk_policy.py](backend/app/ml/risk_policy.py);
clinic-time-zone day counts in [daily_counts.py](backend/app/services/daily_counts.py); sensitivity-targeted threshold search (O(n log n)) in
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
scripts/              init_env, seed, reset_demo_data, benchmark, dr_v2_metrics, evaluate_fundus_check, extract_notebook_metrics, export_tflite, e2e_server
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

**Demo accounts** (synthetic data only, demo-only passwords, never use them on a hosted deployment):

| Role | Email | Password |
|---|---|---|
| Admin | `admin@example.org` | `DemoAdmin2026!` |
| Specialist | `specialist@example.org` | `DemoSpecialist2026!` |
| Health worker (approved) | `nurse@example.org` | `DemoNurse2026!` |

These are set by `scripts/init_env.py --demo-passwords` (without the flag, random passwords are written to
`.env` instead) and created by `scripts/seed.py`. New accounts come from the sign-up page (health worker or specialist
requested) and stay pending until the admin approves them on the Users page.

**Clean demo data:** `.venv\Scripts\python scripts\reset_demo_data.py --yes` (stop the backend first) backs up
the local SQLite file, deletes it and the stored photos, re-runs the migrations and the seed. Approved accounts
that are not demo accounts (for example your own) are carried over with their password; pending and rejected
requests are removed (`--drop-accounts` removes every non-demo account). It refuses to run against anything
except the SQLite file under `data/`.

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
Runs, all three jobs green: [run #1 (final-app)](https://github.com/Mikekimm/michael-kimani-eye-screening-capstone/actions/runs/40503709691)
and [run #2 (main)](https://github.com/Mikekimm/michael-kimani-eye-screening-capstone/actions/runs/40503744036) (27 Oct);
[run #4 (wip-final-fixes)](https://github.com/Mikekimm/michael-kimani-eye-screening-capstone/actions/runs/40675193040) (28 Oct, with all of the 28 October changes). [Run #3](https://github.com/Mikekimm/michael-kimani-eye-screening-capstone/actions/runs/40672299037) failed: on
Python 3.12 pytest could not collect the tests (fixed, see the testing report).

Latest recorded results (28 Oct 2026 evening, branch with specialty routing and the referral policy; development
laptop, Python 3.14; the backend suite also ran on Python 3.12: 298 passed, 1 skipped because TensorFlow is not
installed there):

| Suite | Result |
|---|---|
| Backend pytest (137 unit/algorithm + 162 API integration, real models incl. parity and Keras-vs-TFLite agreement) | 299 passed, 0 skipped |
| Frontend Vitest (algorithms, API client, components, forms, routes, capture flow, ask form, queue tabs, auto-refresh, new decisions) | 84 passed |
| TypeScript strict type-check / ESLint | clean / clean |
| Playwright end-to-end (12 tests per profile: the routing loop (ask with conditions and priority, My specialties, Take this case, Being reviewed by, New decision), sign-up requests, duplicate email, rejection, specialist sign-up, capture flow with a refused non-eye photo, Save / Discard, health worker journey, specialist review, decision and retake returned, unauthorized access, invalid input; on Chromium mobile + desktop, Firefox desktop, WebKit/iPhone 13; plus axe-core and throttled-performance checks on Chromium) | 51 passed (48 functional + 2 accessibility + 1 performance), 3 skipped by design (those checks run on Chromium only), 0 failed |
| Browser performance (upload to result, Chromium, three models; 28 Oct evening, run alone) | median 0.60 s; 4.15 s with emulated 6x slower CPU + slow 3G (before the routing and referral changes: 0.44 s / 2.73 s) |
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
* Fundus check (the classifiers cannot recognise a non-eye photo themselves): `scripts/evaluate_fundus_check.py`
  on 25 real fundus photos and 77 non-eye images wrongly rejected **3 of 25** fundus photos (all grey-background
  processed dataset images) and wrongly accepted **0 of 77** non-eye images. The rules were tuned on these same
  images and no face photos were available, so these figures are optimistic; the check is a heuristic and can be fooled.
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

I designed and directed the project, wrote the proposal and made the scope decisions. I trained the models myself by running the Kaggle training notebooks. I reviewed the results and I am responsible for the work.

## 12. Known issues

* DR specificity (0.748) and both glaucoma targets are below the proposal's targets; glaucoma precision is
  about 0.10. The result screens show these limits next to each result.
* Offline mode queues photos but cannot analyse them on the device; an uncertain case is queued for the specialist
  when the photo is scored after sync, not on the device.
* No SMS or email notifications of new cases or decisions (future work); the screens refresh every 30 seconds.
* The fundus check is a heuristic tuned on a small set (3 of 25 real fundus photos wrongly refused; no face photos
  tested); an unusual photo can still pass it or be refused.
* PostgreSQL runs in CI (backend tests) and Docker images are built in CI; the full Docker stack has not been
  started locally.
* Rate limits are in memory per process; behind several API instances they would need a shared store.
* No usability study with health workers has been completed yet.
* On the free Render plan the API sleeps after 15 minutes without use (the next request takes about a
  minute), its disk is wiped on restart (records and results stay in PostgreSQL, but older photos stop
  displaying), and the free database expires after 30 days.
