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
| `notebooks/model_notebook.ipynb` | See decision D1. |
| `docs/evaluation/dr_v2/*`, `docs/metrics.json`, `docs/odir_metrics.json`, `docs/evaluation/dr_v1_metrics.json` | Read by `scripts/dr_v2_metrics.py` and pytest (`test_notebook_metrics.py`, `test_dr_parity.py`); cited by README and report. |
| `docs/screenshots/e2e/` | Written by the Playwright tests; two are figures in the report; linked from the testing report. |
| `docs/benchmarks/`, `docs/lighthouse/`, `docs/accessibility/` | Evidence cited in the testing report, README and report; `performance.spec.ts` writes `browser-timings.jsonl`. |
| `docs/diagrams/` | Linked from `docs/architecture.md`; `architecture.png` is Figure 1 of the report. |
| `docs/report/` | The report, its source, the editable .docx and its figures. |
| All of `scripts/` | Each is named in the README, CI, a test or the Playwright config. |
| `render.yaml`, `docker-compose.yml`, both Dockerfiles, `frontend/nginx.conf` | Deployment; built by CI. |

## 4. Needs your decision (not deleted)

| # | Item | Facts | Suggestion |
|---|---|---|---|
| D1 | `notebooks/model_notebook.ipynb` (DR v0.3, 2.1 MB) | A retired model, but the report says "the earlier DR model (v0.3) reached only 0.542 sensitivity", and this notebook's saved outputs are the evidence; `test_notebook_metrics.py` reads it. Deleting it means deleting that test and `scripts/extract_notebook_metrics.py`. | Keep. Optionally rename to `dr_v0.3_retired.ipynb` (updates 3 files). |
| D2 | `notebooks/odir_glaucoma_cataract.ipynb` has **no saved outputs** | The glaucoma and cataract results exist only in `docs/odir_metrics.json` and the model cards. | Keep. If the executed version is still in your Kaggle account, download it and replace this copy. |
| D3 | `scripts/calibrate_threshold.py`, `backend/app/ml/metrics_report.py`, `docs/kaggle_holdout_predictions.py` | Tooling for the DR v0.3 hold-out path that never ran. Covered by `test_metrics_report.py` and the testing report. Running the script would overwrite `docs/metrics.json` and the DR model card. | Keep for now (removing code and tests changes the test counts in the report). |
| D4 | `docs/progress_notes.md`, `docs/submission_checklist.md` | Working notes; nothing links to them. | Keep or move out before the final submission. |
| D5 | `CLAUDE.md` | AI working rules at the repository root; AI use is disclosed in README section 11. | Your call. |
| D6 | Local only, never in git (ignored): `incoming/` (raw Kaggle downloads already installed, and the proposal PDF), `data/app.db.bak-*` (database backups), empty `Documents and Settings/` and `$Recycle.Bin/` folders | Not in the GitHub repository, so they do not affect readers. | Not touched (no data deleted). |

## 5. Checks run

See the summary in the commit message and the hand-over notes.
