"""POST /screenings with the REAL DR model: outputs, missing models, idempotency, invalid inputs."""
import io
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
from PIL import Image

from app.models import Screening
from app.models.enums import Role

from ..conftest import encode
from .conftest import auth_headers, fundus_jpeg, register_patient, upload


def _worker_with_patient(client):
    _, headers = auth_headers(client, Role.HEALTH_WORKER)
    return headers, register_patient(client, headers)


def test_real_models_return_one_result_per_condition(client):
    headers, patient = _worker_with_patient(client)
    response = upload(client, headers, patient["id"])
    assert response.status_code == 201, response.text
    body = response.json()
    results = {r["condition"]: r for r in body["results"]}
    assert [r["condition"] for r in body["results"]] == ["dr", "glaucoma", "cataract"]  # product order

    for condition in ("dr", "glaucoma", "cataract"):
        result = results[condition]
        assert result["model_available"] is True
        assert result["model_version"] == client.container.registry.get(condition).version
        assert 0.0 <= result["probability"] <= 1.0
        assert result["positive"] == (result["probability"] >= result["threshold"])

    assert 1 <= results["dr"]["severity_band"] <= 5
    # ODIR-5K has no severity grades, so glaucoma and cataract are binary only
    assert results["glaucoma"]["severity_band"] is None and results["cataract"]["severity_band"] is None

    assert "not a diagnosis" in body["disclaimer"].lower()


def test_specialist_can_override_a_glaucoma_result(client):
    headers, patient = _worker_with_patient(client)
    screening = upload(client, headers, patient["id"]).json()
    assert screening["status"] == "completed"  # nothing is sent automatically
    asked = client.post(f"/api/screenings/{screening['id']}/ask-specialist", headers=headers,
                        json={"question": "Is the optic disc cupped?"})
    assert asked.status_code == 200
    _, specialist = auth_headers(client, Role.SPECIALIST)
    queued = next(i for i in client.get("/api/reviews/queue", headers=specialist).json()
                  if i["screening_id"] == screening["id"])
    flagged = {r["condition"] for r in screening["results"] if r["refer_suggested"]}
    assert set(queued["flagged_conditions"]) == flagged

    response = client.post(f"/api/reviews/{screening['id']}", headers=specialist, json={
        "action": "override", "condition": "glaucoma", "override_positive": False, "note": "Disc looks normal."})
    assert response.status_code == 201, response.text
    event = response.json()["reviews"][-1]
    assert event["condition"] == "glaucoma" and event["override_positive"] is False


def test_condition_without_a_model_is_reported_as_not_available(stub_client):
    """The stub registry has no glaucoma or cataract model, which is how a missing folder behaves."""
    headers, patient = _worker_with_patient(stub_client)
    body = upload(stub_client, headers, patient["id"]).json()
    for result in body["results"]:
        if result["condition"] == "dr":
            continue
        assert result["model_available"] is False
        assert result["probability"] is None and result["severity_band"] is None
        assert "not available yet" in result["recommendation"].lower()


def test_same_image_gives_same_score(client):
    headers, patient = _worker_with_patient(client)
    first = upload(client, headers, patient["id"], data=fundus_jpeg(seed=7)).json()
    second = upload(client, headers, patient["id"], data=fundus_jpeg(seed=7)).json()
    dr_score = lambda body: next(r["probability"] for r in body["results"] if r["condition"] == "dr")  # noqa: E731
    assert dr_score(first) == dr_score(second)


def test_resubmitting_same_client_uuid_is_idempotent(client):
    headers, patient = _worker_with_patient(client)
    key = str(uuid.uuid4())
    first = upload(client, headers, patient["id"], client_uuid=key)
    retry = upload(client, headers, patient["id"], client_uuid=key, attempt=2)
    assert first.status_code == 201 and retry.status_code == 200
    assert retry.json()["duplicate"] is True and retry.json()["id"] == first.json()["id"]
    for session in client.container.database.session():
        assert session.query(Screening).filter_by(client_uuid=key).count() == 1


def test_another_users_client_uuid_is_a_conflict(client):
    headers, patient = _worker_with_patient(client)
    other_headers, other_patient = _worker_with_patient(client)
    key = str(uuid.uuid4())
    upload(client, headers, patient["id"], client_uuid=key)
    assert upload(client, other_headers, other_patient["id"], client_uuid=key).status_code == 409


def test_non_eye_image_is_refused_and_nothing_is_saved(client):
    headers, patient = _worker_with_patient(client)
    page = Image.new("RGB", (390, 844), (255, 255, 255))  # like a phone screenshot
    for y in range(80, 800, 40):
        page.paste((80, 80, 80), (20, y, 360, y + 12))
    response = upload(client, headers, patient["id"], data=encode(page, "PNG"), content_type="image/png")
    assert response.status_code == 422
    assert "does not look like a retinal fundus photograph" in response.json()["message"]
    for session in client.container.database.session():
        assert session.query(Screening).count() == 0
    uploads = client.container.settings.upload_dir
    assert not uploads.exists() or not any(uploads.iterdir())


def test_blank_image_is_rejected_with_reason(client):
    headers, patient = _worker_with_patient(client)
    blank = encode(Image.new("RGB", (300, 300), (40, 40, 40)), "JPEG")
    response = upload(client, headers, patient["id"], data=blank)
    assert response.status_code == 422
    assert "blank" in response.json()["message"].lower()


def test_tiny_image_is_rejected(client):
    headers, patient = _worker_with_patient(client)
    tiny = encode(Image.fromarray(np.random.default_rng(0).integers(0, 255, (32, 32, 3), dtype=np.uint8)), "PNG")
    response = upload(client, headers, patient["id"], data=tiny, content_type="image/png")
    assert response.status_code == 422 and "too small" in response.json()["message"]


def test_non_image_bytes_are_rejected(client):
    headers, patient = _worker_with_patient(client)
    response = upload(client, headers, patient["id"], data=b"%PDF-1.4 not an image")
    assert response.status_code == 422


def test_disallowed_content_type_is_rejected(client):
    headers, patient = _worker_with_patient(client)
    response = upload(client, headers, patient["id"], content_type="image/gif")
    assert response.status_code == 422


def test_declared_jpeg_that_is_really_bmp_is_rejected(client):
    headers, patient = _worker_with_patient(client)
    buffer = io.BytesIO()
    Image.new("RGB", (300, 300), (200, 90, 30)).save(buffer, format="BMP")
    response = upload(client, headers, patient["id"], data=buffer.getvalue())
    assert response.status_code == 422


def test_oversized_upload_is_rejected(client):
    headers, patient = _worker_with_patient(client)
    client.container.pipeline._max_upload_bytes = 1024
    response = upload(client, headers, patient["id"])
    assert response.status_code == 413


def test_future_capture_time_is_rejected(client):
    headers, patient = _worker_with_patient(client)
    future = datetime.now(timezone.utc) + timedelta(days=1)
    assert upload(client, headers, patient["id"], captured_at=future).status_code == 400


def test_invalid_eye_is_rejected(client):
    headers, patient = _worker_with_patient(client)
    assert upload(client, headers, patient["id"], eye="both").status_code == 422


def test_unknown_patient_is_404(client):
    _, headers = auth_headers(client, Role.HEALTH_WORKER)
    assert upload(client, headers, "does-not-exist").status_code == 404


def test_image_is_served_only_to_authorised_users(client):
    headers, patient = _worker_with_patient(client)
    screening = upload(client, headers, patient["id"]).json()
    _, stranger = auth_headers(client, Role.HEALTH_WORKER)
    ok = client.get(f"/api/screenings/{screening['id']}/image", headers=headers)
    assert ok.status_code == 200 and ok.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/screenings/{screening['id']}/image", headers=stranger).status_code == 404


def test_models_endpoint_reports_availability_and_labelled_test_metrics(client):
    _, headers = auth_headers(client, Role.HEALTH_WORKER)
    models = {m["condition"]: m for m in client.get("/api/models", headers=headers).json()}
    assert models["dr"]["available"] and models["dr"]["version"] == "mobilenetv2-dr-binary-2.0"
    assert models["dr"]["threshold"] == 0.41817495226860046
    assert "held-out test split by image" in models["dr"]["metrics_status"]
    assert "below the 80% specificity target" in models["dr"]["metrics_status"]
    assert models["dr"]["limitations"]
    for condition in ("glaucoma", "cataract"):
        assert models[condition]["available"]
        assert "patient-separated held-out test split" in models[condition]["metrics_status"]
    assert "below the 85% sensitivity" in models["glaucoma"]["metrics_status"]


def test_patient_history_lists_screenings(client):
    headers, patient = _worker_with_patient(client)
    upload(client, headers, patient["id"], eye="left")
    upload(client, headers, patient["id"], eye="right")
    history = client.get(f"/api/patients/{patient['id']}/screenings", headers=headers).json()
    assert {s["eye"] for s in history} == {"left", "right"}
    detail = client.get(f"/api/patients/{patient['id']}", headers=headers).json()
    assert detail["screening_count"] == 2


def test_screening_without_patient_consent_is_refused_and_nothing_is_stored(client):
    headers, patient = _worker_with_patient(client)
    response = upload(client, headers, patient["id"], consent=False)
    assert response.status_code == 422
    assert response.json()["error"] == "consent_required"
    for session in client.container.database.session():
        assert session.query(Screening).count() == 0
    uploads = client.container.settings.upload_dir
    assert not uploads.exists() or not any(uploads.iterdir())  # the photo was not saved either


def test_consent_is_recorded_with_the_screening(client):
    headers, patient = _worker_with_patient(client)
    assert upload(client, headers, patient["id"]).json()["patient_consent"] is True
