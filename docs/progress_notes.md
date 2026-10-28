# Progress notes (28 October 2026, after the remote-testing merge)

Hand-over notes for picking the work up again. Read this first.

## 1. What is on `main`
- `main` = **`974e3f90ca1de0a68cc094efc1c92e88c41c0e77`** ("Merge branch 'remote-testing'"), pushed 28 Oct.
  CI run #12 on `main` (974e3f9): all three jobs green (backend tests on PostgreSQL 16, frontend checks, Docker build).
- From `remote-testing` (docs only, no code change): `docs/remote_testing.md` = remote usability sessions over a
  Cloudflare quick tunnel (`cloudflared tunnel --url http://localhost:4173` in front of `vite preview`, which proxies
  `/api`), safety checklist, moderator script (task 1 now includes the live admin approval), results procedure.
  Verified 28 Oct through the tunnel: demo nurse sign-in, patient, upload, result page, History (offline task 3 and a
  real phone not verified). Never commit a tunnel URL.
- Earlier merge: `b34a084745cca8afa8593b1286ee0fb0fa97b777` (admin-overview; CI #10 green).
- Earlier merges: `e2ad2a5533acf9c4c349c079bd19873c48976d42` (specialty-routing; CI #8 green), `85ccc53` (wip-final-fixes).
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
- From `admin-overview`: Analytics home shows approved, active health workers / specialists / admins and the
  sign-up requests waiting for approval (links to Users); local emails (password-reset links) are also printed to
  the backend console when no `SMTP_HOST` is set (README explains SMTP); `scripts/create_admin.py` creates a personal
  admin from `PERSONAL_ADMIN_EMAIL` / `PERSONAL_ADMIN_PASSWORD` in the git-ignored `.env` (never printed or committed).
  The long health-worker E2E journey has a 120 s timeout (slow laptop under load; noted in `docs/testing_report.md`).
- Migration head: `c4e8a2f61b37` (unchanged by admin-overview). After pulling, run `alembic upgrade head` (or `scripts/reset_demo_data.py --yes`).

## 2. Final test counts (28 Oct, the code now on `main`)
| Suite | Result |
|---|---|
| Backend pytest, Python 3.14 | 302 passed |
| Backend pytest, Python 3.12 / PostgreSQL 16 (CI #10) | green |
| Vitest | 85 passed |
| TypeScript type-check / ESLint | clean / clean |
| Playwright, 4 profiles (Chromium mobile + desktop, Firefox, WebKit) | 51 passed, 3 skipped by design, 0 failed, 0 did not run (16.2 min; two earlier runs had 1 mobile-webkit timeout, fixed by the 120 s limit) |
| Browser round trip (run alone) | 0.60 s; 4.15 s on an emulated slow phone + slow 3G (was 0.44 / 2.73 s before routing; not optimised) |
| Report PDF | 5 pages |

## 3. Current branch
`main`. Branches `remote-testing`, `admin-overview`, `specialty-routing` and `wip-final-fixes` are merged and kept (local; `wip-final-fixes` also on
GitHub). No branch or tag was deleted.

## 4. Still to do, in order
0. Optional: put `PERSONAL_ADMIN_EMAIL` / `PERSONAL_ADMIN_PASSWORD` in `.env` and run `scripts/create_admin.py`.
1. Rotate the secret from the screenshot uploaded on 28 Oct (the file was deleted).
2. Reset the demo data (`scripts/reset_demo_data.py --yes`, backend stopped) and record the walkthrough video
   (`docs/video_script.md`, demo order and demo-only credentials).
3. Add the two links (video, report) to the README and the report; rebuild the PDF (5 pages max).
4. Final-submission tag on `main` and the Attempt 2 ZIP (`git archive` of `main` + the video file).
5. If time: physical-phone test, SUS usability test (remote: `docs/remote_testing.md`; results into
   `docs/usability/results.csv` and the report), HTTPS deploy, speed up the result page on slow phones.

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
