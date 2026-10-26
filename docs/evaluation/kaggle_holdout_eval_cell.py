# ===================== HOLD-OUT EVALUATION CELL =====================
# Paste into ONE new cell at the bottom of notebooks/model_notebook.ipynb on Kaggle, AFTER running
# code cells 1 (setup + SEED), 2 (DATASET_PATH) and 3 (builds df) UNCHANGED.
# Do NOT run code cells 4-12 (visualisation, generators, training, saving).
#
# Needs two inputs added with "Add Input -> Upload -> New Dataset":
#   the dataset  ascanipek/eyepacs-aptos-messidor-diabetic-retinopathy
#   the models   models/dr/model.h5 and models/dr/model.tflite from this repo
#                (the original names dr_screening_model.h5 / .tflite also work)
#
# What it does: rebuilds the SAME validation fold as the notebook's split cell (same code, same
# SEED), checks it matches what the notebook printed during training, predicts with BOTH the .h5
# and the .tflite model, and writes /kaggle/working/holdout_predictions.csv + holdout_run_info.json.
# If the .h5 reproduces the notebook's validation metrics, the shipped model IS the notebook's
# 8-epoch model and this fold was never trained on. If not, do not use these numbers.

import glob, json, os, re
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.preprocessing.image import ImageDataGenerator

IMG_SIZE = (224, 224)      # same as the notebook's split cell
BATCH_SIZE = 32            # same as the notebook's split cell
EXPECTED = {               # taken from the saved outputs inside notebooks/model_notebook.ipynb
    "n_total": 236170,
    "n_val": 47234,
    "val_counts": {0: 27581, 1: 19653},
    "first_diagnoses": [2, 2, 2, 2, 2],
    "metrics_at_0.5": {"accuracy": 0.790, "precision": 0.920, "recall": 0.542, "f1": 0.682},
}
problems = []

# ---------- 1. Is df the same df the model was trained on? ----------
print("len(df) =", len(df), "| expected", EXPECTED["n_total"])
assert len(df) == EXPECTED["n_total"], (
    "len(df) differs from training. STOP: the dataset version is different. "
    "Do not use any numbers from this run.")
first5 = df["diagnosis"].head(5).tolist()
print("first 5 diagnoses =", first5, "| expected", EXPECTED["first_diagnoses"])
if first5 != EXPECTED["first_diagnoses"]:
    problems.append("row order of df differs from training (first 5 diagnoses)")

# ---------- 2. Rebuild the validation fold exactly as the notebook does ----------
def base_id(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    return re.sub(r'(_aug\d*|_flip\w*|_rot(ate)?\d*|_crop\d*|_v\d+|_\d+)$', '', stem, flags=re.IGNORECASE)

df["base_id"] = df["filepath"].apply(base_id)
sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
train_idx, val_idx = next(sgkf.split(df, y=df["label"], groups=df["base_id"]))
val_df = df.iloc[val_idx].copy().reset_index(drop=True)
val_counts = {int(k): int(v) for k, v in val_df["label"].value_counts().items()}
print("validation rows =", len(val_df), "| class counts =", val_counts)
if len(val_df) != EXPECTED["n_val"] or val_counts != EXPECTED["val_counts"]:
    problems.append("validation fold size/class counts differ from training")

# ---------- 3. Find the model files (searches a few folder depths only) ----------
def find_file(*names):
    patterns = ["/kaggle/working/", "/kaggle/input/*/", "/kaggle/input/*/*/", "/kaggle/input/*/*/*/"]
    for name in names:
        for p in patterns:
            hits = glob.glob(p + name)
            if hits:
                return hits[0]
    raise FileNotFoundError(f"None of {names} found. Upload them as a Kaggle dataset (Add Input) or to /kaggle/working.")

h5_path = find_file("model.h5", "dr_screening_model.h5")
tflite_path = find_file("model.tflite", "dr_screening_model.tflite")
print("h5     :", h5_path)
print("tflite :", tflite_path)

# ---------- 4. Same preprocessing as training validation ----------
val_df["label_str"] = val_df["label"].astype(str)
val_gen = ImageDataGenerator(preprocessing_function=preprocess_input).flow_from_dataframe(
    val_df, x_col="filepath", y_col="label_str",
    target_size=IMG_SIZE, batch_size=BATCH_SIZE,
    class_mode="binary", shuffle=False, seed=SEED)
assert len(val_gen.filenames) == len(val_df), "some validation images could not be read"
assert list(val_gen.filenames) == val_df["filepath"].tolist(), "generator order != dataframe order"

# ---------- 5. Predict with the .h5 model ----------
model = tf.keras.models.load_model(h5_path, compile=False)
val_gen.reset()
prob_h5 = model.predict(val_gen, verbose=1).ravel()

# ---------- 6. Predict with the .tflite model (the one the app serves) ----------
interp = tf.lite.Interpreter(model_path=tflite_path)
interp.allocate_tensors()
inp, out = interp.get_input_details()[0], interp.get_output_details()[0]
assert inp["dtype"] == np.float32, f"unexpected tflite input dtype {inp['dtype']}"
prob_tfl = []
for b in range(len(val_gen)):
    xb, _ = val_gen[b]
    for img in xb:
        interp.set_tensor(inp["index"], img[None].astype(np.float32))
        interp.invoke()
        prob_tfl.append(float(interp.get_tensor(out["index"]).ravel()[0]))
prob_tfl = np.array(prob_tfl)
assert len(prob_tfl) == len(val_df)

# ---------- 7. Metrics at 0.5 and the reproducibility check ----------
y = val_df["label"].values
def report(name, p, thr=0.5):
    yhat = (p > thr).astype(int)
    m = {"accuracy": accuracy_score(y, yhat), "precision": precision_score(y, yhat),
         "recall": recall_score(y, yhat), "f1": f1_score(y, yhat)}
    print(f"\n{name} @ threshold {thr}:", {k: round(v, 3) for k, v in m.items()})
    print(confusion_matrix(y, yhat))
    return m

m_h5 = report("h5", prob_h5)
report("tflite", prob_tfl)
for k, v in EXPECTED["metrics_at_0.5"].items():
    if abs(m_h5[k] - v) > 0.002:
        problems.append(f"h5 {k} {m_h5[k]:.3f} does not match notebook value {v}")
print("\nmax |h5 - tflite| probability difference:", float(np.abs(prob_h5 - prob_tfl).max()))

# ---------- 8. Save ----------
res = pd.DataFrame({
    "filepath": val_df["filepath"], "diagnosis": val_df["diagnosis"], "label": val_df["label"],
    "prob_h5": prob_h5, "prob_tflite": prob_tfl})
res.to_csv("/kaggle/working/holdout_predictions.csv", index=False)
info = {"n_total": len(df), "n_holdout": len(res), "seed": SEED, "tensorflow": tf.__version__,
        "h5": os.path.basename(h5_path), "tflite": os.path.basename(tflite_path),
        "max_abs_h5_tflite_diff": float(np.abs(prob_h5 - prob_tfl).max()),
        "h5_metrics_at_0.5": {k: float(v) for k, v in m_h5.items()},
        "reproducibility_problems": problems}
json.dump(info, open("/kaggle/working/holdout_run_info.json", "w"), indent=2)

print("\n" + "=" * 60)
if problems:
    print("REPRODUCIBILITY CHECK FAILED. Treat metrics as UNVERIFIED and tell Claude Code:")
    for p in problems: print(" -", p)
else:
    print("REPRODUCIBILITY CHECK PASSED: fold size, class counts, row order and h5 metrics all match training.")
print("Saved: /kaggle/working/holdout_predictions.csv and holdout_run_info.json")
