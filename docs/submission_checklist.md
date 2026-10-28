# Submission checklist

Status on 28 October 2026. Ticked items have evidence in the repository.

## Models and evidence
- [x] DR v2 trained on Kaggle and installed; checksum equals the notebook's; metrics recomputed by
  `scripts/dr_v2_metrics.py` into `docs/metrics.json` and the model card; parity test passes (24 photos, max 0.021)
- [x] Glaucoma and cataract (ODIR-5K) trained, installed and labelled with their real results (`docs/odir_metrics.json`)
- [x] DR v1 figures kept as history only (`docs/evaluation/dr_v1_metrics.json`), labelled as validation results
- [x] ~~Kaggle hold-out evaluation of DR v1 (`notebooks/kaggle_holdout_eval.ipynb`)~~ **Superseded** by the DR v2
  held-out test split (35,426 images; `docs/metrics.json`). The v1 hold-out run was never completed and is not cited
- [x] Fundus check evaluated (`scripts/evaluate_fundus_check.py`): 3 of 25 real fundus photos wrongly refused,
  0 of 77 non-eye images accepted; tuned on the same images, no face photos: labelled optimistic
- [x] Honesty labels on the README, model cards, About screen, result screens, scope table, testing report and report

## Product and tests
- [x] Sign-up request (name, email, password, requested role) pending until admin approval; one account per email;
  facility optional, set by the admin; rejection reason; staff
  accounts created by admins; no claim that anyone is verified
- [x] Nothing sent automatically: "Ask a specialist" with a question; Awaiting specialist / Reviewed / Retake needed
- [x] Specialist review: override any condition, waiting time, overdue targets; notice on results from earlier models
- [x] Capture flow (Cancel / Analyse, Retake / Upload another, Save / Discard); remove screening with a reason
- [x] Daily counts in the clinic time zone; demo reset script (keeps approved own accounts); demo credentials documented
- [x] Uploaded screenshot with a secret removed (28 Oct, via Remove screening; file deleted). Rotate that secret
- [x] All suites re-run on 28 October: `pytest -q`, `npm.cmd test`, `npm.cmd run typecheck`, `npm.cmd run lint`,
  `npx playwright test` on all four profiles (counts in README section 8)
- [x] CI green on GitHub (runs #1, #2 and #4: backend on PostgreSQL 16, frontend checks, Docker build; run #3 failed on Python 3.12 collection, fixed)
- [x] Changes of 27-28 October committed on `wip-final-fixes` and pushed
- [ ] CI green on `wip-final-fixes`, then merge into `main` and push after "OK, push"
- [ ] Physical-device test on an iPhone 13 Pro (needs the HTTPS deploy)
- [ ] Usability test with 3-5 people (SUS kit in `docs/usability/`)

## Report and video
- [x] Report updated with the real metrics and rebuilt: `node scripts/build-report.mjs` (from `frontend/`), 5 pages or fewer
- [ ] Video recorded ([video_script.md](video_script.md)), uploaded unlisted, link opens in a private window
- [ ] Video link and report link added to README lines 13-14 and the report

## Attempt 1: GitHub repository link
- [ ] `main` contains the code, README, `docs/report/report.pdf` and the video link

## Attempt 2: ZIP of the same repository
Include: the repository files, `docs/report/report.pdf`, the video file (.mp4).
Exclude: `.venv/`, `frontend/node_modules/`, `data/`, `incoming/`, `.env`, `__pycache__/`, `frontend/dist/`,
`frontend/test-results/`, `frontend/playwright-report/`, `$Recycle.Bin/`.
Easiest clean export (repository root, PowerShell): `git archive --format=zip -o ..\capstone-submission.zip main`
(only committed files, so the exclusions are automatic), then add the video file to the ZIP.
There is no APK: the app is a PWA installed from the browser on Android and iPhone.
