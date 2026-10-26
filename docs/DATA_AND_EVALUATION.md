# Data and evaluation protocol

This document answers the supervisor's second revision point: dataset access, source, labels and
identifiers; patient-separated development and test sets; external evaluation; and the baselines and
metrics that answer the research questions. It is written to keep the **research evaluation** (is the
model good enough, and how sure are we?) separate from the **software verification** (does the system
behave correctly?), which lives in [TESTING.md](TESTING.md).

## 1. Dataset

| Item | Detail |
|---|---|
| Name and access | `ascanipek/eyepacs-aptos-messidor-diabetic-retinopathy` on Kaggle (free account needed). A third-party redistribution of EyePACS, APTOS 2019 and Messidor-2 images, resized to 600x600. |
| Licence | The underlying EyePACS and APTOS competition data are licensed for non-commercial / academic use. This redistribution is acceptable for coursework; it must not be used commercially or redistributed from this repository (no images are committed). |
| Labels | 5-level ICDR severity (0 = no DR ... 4 = proliferative DR), assigned by the original graders. The model is binary: **0 = no DR, 1 = DR present (grades 1-4)**. 41.6% of the 236,170 images are positive. |
| Patient identifiers | **None are provided.** There is no patient or eye ID, so images of the same patient (or the same eye) cannot be linked. |
| Augmentation | The curator reports augmentation that enlarges the data by about 55% over the source sets. The training notebook tried to recover a "base id" from filenames to group-split near-duplicates; it found 236,170 unique ids for 236,170 images, which means the filename rule found **no** groups. |

**Consequence (stated as a limitation, not hidden):** a patient-separated or duplicate-safe split is
**not possible** with this dataset as distributed. Any split is image-level, so augmented copies or
both eyes of one patient can sit on both sides, and every metric below is an **optimistic estimate**.

## 2. Splits actually used

| Set | Source | Used for |
|---|---|---|
<!-- CONFIRM: the 15,000-image fine-tune description comes from an earlier working session; check it matches what you actually trained. -->
| Training / validation | The deployed model was fine-tuned on a 15,000-image stratified subset (seed 42) with an internal validation split. | Fitting weights, early stopping. |
| Hold-out | 6,000 images sampled only from the remaining ~221,000 images the model never trained on (`docs/kaggle_holdout_predictions.py`). | Everything below. |
| Tuning half | 50% of the hold-out, stratified, seed 42. | Choosing the decision threshold **only**. |
| Test half | The other 50% of the hold-out. | Every reported metric. The threshold never saw it. |

The tuning/test separation is implemented in `src/evaluation.py::stratified_split` and used by
`scripts/calibrate_threshold.py`. Splitting the *same* images twice (tune and report on one set) would
inflate sensitivity at the chosen threshold; the two-half design avoids that.

**External evaluation:** none has been run. A compatible external set would be an independent DR
dataset with the same ICDR labels that is not part of this combined collection. Until one is evaluated,
the results describe in-distribution performance only and should not be read as how the tool would
perform on photographs from a low-cost smartphone fundus attachment.

## 3. Baselines

1. **Flag everyone** and **flag no one** (trivial classifiers) to show what the metrics mean at the extremes.
2. **Default threshold 0.5** versus the **tuned threshold**, to show the sensitivity/specificity trade-off.
3. **Literature reference (not a like-for-like comparison):** Gulshan et al. (2016) reported 90.3%
   sensitivity and 98.1% specificity for referable DR with a much larger model trained on far more data
   and evaluated on different images and a different operating point. The proposal uses it as a
   reference point, not as a target this prototype is expected to beat.

## 4. Metrics and how they answer the research questions

| Research question (proposal 1.4) | Evidence in this repository | Metric / test |
|---|---|---|
| RQ1 Gaps in existing tools | Literature review (proposal ch. 2); the prototype demonstrates offline + referral together for DR | Qualitative; feature table in [SCOPE_TABLE.md](SCOPE_TABLE.md) |
| RQ2 Architecture and sync design for intermittent connectivity | Local-first store, idempotent sync, stop-on-offline rule | Integration tests incl. connection drop mid-sync (`tests/test_sync.py`, `tests/test_api_integration.py`) |
| RQ3 How accurately can an on-device model classify DR | Hold-out evaluation | **Sensitivity (primary)**, specificity, precision, F1, AUC, each with a 95% bootstrap interval (1,000 resamples) on the test half; targets: sensitivity >= 85% and specificity >= 80% |
| RQ4 Does the referral workflow connect health workers to specialists | Offline-to-online loop with review history | End-to-end test `test_offline_then_online_full_loop`; no clinical outcome study was possible |

Sensitivity is the primary metric because a missed case costs more than a false alarm. Reported
intervals reflect sampling error only, not the data-leakage bias described in section 1.

## 5. Results

Results are produced by `python scripts/calibrate_threshold.py --predictions holdout_predictions.csv`
and are copied into the report. **Do not quote numbers from earlier training runs for the deployed model.**

> RESULTS-TO-FILL (from your Kaggle hold-out run): paste the printed table here.

## 6. Qualified claims

* This is **preliminary screening support, not a diagnosis**, and it is not clinically validated.
* Performance was measured retrospectively on public datasets that include augmented images and no
  patient identifiers; real-world performance is expected to be lower.
* Only diabetic retinopathy is classified. Glaucoma and cataract are future work.
* Lowering the threshold to reach the sensitivity target increases false alarms (lower specificity),
  which means more referrals; the borderline band (+/-0.10 around the threshold) adds further referrals
  by design.
* The synthetic images used in tests are fixtures for exercising code paths. They are not retinal photographs
  and are never used to report model performance.
