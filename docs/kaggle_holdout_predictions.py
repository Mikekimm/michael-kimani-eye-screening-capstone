"""Paste into a Kaggle notebook cell (GPU on) to create holdout_predictions.csv.

Purpose: get HONEST metrics for the model that is actually deployed in the app.
The deployed model was fine-tuned on a 15,000-image subset, so we evaluate on
images drawn only from the remaining ~221,000 that it never saw.

Before running:
  1. In the notebook, run the setup + dataset-loading cells so `df`, `SEED` exist.
  2. Add dr_screening_model.h5 to the notebook: Input panel -> Upload -> new dataset.
     (A new dataset upload is fine; it is only used to load the weights.)
  3. SEED must be the same value used when the model was trained (the notebook's SEED).
"""
import glob

import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.model_selection import train_test_split
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.preprocessing.image import ImageDataGenerator

HOLDOUT_SIZE = 6000

model_path = glob.glob("/kaggle/input/**/dr_screening_model.h5", recursive=True)[0]
model = tf.keras.models.load_model(model_path, compile=False)

# Reproduce the exact subset the deployed model was trained/validated on...
quick_df, unseen_df = train_test_split(
    df, train_size=15000, stratify=df["label"], random_state=SEED
)
# ...and evaluate only on images outside it.
holdout = unseen_df.sample(HOLDOUT_SIZE, random_state=SEED).reset_index(drop=True)

generator = ImageDataGenerator(preprocessing_function=preprocess_input).flow_from_dataframe(
    holdout.assign(label_str=holdout["label"].astype(str)),
    x_col="filepath", y_col=None, class_mode=None,
    target_size=(224, 224), batch_size=64, shuffle=False,
)
y_prob = model.predict(generator, verbose=1).ravel()

out = pd.DataFrame({"y_true": holdout["label"].to_numpy(), "y_prob": y_prob})
out.to_csv("/kaggle/working/holdout_predictions.csv", index=False)
print(out.shape, "| positives:", int(out["y_true"].sum()))

from IPython.display import FileLink
FileLink("holdout_predictions.csv")

# Limitation to state in the report: the dataset contains augmented copies, so some
# held-out images may be near-duplicates of training images. Treat results as an
# optimistic estimate, not a clinical performance claim.
