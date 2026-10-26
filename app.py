"""Clinic app (offline-first): screen a fundus photo, save it locally, sync later.

This file only handles presentation. All logic lives in the ``src`` package.

Run:  streamlit run app.py
"""
import os

import sys
from pathlib import Path

import streamlit as st

# The ML package lives in backend/app/ml (legacy Streamlit prototype, superseded by frontend/).
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.ml.api_client import ClinicClient
from app.ml.classifier import load_classifier
from app.ml.config import LOCAL_DB_PATH, LOCAL_IMAGE_DIR
from app.ml.exceptions import (
    ImageQualityError,
    InvalidImageError,
    ModelNotAvailableError,
    RecordValidationError,
    ScreeningError,
)
from app.ml.service import ScreeningService
from app.ml.storage import ScreeningRepository
from app.ml.sync import SyncService
from app.ml.thresholding import load_threshold
from app.ml.workflow import ScreeningWorkflow

st.set_page_config(page_title="Retinal Screening Assistant", page_icon="\U0001F441", layout="centered")

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=Fraunces:wght@500;600&display=swap');
html, body, [class*="css"] { font-family: 'Source Sans 3', sans-serif; }
.stApp { background-color: #F6F5F1; }
.hero-title { font-family: 'Fraunces', serif; font-size: 2.1rem; font-weight: 600; color: #133C36; margin-bottom: 0.1rem; }
.hero-sub { color: #4A5A57; font-size: 1.02rem; margin-bottom: 1.2rem; }
.result-card { border-radius: 10px; padding: 1.4rem 1.6rem; margin-top: 1.2rem; border: 1px solid rgba(0,0,0,0.08); }
.result-clear { background-color: #EAF3EE; border-left: 5px solid #2E7D5B; }
.result-flagged { background-color: #FBF0E4; border-left: 5px solid #C97A2B; }
.result-label { font-family: 'Fraunces', serif; font-size: 1.4rem; font-weight: 600; margin-bottom: 0.2rem; color: #133C36; }
.detail-row { font-size: 0.95rem; color: #4A5A57; margin-top: 0.4rem; }
.scope-note { font-size: 0.85rem; color: #6B7876; border-top: 1px solid rgba(0,0,0,0.08); margin-top: 2.2rem; padding-top: 0.9rem; }
</style>
"""


@st.cache_resource
def build_service():
    """Create the screening service once per server process (None if no model)."""
    try:
        classifier = load_classifier()
    except ModelNotAvailableError:
        return None
    return ScreeningService(classifier, threshold=load_threshold())


@st.cache_resource
def build_repository():
    return ScreeningRepository(LOCAL_DB_PATH, LOCAL_IMAGE_DIR)


def show_image(data: bytes, caption: str) -> None:
    """Display an image across Streamlit versions (the width API changed)."""
    try:
        st.image(data, caption=caption, width="stretch")
    except TypeError:
        st.image(data, caption=caption, use_container_width=True)


def render_result(result) -> None:
    css_class = "result-flagged" if result.needs_review else "result-clear"
    st.markdown(
        f"""
        <div class="result-card {css_class}">
            <div class="result-label">{result.headline}</div>
            <div class="detail-row">Model score: {result.probability:.0%}
                (flag threshold: {result.threshold:.0%})</div>
            <div class="detail-row">{result.recommendation}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for warning in result.quality.warnings:
        st.warning(warning)


def render_sidebar(service, repository):
    with st.sidebar:
        st.markdown("### About this model")
        if service is None:
            st.write("No model loaded.")
        else:
            st.write(f"Version: `{service.model_version}`")
            st.write(f"Back-end: `{service.classifier_name}`")
            st.write(f"Decision threshold: `{service.threshold:.2f}`")
        st.markdown("### Clinic settings")
        operator = st.text_input("Your name or ID", value=os.environ.get("SCREENING_OPERATOR", ""))
        server_url = st.text_input("Server URL", value=os.environ.get("SCREENING_API_URL", "http://127.0.0.1:8000"))
        token = st.text_input("Access token", type="password", value=os.environ.get("SCREENING_API_TOKEN", ""))
        stats = repository.stats()
        st.metric("Waiting to sync", stats["pending_sync"])
        st.caption("Preliminary screening support only. Not a diagnosis.")
    return operator.strip(), server_url.strip(), token.strip()


def screen_tab(service, workflow, operator):
    col_a, col_b = st.columns(2)
    patient_ref = col_a.text_input("Patient code (not a name)", placeholder="PT-0001")
    laterality = col_b.selectbox("Eye photographed", ["left", "right", "unknown"])
    uploaded = st.file_uploader("Retinal image (JPG or PNG)", type=["jpg", "jpeg", "png"])

    if service is None:
        st.warning("No trained model found. Place `dr_screening_model.h5` in the `models/` folder and restart the app.")
    if uploaded is None:
        return

    data = uploaded.getvalue()
    left, right = st.columns(2)
    with left:
        try:
            show_image(data, "Uploaded image")
        except Exception:  # noqa: BLE001 - preview only; screening reports real errors
            st.caption("Preview unavailable.")
    with right:
        if st.button("Run screening and save", type="primary", disabled=service is None):
            if not operator:
                st.error("Enter your name or ID in the sidebar first.")
                return
            try:
                with st.spinner("Analyzing image..."):
                    record, result = workflow.run(data, patient_ref.strip(), laterality, operator)
                render_result(result)
                st.success(f"Saved on this device (record {record.id[:8]}). It will upload at the next sync.")
            except InvalidImageError:
                st.error("This file could not be read as an image. Please upload a valid JPG or PNG.")
            except ImageQualityError as exc:
                st.error(f"This image cannot be screened: {exc}")
            except RecordValidationError as exc:
                st.error(str(exc))
            except ScreeningError as exc:
                st.error(f"Screening failed: {exc}")


def records_tab(repository, server_url, token):
    stats = repository.stats()
    cols = st.columns(4)
    cols[0].metric("Saved", stats["screenings"])
    cols[1].metric("Waiting to sync", stats["pending_sync"])
    cols[2].metric("Sent to specialist", stats["needs_review"])
    cols[3].metric("Specialist replied", stats["reviewed"])

    if st.button("Sync now"):
        if not server_url or not token:
            st.error("Enter the server URL and access token in the sidebar.")
        else:
            report = SyncService(repository, ClinicClient(server_url, token)).sync()
            if report.auth_error:
                st.error(report.summary)
            elif report.offline:
                st.warning(report.summary)
            else:
                st.success(report.summary)

    records = repository.list_screenings(limit=200)
    if not records:
        st.info("No screenings saved yet.")
        return
    rows = []
    for record in reversed(records):
        latest = repository.latest_review(record.id)
        outcome = "DR flagged" if record.dr_detected else ("Borderline" if record.needs_review else "Clear")
        rows.append({
            "Time (UTC)": record.created_at.replace("T", " ")[:16],
            "Patient": record.patient_ref,
            "Eye": record.laterality.value,
            "Result": outcome,
            "Score": f"{record.probability:.0%}",
            "Model": record.model_version,
            "Sync": record.sync_status.value,
            "Specialist": latest.decision.value if latest else "",
        })
    st.dataframe(rows)

    chosen = st.selectbox("Review history for", [r.id for r in reversed(records)],
                          format_func=lambda rid: next(f"{r.patient_ref} ({r.laterality.value}) {r.created_at[:16]}"
                                                       for r in records if r.id == rid))
    history = repository.reviews_for(chosen)
    if not history:
        st.caption("No specialist review yet.")
    for review in history:
        st.write(f"**{review.decision.value}** by {review.reviewer} at {review.reviewed_at[:16]}"
                 + (f" - {review.notes}" if review.notes else ""))


st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
st.markdown('<div class="hero-title">Retinal Screening Assistant</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">Screen a retinal photo offline, keep the record on this device, '
    "and send it to a specialist when a connection is available.</div>",
    unsafe_allow_html=True,
)

service = build_service()
repository = build_repository()
operator, server_url, token = render_sidebar(service, repository)
workflow = ScreeningWorkflow(service, repository) if service is not None else None

tab_screen, tab_records = st.tabs(["Screen a patient", "Records and sync"])
with tab_screen:
    screen_tab(service, workflow, operator)
with tab_records:
    records_tab(repository, server_url, token)

st.markdown(
    '<div class="scope-note">Prototype for diabetic retinopathy only. Glaucoma and cataract '
    "screening are future work. This tool provides preliminary screening support and does not "
    "replace clinical diagnosis.</div>",
    unsafe_allow_html=True,
)
