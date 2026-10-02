Retinal Disease Screening — Initial MVP
Description

This is the initial MVP for my capstone project: an offline-first application for multi-disease retinal screening in primary health centers, where specialist ophthalmologists and expensive diagnostic equipment are often unavailable.

Many preventable causes of blindness — diabetic retinopathy, glaucoma, cataracts — can be caught early from a simple photo of the retina, but screening requires access to a specialist. This project explores whether a lightweight, pretrained computer vision model can bring a first layer of screening directly into a clinic or community health worker's hands, with no internet connection required at inference time.

This MVP covers the first of those three conditions: diabetic retinopathy (DR). A user uploads a retinal fundus photo, and a MobileNetV2-based model returns a preliminary result — DR present or not — along with a recommended next action. Glaucoma and cataract screening, true offline/on-device inference, and specialist referral routing are planned for the Final Capstone Implementation.

GitHub Repository



Environment Setup
Requirements
Python 3.9+
~400MB free disk space (model file + dependencies)
1. Clone the repository
bash
git clone https://github.com/Mikekimm/michael-kimani-eye-screening-capstone.git
cd michael-kimani-eye-screening-capstone
2. Create a virtual environment
bash
python -m venv .venv
3. Activate it

Windows (PowerShell):

powershell
.venv\Scripts\activate

Mac/Linux:

bash
source .venv/bin/activate
4. Install dependencies
bash
pip install -r requirements.txt
5. (Optional) Re-run the training notebook

model_notebook.ipynb was developed and run on Kaggle with a GPU accelerator (T4 x2), using the ascanipek/eyepacs-aptos-messidor-diabetic-retinopathy dataset. To reproduce training, open the notebook in Kaggle (recommended — it downloads the ~90k+ image dataset automatically) and run all cells in order. Running it on a local CPU machine is not recommended; it is the slowest way to get here, and the trained model (dr_screening_model.h5) is already included in this repo so you don't need to.

6. Run the Streamlit application
bash
streamlit run app.py

This opens automatically at http://localhost:8501. Upload a retinal fundus image (JPG or PNG) to get a screening result.

Model Performance (Initial MVP)

Trained for 8 epochs with a frozen MobileNetV2 backbone (ImageNet weights), evaluated on a held-out, group-stratified validation split:

Metric	Score
Accuracy	0.790
Precision	0.920
Recall (sensitivity)	0.542
F1 score	0.682
Class	Precision	Recall	F1
No DR	0.75	0.97	0.84
DR present	0.92	0.54	0.68

On the recall gap: my proposal set a target of 85% sensitivity for DR classification, prioritized over raw accuracy, since missing a real positive case carries far more clinical risk than a false alarm. This MVP's recall (0.542) sits below that target, which is expected for a first pass with a frozen backbone and only 8 training epochs. Closing this gap — by unfreezing deeper backbone layers, training longer, and tuning the decision threshold toward higher sensitivity — is the main technical priority for the Final Capstone Implementation.




Deployment Plan

Current (MVP): a Streamlit web application running locally, loading the trained MobileNetV2 model (dr_screening_model.h5) directly for inference. This demonstrates the full intended workflow end-to-end: a user uploads an image, the app preprocesses it, runs it through the model, and returns a clear, color-coded result with a recommended next step.

Path to production:

Hosting: deploy the same Streamlit app to Streamlit Community Cloud (or an equivalent lightweight host) for a shareable, always-on demo link, without changing any application code.
Offline-first mobile deployment: the training notebook already exports a dr_screening_model.tflite version of the model alongside the .h5 file. The Final Capstone Implementation will use this to run inference directly on-device (e.g. via a mobile app), so screening works in clinics without reliable internet access — the core requirement this project is built around.
Multi-disease expansion: extend the same pipeline to glaucoma and cataract classification (using the ODIR-5K dataset), combining all three into a single multi-head model rather than three separate tools.
Video Demo

<insert your video link here>

Code Files
model_notebook.ipynb — dataset loading, visualization, model architecture, training, evaluation, and model export (including the leakage-safe, group-stratified train/validation split)
app.py — the Streamlit screening interface
dr_screening_model.h5 — the trained MobileNetV2 model used by the app
requirements.txt — Python depend
