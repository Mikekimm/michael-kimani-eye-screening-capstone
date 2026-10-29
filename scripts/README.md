# Scripts

Run every script from the repository root with the project virtual environment, for example
`.venv\Scripts\python scripts\seed.py`. None of them is needed to use the app once it is set up.

| Script | What it does | When to run it |
|---|---|---|
| [init_env.py](init_env.py) | Creates `.env` from `.env.example` with a random `JWT_SECRET` and demo passwords (`--demo-passwords` for the documented demo ones). Refuses to overwrite an existing `.env` | Once, on first install |
| [seed.py](seed.py) | Creates the demo admin, specialist and health worker (from the `SEED_*` values in `.env`) and 5 synthetic patients. Safe to run twice | After `alembic upgrade head` on a new database |
| [create_admin.py](create_admin.py) | Creates or updates your personal admin account from `PERSONAL_ADMIN_EMAIL` / `PERSONAL_ADMIN_PASSWORD` in `.env`; never prints the password | Optional, when you want your own admin login |
| [reset_demo_data.py](reset_demo_data.py) | Backs up and recreates the local SQLite demo database and deletes stored photos; keeps approved non-demo accounts (`--yes` to confirm) | Before a demo or video recording; stop the backend first |
| [e2e_server.py](e2e_server.py) | Starts a throwaway backend on port 8001 with its own database for the Playwright tests | Never by hand: `frontend/playwright.config.ts` starts it |
| [benchmark.py](benchmark.py) | Times model-only and full-pipeline inference and memory; writes `docs/testing/benchmarks/<label>.json` and `.md` | When measuring performance on a machine |
| [dr_v2_metrics.py](dr_v2_metrics.py) | Recomputes every DR v2 figure from the notebook's predictions with the app's code and writes `docs/models/metrics.json` and the DR model card; stops if anything differs from the notebook | Only if the DR v2 evidence files change |
| [extract_notebook_metrics.py](extract_notebook_metrics.py) | Copies the retired DR v0.3 validation figures from the saved outputs of `notebooks/model_notebook.ipynb` into `docs/models/evaluation/dr_v1_metrics.json` (history only) | Not needed again; a test re-checks the values |
| [calibrate_threshold.py](calibrate_threshold.py) | Chooses a threshold from a CSV of hold-out predictions and writes a metrics report and model card. **Overwrites `docs/models/metrics.json` and the DR card**, so do not run it on the current model | Kept because its end-to-end test is cited in the report |
| [evaluate_fundus_check.py](evaluate_fundus_check.py) | Counts how often the fundus check rejects real fundus photos or accepts non-eye images | After changing the fundus check. The non-eye set is `docs/screenshots` (all four profiles exist locally after a Playwright run) plus `docs/diagrams` |
| [sus_score.py](sus_score.py) | Scores System Usability Scale answers and task results from `docs/usability/results.csv` | After the usability sessions |
