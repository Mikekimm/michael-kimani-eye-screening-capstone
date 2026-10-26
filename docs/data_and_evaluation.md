# Data and evaluation protocol

This answers the supervisor's second revision point: dataset access, source, labels and identifiers;
patient-separated development and test sets; external evaluation; and the baselines and metrics that
answer the research questions. It keeps the **research evaluation** (is the model good enough, and how
sure are we?) separate from **software verification** ([testing_report.md](testing_report.md)).

## 1. Dataset

| Item | Detail |
|---|---|
| Name and access | Kaggle `ascanipek/eyepacs-aptos-messidor-diabetic-retinopathy` (free Kaggle account). A third-party redistribution of EyePACS, APTOS 2019 and Messidor-2 images |
| Licence | The underlying competition data are for non-commercial / academic use. No images are stored in this repository |
| Size as loaded | 236,170 images (training notebook output). The loader may count overlapping folder trees, so this is the number of files found, not of unique photographs |
| Labels | 5-level ICDR grade (0 = no DR ... 4 = proliferative). The model is binary: **0 = no DR, 1 = DR present (grades 1-4)** |
| Patient identifiers | **None.** Images of the same patient or eye cannot be linked |
| Augmentation | The redistribution includes augmented copies. The notebook's group split strips common augmentation suffixes from file names to group copies, but found as many groups as images, so near-duplicates may not have been grouped |

## 2. Split actually used (verified from the notebook's saved outputs)

| Set | How it was made | Size |
|---|---|---|
| Training | `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)`, groups = file-name base id, fold 1 train part | 188,936 images |
| Validation | the same fold's held-out part; also used for early stopping during training | 47,234 images (27,581 no DR, 19,653 DR = 41.6%) |

Model: MobileNetV2 (ImageNet weights, frozen) + small head, 8 epochs, class weights, early stopping on
validation loss. At threshold 0.5 the notebook reported on this validation set: accuracy 0.790,
precision 0.920, recall 0.542, F1 0.682.

**Whether the shipped files are that model is being checked**: the hold-out notebook
([../notebooks/kaggle_holdout_eval.ipynb](../notebooks/kaggle_holdout_eval.ipynb)) rebuilds the
same fold, confirms size, class counts and row order, and checks that `models/dr/model.h5` reproduces
those four numbers. Only if it does are the fold's metrics reported for the shipped model.

**Consequences, stated as limitations:** splits are image-level (no patient IDs); augmented copies
may sit on both sides; the validation fold influenced early stopping. Every metric is therefore an
**optimistic estimate**, not a measure of clinical performance.

## 3. Threshold calibration and reporting

`scripts/calibrate_threshold.py` splits the fold's predictions in two (stratified, seed 42):

* **tuning half**: picks the highest threshold that reaches 85% sensitivity (`select_threshold`, O(n log n));
* **test half**: every reported number, with 95% bootstrap intervals (1,000 resamples) and AUC.

It writes [metrics.json](metrics.json) and updates the model card the API serves. It reports the
`.tflite` scores, because that is the file the app runs.

## 4. Baselines

1. Flag everyone / flag no one, to show what the metrics mean at the extremes.
2. Default threshold 0.5 versus the calibrated threshold, to show the sensitivity/specificity trade-off.
3. Literature reference only: Gulshan et al. (2016), 90.3% sensitivity / 98.1% specificity, on
   different data, model and operating point, so not a like-for-like comparison.

## 5. How the evidence answers the research questions

| Research question (proposal 1.4) | Evidence |
|---|---|
| RQ1 gaps in existing tools | literature review (proposal ch. 2); this prototype combines offline capture, multi-condition design and referral |
| RQ2 architecture and sync for intermittent connectivity | idempotent sync with backoff; tests of lost replies and offline queues ([testing_report.md](testing_report.md)) |
| RQ3 how accurately the model classifies DR | hold-out metrics in [metrics.json](metrics.json), **pending** |
| RQ4 how the referral workflow connects workers to specialists | end-to-end journeys: referral, review, decision pulled back; no clinical outcome study |

## 6. Qualified claims

* Screening support only, not a diagnosis, not clinically validated.
* Only diabetic retinopathy has a model; glaucoma and cataract are future work.
* Lowering the threshold to reach the sensitivity target raises false alarms (more referrals); the
  borderline band adds referrals by design.
* Synthetic images used in tests and benchmarks are code-path fixtures, never used to report model
  performance.
