# Progress notes (28 October 2026)

Working notes for picking the work up again. Nothing below is committed: the last commit is `0067f93`
(Render blueprint). No commit or push until Michael types "OK, push". No Co-Authored-By or Claude trailers on
any commit; AI help is acknowledged only in README section 11 ("I used Claude to help me build this project.").

## 1. Done and verified (real test output)

### Models (27 October)
- DR v2.0 installed (`models/dr/`, `mobilenetv2-dr-binary-2.0`, threshold 0.41817, bilinear resize). SHA-256
  `eb2603ab5b8ed412ac4462fc7fcad3cc6b8b84a7a7bf5d711ba24b673f05eb30` equals the notebook's `results.json`.
- Metrics recomputed from the notebook's predictions with the app's own code (`scripts/dr_v2_metrics.py`): test split
  35,426 images, sensitivity 0.851 (95% CI 0.845-0.857), specificity 0.748 (0.743-0.754), precision 0.706, AUC 0.900.
- Parity: the app reproduces the notebook's scores on 24 test photos, max difference 0.021 (tolerance 0.03, my
  choice), 0 decisions changed; nearest-neighbour resize would have changed 6 of 24. Resize now comes from each model card.
- Glaucoma and cataract (ODIR-5K) installed: glaucoma sens 0.762 / spec 0.721 / precision 0.103 on 1,040 eyes (42
  positive); cataract 0.978 / 0.962 / 0.542 on 1,044 eyes (46 positive).

### Fixes from Michael's test (28 October), code done
| Item | State | Evidence |
|---|---|---|
| Uploaded screenshot with a secret | Located, **not yet deleted**: screening `467fb416f05e44eca12238bcf0a62226` (patient PHC-MXPTKJ), file `data/uploads/52a397510df6417e8033344d79b9afb4.png`. `data/` is gitignored and no upload has ever been in git history; only one copy on disk | see section 5 |
| Non-eye images are a hard stop | Done: `FundusCheck` in `backend/app/ml/quality.py` blocks before any model runs; nothing saved (422) | 25 real fundus photos: 3 wrongly rejected (all grey-background processed dataset images); 77 non-eye images: 0 wrongly accepted (`scripts/evaluate_fundus_check.py`). Tuned on the same images, no face photos available: optimistic |
| Cancel / Analyse, Retake / Upload another, Save / Discard | Done (`ScreenPage.tsx`, `ImageCaptureGuide.tsx`, `ScreeningDetailPage.tsx`) | Vitest `ScreenPage.test.tsx` 2/2; Playwright `capture.spec.ts` passes on desktop Chrome |
| Soft delete with reason | Done: `POST /screenings/{id}/discard`, owner health worker only, hidden everywhere, photo file deleted, audit entry kept | `test_discard_hides_the_screening_keeps_the_audit_and_deletes_the_photo` |
| Demo reset | Done as a command, not a button: `scripts/reset_demo_data.py --yes` (local SQLite under `data/` only; backs up, recreates via Alembic, re-seeds; never deletes append-only review rows) | `test_reset_demo_data.py` 4/4 |
| Referral rule: nothing automatic | Done: labels "No referral needed" / "Refer recommended" / "Uncertain, consider asking a specialist"; only "Ask a specialist" (with a question) sends a case; "Awaiting specialist", "Reviewed", "Retake needed" for sent cases. Logic in `ReferralAdvisor` (`risk_policy.py`) + `config/risk_policy.json` | workflow tests; journeys E2E incl. retake loop |
| Sign-up: requested role, free-text facility, no registration number | Done: pending until approved; requested role grants nothing; admin approves with that role or another, or rejects with a reason; every decision audited. Facility list feature removed | `test_auth.py`, `approval.spec.ts` (incl. specialist sign-up -> only the specialist sees the queue) |
| Registration number removed | Done in code, schema, migration (`7a3c5e9b1d20` drops the column), tests, seed, sign-up and admin screens. **Docs still mention it** (section 3) | `test_admin_role_cannot_be_requested_and_registration_numbers_are_gone` |
| Daily counts | Done: was a browser count of the last 50 screenings in the phone's time zone. Now server-side in setting `TIME_ZONE` (default Africa/Kigali); History has a day filter and 7-day counts; admin per-day chart uses the same zone | `test_daily_counts.py` (23:59 vs 00:01), `test_history_can_be_filtered_by_day_in_the_clinic_time_zone` |
| Old-result notice | Done (27 Oct), also on the specialist screen | `results.test.tsx` |

### Latest real test runs (28 October)
- Backend pytest: **269 passed** (full run), then `test_reset_demo_data.py` 4 passed separately (not yet in a full run).
- Vitest: last full run 76 passed + 2 failed; the 2 (capture flow) were fixed and pass alone (2/2). **Full re-run pending.**
- TypeScript type-check and ESLint: clean.
- Playwright, desktop Chrome only: **11 passed, 1 skipped**. **Full 4-profile run pending.**

### Local database
- `data/app.db` migrated to `7a3c5e9b1d20` and seeded; all existing users and screenings load.
  Backups: `data/app.db.bak-before-facilities`, `data/app.db.bak-before-access-rework`.
- The backend on port 8000 is **stopped** (it was stopped for the migration). Start it again with
  `cd backend; ..\.venv\Scripts\python -m uvicorn app.main:app --port 8000`.

## 2. In progress right now
Nothing is half-edited. The code for every fix above is complete; what remains is verification and documentation.

## 3. Still to do, in order
1. Delete the secret screenshot (section 5) and rotate that secret.
2. Full test runs: `pytest -q`, `npm.cmd test`, typecheck, lint, `npx playwright test` (all 4 profiles); record real counts.
3. Docs to update for the 28 October changes, all with the same labels and numbers:
   - README: features, roles section, new "How access is controlled" section, registration number removed,
     facility list removed (now free text), referral rule, capture flow, daily counts, test counts.
   - Report (`docs/report/report.html`): same, plus "How access is controlled"; rebuild with
     `node scripts/build-report.mjs` from `frontend/` (5 pages max).
   - `docs/scope_table.md`, `docs/testing_report.md` (fundus-check counts, new tests), `docs/risk_policy.md`
     (referral advice replaces automatic referral), `docs/video_script.md` (new flow, demo credentials, no
     registration number or facility list), `docs/submission_checklist.md`, `CLAUDE.md` sections 3/4/12b,
     `docs/data_and_evaluation.md` if affected.
   - Search the repo for "registration number", "registration_number", "Staff ID", "facility list",
     "Facilities page", "auto_refer", "Refer to a specialist anyway" and list every change.
4. Commits (small, conventional, no trailers), then push only after "OK, push".
5. At the push: delete the backup branches and tags holding the 33 old Claude trailers, and the
   `legacy-streamlit-prototype` tag (13), as Michael approved:
   `git push origin --delete backup-before-history-edit-main backup-before-history-edit-final-app`,
   `git push origin :refs/tags/backup-before-history-edit-main :refs/tags/backup-before-history-edit-final-app :refs/tags/legacy-streamlit-prototype`,
   then the same names locally (`git branch -D ...`, `git tag -d ...`).
6. After the push: CI green; Render HTTPS deploy + SMTP; iPhone 13 Pro and Android test; then (if time)
   on-device inference and a load balancer; SUS usability test; video; Attempt 2 ZIP.

## 4. Honesty rules and agreed labels
- Real trained models only; never invent or estimate a number; only values from `results.json`, the model cards,
  `docs/metrics.json` or `docs/odir_metrics.json`.
- DR label: "held-out test split by image (no patient IDs available; near-duplicates could not be excluded); not
  external validation; not clinically validated". Sensitivity target met, specificity target (80%) not met.
- Glaucoma: "below target, limited evidence", always shown with precision 0.103 (about 9 in 10 flags are false alarms).
  Cataract: meets targets, limited evidence (46 positives). ODIR labels are free-text keywords and may be noisy.
- DR v0.3 figures (sensitivity 0.542, validation fold) are history only; its hold-out run never finished.
- Screening support only, not a diagnosis. The 1-5 band is an estimate, not an ICDR grade.
- The app cannot verify who someone is; sign-up is a request an admin approves. Never claim verification.
- The fundus check is a heuristic and can be fooled; the classifiers cannot detect non-eye images themselves.
- Offline = capture and queue; scoring happens on the server after sync (no on-device inference).
- Review targets (urgent 24 h, routine 72 h) are a design decision, not a proposal requirement.

## 5. Deleting the uploaded secret
Option A (in the app, once the backend runs): sign in as the account that uploaded it, open that screening and
press "Remove screening" with a reason. The photo file is deleted; the record and audit entry stay.
Option B (directly): stop the backend, then
`Remove-Item C:\Users\HP\michael-kimani-eye-screening-capstone\data\uploads\52a397510df6417e8033344d79b9afb4.png`
(the screening row then shows "Image unavailable"). The backups `data/app.db.bak-*` hold database rows only, no
photos. Rotate the secret either way.

## 6. Uncommitted changes
About 95 modified files and 22 new ones (backend, frontend, tests, docs, models, scripts), plus 58 refreshed E2E
screenshots. New files include migration `7a3c5e9b1d20`, `services/daily_counts.py`, `services/review_targets.py`,
`scripts/reset_demo_data.py`, `scripts/evaluate_fundus_check.py`, `scripts/dr_v2_metrics.py`,
`e2e/capture.spec.ts`, `e2e/approval.spec.ts`, `e2e/fixtures/not-a-fundus.png`, `models/glaucoma/`,
`models/cataract/`, `models/dr/model.keras`, `docs/evaluation/dr_v2/`. Deleted: `models/dr/model.h5`.
`incoming/` (Kaggle downloads, parity photos) is gitignored and must stay out of the ZIP.
