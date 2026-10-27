# Data and evaluation protocol

This answers the supervisor's second revision point: dataset access, source, labels and identifiers;
patient-separated development and test sets; external evaluation; and the baselines and metrics that
answer the research questions. It keeps the **research evaluation** (is the model good enough, and how
sure are we?) separate from **software verification** ([testing_report.md](testing_report.md)).

## 1. Dataset (diabetic retinopathy)

| Item | Detail |
|---|---|
| Name and access | Kaggle `ascanipek/eyepacs-aptos-messidor-diabetic-retinopathy` (free Kaggle account). A third-party redistribution of EyePACS, APTOS 2019 and Messidor-2 images |
| Licence | The underlying competition data are for non-commercial / academic use. No images are stored in this repository |
| Size as loaded | 236,170 images (training notebook output). The loader may count overlapping folder trees, so this is the number of files found, not of unique photographs |
| Labels | 5-level ICDR grade (0 = no DR ... 4 = proliferative). The model is binary: **0 = no DR, 1 = DR present (grades 1-4)** |
| Patient identifiers | **None.** Images of the same patient or eye cannot be linked |
| Augmentation | The redistribution includes augmented copies. The notebook's group split strips common augmentation suffixes from file names to group copies, but found as many groups as images, so near-duplicates may not have been grouped |

## 2. DR v2: split actually used (from the notebook's saved outputs)

[../notebooks/dr_v2_finetune.ipynb](../notebooks/dr_v2_finetune.ipynb), run on Kaggle (2 x T4, 224 minutes):

| Set | How it was made | Size |
|---|---|---|
| Training | 70/15/15 split by image group (augmentation suffixes stripped), stratified, seed 42 | 165,319 images |
| Validation | used for early stopping and to choose the threshold | 35,425 images |
| Test | scored once, after the threshold was fixed | 35,426 images (14,740 DR present) |

Model: MobileNetV2 (ImageNet) fine-tuned from `block_13_expand`, head GAP-Dropout-Dense(64)-Dropout-Dense(1),
class weights, bilinear anti-aliased resize to 224 x 224, 10 epochs (best validation AUC 0.896).

**Limitation that matters most:** the notebook found 236,170 groups for 236,170 images, so augmented copies
and a patient's two eyes could not be grouped; near-duplicates may sit in both training and test, and the
figures may be optimistic. Label used everywhere: held-out test split by image (no patient IDs available;
near-duplicates could not be excluded); not external validation; not clinically validated.

## 3. Threshold and reporting

* **Threshold:** the highest validation threshold with sensitivity >= 85%: 0.418.
* **Test split, once:** sensitivity 0.851 (95% CI 0.845-0.857), specificity 0.748 (0.743-0.754),
  precision 0.706, AUC 0.900. Sensitivity target met, specificity target not met.
* **Recomputed, not copied:** `scripts/dr_v2_metrics.py` reads the notebook's validation and test
  predictions ([evaluation/dr_v2/](evaluation/dr_v2/)) and recomputes the threshold and every figure with
  the app's own `select_threshold` (O(n log n)), `metrics_at_threshold` and bootstrap code; it stops if
  any value differs from the notebook. It writes [metrics.json](metrics.json) and the served model card.
* **Same file, same input:** the served `.tflite` has the checksum the notebook recorded, and the app's
  pipeline reproduces the notebook's scores on 24 test photos within 0.021 with no decision changed
  ([testing_report.md](testing_report.md) section 6).
* **History:** the first DR model (v0.3, frozen backbone, nearest-neighbour resize, threshold 0.5) reported
  sensitivity 0.542 on its training-notebook validation fold
  ([evaluation/dr_v1_metrics.json](evaluation/dr_v1_metrics.json)); its independent hold-out run never finished.

## 4. Baselines

1. The default threshold 0.5 versus the chosen 0.418 on the same test split: 0.5 gives sensitivity 0.799
   and specificity 0.845, so the lower threshold buys sensitivity with false alarms.
2. The previous model (v0.3): sensitivity 0.542 on its validation fold.
3. Literature reference only: Gulshan et al. (2016), 90.3% sensitivity / 98.1% specificity, on
   different data, model and operating point, so not a like-for-like comparison.

## 5. How the evidence answers the research questions

| Research question (proposal 1.4) | Evidence |
|---|---|
| RQ1 gaps in existing tools | literature review (proposal ch. 2); this prototype combines offline capture, multi-condition design and referral |
| RQ2 architecture and sync for intermittent connectivity | idempotent sync with backoff; tests of lost replies and offline queues ([testing_report.md](testing_report.md)) |
| RQ3 how accurately the models classify DR, glaucoma and cataract | DR: held-out test split by image, sensitivity 0.851, specificity 0.748 ([metrics.json](metrics.json)). Glaucoma: 0.762 / 0.721, precision 0.103. Cataract: 0.978 / 0.962 ([odir_metrics.json](odir_metrics.json)). No images from low-cost smartphone lenses were tested |
| RQ4 how the referral workflow connects workers to specialists | end-to-end journeys: referral, review, decision pulled back; no clinical outcome study |

## 6. Glaucoma and cataract (ODIR-5K)

[notebooks/odir_glaucoma_cataract.ipynb](../notebooks/odir_glaucoma_cataract.ipynb) applies the same rigour
with one improvement ODIR-5K allows: it has **patient IDs**, so the split is by patient (70/15/15,
stratified), and no person appears in two splits (checked by an assertion and in the final checks).

* Labels per eye from ODIR's diagnostic keywords: positive if the condition is named for that eye;
  "suspected" findings and (for glaucoma) an invisible optic disc are excluded rather than guessed;
  photos marked low quality, offset, anterior segment or "no fundus image" are excluded.
* The notebook prints the true class counts before training and states when positives are too few
  to trust (fewer than 150 positive training eyes or 30 positive test eyes).
* Threshold chosen on the validation split only (highest with >= 85% sensitivity); the test split is
  scored once, with the exported `.tflite`, with patient-level bootstrap intervals.
* Binary output only: ODIR-5K has no severity grades, so no severity band is produced.
* Results ([odir_metrics.json](odir_metrics.json), all notebook integrity checks passed):

| Test split | Eyes (positive) | Patients | Threshold | Sensitivity | Specificity | Precision | AUC |
|---|---|---|---|---|---|---|---|
| Glaucoma | 1,040 (42) | 524 | 0.320 | 0.762 | 0.721 | 0.103 | 0.818 |
| Cataract | 1,044 (46) | 525 | 0.541 | 0.978 | 0.962 | 0.542 | 0.991 |

Glaucoma is below both targets and is limited evidence; cataract meets both but rests on 46 positives.

## 7. Qualified claims

* Screening support only, not a diagnosis, not clinically validated.
* All three models are deployed with their real results; glaucoma is weak (precision about 0.10) and the app
  says so next to every glaucoma result.
* Lowering the threshold to reach the sensitivity target raises false alarms (more referrals); the
  borderline band adds referrals by design.
* Synthetic images used in tests and benchmarks are code-path fixtures, never used to report model
  performance.
