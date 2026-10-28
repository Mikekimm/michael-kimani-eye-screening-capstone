# Progress notes (28 October 2026, evening)

Hand-over notes for picking the work up again. Read this first.

## 1. What is on `main`
- `main` = **`85ccc53f7df3f4892ee11e82f72ab3ee673866bd`** ("Merge branch 'wip-final-fixes'"), pushed 28 Oct.
  It contains everything up to the 28 October fixes: DR v2 + ODIR glaucoma/cataract models, fundus check (hard
  stop), capture flow, soft delete, demo reset (keeps approved own accounts), sign-up request without a facility
  (admin sets it on approval), duplicate-email protection, Kigali daily counts, Python 3.12 fix + tzdata, docs,
  proposal compliance table, report PDF (5 pages).
- CI on GitHub: run #6 on `main` (85ccc53) green; runs #4 and #5 on `wip-final-fixes` green; run #3 failed
  (Python 3.12 collection, fixed).

## 2. Final test counts on `main` (28 Oct)
| Suite | Result |
|---|---|
| Backend pytest, Python 3.14 | 277 passed (134 unit/algorithm + 143 API) |
| Backend pytest, Python 3.12 (as in CI) | 276 passed, 1 skipped (Keras test without TensorFlow) |
| Vitest | 78 passed |
| TypeScript type-check / ESLint | clean / clean |
| Playwright, 4 profiles (Chromium mobile + desktop, Firefox, WebKit) | 47 passed, 3 skipped by design, 0 failed |
| Live demo path against the real backend | 10/10 steps passed |

## 3. Current branch: `specialty-routing` (from `main`, not merged, not pushed)
Work in progress, uncommitted at the time of writing:
- Specialty routing (extension beyond the proposal): conditions + routine/urgent on "Ask a specialist";
  specialties per specialist (admin sets them); "My specialties" / "All cases"; "Take this case"; "Being reviewed
  by"; overdue per priority in analytics. Migration `c4e8a2f61b37`.
- Proposal-alignment items 9 to 13, coded:
  9. Referral policy in `risk_policy.json` (`referral_advice.queue_automatically`, `urgent_from_band`): uncertain
     cases queued automatically, clear positives sent by the health worker, severe = urgent.
  10. "New decisions" on the health worker's home + "New decision" mark in History, cleared on opening.
  11. Scope table: uncertain flag-and-queue and decision pull-back marked met; sequence-diagram step table.
  12. Auto-refresh every 30 s (`VITE_REFRESH_SECONDS`) for the specialist queue, home and history.
  13. Wording: asynchronous shared queue, specialists do not prescribe, SMS/email future work.
- Last partial runs on the branch: backend affected suites 91 passed; Vitest 84 passed; key E2E specs on desktop
  Chrome 8 passed. Still to run: full pytest (3.14 and 3.12), full Playwright on 4 profiles, report PDF rebuild.

## 4. Still to do, in order
1. Finish items 9 to 13 on `specialty-routing`: full test runs, PDF (5 pages max), small commits, push the branch,
   show the planned merge and wait for "OK, push".
2. Rotate the secret from the screenshot that was uploaded on 28 Oct (the file was deleted).
3. Walkthrough video (script and demo order in `docs/video_script.md`), then the two links (video, report) in the
   README and the report.
4. Final-submission tag and the Attempt 2 ZIP (`git archive` of `main` + the video file).
5. If time: HTTPS deploy, physical-phone test, SUS usability test.

## 5. Rules
- No Co-Authored-By or any attribution trailer in commit messages. README section 11 "Use of AI assistance"
  stays in place and accurate, and the report carries the same statement.
- Never push `main` until Michael types "OK, push" for that step. Push only the branch named.
- Stop the backend before any checkout or merge (Windows locks `models/*/model.tflite` while it runs).
- Do not delete any branch or tag (backup branches, `legacy-streamlit-prototype`).
- Demo-only credentials: admin@example.org / DemoAdmin2026!, specialist@example.org / DemoSpecialist2026!,
  nurse@example.org / DemoNurse2026!.
- Honesty labels as in CLAUDE.md section 3 (DR held-out split by image; glaucoma below target, precision about
  10%; cataract 46 positive test eyes; fundus check 3/25 wrongly refused, 0/77 accepted, optimistic).
