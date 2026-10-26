"""Specialist review portal (the cloud-side "dashboard").

Shows flagged and borderline cases uploaded by clinics, with the image, laterality,
model version and previous reviews, and lets a specialist approve or override.

Run (after starting the backend):  streamlit run specialist_app.py
"""
import os

import sys
from pathlib import Path

import streamlit as st

# The ML package lives in backend/app/ml (legacy Streamlit prototype, superseded by frontend/).
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.ml.api_client import SpecialistClient
from app.ml.domain import ReviewDecision
from app.ml.exceptions import RemoteAuthError, RemoteError, RemoteRejectedError

st.set_page_config(page_title="Specialist Review Portal", page_icon="\U0001FA7A", layout="wide")

DECISION_LABELS = {
    ReviewDecision.APPROVE.value: "Approve the screening result",
    ReviewDecision.OVERRIDE_DR_PRESENT.value: "Override: DR is present",
    ReviewDecision.OVERRIDE_NO_DR.value: "Override: no DR",
    ReviewDecision.UNGRADABLE.value: "Image ungradable: ask for a retake",
}
MAX_CASES_SHOWN = 20

st.title("Specialist Review Portal")
st.caption("Referred and borderline screenings from connected clinics. "
           "Your decision is added to the case history and sent back to the clinic at its next sync.")

with st.sidebar:
    st.markdown("### Connection")
    server_url = st.text_input("Server URL", value=os.environ.get("SCREENING_API_URL", "http://127.0.0.1:8000"))
    token = st.text_input("Specialist access token", type="password", value=os.environ.get("SCREENING_API_TOKEN", ""))
    show_reviewed = st.checkbox("Include already reviewed cases", value=False)

if not token:
    st.info("Enter your specialist access token in the sidebar to load cases.")
    st.stop()

client = SpecialistClient(server_url.strip(), token.strip())
try:
    cases = client.list_cases(unreviewed_only=not show_reviewed)
    stats = client.stats()
except RemoteAuthError as exc:
    st.error(f"Access denied: {exc}")
    st.stop()
except RemoteError as exc:
    st.error(f"Could not load cases: {exc}")
    st.stop()

cols = st.columns(3)
cols[0].metric("Screenings on server", stats["screenings"])
cols[1].metric("Flagged or borderline", stats["needs_review"])
cols[2].metric("Reviewed", stats["reviewed"])

if not cases:
    st.success("No cases are waiting for review.")
    st.stop()

st.subheader(f"{len(cases)} case(s) to review")
for case in cases[:MAX_CASES_SHOWN]:
    title = f"{case['patient_ref']} - {case['laterality']} eye - score {case['probability']:.0%} - {case['created_at'][:16]}"
    with st.expander(title):
        image_col, detail_col = st.columns([1, 1])
        try:
            image_col.image(client.get_image(case["id"]), caption="Fundus image")
        except RemoteError as exc:
            image_col.warning(f"Image unavailable: {exc}")
        detail_col.write(f"**Model version:** `{case['model_version']}`  ")
        detail_col.write(f"**Score / threshold:** {case['probability']:.2f} / {case['threshold']:.2f}")
        detail_col.write(f"**Screened by:** {case['created_by']}")
        for warning in case["quality"].get("warnings", []):
            detail_col.warning(warning)
        for review in case["reviews"]:
            detail_col.write(f"Earlier review: **{review['decision']}** by {review['reviewer']} "
                             f"({review['reviewed_at'][:16]}) {review['notes']}")

        decision = detail_col.radio("Decision", list(DECISION_LABELS), key=f"decision-{case['id']}",
                                    format_func=DECISION_LABELS.get)
        notes = detail_col.text_area("Notes (optional)", key=f"notes-{case['id']}", max_chars=2000)
        if detail_col.button("Submit review", key=f"submit-{case['id']}"):
            try:
                client.submit_review(case["id"], decision, notes)
                st.success("Review saved. Reload the page to see the updated list.")
            except RemoteRejectedError as exc:
                st.error(f"The server rejected this review: {exc}")
            except RemoteError as exc:
                st.error(f"Could not save the review: {exc}")

if len(cases) > MAX_CASES_SHOWN:
    st.caption(f"Showing the first {MAX_CASES_SHOWN} of {len(cases)} cases.")
