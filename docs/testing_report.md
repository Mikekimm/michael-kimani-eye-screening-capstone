# Testing, validation and performance report

Results were produced on 26-28 October 2026 on the development laptop (Windows 11 Pro, Intel CPU with
8 logical cores, Python 3.14.6, Node 24.22.1) unless stated otherwise, and in GitHub Actions (Ubuntu,
PostgreSQL 16). Commands to reproduce them are in the [README](../README.md#8-tests).

Seven strategies were used, each chosen for a specific risk in a screening-and-referral tool:

| # | Strategy | Risk it addresses | Tooling | Result |
|---|---|---|---|---|
| 1 | Unit testing of algorithms | wrong decision logic silently mis-triages patients | pytest, Vitest | 137 backend ML and algorithm tests + 84 Vitest tests pass |
| 2 | Integration testing of the API with the real models | layers work alone but not together; RBAC gaps; fake accounts | pytest + FastAPI TestClient + LiteRT; PostgreSQL in CI | 162 API tests pass (incl. 60 role-matrix and signed-out cases) |
| 3 | End-to-end functional testing | the user cannot complete a clinical task; a stranger gets in | Playwright | 12 tests x 4 browser/device profiles: 48/48 pass |
| 4 | Compatibility testing | works in one browser only | Playwright: Chromium, Firefox, WebKit | all 12 tests pass on all three engines |
| 5 | Performance testing | too slow on clinic hardware or networks | benchmark script, Playwright + CDP throttling, Lighthouse | 74 ms server pipeline (DR v1); 0.60 s / 4.15 s round trip; Lighthouse 96-100 |
| 5b | Accessibility testing | health workers with low vision or screen readers cannot use it | axe-core (WCAG 2.1 A/AA) on every screen | 0 violations on 20 audited pages, mobile and desktop |
| 6 | Model validation and parity | the model is worse than claimed, or the app feeds it differently from training | held-out test splits; recomputation with the app's code; 24-photo parity test | DR sensitivity 0.851 (target met), specificity 0.748 (not met); app reproduces notebook scores within 0.021 |

Usability testing with health workers (SUS questionnaire, kit in [usability/](usability/)) is planned but
**has not been run**.

---

## 1. Unit testing of algorithms

**Why:** every clinical decision passes through a few small algorithms. A boundary error (for
example `>` instead of `>=` at the threshold) would turn referrals into "no signs detected" with
no visible failure.

**How:** boundary-value and property tests on the pure functions.

| Area | File | Tests | What is checked |
|---|---|---|---|
| Risk policy and referral advice | `backend/tests/ml/test_risk_policy.py` | 35 | every band edge, uncertain zone, referral-suggestion switches, which recommendations are queued automatically, severe (band 4+) = urgent, queued conditions, all read from the config, the screening-level recommendation (`ReferralAdvisor`: positive, borderline, quality warnings), invalid config; a sweep of 1,001 scores proves bands never contradict the decision |
| Threshold selection | `test_thresholding.py` | 10 | known confusion matrices; chosen threshold is the highest meeting the sensitivity target |
| Evaluation | `test_evaluation.py` | 11 | stratified split keeps class ratios; AUC equals scikit-learn's; bootstrap intervals contain the estimate |
| Preprocessing / quality / fundus check | `test_preprocessing.py`, `test_quality.py` | 26 | [-1, 1] scaling; nearest-neighbour copies pixels, bilinear stays in float like TensorFlow; blank and tiny images block; non-eye images block before any model runs; fundus-like images at several brightness levels pass; blur and darkness warn |
| Registry and model cards | `test_registry.py` | 15 | checksum mismatch, bad card, wrong folder, missing file, and a card that does not name its resize are rejected; each card names the resize it was trained with |
| Review targets, daily counts, demo reset | `test_review_targets.py`, `test_daily_counts.py`, `test_reset_demo_data.py` | 10 | urgent 24 h / routine 72 h due times, overdue one second after; a screening at 23:59 and one at 00:01 Kigali time fall on different days; the reset refuses anything but the local SQLite file, backs it up first and carries approved own accounts over unchanged |
| Rate limits, patient codes, SUS score | `test_throttle.py`, `test_patient_codes.py`, `test_sus_score.py` | 18 | sliding window and Retry-After; check character catches typos; SUS arithmetic |
| Backoff and sync queue | `frontend/src/offline/*.test.ts` | 15 | **reply lost after the server saved** -> retry creates no duplicate; stops at first network error and keeps order; backoff with jitter; attempt limit |
| Waiting time, image hints | `utils.test.ts`, `imageQuality.test.ts` | 8 | "30 min", "5 h", "3 days" for a case referred at midnight; sharpness and brightness hints |

**Checking the tests themselves:** I deliberately broke the code (band 3 returned as 2; the
append-only guard disabled). 10 tests failed as expected, then the code was restored.

## 2. Integration testing (API + database + real models)

**Why:** most security and data-integrity rules live where layers meet: who may see a record,
whether a stranger can get in, whether a retried upload duplicates, whether review history can be rewritten.

**How:** each test gets a fresh database and calls the real HTTP API. Screening tests use the **real,
checksum-verified DR, glaucoma and cataract models**. Referral and review tests that need a forced score
use a clearly labelled test double (`FixedScoreModel`); it is never used outside tests. In CI the same
suite runs against **PostgreSQL 16** after `alembic upgrade head`:
[run #1](https://github.com/Mikekimm/michael-kimani-eye-screening-capstone/actions/runs/40503709691) (final-app)
and [run #2](https://github.com/Mikekimm/michael-kimani-eye-screening-capstone/actions/runs/40503744036) (main),
27 October 2026, all three jobs green (backend tests on PostgreSQL, frontend checks, Docker image build).
After the 28 October changes, [run #3](https://github.com/Mikekimm/michael-kimani-eye-screening-capstone/actions/runs/40672299037) failed: the migrations applied on PostgreSQL but pytest could not collect the tests on Python 3.12 (see the last section); after the fix [run #4](https://github.com/Mikekimm/michael-kimani-eye-screening-capstone/actions/runs/40675193040) passed all three jobs.

| Area | Tests | Highlights |
|---|---|---|
| Auth and approval | 36 | sign-up is a **pending request**: with the correct password, sign-in returns 403 "Your account is waiting for administrator approval."; the requested role (health worker or specialist) grants nothing until approved; admin cannot be requested; sign-up has no facility field (422 if sent); a duplicate email (any case) is refused and leaves the existing account's name, password hash, role, status and requested role unchanged, for a pending and an approved account; the admin approves with the requested or another role and may set the facility (audited), or rejects with a reason, which is emailed; each decision audited; password needs a letter and a number; sign-ups rate-limited (429); Argon2id; refresh rotation; logout revokes; password reset |
| RBAC | 65 | every protected route x every role (45) and without a token (15): a health worker gets 403 on specialist and admin routes, a specialist gets 403 on admin routes; self-promotion blocked; workers cannot see each other's patients |
| Screenings | 21 | all three real models return a score in [0, 1]; DR has a band, glaucoma/cataract do not; a condition without a model is "not available" with no score; idempotent `client_uuid`; blank / tiny / **non-eye photo** / non-image / wrong type / oversized / future timestamp / bad eye / no consent rejected with nothing saved; specialist overrides a glaucoma result |
| Routing (extension) | 9 | ask names conditions and priority (default urgent for a severe result); conditions must have been scored; "My specialties" first ("general" matches all); Take this case: idempotent, others get 409 and cannot decide, the health worker sees "Being reviewed by"; deciding without Take also takes it; a health worker cannot take or decide (403); only open queued cases can be taken; admin sets specialties on approval and later (audited, invalid ones 422); overdue counted per priority |
| Workflow | 26 | **uncertain (borderline or low-quality) cases are queued automatically, routine, and the health worker can add a question once; clear positives and negatives are not queued**; "new decision" shows until the health worker opens the screening (not when the specialist opens it); "Ask a specialist" needs a question and works once, only for the owner, also for a negative result; recommendation for positive and borderline scores (borderline score derived from the model card's threshold); approve / override / retake (shown as "Retake needed") / comment; remove screening hides it, keeps the audit and deletes the photo; History day filter in the clinic time zone; append-only history; sync pull; analytics without identifiers; waiting time, priority and overdue flag in the queue, on the screening and in admin analytics |

**Inputs varied:** positive, borderline and negative scores; real fundus photos and synthetic images; blank,
tiny, corrupt, wrong-type and oversized uploads; non-eye images; questions that are too short; weak passwords; valid and invalid
tokens; every role.

## 3. End-to-end functional testing (Playwright)

**Why:** to prove a real user can finish each core task through the real UI, API and models.

**How:** the specs start a throwaway migrated, seeded backend and the production build, then drive a browser. The clinical journeys upload a synthetic fixture, so they test
the software, not model accuracy.

| Journey | Steps checked |
|---|---|
| Fake sign-up (supervisor's check) | sign up (name, email, password, role only) -> "pending" -> wrong password: "Incorrect email or password" -> correct password: "waiting for administrator approval" -> admin sees name, email, requested role, no facility -> records a facility and approves -> sign-in works |
| Duplicate email | a second sign-up with the same email in upper case, another name, password and role -> "already registered"; the admin still sees one account with the original name and role; the second password does not work |
| Specialist sign-up | request specialist -> sign-in refused (403) -> admin approves with the requested role preselected -> the new specialist sees the review queue; a health worker is sent away from it and the API returns 403 |
| Rejection | admin clicks Reject -> "Give a reason." -> rejects with a reason -> reason shown; sign-in still 403 |
| Capture flow | Cancel discards the chosen photo; a non-eye photo is refused ("does not look like a retinal fundus photograph ... Nothing was saved") with Retake / Upload another and no screening stored; Upload another with a usable photo gives a result; Save keeps it; Discard needs a reason and removes it |
| Health worker | sign up -> admin approval -> consent -> register patient -> eye -> Cancel / Analyse -> DR v2.0 card with band; glaucoma and cataract cards with model versions, "Binary result only" -> status is **not** "Awaiting specialist" -> Ask a specialist with a question -> "Awaiting specialist", the question, waiting time and review target -> history |
| Specialist | queue shows the question -> open case -> glaucoma reliability box ("false alarms") -> override glaucoma with a reason -> approve with note -> comment -> all entries kept |
| Routing loop | ask about DR, urgent -> the specialist's "My specialties" tab -> Take this case -> "Taken by you" -> the health worker sees "Being reviewed by Demo Specialist" -> approve with a note -> History shows "Reviewed" and "New decision" -> opening the screening clears it |
| Decision returns | health worker's History shows "Reviewed" and the decisions; a second case answered with a retake request shows "Retake needed" with the specialist's note |
| Unauthorized access | worker opening `/admin/users` is redirected; API returns 401 without a token and 403 with a worker token |
| Invalid input | future year of birth rejected by the form; blank photo -> server 422 shown as "blank or uniform" with Upload another |

Screenshots of every step: [screenshots/e2e/](screenshots/e2e/) (files `10-` to `12-` show the fake sign-up).

## 4. Compatibility testing

| Browser engine | Profile | Journeys |
|---|---|---|
| Chromium (Playwright 1.48.2 build) | Pixel 5 (mobile, 393x851, touch) | 12/12 (+ accessibility, performance) |
| Chromium | Desktop Chrome 1280x720 | 12/12 (+ accessibility) |
| Firefox (Playwright build) | Desktop Firefox | 12/12 |
| WebKit (Safari's engine) | iPhone 13 | 12/12 |

Full run on 28 October evening (with routing and the referral policy): 51 passed, 3 skipped by design, 0 failed
(16 min). Earlier full run that day: 47 passed, 3 skipped, 0 failed (7.2 min). A first full run that day, made
while the backend suite and a manual demo ran at the same time, had 5 timeouts; re-run alone they passed except
two genuine test bugs (an old button label; a timeout too short for four Firefox sessions), which were fixed.
This long journey test needed a longer timeout on mobile-webkit (60 s raised to 120 s for that one test only) because
the development laptop is slow under load: it timed out twice in full runs on admin-overview (46 passed, 1 failed,
3 skipped, 4 did not run), at a different step each time. The test itself and its assertions were not weakened. Full run after the change (all four profiles): 51 passed,
3 skipped by design, 0 failed, 0 did not run (16.2 min).

Layout: bottom tabs below 1024 px, sidebar above. Limits: all on Windows 11; no physical Android/iOS
device or real Safari on iOS has been tested yet (planned on an iPhone 13 Pro after the HTTPS deploy).

## 5. Performance testing

**Server (scripts/benchmark.py, 200 runs after warm-up, synthetic 1024 px JPEG; measured 26 October with
the DR v1 model, 2.6 MB):**

| Configuration | Model only mean / p95 | Full pipeline mean / p95 | Memory |
|---|---|---|---|
| All cores (default) | 55 ms / 68 ms | 74 ms / 90 ms | 90 -> 117 MB |
| 1 thread (closer to a low-end CPU) | 60 ms / 84 ms | 77 ms / 103 ms | 90 -> 117 MB |

The served models are now three float32 files of about 9 MB each; the benchmark has not yet been
re-run with them.

**Client round trip** (`e2e/performance.spec.ts`, tap "Analyse" to result shown, 3 runs each):

| Profile | Median |
|---|---|
| No throttling | 0.60 s (earlier on 28 Oct: 0.44 s; 26 Oct, DR v1 only: 0.50 s) |
| Emulated low-end phone: 6x CPU slowdown + slow 3G (400 ms latency, 400 kbit/s) | 4.15 s (earlier on 28 Oct: 2.73 s; 26 Oct: 3.17 s) |

The evening figures were measured after specialty routing, automatic queueing, "New decisions" and auto-refresh
were added, with the spec run alone; inside the full 16-minute run the throttled median was 6.1 s. The slower
throttled time is a real regression of about 1.4 s on an emulated slow phone (more data and requests on the
result page); it has not been optimised yet.

Measured 28 October with all three models, on a quiet machine. An earlier run the same day, while the backend
test suite ran in parallel, failed its 240 s limit for a wrong button label in the test (fixed).

All runs: [benchmarks/browser-timings.jsonl](benchmarks/browser-timings.jsonl). This is Chrome DevTools
emulation, not a physical low-end device; a later run under heavy laptop load measured 5.4 s throttled.

**Lighthouse 12.2.1** (production build, sign-in page): mobile 96/100/100/100, desktop 100/100/100/100
(performance / accessibility / best practices / SEO).

## 5b. Accessibility (axe-core, WCAG 2.1 A and AA)

`frontend/e2e/accessibility.spec.ts` signs in as each role, creates a patient, a screening and a
referral, and runs axe-core on 20 pages (public, health worker incl. the capture steps, specialist,
admin, and the Ask a specialist form) on Chromium mobile and desktop. Results, with the selector of any failing element:
[accessibility/](accessibility/).

**Found and fixed:** the hidden camera and gallery inputs had no labels (critical); and on 27 October,
once the new models started referring the test image, the amber "Awaiting specialist" and "Borderline"
badges failed contrast (4.3:1 against 4.5:1 required). The colour was darkened from 34% to 30%
lightness; 0 violations of any severity since.

## 6. Model validation and parity

**DR v2** ([notebooks/dr_v2_finetune.ipynb](../notebooks/dr_v2_finetune.ipynb), outputs in
[evaluation/dr_v2/](evaluation/dr_v2/)): split 70/15/15 by image group (train 165,319 / validation
35,425 / test 35,426). The threshold (0.418) was chosen on validation as the highest with sensitivity
>= 85%; the test split was scored once.

| Test split (35,426 images) | Sensitivity | Specificity | Precision | AUC |
|---|---|---|---|---|
| At threshold 0.418 | **0.851** (95% CI 0.845-0.857) | **0.748** (0.743-0.754) | 0.706 | 0.900 |
| At 0.5 (for comparison) | 0.799 | 0.845 | 0.786 | |

Sensitivity target met; **specificity target (80%) not met**. Referable DR (grade 2+) sensitivity 0.869.
Label: held-out test split by image (no patient IDs available; near-duplicates could not be excluded); not
external validation; not clinically validated. The notebook found as many image groups as images
(236,170), so augmented copies and a patient's two eyes could not be grouped: these figures may be
optimistic.

**Recomputation:** `scripts/dr_v2_metrics.py` reads the notebook's validation and test predictions and
recomputes the threshold and every figure with the app's own `select_threshold`, `metrics_at_threshold`
and bootstrap code; it stops if anything differs from the notebook. Threshold, sensitivity, specificity,
precision, accuracy, F1 and AUC matched exactly. The specificity interval differs in the third decimal
from the notebook's (0.742-0.754) because the two bootstrap implementations differ; the app's is reported.
`test_notebook_metrics.py` repeats this check on every test run.

**Parity (does the app feed the model exactly as the notebook did?):** the notebook saved 24 of its test
photos with the score its TFLite file gave each one. `test_dr_parity.py` runs the same photos through the
app's own pipeline (Pillow decode, bilinear resize from the model card, scaling, LiteRT):

| | Result |
|---|---|
| Served file SHA-256 | `eb2603ab5b8ed412ac4462fc7fcad3cc6b8b84a7a7bf5d711ba24b673f05eb30`, equal to the notebook's `results.json` |
| Largest score difference from the notebook | **0.021** (mean 0.005) |
| Tolerance | 0.03, chosen by me; it is not a standard. I set it after the first measurement, so the stronger evidence is the next row |
| Screening decisions changed | **0 of 24** |
| Same test with nearest-neighbour resize (the old hard-coded default) | largest difference 0.68, **6 of 24 decisions changed** |

A small difference is expected because the app and the notebook use different image-decoding and resize
code (TensorFlow's JPEG decoder and `tf.image.resize` versus Pillow). The parity photos come from the
dataset and are not committed, so this test skips in CI and runs where `incoming/dr_v2/parity/` exists.
The Keras-vs-TFLite agreement test also passes (tolerance 1e-3; the notebook measured 9.8e-06).

**Glaucoma and cataract** ([notebooks/odir_glaucoma_cataract.ipynb](../notebooks/odir_glaucoma_cataract.ipynb),
[odir_metrics.json](odir_metrics.json)): split by patient, thresholds chosen on validation, test scored
once with the exported file; all integrity checks in the notebook passed.

| Test split | Sensitivity | Specificity | Precision | AUC | Positives |
|---|---|---|---|---|---|
| Glaucoma (1,040 eyes) | 0.762 | 0.721 | **0.103** | 0.818 | 42 |
| Cataract (1,044 eyes) | 0.978 | 0.962 | 0.542 | 0.991 | 46 |

Glaucoma is below both targets and about 9 in 10 of its positive flags are false alarms; the result
screens say so next to every glaucoma result. Cataract meets both targets, but with 46 positives the
intervals are wide. ODIR-5K labels come from free-text keywords and may be noisy.

**History:** the earlier DR model (v0.3) reported sensitivity 0.542 on its training-notebook validation
fold ([evaluation/dr_v1_metrics.json](evaluation/dr_v1_metrics.json)). Results it produced keep its version
label, and the app shows a notice on them instead of re-scoring them silently.

## 7. Fundus check (refusing non-eye photos)

The classifiers always return a score, even for a photo of a desk, so a separate check runs first
(`FundusCheck` in `backend/app/ml/quality.py`: dark corners, a brighter centre, red/green ratio, fraction of
the frame that is lit). A photo that fails is refused with HTTP 422 and nothing is saved.
`scripts/evaluate_fundus_check.py` on the images available locally:

| Images | Count | Wrongly decided |
|---|---|---|
| Real fundus photos (dataset images) | 25 | **3 wrongly rejected** (all grey-background processed dataset images) |
| Non-eye images | 77 | **0 wrongly accepted** |

The thresholds were tuned on these same images and no photos of faces were available, so the figures are
optimistic. The check is a heuristic and can be fooled; it is not a trained classifier.

## Improvements made because of testing

| Found by | Problem | Fix |
|---|---|---|
| CI run #3 (PostgreSQL, Python 3.12) | pytest stopped at collection (exit 2); reproduced locally with Python 3.12: `list[datetime]` inside a class with a `list` method fails on 3.12 (3.14 evaluates annotations lazily), and `tzdata` was missing for `Africa/Kigali` | `from __future__ import annotations` in the repositories, `tzdata` pinned; full suite on 3.12: 276 passed, 1 skipped (Keras test without TensorFlow) |
| Manual test (28 Oct) | "Incorrect email or password" for the developer's own account | cause found in the database backups: `reset_demo_data.py` (run twice that day) recreated the database with only the demo accounts, deleting the account; a later sign-up with the same email created a new pending account, which the second reset also deleted. It was not a duplicate-email bug (a duplicate is refused with 409). Fix: the reset now carries approved non-demo accounts over unchanged; the account was restored from the backup; duplicate-email tests added |
| Supervisor's live test (28 Oct) | a screenshot containing a secret was accepted and scored as an eye | fundus check as a hard stop before any model runs; Remove screening deletes the photo file; the uploaded file was removed |
| Supervisor's live test (28 Oct) | every positive or borderline result was sent to the specialist automatically | first: nothing automatic, "Ask a specialist" with a question; then, to match the proposal's sequence diagram, a configurable policy: only uncertain cases are queued automatically, clear positives are sent by the health worker |
| Supervisor's live test (28 Oct) | "Screened today" counted in the phone's time zone from the last 50 screenings | server-side counts in the clinic time zone (`TIME_ZONE`), tested at 23:59 vs 00:01 |
| Parity test | the app resized every photo with nearest-neighbour; DR v2 was trained with bilinear: 6 of 24 decisions would have changed | each model card states its resize; the pipeline uses it; a card without one is refused |
| Full test run after the DR v2 install | a borderline test hard-coded the old 0.5 threshold | the borderline score is derived from the model card |
| Supervisor's live test | a fake sign-up seemed to get in | audit log showed the fake account never signed in (the browser signed in the developer's own account); approval was already enforced. Added rejection reasons, password rule, sign-up rate limit and an E2E test of the whole path |
| axe-core | amber badges below 4.5:1 contrast | colour darkened |
| Vitest (form tests) | password field dropped React Hook Form's ref: **login could never succeed** | `forwardRef` on `PasswordInput` |
| pytest (script test) | `calibrate_threshold.py` never wrote `metrics.json` | rewritten and covered by an end-to-end script test |
| E2E screenshots | results listed alphabetically | product order: DR, glaucoma, cataract |
| Lighthouse | SEO 91: no `robots.txt` | added; SEO 100 |
| Manual review | relative SQLite path created two databases depending on the folder | paths anchored to the repository root |
