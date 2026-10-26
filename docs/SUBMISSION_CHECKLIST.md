# Submission checklist (due Friday 23:59, two attempts)

## Before you record or submit
- [ ] `pytest` passes on your laptop; paste the last line into docs/TESTING.md
- [ ] Kaggle hold-out run done; `holdout_predictions.csv` -> `python scripts/calibrate_threshold.py --predictions holdout_predictions.csv`
- [ ] Results pasted into README, docs/DATA_AND_EVALUATION.md section 5 and the report
- [ ] Confirm the "15,000-image fine-tune" statement in docs/DATA_AND_EVALUATION.md is true (search for CONFIRM)
- [ ] `models/threshold.json` committed (created by the calibration script)
- [ ] Benchmarks run on two devices; tables pasted into docs/TESTING.md and the report
- [ ] Browser compatibility table filled
- [ ] README TODOs replaced (video link, report link, versions)

## Attempt 1: GitHub link
- [ ] Several meaningful commits (package, tests, scripts, docs), pushed to `main`
- [ ] README opens correctly on GitHub and the diagrams display
- [ ] Video and report links work when you are logged out

## Attempt 2: ZIP
- [ ] ZIP of the repository **plus** the report PDF and the video file (no APK or executable applies; say so in the README)
- [ ] Open the ZIP once to check the video and report are inside
