# Progress notes (28 October 2026, late evening)

Hand-over notes for picking the work up again. Read this first.

## 1. What is on `main`
- `main` = **`e2ad2a5533acf9c4c349c079bd19873c48976d42`** ("Merge branch 'specialty-routing'"), pushed 28 Oct.
  Earlier merge: `85ccc53` (wip-final-fixes). CI run #8 on `main` (e2ad2a5): all three jobs green (backend tests on
  PostgreSQL 16, frontend checks, Docker build).
- Contents: DR v2 + ODIR glaucoma/cataract models, fundus check (hard stop), capture flow, soft delete, demo reset
  (keeps approved own accounts), sign-up request without a facility, duplicate-email protection, Kigali daily
  counts, and from `specialty-routing`:
  - specialty routing (extension beyond the proposal): conditions + routine/urgent when asking, specialties per
    specialist, "My specialties" / "All cases", "Take this case", "Being reviewed by", overdue per priority;
  - referral policy as in the proposal's sequence diagram (configurable): uncertain cases queued automatically,
    clear positives sent by the health worker, severe (DR band 4-5) = urgent;
  - "New decisions" on the health worker's home, cleared on opening;
  - auto-refresh every 30 s (`VITE_REFRESH_SECONDS`) for the specialist queue, home and history;
  - docs: proposal compliance and sequence-diagram mapping in `docs/scope_table.md`, shared asynchronous queue,
    specialists do not prescribe, SMS/email future work; README section 11 and report AI-use statement.
- Migration head: `c4e8a2f61b37`. After pulling, run `alembic upgrade head` (or `scripts/reset_demo_data.py --yes`).

## 2. Final test counts (28 Oct, the code now on `main`)
| Suite | Result |
|---|---|
| Backend pytest, Python 3.14 | 299 passed (137 unit/algorithm + 162 API) |
| Backend pytest, Python 3.12 (as in CI) | 298 passed, 1 skipped (Keras test without TensorFlow) |
| Vitest | 84 passed |
| TypeScript type-check / ESLint | clean / clean |
| Playwright, 4 profiles (Chromium mobile + desktop, Firefox, WebKit) | 51 passed, 3 skipped by design, 0 failed |
| Browser round trip (run alone) | 0.60 s; 4.15 s on an emulated slow phone + slow 3G (was 0.44 / 2.73 s before routing; not optimised) |
| Report PDF | 5 pages |

## 3. Current branch
`main`. Branches `specialty-routing` and `wip-final-fixes` are merged and kept (local; `wip-final-fixes` also on
GitHub). No branch or tag was deleted.

## 4. Still to do, in order
1. Rotate the secret from the screenshot uploaded on 28 Oct (the file was deleted).
2. Reset the demo data (`scripts/reset_demo_data.py --yes`, backend stopped) and record the walkthrough video
   (`docs/video_script.md`, demo order and demo-only credentials).
3. Add the two links (video, report) to the README and the report; rebuild the PDF (5 pages max).
4. Final-submission tag on `main` and the Attempt 2 ZIP (`git archive` of `main` + the video file).
5. If time: HTTPS deploy, physical-phone test, SUS usability test, speed up the result page on slow phones.

## 5. Rules
- No Co-Authored-By or any attribution trailer in commit messages. README section 11 "Use of AI assistance"
  stays: one line that Claude helped build the project, plus Michael's role (designed and directed the project,
  wrote the proposal, made the scope decisions, trained the models by running the Kaggle notebooks, reviewed the
  results, responsible for the work). The report carries the same statement.
- Never push `main` until Michael types "OK, push" for that step. Push only the branch named.
- Stop the backend before any checkout or merge (Windows locks `models/*/model.tflite` while it runs).
- Do not delete any branch or tag (backup branches, `legacy-streamlit-prototype`).
- Demo-only credentials: admin@example.org / DemoAdmin2026!, specialist@example.org / DemoSpecialist2026!,
  nurse@example.org / DemoNurse2026!.
- Honesty labels as in CLAUDE.md section 3 (DR held-out split by image; glaucoma below target, precision about
  10%; cataract 46 positive test eyes; fundus check 3/25 wrongly refused, 0/77 accepted, optimistic).
