# Notebooks

All training ran on Kaggle (GPU). The datasets are not stored in this repository; each notebook downloads
its Kaggle dataset by name. Every figure below is a value saved in the notebook or in the files named, not an
estimate. None of these results is clinical validation.

| Notebook | What it trained | What it printed / where the results are | Used by |
|---|---|---|---|
| [dr_v2_finetune.ipynb](dr_v2_finetune.ipynb) | **DR v2.0 (served).** Binary MobileNetV2 (no DR / DR present), fine-tuned from `block_13_expand`, bilinear resize, on Kaggle `ascanipek/eyepacs-aptos-messidor-diabetic-retinopathy`; 70/15/15 split by image group (train 165,319 / validation 35,425 / test 35,426); 2 x T4, about 224 min | Outputs saved. Threshold 0.4182 chosen on validation; test: sensitivity 0.851 (95% CI 0.845-0.857), specificity 0.748 (0.742-0.754), AUC 0.900; referable DR (grade 2+) sensitivity 0.869; TFLite vs Keras max difference 0.00001. Exported files in [docs/models/evaluation/dr_v2/](../docs/models/evaluation/dr_v2/), recomputed by `scripts/dr_v2_metrics.py` into [docs/models/metrics.json](../docs/models/metrics.json) | `models/dr/`, README, report |
| [odir_glaucoma_cataract.ipynb](odir_glaucoma_cataract.ipynb) | **Glaucoma and cataract (served).** One binary MobileNetV2 per condition on Kaggle `andrewmvd/ocular-disease-recognition-odir5k`, split by patient (70/15/15), thresholds chosen on validation | **Outputs not saved in this copy.** The results it produced are in [docs/models/odir_metrics.json](../docs/models/odir_metrics.json) and the model cards: glaucoma sensitivity 0.762 / specificity 0.721 / precision 0.103 (1,040 eyes, 42 positive); cataract 0.978 / 0.962 / 0.542 (1,044 eyes, 46 positive) | `models/glaucoma/`, `models/cataract/`, README, report |
| [model_notebook.ipynb](model_notebook.ipynb) | **DR v0.3 (retired, history only).** First DR model: frozen MobileNetV2 backbone, nearest-neighbour resize | Outputs saved (validation fold only, not a test set): accuracy 0.790, precision 0.920, sensitivity 0.542, specificity 0.97 at threshold 0.5. Extracted by `scripts/extract_notebook_metrics.py` into [docs/models/evaluation/dr_v1_metrics.json](../docs/models/evaluation/dr_v1_metrics.json) | the report's "earlier model reached only 0.542" sentence; `backend/tests/ml/test_notebook_metrics.py` |

Limitations that apply to all three: public datasets only, no external test set, no images from low-cost
smartphone lenses; the DR split is by image (no patient IDs, augmented near-duplicates), so its figures may be
optimistic; ODIR labels are free-text keywords and its positive classes are small.

Removed in the repository clean-up (still in the git history): `kaggle_holdout_eval.ipynb`, a DR v0.3 hold-out
run that never finished and was superseded by the DR v2 test split. See [docs/cleanup_report.md](../docs/cleanup_report.md).
