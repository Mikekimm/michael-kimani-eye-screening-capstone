# Hold-out evaluation

1. On Kaggle, import `notebooks/model_notebook.ipynb`, add the dataset and upload `models/dr/model.h5` + `model.tflite`.
2. Run code cells 1, 2 and 3 only, then paste `kaggle_holdout_eval_cell.py` into a new cell and run it.
3. Download `holdout_predictions.csv` and `holdout_run_info.json` into this folder.
4. From the repo root:
   `.venv\Scripts\python scripts\calibrate_threshold.py --predictions docs/evaluation/holdout_predictions.csv`
   Add `--row-order-verified` only if `holdout_run_info.json` lists no reproducibility problems.
