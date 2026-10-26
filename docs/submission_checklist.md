# Submission checklist

## Before submitting
- [ ] Kaggle hold-out run done; `holdout_predictions.csv` and `holdout_run_info.json` in `docs/evaluation/`
- [ ] `scripts/calibrate_threshold.py` run (add `--row-order-verified` only if the run info lists no problems); `docs/metrics.json` committed
- [ ] Report and README updated with the real metrics, then `node scripts/build-report.mjs` (from `frontend/`) re-run: 5 pages or fewer
- [ ] Video recorded ([video_script.md](video_script.md)), uploaded unlisted, link opens in a private window
- [ ] Video link and report link added to README and report
- [ ] All tests re-run: `pytest -q`, `npm.cmd test`, `npm.cmd run typecheck`, `npm.cmd run lint`, `npx playwright test`
- [ ] `final-app` merged into `main` and pushed (no force-push)

## Attempt 1: GitHub repository link
- [ ] `main` contains the code, README, `docs/report/report.pdf` and the video link

## Attempt 2: ZIP of the same repository
Include: the repository files, `docs/report/report.pdf`, the video file (.mp4).
Exclude: `.venv/`, `frontend/node_modules/`, `data/`, `.env`, `__pycache__/`, `frontend/dist/`,
`frontend/test-results/`, `frontend/playwright-report/`, `$Recycle.Bin/`.
Easiest clean export (repository root, PowerShell): `git archive --format=zip -o ..\capstone-submission.zip main`,
then add the report PDF (already in the repo) and the video file to the ZIP.
There is no APK: the app is a PWA installed from the browser.
