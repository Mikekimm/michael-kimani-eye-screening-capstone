# Testing, validation and performance report

All results below were produced on 26 October 2026 on the development laptop (Windows 11 Pro,
Intel CPU with 8 logical cores, Python 3.14.6, Node 24.22.1) unless stated otherwise. Commands to
reproduce them are in the [README](../README.md#8-tests).

Six strategies were used, each chosen for a specific risk in a screening-and-referral tool:

| # | Strategy | Risk it addresses | Tooling | Result |
|---|---|---|---|---|
| 1 | Unit testing of algorithms | wrong decision logic silently mis-triages patients | pytest, Vitest | 94 backend ML and algorithm tests + 25 frontend logic tests pass |
| 2 | Integration testing of the API with the real model | layers work alone but not together; RBAC gaps | pytest + FastAPI TestClient + LiteRT | 90 API tests pass (incl. 45-case role matrix) |
| 3 | End-to-end functional testing | the user cannot complete a clinical task | Playwright | 16/16 journeys pass on 4 browser/device profiles |
| 4 | Compatibility testing | works in one browser only | Playwright: Chromium, Firefox, WebKit | all journeys pass on all three engines |
| 5 | Performance testing | too slow on clinic hardware or networks | benchmark script, Playwright + CDP throttling, Lighthouse | 74 ms server pipeline; 0.5 s / 3.2 s round trip; Lighthouse 96-100 |
| 5b | Accessibility testing | health workers with low vision or screen readers cannot use it | axe-core (WCAG 2.1 A/AA) on every screen, Lighthouse | 0 violations on 15 screens, mobile and desktop |
| 6 | Model validation | the model is worse than claimed | training-notebook validation fold; hold-out notebook prepared | sensitivity 0.542, specificity 0.97 at 0.5 (validation, not hold-out): **target not met** |

Usability testing with health workers (SUS questionnaire) is planned but **has not been run**.

---

## 1. Unit testing of algorithms

**Why:** every clinical decision passes through a few small algorithms. A boundary error (for
example `>` instead of `>=` at the threshold) would turn referrals into "no signs detected" with
no visible failure.

**How:** boundary-value and property tests on the pure functions.

| Area | File | Tests | What is checked |
|---|---|---|---|
| Risk policy | `backend/tests/ml/test_risk_policy.py` | 30 | every band edge (0.1999 vs 0.2, ...), uncertain zone, auto-refer switches, invalid config; a sweep of 1,001 scores proves bands never contradict the decision |
| Threshold selection | `test_thresholding.py` | 10 | known confusion matrices; chosen threshold is the highest meeting the sensitivity target |
| Evaluation | `test_evaluation.py` | 11 | stratified split keeps class ratios; AUC equals scikit-learn's; bootstrap intervals contain the estimate |
| Preprocessing / quality | `test_preprocessing.py`, `test_quality.py` | 17 | nearest-neighbour resize and [-1, 1] scaling match training; blank and tiny images block; blur and darkness warn |
| Registry | `test_registry.py` | 8 | checksum mismatch, bad card, wrong folder, missing file are rejected; a dropped-in model folder is registered with no code change |
| Backoff | `frontend/src/offline/backoff.test.ts` | 5 | exponential growth, cap, full jitter, invalid input |
| Sync queue | `syncQueue.test.ts` | 10 | **reply lost after the server saved** -> retry creates no duplicate; stops at first network error and keeps order; respects backoff; permanent failure on 422; attempt limit then manual retry; offline patient pushed before its screening |
| Image hints | `imageQuality.test.ts` | 4 | Laplacian sharpness and brightness hints |

**Checking the tests themselves:** I deliberately broke the code (band 3 returned as 2; the
append-only guard disabled). 10 tests failed as expected, then the code was restored.

## 2. Integration testing (API + database + real model)

**Why:** most security and data-integrity rules live where layers meet: who may see a record,
whether a retried upload duplicates, whether review history can be rewritten.

**How:** each test gets a fresh SQLite database and calls the real HTTP API. Screening tests use the
**real, checksum-verified DR model**. Referral and review tests use a clearly labelled test double
(`FixedScoreModel`) so a referral can be forced; it is never used outside tests.

| Area | Tests | Highlights |
|---|---|---|
| Auth | 14 | sign-up cannot set a role (422); Argon2id hash stored; refresh rotation (replayed token rejected); logout revokes; same error for unknown email and wrong password |
| RBAC | 45 | every protected route x every role, plus unauthenticated access to each route; self-promotion blocked; workers cannot see each other's patients |
| Screenings | 16 | real model returns a probability in [0, 1], deterministic; glaucoma/cataract return "not available" with no score; same `client_uuid` twice gives one record (200, duplicate); blank / tiny / non-image / BMP-as-JPEG / GIF / oversized / future timestamp / bad eye are all rejected with clear errors |
| Workflow | 15 | positive and borderline referral; approve / override (reason required) / retake / comment; ORM refuses to update or delete review events; sync pull returns only new decisions; sync push idempotent; analytics contain no identifiers; audit log entries |

**Inputs varied:** positive (0.9), borderline (0.45), negative (0.05), blank, tiny, corrupt,
wrong-type and oversized images; valid and invalid tokens; every role.

## 3. End-to-end functional testing (Playwright)

**Why:** to prove a real user can finish each core task through the real UI, API and model.

**How:** `frontend/e2e/journeys.spec.ts` starts a throwaway migrated backend and the production build,
then drives a browser. The uploaded photo is a synthetic fixture (a textured disc), so the journeys
test the software, not model accuracy.

| Journey | Steps checked |
|---|---|
| Health worker | sign up -> consent -> register patient -> choose eye -> upload -> real result: DR card with model version and estimated band, glaucoma and cataract "Model not available yet", disclaimer -> referral -> history |
| Specialist | sign in -> queue -> open case -> approve with note -> add comment -> both entries visible (append-only) |
| Unauthorized access | worker opening `/admin/users` is redirected; API returns 401 without a token and 403 with a worker token |
| Invalid input | name-like patient code rejected by the form; blank photo -> server 422 shown as "cannot be screened ... blank or uniform" |

**Result:** 16/16 passed. Screenshots of every step: [screenshots/e2e/](screenshots/e2e/).

## 4. Compatibility testing

| Browser engine | Profile | Journeys |
|---|---|---|
| Chromium (Playwright 1.48.2 build) | Pixel 5 (mobile, 393x851, touch) | 4/4 |
| Chromium | Desktop Chrome 1280x720 | 4/4 |
| Firefox (Playwright build) | Desktop Firefox | 4/4 |
| WebKit (Safari's engine) | iPhone 13 | 4/4 |

Layout: bottom tabs below 1024 px, sidebar above (screenshots for both). Limits: all on Windows 11;
no physical Android/iOS device or real Safari on macOS/iOS has been tested yet.

## 5. Performance testing

**Server (scripts/benchmark.py, 200 runs after warm-up, synthetic 1024 px JPEG):**

| Configuration | Model only mean / p95 | Full pipeline mean / p95 | Memory |
|---|---|---|---|
| All cores (default) | 55 ms / 68 ms | 74 ms / 90 ms | 90 -> 117 MB |
| 1 thread (closer to a low-end CPU) | 60 ms / 84 ms | 77 ms / 103 ms | 90 -> 117 MB |

Model file 2.6 MB; registry load (including SHA-256 check) under 0.15 s. A first run earlier the
same day, under background load, measured 110 / 166 ms means: timings vary with machine load, so
both are reported.

**Client round trip** (`e2e/performance.spec.ts`, tap "Analyse photo" to result shown, 3 runs each):

| Profile | Median |
|---|---|
| No throttling | 0.50 s |
| Emulated low-end phone: 6x CPU slowdown + slow 3G (400 ms latency, 400 kbit/s) | 3.17 s |

A repeat run gave 0.48 s and 3.09 s (all runs: [benchmarks/browser-timings.jsonl](benchmarks/browser-timings.jsonl)). This is Chrome DevTools emulation, not a physical low-end device.

**Lighthouse 12.2.1** (production build, sign-in page; protected pages need a session, which
Lighthouse cannot create):

| | Performance | Accessibility | Best practices | SEO |
|---|---|---|---|---|
| Mobile (simulated 4G, 4x CPU) | 96 | 100 | 100 | 100 |
| Desktop | 100 | 100 | 100 | 100 |

Bundle: route-level code splitting; core JS about 110 KB gzipped; the charts library (103 KB
gzipped) loads only on the admin analytics page.

## 5b. Accessibility (axe-core, WCAG 2.1 A and AA)

**Why:** Lighthouse can only reach the public sign-in page; clinical screens need checking too.
**How:** `frontend/e2e/accessibility.spec.ts` signs in as each role, creates a patient, a screening and a
referral, and runs axe-core on 15 screens (public, health worker incl. the capture step, specialist,
admin) on Chromium mobile and desktop. Results: [accessibility/](accessibility/).
**Result:** first run found 2 critical issues (the hidden camera and gallery file inputs had no labels);
after fixing, **0 violations of any severity** on all 15 screens in both profiles.

## 6. Model validation

**Reported result (validation results from the training notebook, not an independent hold-out):** on the 47,234-image validation fold at threshold
0.5, accuracy 0.790, precision 0.920, sensitivity 0.542, specificity 0.97, F1 0.682 (AUC not computed).
The **85% sensitivity target is not met**: about 46% of DR images in that fold were missed. Values are
parsed from the notebook by `scripts/extract_notebook_metrics.py`. The independent hold-out run did
not finish. The protocol that was prepared for it:
[notebooks/kaggle_holdout_eval.ipynb](../notebooks/kaggle_holdout_eval.ipynb) rebuilds the
training run's validation fold and first checks it matches the training notebook's own record
(fold size 47,234, class counts, row order, and the `.h5`'s metrics at 0.5). Then
`scripts/calibrate_threshold.py` chooses a threshold for 85% sensitivity on half of the fold and
reports every metric on the other half with 95% bootstrap intervals into
[metrics.json](metrics.json). Known bias: this fold was also used for early stopping during
training, and the dataset has no patient IDs and contains augmented near-duplicates, so any result
is an optimistic estimate.

## Improvements made because of testing

| Found by | Problem | Fix |
|---|---|---|
| Vitest (form tests) | password field dropped React Hook Form's ref: **login could never succeed** | `forwardRef` on `PasswordInput` |
| pytest (script test) | `calibrate_threshold.py` never wrote `metrics.json` (an edit had silently not applied) | rewritten and covered by an end-to-end script test |
| E2E screenshots | results listed alphabetically, so cataract (no model) appeared above DR | product order: DR, glaucoma, cataract |
| E2E screenshots | "referred because the result was manual" | plain-language referral reasons |
| Lighthouse | SEO 91: no `robots.txt` | added; SEO 100 |
| axe-core | camera and gallery file inputs had no accessible name (critical) | labelled and removed from tab order |
| Agreement test | `.tflite` differs from `.h5` by up to 0.034 (quantized export) | tolerance documented; full-fold difference recorded by the Kaggle run |
| Manual review | relative SQLite path created two databases depending on the folder | paths anchored to the repository root |
| Manual review | `.local` demo emails rejected by email validation | demo accounts use `example.org` |
