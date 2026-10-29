# Repository clean-up (29 Oct 2026, branch `repo-cleanup`)

Method: for every tracked file outside the app code, `git grep` for its name across code, tests, CI
(`.github/workflows/ci.yml`), Docker files, `render.yaml`, scripts, the README, the docs and the report
(`docs/report/report.html`). A file was deleted only when nothing refers to it and the report does not rely
on it as evidence. Everything deleted stays in the git history (for example
`git show b46e5a9:notebooks/kaggle_holdout_eval.ipynb`).

## 1. Environment files

There was already only one tracked template, `.env.example` (no Docker-specific copy exists). It now lists
every variable the app reads, with optional ones commented out, and states that docker compose and CI use it
too. `.env` stays git-ignored. Updated: `.env.example`, comment in `docker-compose.yml`, README sections 5 and 7.

## 2. Deleted (clearly unused)

| File | Evidence |
|---|---|
| `docs/screenshots/Screenshot 2026-10-02 141833.png`, `...141923.png`, `...144133.png` | Screenshots of the retired Streamlit prototype ("Model confidence 81%" card). No reference anywhere; the prototype is preserved by the tag `legacy-streamlit-prototype`. |
| `notebooks/kaggle_holdout_eval.ipynb` | No saved outputs; the run never finished; marked "Superseded" in `docs/submission_checklist.md`. Its only mentions were that checklist line and a caveat in `dr_v1_metrics.json`, both reworded. |
| `docs/evaluation/kaggle_holdout_eval_cell.py` | The cell pasted into that unfinished run; referenced only by `docs/evaluation/README.md`. |
| `docs/evaluation/README.md` | Instructions for that unfinished run; tells the reader to upload `models/dr/model.h5`, which does not exist. Not linked from anywhere. |

## 3. Kept (in use)

| Item | Why |
|---|---|
| `notebooks/dr_v2_finetune.ipynb`, `notebooks/odir_glaucoma_cataract.ipynb` | Training notebooks of the three served models; named in the model cards, README, testing report. |
| `notebooks/model_notebook.ipynb` | Kept; reason in section 4. |
| `docs/evaluation/dr_v2/*`, `docs/metrics.json`, `docs/odir_metrics.json`, `docs/evaluation/dr_v1_metrics.json` | Read by `scripts/dr_v2_metrics.py` and pytest (`test_notebook_metrics.py`, `test_dr_parity.py`); cited by README and report. |
| `docs/screenshots/e2e/` | Written by the Playwright tests; two are figures in the report; linked from the testing report. |
| `docs/benchmarks/`, `docs/lighthouse/`, `docs/accessibility/` | Evidence cited in the testing report, README and report; `performance.spec.ts` writes `browser-timings.jsonl`. |
| `docs/diagrams/` | Linked from `docs/architecture.md`; `architecture.png` is Figure 1 of the report. |
| `docs/report/` | The report, its source, the editable .docx and its figures. |
| All of `scripts/` | Each is named in the README, CI, a test or the Playwright config. |
| `render.yaml`, `docker-compose.yml`, both Dockerfiles, `frontend/nginx.conf` | Deployment; built by CI. |

## 4. Second round (decisions made)

| Item | Action | Evidence |
|---|---|---|
| `docs/progress_notes.md`, `docs/submission_checklist.md` | Deleted | Working notes; no link from code, tests, CI, README, docs or the report. |
| `docs/kaggle_holdout_predictions.py` | Deleted | Paste-in Kaggle helper for the unfinished DR v0.3 hold-out run; mentioned only in the docstring of `scripts/calibrate_threshold.py` (reworded). |
| `CLAUDE.md` | Removed from git, kept on the developer machine and git-ignored | AI working rules, not used by the app, tests or docs. AI use is disclosed in README section 11. |
| `docs/remote_testing.md` | Moved to `docs/usability/remote_testing.md` | It is the moderator guide for the usability test; links updated. |

Kept on purpose:

| Item | Reason |
|---|---|
| `notebooks/model_notebook.ipynb` | The report cites its result (DR v0.3 sensitivity 0.542); `test_notebook_metrics.py` reads its saved outputs. Not renamed, as instructed. |
| `notebooks/odir_glaucoma_cataract.ipynb` | Training code of the served glaucoma and cataract models, named in both model cards, the README and the testing report. It has no saved outputs; its results are in `docs/odir_metrics.json`. |
| `scripts/calibrate_threshold.py`, `backend/app/ml/metrics_report.py`, `backend/tests/ml/test_metrics_report.py` | The submitted report cites the end-to-end test of the calibration script ("exposed that the calibration script did not write its outputs (fixed)"). |
| `docs/screenshots/e2e/` (all 72) | Written by every Playwright run; the report embeds two of them. |
| `render.yaml`, `docker-compose.yml`, `.dockerignore` at the root | Render reads `render.yaml` from the root; compose and the backend image build from the root context. |

Code check: every module in `backend/app` and `frontend/src` is imported by something (routers, lazy routes,
the Vitest setup), so no code was deleted.

Not in the repository (git-ignored, local only, left untouched): `incoming/`, `data/` (database and backups),
empty `Documents and Settings/` and `$Recycle.Bin/` folders.

## 5. Links

Every relative link in the tracked Markdown and HTML files was checked after the changes; none is broken.
