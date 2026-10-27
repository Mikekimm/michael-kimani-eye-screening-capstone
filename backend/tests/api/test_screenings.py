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


def test_real_model_returns_one_result_per_condition(client):
    headers, patient = _worker_with_patient(client)
    response = upload(client, headers, patient["id"])
    assert response.status_code == 201, response.text
    body = response.json()
    results = {r["condition"]: r for r in body["results"]}
    assert [r["condition"] for r in body["results"]] == ["dr", "glaucoma", "cataract"]  # product order

    dr = results["dr"]
    assert dr["model_available"] is True
    assert dr["model_version"] == "mobilenetv2-dr-binary-0.3"
    assert 0.0 <= dr["probability"] <= 1.0
    assert 1 <= dr["severity_band"] <= 5
    assert dr["positive"] == (dr["probability"] >= dr["threshold"])

    for condition in ("glaucoma", "cataract"):
        missing = results[condition]
        assert missing["model_available"] is False
        assert missing["probability"] is None and missing["severity_band"] is None
        assert "not available yet" in missing["recommendation"].lower()

    assert "not a diagnosis" in body["disclaimer"].lower()


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


def test_models_endpoint_reports_availability_and_labelled_validation_metrics(client):
    _, headers = auth_headers(client, Role.HEALTH_WORKER)
    models = {m["condition"]: m for m in client.get("/api/models", headers=headers).json()}
    assert models["dr"]["available"] and models["dr"]["version"] == "mobilenetv2-dr-binary-0.3"
    assert models["dr"]["metrics"]["sensitivity"] == 0.542
    assert "not an independent hold-out" in models["dr"]["metrics_status"]
    assert models["dr"]["limitations"]
    assert not models["glaucoma"]["available"] and not models["cataract"]["available"]


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
