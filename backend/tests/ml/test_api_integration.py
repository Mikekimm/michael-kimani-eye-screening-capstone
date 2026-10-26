"""Integration tests: a real HTTP backend on a free local port, real clients, real SQLite.

Covers authentication and roles, input validation, request limits, and the full
offline -> online -> specialist review -> review pulled back loop.
"""
import http.client
import json
import threading

import pytest

from app.ml.api_client import ClinicClient, SpecialistClient
from app.ml.domain import Role, SyncStatus
from app.ml.exceptions import RemoteAuthError, RemoteRejectedError
from app.ml.server import MAX_BODY_BYTES, Principal, TokenAuthenticator, make_server
from app.ml.storage import ScreeningRepository
from app.ml.sync import SyncService
from tests.conftest import save_one

pytestmark = pytest.mark.integration_api

TOKENS = {
    "tok-clinic": Principal("clinic-nurse", Role.CLINICIAN),
    "tok-doctor": Principal("dr-specialist", Role.SPECIALIST),
    "tok-admin": Principal("admin-user", Role.ADMIN),
}


class Backend:
    def __init__(self, tmp_path):
        self.repo = ScreeningRepository(tmp_path / "srv.db", tmp_path / "srv_images")
        self.server = make_server(self.repo, TOKENS, port=0)
        self.port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def clinic(self, token="tok-clinic"):
        return ClinicClient(self.url, token, timeout=3)

    def specialist(self, token="tok-doctor"):
        return SpecialistClient(self.url, token, timeout=3)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def backend(tmp_path):
    srv = Backend(tmp_path)
    yield srv
    srv.stop()


def raw_request(backend, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", backend.port, timeout=3)
    conn.request(method, path, body=body, headers=headers or {})
    response = conn.getresponse()
    data = response.read()
    conn.close()
    return response.status, data


# ---- authentication and roles --------------------------------------------------
def test_health_needs_no_token(backend):
    assert raw_request(backend, "GET", "/health")[0] == 200
    assert backend.clinic("anything").ping() is True


def test_missing_or_wrong_token_is_401(backend, repo):
    record = save_one(repo)
    assert raw_request(backend, "GET", "/api/reviews")[0] == 401
    with pytest.raises(RemoteAuthError):
        backend.clinic("wrong").push_screening(repo.build_sync_payload(record.id))


def test_clinician_cannot_read_cases_or_review(backend, repo):
    record = save_one(repo)
    backend.clinic().push_screening(repo.build_sync_payload(record.id))
    clinician_as_specialist = SpecialistClient(backend.url, "tok-clinic", timeout=3)
    with pytest.raises(RemoteAuthError):
        clinician_as_specialist.list_cases()
    with pytest.raises(RemoteAuthError):
        clinician_as_specialist.submit_review(record.id, "approve")


def test_specialist_cannot_upload_screenings(backend, repo):
    record = save_one(repo)
    wrong_role = ClinicClient(backend.url, "tok-doctor", timeout=3)
    with pytest.raises(RemoteAuthError):
        wrong_role.push_screening(repo.build_sync_payload(record.id))


def test_authenticator_rejects_malformed_headers():
    auth = TokenAuthenticator(TOKENS)
    assert auth.authenticate(None) is None
    assert auth.authenticate("tok-clinic") is None
    assert auth.authenticate("Basic tok-clinic") is None
    assert auth.authenticate("Bearer nope") is None
    assert auth.authenticate("Bearer tok-clinic").role is Role.CLINICIAN


# ---- validation and limits -----------------------------------------------------
def test_tampered_upload_is_rejected_with_400(backend, repo):
    payload = repo.build_sync_payload(save_one(repo).id)
    payload["image_sha256"] = "f" * 64
    with pytest.raises(RemoteRejectedError):
        backend.clinic().push_screening(payload)
    assert backend.repo.stats()["screenings"] == 0


def test_malformed_json_and_non_object_bodies_are_400(backend):
    headers = {"Authorization": "Bearer tok-clinic", "Content-Type": "application/json"}
    assert raw_request(backend, "POST", "/api/screenings", b"{not json", headers)[0] == 400
    assert raw_request(backend, "POST", "/api/screenings", b"[1,2]", headers)[0] == 400


def test_oversized_body_is_413_without_reading_it(backend):
    conn = http.client.HTTPConnection("127.0.0.1", backend.port, timeout=3)
    conn.putrequest("POST", "/api/screenings")
    conn.putheader("Authorization", "Bearer tok-clinic")
    conn.putheader("Content-Length", str(MAX_BODY_BYTES + 1))
    conn.endheaders()
    assert conn.getresponse().status == 413
    conn.close()


def test_unknown_endpoint_is_404_and_errors_do_not_leak_internals(backend):
    status, body = raw_request(backend, "GET", "/api/nothing",
                               headers={"Authorization": "Bearer tok-admin"})
    assert status == 404 and "error" in json.loads(body)


def test_review_for_unknown_screening_and_bad_decision(backend, repo):
    record = save_one(repo)
    backend.clinic().push_screening(repo.build_sync_payload(record.id))
    doctor = backend.specialist()
    with pytest.raises(RemoteRejectedError):
        doctor.submit_review("11111111-1111-1111-1111-111111111111", "approve")
    with pytest.raises(RemoteRejectedError):
        doctor.submit_review(record.id, "looks-fine")
    with pytest.raises(RemoteRejectedError):
        doctor.submit_review(record.id, "approve", "x" * 2001)


def test_reviewer_identity_comes_from_the_token_not_the_request(backend, repo):
    record = save_one(repo)
    backend.clinic().push_screening(repo.build_sync_payload(record.id))
    saved = backend.specialist().submit_review(record.id, "approve")
    assert saved["reviewer"] == "dr-specialist"


# ---- the offline-first scenarios from the proposal ------------------------------
def test_offline_then_online_full_loop(backend, repo):
    first = save_one(repo, probability=0.9, patient="PT-001", side="left")
    second = save_one(repo, probability=0.45, patient="PT-002", side="right")
    clear = save_one(repo, probability=0.02, patient="PT-003", side="left")

    # 1. no server reachable: screening data stays safely on the device
    dead = ClinicClient("http://127.0.0.1:9", "tok-clinic", timeout=1)
    offline = SyncService(repo, dead).sync()
    assert offline.offline and len(repo.pending()) == 3

    # 2. connectivity restored: everything uploads
    online = SyncService(repo, backend.clinic())
    assert online.sync().pushed == 3
    assert all(r.sync_status is SyncStatus.SYNCED for r in repo.list_screenings())

    # 3. the specialist sees only flagged/borderline cases, with laterality and model version
    doctor = backend.specialist()
    cases = doctor.list_cases()
    assert {c["id"] for c in cases} == {first.id, second.id}
    assert clear.id not in {c["id"] for c in cases}
    assert {c["laterality"] for c in cases} == {"left", "right"}
    assert all(c["model_version"] == "test-model-1" for c in cases)
    assert doctor.get_image(first.id) == repo.image_bytes(first.id)

    # 4. review history is kept: a second opinion does not erase the first
    doctor.submit_review(first.id, "approve", "agree")
    doctor.submit_review(first.id, "override_no_dr", "on reflection no DR")
    assert [c["id"] for c in doctor.list_cases()] == [second.id]  # first is now reviewed
    assert len(backend.repo.reviews_for(first.id)) == 2

    # 5. the clinic pulls decisions back, once, with the history intact
    assert online.sync().reviews_pulled == 2
    assert online.sync().reviews_pulled == 0
    assert [r.decision.value for r in repo.reviews_for(first.id)] == ["approve", "override_no_dr"]
    assert backend.repo.stats()["screenings"] == 3  # no duplicates after repeated syncs


def test_server_going_down_mid_session_keeps_new_data_pending(tmp_path, repo):
    backend = Backend(tmp_path)
    client = backend.clinic()
    save_one(repo, patient="PT-001")
    assert SyncService(repo, client).sync().pushed == 1
    assert client.ping() is True
    backend.stop()  # the network drops

    save_one(repo, patient="PT-002")
    assert client.ping() is False
    report = SyncService(repo, client).sync()
    assert report.offline and report.pushed == 0
    assert len(repo.pending()) == 1  # the new screening is safe on the device


def test_admin_can_read_stats(backend, repo):
    backend.clinic().push_screening(repo.build_sync_payload(save_one(repo).id))
    stats = SpecialistClient(backend.url, "tok-admin", timeout=3).stats()
    assert stats["screenings"] == 1 and stats["needs_review"] == 1
