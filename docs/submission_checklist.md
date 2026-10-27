# Submission checklist

Status on 27 October 2026. Ticked items have evidence in the repository.

## Models and evidence
- [x] DR v2 trained on Kaggle and installed; checksum equals the notebook's; metrics recomputed by
  `scripts/dr_v2_metrics.py` into `docs/metrics.json` and the model card; parity test passes (24 photos, max 0.021)
- [x] Glaucoma and cataract (ODIR-5K) trained, installed and labelled with their real results (`docs/odir_metrics.json`)
- [x] DR v1 figures kept as history only (`docs/evaluation/dr_v1_metrics.json`), labelled as validation results.
  Its independent hold-out run (`notebooks/kaggle_holdout_eval.ipynb`) was **not completed**; DR v2's held-out
  test split replaces it
- [x] Honesty labels on the README, model cards, About screen, result screens, scope table, testing report and report

## Product and tests
- [x] Sign-up pending until admin approval; facility list; rejection reason; staff accounts created by admins
- [x] Specialist review: override any condition, waiting time, overdue targets; notice on results from earlier models
- [x] All suites re-run on 27 October: `pytest -q`, `npm.cmd test`, `npm.cmd run typecheck`, `npm.cmd run lint`,
  `npx playwright test` (counts in README section 8)
- [x] CI green on GitHub (runs #1 and #2: backend on PostgreSQL 16, frontend checks, Docker build)
- [ ] Changes of 27 October committed, then pushed after "OK, push"; CI green on that push
- [ ] Physical-device test on an iPhone 13 Pro (needs the HTTPS deploy)
- [ ] Usability test with 3-5 people (SUS kit in `docs/usability/`)

## Report and video
- [ ] Report updated with the real metrics and rebuilt: `node scripts/build-report.mjs` (from `frontend/`), 5 pages or fewer
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
