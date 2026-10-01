# Diabetic Retinopathy Screening — Capstone MVP

**Capstone Project:** An Offline-First Mobile Application for Multi-Disease Retinal Screening in Primary Health Centers  
**Author:** Michael Kimani

---

## Overview

This is the initial MVP (minimum viable product) for a retinal disease screening system designed to support health workers in primary care settings. The system uses deep learning to provide rapid, preliminary screening for diabetic retinopathy from retinal fundus images.

Right now, the MVP focuses on **diabetic retinopathy detection** using a MobileNetV2-based classifier. The plan is to extend this to glaucoma and cataract detection in the final version, eventually delivering an offline-first mobile app that works even when connectivity is limited.

---

## GitHub Repository

[michael-kimani-eye-screening-capstone](https://github.com/Mikekimm/michael-kimani-eye-screening-capstone.git)

---

## Getting Started

### What You Need
- Python 3.9 or higher
- A terminal or PowerShell
- About 2GB of disk space (for TensorFlow and the model)

### Setup Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Mikekimm/michael-kimani-eye-screening-capstone.git
   cd michael-kimani-eye-screening-capstone
   ```

2. **Create a Python virtual environment** (optional but recommended):
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # source venv/bin/activate  # On Mac/Linux
   ```

3. **Install the required packages:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Get the trained model:**
   - Download `dr_screening_model.h5` from [this Kaggle notebook](https://www.kaggle.com/code/ascanipek/eyepacs-aptos-messidor-diabetic-retinopathy) (in the Outputs section)
   - Place it in the root folder (same location as `app.py`)
   - **File size:** ~90MB — GitHub has a 100MB limit, so it's not included in the repo
   - **Alternative:** If you can't download from Kaggle, the app will still run but show "Model not loaded — showing interface only"

5. **Run the app:**
   ```bash
   streamlit run app.py
   ```
   Your browser will open automatically to `http://localhost:8501`

6. **Try it out:**
   - Click "Browse files" and upload a retinal image (JPG or PNG)
   - The model will analyze it and show you whether signs of DR were detected
   - You'll see the confidence level for that prediction

---

## The Model & Data

### Data Source
The model was trained on the combined EyePACS + APTOS + Messidor dataset available on Kaggle. This collection includes:
- Real-world retinal fundus photographs (600×600 resolution)
- Diagnoses ranging from no DR to proliferative DR
- Images from different populations and imaging systems
- A total of ~47k images split into training and validation sets

### How We Prevent Overfitting
This dataset includes augmented versions of the same source images. To avoid the model seeing the same underlying image in both training and validation, we use **group-based splitting** — all variants of one source photo stay on the same side of the split.

### Model Architecture
The approach uses **transfer learning**:
- **Backbone:** MobileNetV2 (pretrained on ImageNet, frozen weights for this MVP)
- **Classifier head:** 
  - Global Average Pooling
  - Dropout (30%)
  - Dense layer (64 units, ReLU activation)
  - Dropout (20%)
  - Output (sigmoid for binary classification)

**Why MobileNetV2?** It's lightweight and efficient — perfect for eventual deployment to mobile devices via TensorFlow Lite, which is the plan for the final version.

### Training Details
- **Optimizer:** Adam (learning rate 1e-4)
- **Loss function:** Binary cross-entropy
- **Epochs:** 8 (with early stopping to avoid overfitting)
- **Class weights:** Applied to handle the imbalance between DR and non-DR cases
- **Augmentation:** Rotation, horizontal flips, zoom during training

---

## Initial Performance Results

Evaluated on a held-out validation set of ~47k images:

| Metric | Score |
|--------|-------|
| **Accuracy** | 79.0% |
| **Precision** | 92.0% |
| **Recall (Sensitivity)** | 54.2% |
| **F1 Score** | 68.2% |

### What These Numbers Mean
- **Accuracy:** Overall, the model got 79% of cases right
- **Precision:** When the model says "DR detected," it's correct 92% of the time (few false alarms)
- **Recall:** The model caught 54% of the actual DR cases — this is the key number to improve
- **F1:** A balanced view of precision and recall (68%)

### Note on the Recall Number
The research proposal targets ≥85% sensitivity (recall). We're at 54% right now because this MVP uses a frozen backbone and just 8 epochs of training. The final implementation will fine-tune more aggressively to reach the clinical target. A higher recall is critical in screening — it's better to flag a questionable case for specialist review than to miss a real disease.

---

## App Screenshots & Interface

The Streamlit interface is designed to be simple and accessible for health workers:

1. **Upload Screen** — Clean file uploader for retinal images
2. **Processing** — The app shows "Analyzing image..." while the model runs
3. **Result Card** — Color-coded output:
   - Green card: "No signs of DR detected" → routine follow-up screening
   - Orange card: "Signs of DR detected" → refer for specialist review
4. **Confidence Score** — Shows how confident the model is in its prediction

---

## Deployment Plan

### Current (MVP – Streamlit Web App)
- **Platform:** Python with Streamlit
- **Interface:** Web browser (local or cloud)
- **Deployment options:**
  - Run locally (development)
  - Deploy to Streamlit Cloud (free tier available)
  - Deploy to Docker for institutional use
- **Use case:** Telemedicine consultations, screening center workflows with internet connectivity

### Next Phase (Final Capstone Implementation)
- **Mobile app:** React Native or Flutter
- **On-device inference:** TensorFlow Lite (no internet required for screening)
- **Backend services:** 
  - FastAPI for referral routing
  - Patient data storage
  - Results sync when online
- **Multi-disease screening:** Extend to glaucoma and cataract detection
- **Offline-first architecture:** Works without connectivity; queues results for sync when available

---

## Video Demo

[Demo video: demo_video.mp4]

The video walkthrough covers:
- Uploading a retinal image
- Seeing the model's prediction in real time
- Understanding the confidence score and recommended action
- Example cases showing both "clear" and "flagged" results

---

## Project Structure

```
.
├── app.py                      # Streamlit app (the interface users see)
├── model_notebook.ipynb        # Full training pipeline with all metrics
├── dr_screening_model.h5       # Trained model — download from Kaggle (see Setup step 4)
├── requirements.txt            # Python dependencies
├── README.md                   # This file
└── screenshots/                # App interface screenshots
    ├── screenshot_1_dr_detected.png   # Result card showing DR detected (orange)
    └── screenshot_2_healthy.png       # Result card showing no DR (green)
```

---

## Important Disclaimer

**This tool provides preliminary screening support only.** It does not and cannot replace clinical diagnosis by a qualified healthcare professional.

- **Always** have predictions reviewed by a licensed clinician
- **Do not** make clinical decisions based on this tool alone
- **Report** any errors or concerning predictions to your supervisor immediately
- This is a research/educational MVP, not a medical device

---

## What's Next?

The final capstone implementation will:
1. ✅ Improve recall to meet the 85% target through additional fine-tuning
2. ✅ Extend to glaucoma and cataract screening
3. ✅ Deploy to mobile platforms (iOS/Android)
4. ✅ Implement offline-first architecture
5. ✅ Add specialist referral routing
6. ✅ Build patient data management

---

**Status:** Initial MVP (ready for feedback and evaluation)  
**Next Review:** Final Capstone Implementation  
**Assignment:** Initial Software Product/Solution Demonstration
