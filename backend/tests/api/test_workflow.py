"""Referral -> specialist review -> sync pull, append-only history, and admin analytics.

Uses the FixedScoreModel test double so the referral path is deterministic.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.models import AppendOnlyViolation, AuditEvent, ReviewEvent
from app.models.enums import Role

from .conftest import FixedScoreModel, auth_headers, register_patient, upload


@pytest.fixture
def referred(stub_client):
    """A health worker's screening that the policy referred (score 0.9 -> positive)."""
    FixedScoreModel.score = 0.9
    _, worker = auth_headers(stub_client, Role.HEALTH_WORKER)
    _, specialist = auth_headers(stub_client, Role.SPECIALIST)
    patient = register_patient(stub_client, worker)
    screening = upload(stub_client, worker, patient["id"]).json()
    return stub_client, worker, specialist, screening


def test_positive_result_is_referred_and_queued(referred):
    client, _, specialist, screening = referred
    assert screening["status"] == "referred" and screening["referral_reason"] == "positive"
    queue = client.get("/api/reviews/queue", headers=specialist).json()
    assert [item["screening_id"] for item in queue] == [screening["id"]]
    assert queue[0]["highest_band"] == 5


def test_borderline_negative_is_referred_as_uncertain(stub_client):
    FixedScoreModel.score = 0.45  # below the 0.5 threshold but inside the +/-0.10 band
    _, worker = auth_headers(stub_client, Role.HEALTH_WORKER)
    screening = upload(stub_client, worker, register_patient(stub_client, worker)["id"]).json()
    dr = next(r for r in screening["results"] if r["condition"] == "dr")
    assert dr["positive"] is False and dr["uncertain"] is True and dr["severity_band"] == 3
    assert screening["referral_reason"] == "uncertain"


def test_approve_closes_the_referral(referred):
    client, _, specialist, screening = referred
    response = client.post(f"/api/reviews/{screening['id']}", headers=specialist, json={"action": "approve"})
    assert response.status_code == 201 and response.json()["status"] == "reviewed"
    assert client.get("/api/reviews/queue", headers=specialist).json() == []


def test_override_requires_condition_result_and_reason(referred):
    client, _, specialist, screening = referred
    url = f"/api/reviews/{screening['id']}"
    assert client.post(url, headers=specialist, json={"action": "override", "condition": "dr",
                                                      "override_positive": False}).status_code == 422
    assert client.post(url, headers=specialist, json={"action": "override", "note": "why"}).status_code == 422
    ok = client.post(url, headers=specialist, json={"action": "override", "condition": "dr",
                                                    "override_positive": False, "note": "Artefact, no lesions."})
    assert ok.status_code == 201


def test_cannot_override_a_condition_without_a_model(referred):
    client, _, specialist, screening = referred
    response = client.post(f"/api/reviews/{screening['id']}", headers=specialist,
                           json={"action": "override", "condition": "glaucoma", "override_positive": True, "note": "x"})
    assert response.status_code == 400


def test_review_history_is_append_only(referred):
    client, _, specialist, screening = referred
    url = f"/api/reviews/{screening['id']}"
    client.post(url, headers=specialist, json={"action": "comment", "note": "Looks like microaneurysms."})
    client.post(url, headers=specialist, json={"action": "request_retake", "note": "Image slightly blurred."})
    client.post(url, headers=specialist, json={"action": "approve"})
    final = client.get(f"/api/screenings/{screening['id']}", headers=specialist).json()
    assert [r["action"] for r in final["reviews"]] == ["comment", "request_retake", "approve"]

    for session in client.container.database.session():
        event = session.query(ReviewEvent).first()
        event.note = "rewritten history"
        with pytest.raises(AppendOnlyViolation):
            session.flush()
        session.rollback()
        with pytest.raises(AppendOnlyViolation):
            session.delete(session.query(ReviewEvent).first())
            session.flush()


def test_specialist_cannot_review_unreferred_screening(stub_client):
    FixedScoreModel.score = 0.05
    _, worker = auth_headers(stub_client, Role.HEALTH_WORKER)
    _, specialist = auth_headers(stub_client, Role.SPECIALIST)
    screening = upload(stub_client, worker, register_patient(stub_client, worker)["id"]).json()
    response = stub_client.post(f"/api/reviews/{screening['id']}", headers=specialist, json={"action": "approve"})
    assert response.status_code == 404


def test_sync_pull_returns_only_new_decisions(referred):
    client, worker, specialist, screening = referred
    before = client.get("/api/sync/pull", headers=worker).json()
    assert before["decisions"] == []  # nothing reviewed yet

    client.post(f"/api/reviews/{screening['id']}", headers=specialist, json={"action": "approve"})
    after = client.get("/api/sync/pull", headers=worker, params={"since": before["server_time"]}).json()
    assert [d["screening_id"] for d in after["decisions"]] == [screening["id"]]
    assert after["decisions"][0]["status"] == "reviewed"

    again = client.get("/api/sync/pull", headers=worker, params={"since": after["server_time"]}).json()
    assert again["decisions"] == []


def test_sync_push_is_idempotent_per_client_uuid(stub_client):
    _, worker = auth_headers(stub_client, Role.HEALTH_WORKER)
    batch = {"patients": [{"code": "OFF-001", "client_uuid": str(uuid.uuid4())},
                          {"code": "OFF-002", "client_uuid": str(uuid.uuid4())}]}
    first = stub_client.post("/api/sync/push", headers=worker, json=batch).json()["results"]
    replay = stub_client.post("/api/sync/push", headers={**worker, "X-Sync-Attempt": "2"}, json=batch).json()["results"]
    assert [r["outcome"] for r in first] == ["accepted", "accepted"]
    assert [r["outcome"] for r in replay] == ["duplicate", "duplicate"]
    assert [r["server_id"] for r in first] == [r["server_id"] for r in replay]
    assert len(stub_client.get("/api/patients", headers=worker).json()) == 2


def test_sync_push_rejects_items_without_key_or_with_taken_code(stub_client):
    _, worker = auth_headers(stub_client, Role.HEALTH_WORKER)
    register_patient(stub_client, worker, code="TAKEN-1")
    batch = {"patients": [{"code": "NOKEY-1"}, {"code": "TAKEN-1", "client_uuid": str(uuid.uuid4())}]}
    results = stub_client.post("/api/sync/push", headers=worker, json=batch).json()["results"]
    assert [r["outcome"] for r in results] == ["rejected", "rejected"]
    assert "already registered" in results[1]["error"]


def test_analytics_are_aggregates_only(referred):
    client, _, specialist, screening = referred
    client.post(f"/api/reviews/{screening['id']}", headers=specialist, json={"action": "approve"})
    _, admin = auth_headers(client, Role.ADMIN)
    stats = client.get("/api/admin/analytics", headers=admin).json()
    assert stats["total_screenings"] == 1
    assert stats["positives_per_condition"] == {"dr": 1}
    assert stats["referral_rate"] == 1.0 and stats["open_referrals"] == 0
    assert stats["median_review_turnaround_hours"] is not None
    assert stats["model_versions_in_use"] == {"mobilenetv2-dr-binary-0.3": 1}
    text = str(stats)
    assert screening["patient_code"] not in text and screening["id"] not in text


def test_audit_log_records_key_actions(referred):
    client, _, specialist, screening = referred
    client.post(f"/api/reviews/{screening['id']}", headers=specialist, json={"action": "approve"})
    for session in client.container.database.session():
        actions = {a for (a,) in session.query(AuditEvent.action).all()}
    assert {"auth.login", "patient.created", "screening.created", "review.approve"} <= actions


def test_utc_timestamps_round_trip(referred):
    _, _, _, screening = referred
    created = datetime.fromisoformat(screening["created_at"])
    assert created.tzinfo is not None and created.utcoffset().total_seconds() == 0
    assert abs((datetime.now(timezone.utc) - created).total_seconds()) < 120


def test_health_worker_can_refer_a_negative_result_manually(stub_client):
    FixedScoreModel.score = 0.05
    _, worker = auth_headers(stub_client, Role.HEALTH_WORKER)
    _, specialist = auth_headers(stub_client, Role.SPECIALIST)
    screening = upload(stub_client, worker, register_patient(stub_client, worker)["id"]).json()
    assert stub_client.get("/api/reviews/queue", headers=specialist).json() == []

    referred = stub_client.post(f"/api/screenings/{screening['id']}/refer", headers=worker)
    assert referred.status_code == 200
    assert referred.json()["status"] == "referred" and referred.json()["referral_reason"] == "manual"
    assert [q["screening_id"] for q in stub_client.get("/api/reviews/queue", headers=specialist).json()] == [screening["id"]]
    assert stub_client.post(f"/api/screenings/{screening['id']}/refer", headers=worker).status_code == 409


def test_only_the_owner_can_refer(stub_client):
    FixedScoreModel.score = 0.05
    _, worker = auth_headers(stub_client, Role.HEALTH_WORKER)
    _, other = auth_headers(stub_client, Role.HEALTH_WORKER)
    _, specialist = auth_headers(stub_client, Role.SPECIALIST)
    screening = upload(stub_client, worker, register_patient(stub_client, worker)["id"]).json()
    assert stub_client.post(f"/api/screenings/{screening['id']}/refer", headers=other).status_code == 404
    assert stub_client.post(f"/api/screenings/{screening['id']}/refer", headers=specialist).status_code == 403
