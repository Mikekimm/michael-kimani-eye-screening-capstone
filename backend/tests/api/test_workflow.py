"""Referral -> specialist review -> sync pull, append-only history, and admin analytics.

Uses the FixedScoreModel test double so the referral path is deterministic.
"""
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.core import patient_codes
from app.models import AppendOnlyViolation, AuditEvent, Referral, ReviewEvent, Screening
from app.models.enums import Role

from ..conftest import encode, make_fundus_like
from .conftest import FixedScoreModel, auth_headers, register_patient, upload


QUESTION = "Is this proliferative? Patient reports blurred vision."


def ask(client, headers, screening_id, question=QUESTION, conditions=("dr",), priority=None):
    body = {"question": question, "conditions": list(conditions)} | ({"priority": priority} if priority else {})
    return client.post(f"/api/screenings/{screening_id}/ask-specialist", headers=headers, json=body)


@pytest.fixture
def referred(stub_client):
    """A clear positive (score 0.9) that the health worker chose to send to a specialist with a question."""
    FixedScoreModel.score = 0.9
    _, worker = auth_headers(stub_client, Role.HEALTH_WORKER)
    _, specialist = auth_headers(stub_client, Role.SPECIALIST)
    patient = register_patient(stub_client, worker)
    screening = upload(stub_client, worker, patient["id"]).json()
    assert ask(stub_client, worker, screening["id"]).status_code == 200
    return stub_client, worker, specialist, screening


def _screen(client, score, **upload_args):
    FixedScoreModel.score = score
    _, worker = auth_headers(client, Role.HEALTH_WORKER)
    return worker, upload(client, worker, register_patient(client, worker)["id"], **upload_args).json()


def test_nothing_is_sent_to_a_specialist_automatically(stub_client):
    _, specialist = auth_headers(stub_client, Role.SPECIALIST)
    _, screening = _screen(stub_client, 0.9)
    assert screening["status"] == "completed" and screening["referral_advice"] == "recommended"
    assert screening["referral_reason"] is None
    assert stub_client.get("/api/reviews/queue", headers=specialist).json() == []


@pytest.mark.parametrize(("offset", "advice", "status"), [
    (+0.4, "recommended", "completed"),  # clear positive: "Refer recommended", the health worker sends it
    (-0.05, "consider", "referred"),     # borderline: queued automatically, as in the proposal
    (-0.4, "none", "completed")])        # clear negative: not queued
def test_recommendation_and_automatic_queueing_follow_the_policy(stub_client, offset, advice, status):
    threshold = stub_client.container.registry.get("dr").card.threshold
    _, screening = _screen(stub_client, min(0.99, max(0.01, threshold + offset)))
    assert screening["referral_advice"] == advice and screening["status"] == status
    assert screening["queued_automatically"] is (status == "referred")


def test_negative_result_on_a_low_quality_photo_is_uncertain(stub_client):
    from PIL import ImageFilter
    blurred = encode(make_fundus_like(seed=4).filter(ImageFilter.GaussianBlur(8)), "JPEG")
    _, screening = _screen(stub_client, 0.01, data=blurred)
    assert screening["quality"]["warnings"] and screening["referral_advice"] == "consider"
    assert screening["status"] == "referred" and screening["queued_automatically"] is True  # usable but low quality


def test_asked_case_reaches_the_queue_with_the_question(referred):
    client, worker, specialist, screening = referred
    queue = client.get("/api/reviews/queue", headers=specialist).json()
    assert [item["screening_id"] for item in queue] == [screening["id"]]
    assert queue[0]["question"] == QUESTION and queue[0]["highest_band"] == 5
    assert queue[0]["flagged_conditions"] == ["dr"]  # the stub has no glaucoma or cataract model
    detail = client.get(f"/api/screenings/{screening['id']}", headers=worker).json()
    assert detail["status"] == "referred" and detail["referral_question"] == QUESTION
    assert detail["referral_reason"] == "positive"  # from the recommendation when asked


def test_a_case_is_sent_once_and_needs_a_question(stub_client):
    worker, screening = _screen(stub_client, 0.05)
    assert ask(stub_client, worker, screening["id"], question="  ").status_code == 422
    assert ask(stub_client, worker, screening["id"], question="Please check the macula.").status_code == 200
    assert ask(stub_client, worker, screening["id"]).status_code == 409


def test_discard_hides_the_screening_keeps_the_audit_and_deletes_the_photo(referred):
    client, worker, specialist, screening = referred
    url = f"/api/screenings/{screening['id']}"
    assert client.post(f"{url}/discard", headers=worker, json={"reason": ""}).status_code == 422
    assert client.post(f"{url}/discard", headers=specialist, json={"reason": "wrong photo"}).status_code == 403
    _, stranger = auth_headers(client, Role.HEALTH_WORKER)
    assert client.post(f"{url}/discard", headers=stranger, json={"reason": "wrong photo"}).status_code == 404
    for session in client.container.database.session():
        photo = client.container.images.path_for(session.get(Screening, screening["id"]).image_path)

    assert client.post(f"{url}/discard", headers=worker, json={"reason": "Uploaded the wrong photo."}).status_code == 204
    assert client.get(url, headers=worker).status_code == 404
    assert client.get(url, headers=specialist).status_code == 404
    assert client.get("/api/screenings", headers=worker).json() == []
    assert client.get("/api/reviews/queue", headers=specialist).json() == []
    assert not photo.exists()
    for session in client.container.database.session():
        row = session.get(Screening, screening["id"])
        assert row.discard_reason == "Uploaded the wrong photo." and row.discarded_at is not None
        assert session.query(AuditEvent).filter_by(action="screening.discarded", entity_id=screening["id"]).count() == 1


def test_history_can_be_filtered_by_day_in_the_clinic_time_zone(stub_client):
    worker, first = _screen(stub_client, 0.05)
    second = upload(stub_client, worker, first["patient_id"]).json()
    zone = ZoneInfo(stub_client.container.settings.time_zone)
    late = datetime(2026, 10, 27, 23, 59, tzinfo=zone)  # 23:59 and 00:01 local fall on different days
    for screening_id, local in ((first["id"], late), (second["id"], late + timedelta(minutes=2))):
        for session in stub_client.container.database.session():
            session.get(Screening, screening_id).created_at = local.astimezone(timezone.utc)
            session.commit()
    day = lambda d: [s["id"] for s in stub_client.get("/api/screenings", headers=worker, params={"day": d}).json()]  # noqa: E731
    assert day("2026-10-27") == [first["id"]]
    assert day("2026-10-28") == [second["id"]]


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


def test_retake_request_comes_back_as_retake_needed(referred):
    client, worker, specialist, screening = referred
    client.post(f"/api/reviews/{screening['id']}", headers=specialist,
                json={"action": "request_retake", "note": "Too dark, please retake."})
    pulled = client.get("/api/sync/pull", headers=worker).json()["decisions"][0]
    assert pulled["status"] == "retake_requested" and pulled["latest_note"] == "Too dark, please retake."


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
    batch = {"patients": [{"code": patient_codes.generate(), "client_uuid": str(uuid.uuid4())},
                          {"code": patient_codes.generate(), "client_uuid": str(uuid.uuid4())}]}
    first = stub_client.post("/api/sync/push", headers=worker, json=batch).json()["results"]
    replay = stub_client.post("/api/sync/push", headers={**worker, "X-Sync-Attempt": "2"}, json=batch).json()["results"]
    assert [r["outcome"] for r in first] == ["accepted", "accepted"]
    assert [r["outcome"] for r in replay] == ["duplicate", "duplicate"]
    assert [r["server_id"] for r in first] == [r["server_id"] for r in replay]
    assert len(stub_client.get("/api/patients", headers=worker).json()) == 2


def test_sync_push_rejects_items_without_key_and_replaces_a_taken_device_code(stub_client):
    _, worker = auth_headers(stub_client, Role.HEALTH_WORKER)
    taken = register_patient(stub_client, worker)["code"]
    batch = {"patients": [{"code": patient_codes.generate()}, {"code": taken, "client_uuid": str(uuid.uuid4())}]}
    results = stub_client.post("/api/sync/push", headers=worker, json=batch).json()["results"]
    assert [r["outcome"] for r in results] == ["rejected", "accepted"]
    assert results[1]["code"] != taken and patient_codes.is_valid(results[1]["code"])


def test_analytics_are_aggregates_only(referred):
    client, _, specialist, screening = referred
    client.post(f"/api/reviews/{screening['id']}", headers=specialist, json={"action": "approve"})
    _, admin = auth_headers(client, Role.ADMIN)
    stats = client.get("/api/admin/analytics", headers=admin).json()
    assert stats["total_screenings"] == 1
    assert stats["positives_per_condition"] == {"dr": 1}
    assert stats["referral_rate"] == 1.0 and stats["open_referrals"] == 0
    assert stats["median_review_turnaround_hours"] is not None
    assert stats["model_versions_in_use"] == {"mobilenetv2-dr-binary-2.0": 1}  # the stub uses the real DR card
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


def test_health_worker_can_ask_about_a_negative_result(stub_client):
    _, specialist = auth_headers(stub_client, Role.SPECIALIST)
    worker, screening = _screen(stub_client, 0.05)
    assert screening["referral_advice"] == "none"
    response = ask(stub_client, worker, screening["id"], question="Patient has a family history of glaucoma.")
    assert response.status_code == 200
    assert response.json()["status"] == "referred" and response.json()["referral_reason"] == "manual"
    queue = stub_client.get("/api/reviews/queue", headers=specialist).json()
    assert [(q["screening_id"], q["priority"]) for q in queue] == [(screening["id"], "routine")]


def test_only_the_owner_can_ask_a_specialist(stub_client):
    _, other = auth_headers(stub_client, Role.HEALTH_WORKER)
    _, specialist = auth_headers(stub_client, Role.SPECIALIST)
    _, screening = _screen(stub_client, 0.05)
    assert ask(stub_client, other, screening["id"]).status_code == 404
    assert ask(stub_client, specialist, screening["id"]).status_code == 403


def test_queue_and_screening_show_waiting_time_priority_and_overdue(referred):
    client, worker, specialist, screening = referred
    item = client.get("/api/reviews/queue", headers=specialist).json()[0]
    assert item["priority"] == "urgent" and item["overdue"] is False
    assert item["waiting_since"] and item["due_at"]
    detail = client.get(f"/api/screenings/{screening['id']}", headers=worker).json()
    assert detail["review_priority"] == "urgent" and detail["referred_at"] and detail["review_overdue"] is False

    for session in client.container.database.session():  # pretend the case was referred 25 hours ago
        referral = session.query(Referral).filter_by(screening_id=screening["id"]).one()
        referral.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
        session.commit()
    assert client.get("/api/reviews/queue", headers=specialist).json()[0]["overdue"] is True
    _, admin = auth_headers(client, Role.ADMIN)
    stats = client.get("/api/admin/analytics", headers=admin).json()
    assert stats["overdue_referrals"] == 1 and stats["review_targets_hours"] == {"urgent": 24, "routine": 72}


def test_uncertain_case_is_queued_routine_and_the_health_worker_can_add_a_question(stub_client):
    _, specialist = auth_headers(stub_client, Role.SPECIALIST)
    threshold = stub_client.container.registry.get("dr").card.threshold
    worker, screening = _screen(stub_client, threshold - 0.05)
    assert screening["status"] == "referred" and screening["review_priority"] == "routine"
    assert screening["referral_conditions"] == ["dr"] and screening["referral_question"] is None
    queue = stub_client.get("/api/reviews/queue", headers=specialist).json()
    assert [(q["screening_id"], q["question"]) for q in queue] == [(screening["id"], None)]

    added = ask(stub_client, worker, screening["id"], question="Patient is diabetic for 10 years.")
    assert added.status_code == 200 and added.json()["referral_question"] == "Patient is diabetic for 10 years."
    assert ask(stub_client, worker, screening["id"]).status_code == 409  # the question can be added once
    for session in stub_client.container.database.session():
        actions = {a for (a,) in session.query(AuditEvent.action).filter_by(entity_id=screening["id"]).all()}
    assert {"screening.queued_automatically", "screening.question_added"} <= actions


def test_new_decision_shows_until_the_health_worker_opens_the_screening(referred):
    client, worker, specialist, screening = referred
    assert client.get("/api/screenings/new-decisions", headers=worker).json() == {"count": 0, "screening_ids": []}
    client.post(f"/api/reviews/{screening['id']}", headers=specialist, json={"action": "approve"})
    assert client.get("/api/screenings/new-decisions", headers=worker).json() == {"count": 1, "screening_ids": [screening["id"]]}
    listed = client.get("/api/screenings", headers=worker).json()
    assert listed[0]["new_decision"] is True and listed[0]["status"] == "reviewed"
    client.get(f"/api/screenings/{screening['id']}", headers=specialist)  # the specialist opening it changes nothing
    assert client.get("/api/screenings/new-decisions", headers=worker).json()["count"] == 1
    opened = client.get(f"/api/screenings/{screening['id']}", headers=worker).json()
    assert opened["status"] == "reviewed"
    assert client.get("/api/screenings/new-decisions", headers=worker).json()["count"] == 0
