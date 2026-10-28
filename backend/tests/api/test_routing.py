"""Specialty routing (an extension beyond the proposal): conditions and priority on "Ask a specialist",
specialties per specialist, "Take this case", role checks, and overdue counts for the admin."""
from datetime import datetime, timedelta, timezone

import pytest

from app.models import AuditEvent, Referral, User
from app.models.enums import Role

from .conftest import FixedScoreModel, auth_headers, create_user, login, register_patient, upload


def _specialist(client, specialties, name):
    user = create_user(client, Role.SPECIALIST)
    for session in client.container.database.session():
        stored = session.get(User, user.id)
        stored.specialties, stored.full_name = list(specialties), name
        session.commit()
    return login(client, user)


def _sent_case(client, conditions=("dr",), priority=None, score=0.9):
    FixedScoreModel.score = score
    _, worker = auth_headers(client, Role.HEALTH_WORKER)
    screening = upload(client, worker, register_patient(client, worker)["id"]).json()
    body = {"question": "Please check.", "conditions": list(conditions)} | ({"priority": priority} if priority else {})
    response = client.post(f"/api/screenings/{screening['id']}/ask-specialist", headers=worker, json=body)
    assert response.status_code == 200, response.text
    return worker, response.json()


def test_ask_names_conditions_and_priority(stub_client):
    worker, sent = _sent_case(stub_client, conditions=("dr",), priority="routine")
    assert sent["referral_conditions"] == ["dr"] and sent["review_priority"] == "routine"
    due = datetime.fromisoformat(sent["review_due_at"]) - datetime.fromisoformat(sent["referred_at"])
    assert due == timedelta(hours=72)  # the health worker chose routine although signs were detected


def test_priority_defaults_to_urgent_for_a_clear_positive(stub_client):
    _, sent = _sent_case(stub_client)
    assert sent["review_priority"] == "urgent"


def test_ask_needs_at_least_one_evaluated_condition(stub_client):
    FixedScoreModel.score = 0.9
    _, worker = auth_headers(stub_client, Role.HEALTH_WORKER)
    screening = upload(stub_client, worker, register_patient(stub_client, worker)["id"]).json()
    url = f"/api/screenings/{screening['id']}/ask-specialist"
    assert stub_client.post(url, headers=worker, json={"question": "Please check.", "conditions": []}).status_code == 422
    assert stub_client.post(url, headers=worker, json={"question": "Please check.", "conditions": ["myopia"]}).status_code == 400
    assert stub_client.post(url, headers=worker, json={"question": "Please check.", "conditions": ["glaucoma"]}).status_code == 400  # no model ran
    assert stub_client.post(url, headers=worker, json={"question": "Please check."}).status_code == 422


def test_queue_puts_cases_matching_the_specialty_first(stub_client):
    _, glaucoma_case = _sent_case(stub_client)  # the stub scores DR only; this one is relabelled below
    _, dr_case = _sent_case(stub_client)
    for session in stub_client.container.database.session():
        session.query(Referral).filter_by(screening_id=glaucoma_case["id"]).one().conditions = ["glaucoma"]
        session.commit()
    dr_specialist = _specialist(stub_client, ["dr"], "Dr Retina")
    queue = stub_client.get("/api/reviews/queue", headers=dr_specialist).json()
    assert [(q["screening_id"], q["matches_my_specialties"]) for q in queue] == [
        (dr_case["id"], True), (glaucoma_case["id"], False)]  # matching first, then "All cases"
    general = _specialist(stub_client, ["general"], "Dr General")
    assert all(q["matches_my_specialties"] for q in stub_client.get("/api/reviews/queue", headers=general).json())
    nothing = _specialist(stub_client, [], "Dr None")
    assert not any(q["matches_my_specialties"] for q in stub_client.get("/api/reviews/queue", headers=nothing).json())


def test_take_assigns_the_case_and_others_see_it_as_taken(stub_client):
    worker, sent = _sent_case(stub_client)
    first, second = _specialist(stub_client, ["dr"], "Dr First"), _specialist(stub_client, ["dr"], "Dr Second")
    taken = stub_client.post(f"/api/reviews/{sent['id']}/take", headers=first)
    assert taken.status_code == 200 and taken.json()["assigned_to_name"] == "Dr First"
    assert stub_client.post(f"/api/reviews/{sent['id']}/take", headers=first).status_code == 200  # idempotent

    item = stub_client.get("/api/reviews/queue", headers=second).json()[0]
    assert item["assigned_to_name"] == "Dr First" and item["assigned_to_me"] is False
    assert stub_client.post(f"/api/reviews/{sent['id']}/take", headers=second).status_code == 409
    assert stub_client.post(f"/api/reviews/{sent['id']}", headers=second, json={"action": "approve"}).status_code == 409

    seen = stub_client.get(f"/api/screenings/{sent['id']}", headers=worker).json()
    assert seen["assigned_to_name"] == "Dr First" and seen["status"] == "referred"  # "Being reviewed by Dr First"

    decided = stub_client.post(f"/api/reviews/{sent['id']}", headers=first,
                               json={"action": "override", "condition": "dr", "override_positive": False,
                                     "note": "Artefact, not haemorrhages."})
    assert decided.status_code == 201
    back = stub_client.get(f"/api/screenings/{sent['id']}", headers=worker).json()
    assert back["status"] == "reviewed" and back["reviews"][-1]["note"] == "Artefact, not haemorrhages."
    for session in stub_client.container.database.session():
        actions = [a for (a,) in session.query(AuditEvent.action).filter_by(entity_id=sent["id"]).all()]
    assert actions.count("review.taken") == 1 and "review.override" in actions


def test_deciding_without_take_also_takes_the_case(stub_client):
    worker, sent = _sent_case(stub_client)
    specialist = _specialist(stub_client, ["general"], "Dr Quick")
    stub_client.post(f"/api/reviews/{sent['id']}", headers=specialist, json={"action": "comment", "note": "Looking."})
    assert stub_client.get(f"/api/screenings/{sent['id']}", headers=worker).json()["assigned_to_name"] == "Dr Quick"


def test_role_checks_on_take(stub_client):
    worker, sent = _sent_case(stub_client)
    specialist = _specialist(stub_client, ["dr"], "Dr Checks")
    assert stub_client.post(f"/api/reviews/{sent['id']}/take", headers=worker).status_code == 403
    assert stub_client.post(f"/api/reviews/{sent['id']}", headers=worker, json={"action": "approve"}).status_code == 403
    assert stub_client.post("/api/reviews/not-a-case/take", headers=specialist).status_code == 404

    FixedScoreModel.score = 0.9  # a screening nobody sent is not in the queue
    unsent = upload(stub_client, worker, register_patient(stub_client, worker)["id"]).json()
    assert stub_client.post(f"/api/reviews/{unsent['id']}/take", headers=specialist).status_code == 404

    stub_client.post(f"/api/reviews/{sent['id']}", headers=specialist, json={"action": "approve"})
    assert stub_client.post(f"/api/reviews/{sent['id']}/take", headers=specialist).status_code == 409  # closed


def test_admin_sets_specialties_on_approval_and_later(client):
    admin = login(client, create_user(client, Role.ADMIN))
    applicant = client.post("/api/auth/register", json={"email": "eye@example.org", "full_name": "Dr Eye",
                                                        "password": "s3cure-pass-word1", "requested_role": "specialist"})
    url = f"/api/admin/users/{applicant.json()['id']}"
    approved = client.patch(url, headers=admin, json={"status": "approved", "specialties": ["glaucoma", "dr"]})
    assert approved.status_code == 200
    assert approved.json()["role"] == "specialist" and approved.json()["specialties"] == ["dr", "glaucoma"]
    assert client.patch(url, headers=admin, json={"specialties": ["general"]}).json()["specialties"] == ["general"]
    assert client.patch(url, headers=admin, json={"specialties": ["myopia"]}).status_code == 422
    for session in client.container.database.session():
        assert session.query(AuditEvent).filter_by(action="user.specialties_changed").count() == 2


def test_admin_analytics_count_overdue_cases_by_priority(stub_client):
    _, urgent = _sent_case(stub_client, priority="urgent")
    _, routine = _sent_case(stub_client, priority="routine")
    for session in stub_client.container.database.session():  # both referred 30 hours ago
        for referral in session.query(Referral).all():
            referral.created_at = datetime.now(timezone.utc) - timedelta(hours=30)
        session.commit()
    _, admin = auth_headers(stub_client, Role.ADMIN)
    stats = stub_client.get("/api/admin/analytics", headers=admin).json()
    assert stats["overdue_referrals"] == 1 and stats["overdue_by_priority"] == {"urgent": 1, "routine": 0}
