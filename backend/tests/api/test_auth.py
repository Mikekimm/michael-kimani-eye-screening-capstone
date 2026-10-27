"""Authentication: sign-up with admin approval, hashing, login, token refresh/rotation, logout,
password reset by email, validation errors."""
import re
from datetime import datetime, timedelta, timezone

import pytest

from app.models import AuditEvent, PasswordResetToken, User
from app.models.enums import Role

from .conftest import PASSWORD, create_user, login

NEW_USER = {"email": "nurse@example.org", "full_name": "Amina Nurse", "password": "s3cure-pass-word1",
            "facility": "Hill Health Centre"}


def test_public_sign_up_creates_pending_health_worker(client):
    response = client.post("/api/auth/register", json=NEW_USER)
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "health_worker"
    assert body["status"] == "pending"
    assert body["facility"] == "Hill Health Centre" and body["requested_role"] == "health_worker"
    assert "registration_number" not in body
    assert "password" not in body and "password_hash" not in body


def test_admins_are_emailed_when_someone_signs_up(client):
    admin = create_user(client, Role.ADMIN)
    client.post("/api/auth/register", json=NEW_USER)
    mails = [m.read_text(encoding="utf-8") for m in _outbox(client)]
    assert len(mails) == 1 and admin.email in mails[0]
    assert "Hill Health Centre" in mails[0] and "not verified" in mails[0]
    assert "Requested role: health worker" in mails[0]


def test_pending_account_cannot_sign_in_until_an_admin_approves_it(client):
    created = client.post("/api/auth/register", json=NEW_USER).json()
    sign_in = {"email": NEW_USER["email"], "password": NEW_USER["password"]}
    waiting = client.post("/api/auth/login", json=sign_in)
    assert waiting.status_code == 403
    assert waiting.json()["message"] == "Your account is waiting for administrator approval."

    admin = login(client, create_user(client, Role.ADMIN))
    approved = client.patch(f"/api/admin/users/{created['id']}", headers=admin, json={"status": "approved"})
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert client.post("/api/auth/login", json=sign_in).status_code == 200


def test_rejected_account_cannot_sign_in(client):
    created = client.post("/api/auth/register", json=NEW_USER).json()
    admin = login(client, create_user(client, Role.ADMIN))
    client.patch(f"/api/admin/users/{created['id']}", headers=admin,
                 json={"status": "rejected", "status_reason": "Not on the facility staff list."})
    response = client.post("/api/auth/login", json={"email": NEW_USER["email"], "password": NEW_USER["password"]})
    assert response.status_code == 403
    assert "not approved" in response.json()["message"]


def test_wrong_password_on_a_pending_account_does_not_reveal_that_it_exists(client):
    client.post("/api/auth/register", json=NEW_USER)
    response = client.post("/api/auth/login", json={"email": NEW_USER["email"], "password": "wrong-guess-1"})
    assert response.status_code == 401


def test_sign_up_requires_a_facility(client):
    for missing in ("facility",):
        body = {k: v for k, v in NEW_USER.items() if k != missing}
        assert client.post("/api/auth/register", json=body).status_code == 422


def test_accounts_created_by_an_admin_are_approved_immediately(client):
    admin = login(client, create_user(client, Role.ADMIN))
    response = client.post("/api/admin/users", headers=admin, json={
        "email": "spec@example.org", "full_name": "Dr Okello", "password": PASSWORD, "role": "specialist"})
    assert response.status_code == 201 and response.json()["status"] == "approved"


def test_sign_up_cannot_choose_a_role(client):
    response = client.post("/api/auth/register", json={**NEW_USER, "role": "admin"})
    assert response.status_code == 422  # extra fields are forbidden, so self-promotion is impossible


def test_password_is_stored_as_argon2_hash(client):
    client.post("/api/auth/register", json=NEW_USER)
    for session in client.container.database.session():
        stored = session.query(User).filter_by(email=NEW_USER["email"]).one().password_hash
    assert stored.startswith("$argon2id$")
    assert NEW_USER["password"] not in stored


def test_duplicate_email_is_rejected_case_insensitively(client):
    client.post("/api/auth/register", json=NEW_USER)
    response = client.post("/api/auth/register", json={**NEW_USER, "email": "NURSE@example.org"})
    assert response.status_code == 409


def test_sign_up_validation_errors(client):
    assert client.post("/api/auth/register", json={**NEW_USER, "password": "short"}).status_code == 422
    assert client.post("/api/auth/register", json={**NEW_USER, "email": "not-an-email"}).status_code == 422
    assert client.post("/api/auth/register", json={**NEW_USER, "full_name": ""}).status_code == 422


def test_login_and_me(client):
    user = create_user(client, Role.SPECIALIST)
    response = client.get("/api/auth/me", headers=login(client, user))
    assert response.status_code == 200
    assert response.json()["role"] == "specialist"


def test_wrong_password_and_unknown_email_give_same_error(client):
    user = create_user(client, Role.HEALTH_WORKER)
    wrong = client.post("/api/auth/login", json={"email": user.email, "password": "nope-nope-nope"})
    unknown = client.post("/api/auth/login", json={"email": "ghost@example.org", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["message"] == unknown.json()["message"]


def test_deactivated_user_cannot_log_in(client):
    user = create_user(client, Role.HEALTH_WORKER, active=False)
    response = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 401


def test_missing_or_garbage_token_is_401(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_refresh_rotates_and_old_refresh_token_stops_working(client):
    user = create_user(client, Role.HEALTH_WORKER)
    first = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD}).json()
    second = client.post("/api/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert second.status_code == 200
    new_access = second.json()["access_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_access}"}).status_code == 200
    replay = client.post("/api/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401


def test_access_token_cannot_be_used_as_refresh_token(client):
    user = create_user(client, Role.HEALTH_WORKER)
    tokens = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD}).json()
    assert client.post("/api/auth/refresh", json={"refresh_token": tokens["access_token"]}).status_code == 401


def test_logout_revokes_refresh_token(client):
    user = create_user(client, Role.HEALTH_WORKER)
    tokens = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD}).json()
    assert client.post("/api/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code == 204
    assert client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_repeated_wrong_passwords_are_throttled_even_for_the_right_password(client):
    user = create_user(client, Role.HEALTH_WORKER)
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": user.email, "password": "wrong-guess-1"}).status_code == 401
    blocked = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    assert "Too many failed sign-in attempts" in blocked.json()["message"]


def test_successful_login_resets_the_failure_count(client):
    user = create_user(client, Role.HEALTH_WORKER)
    for _ in range(4):
        client.post("/api/auth/login", json={"email": user.email, "password": "wrong-guess-1"})
    assert client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD}).status_code == 200
    for _ in range(4):
        client.post("/api/auth/login", json={"email": user.email, "password": "wrong-guess-1"})
    assert client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD}).status_code == 200


# ---------- password reset by email ----------

def _outbox(client):
    folder = client.container.settings.email_outbox_dir
    return sorted(folder.glob("*.txt")) if folder.exists() else []


def _reset_token_from_last_email(client) -> str:
    body = _outbox(client)[-1].read_text(encoding="utf-8")
    return re.search(r"/reset-password\?token=([A-Za-z0-9_-]+)", body).group(1)


def test_forgot_password_answers_the_same_for_known_and_unknown_emails(client):
    user = create_user(client, Role.HEALTH_WORKER)
    known = client.post("/api/auth/password/forgot", json={"email": user.email})
    unknown = client.post("/api/auth/password/forgot", json={"email": "ghost@example.org"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(_outbox(client)) == 1  # only the real account gets an email


def test_reset_link_sets_a_new_password_once_and_signs_out_everywhere(client):
    user = create_user(client, Role.HEALTH_WORKER)
    old_session = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD}).json()
    client.post("/api/auth/password/forgot", json={"email": user.email})
    email = _outbox(client)[-1].read_text(encoding="utf-8")
    assert user.email in email and "30 minutes" in email
    token = _reset_token_from_last_email(client)

    assert client.post("/api/auth/password/reset", json={"token": token, "password": "brand-new-pass-1"}).status_code == 204
    assert client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD}).status_code == 401
    assert client.post("/api/auth/login", json={"email": user.email, "password": "brand-new-pass-1"}).status_code == 200
    assert client.post("/api/auth/refresh", json={"refresh_token": old_session["refresh_token"]}).status_code == 401
    reused = client.post("/api/auth/password/reset", json={"token": token, "password": "another-pass-22"})
    assert reused.status_code == 400 and "invalid" in reused.json()["message"]


def test_expired_reset_link_is_refused(client):
    user = create_user(client, Role.HEALTH_WORKER)
    client.post("/api/auth/password/forgot", json={"email": user.email})
    token = _reset_token_from_last_email(client)
    for session in client.container.database.session():
        stored = session.query(PasswordResetToken).one()
        stored.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.commit()
    assert client.post("/api/auth/password/reset", json={"token": token, "password": "brand-new-pass-1"}).status_code == 400


def test_only_a_hash_of_the_reset_token_is_stored(client):
    user = create_user(client, Role.HEALTH_WORKER)
    client.post("/api/auth/password/forgot", json={"email": user.email})
    token = _reset_token_from_last_email(client)
    for session in client.container.database.session():
        stored = session.query(PasswordResetToken).one().token_hash
    assert token not in stored and len(stored) == 64


def test_pending_accounts_get_no_reset_email(client):
    client.post("/api/auth/register", json=NEW_USER)
    assert client.post("/api/auth/password/forgot", json={"email": NEW_USER["email"]}).status_code == 202
    assert _outbox(client) == []


def test_garbage_reset_token_is_refused(client):
    response = client.post("/api/auth/password/reset", json={"token": "x" * 43, "password": "brand-new-pass-1"})
    assert response.status_code == 400


def test_the_person_is_emailed_when_an_admin_approves_or_rejects_them(client):
    admin = login(client, create_user(client, Role.ADMIN))
    approved = client.post("/api/auth/register", json=NEW_USER).json()
    rejected = client.post("/api/auth/register", json={**NEW_USER, "email": "other@example.org"}).json()
    client.patch(f"/api/admin/users/{approved['id']}", headers=admin, json={"status": "approved"})
    client.patch(f"/api/admin/users/{rejected['id']}", headers=admin,
                 json={"status": "rejected", "status_reason": "Registration number not found."})
    mails = [m.read_text(encoding="utf-8") for m in _outbox(client)]
    assert any(NEW_USER["email"] in m and "approved" in m for m in mails)
    assert any("other@example.org" in m and "not approved" in m and "Registration number not found." in m
               for m in mails)


def test_requested_role_grants_nothing_until_an_admin_approves(client):
    created = client.post("/api/auth/register", json={**NEW_USER, "requested_role": "specialist"}).json()
    assert created["requested_role"] == "specialist" and created["role"] == "health_worker"
    sign_in = {"email": NEW_USER["email"], "password": NEW_USER["password"]}
    assert client.post("/api/auth/login", json=sign_in).status_code == 403

    admin = login(client, create_user(client, Role.ADMIN))
    approved = client.patch(f"/api/admin/users/{created['id']}", headers=admin, json={"status": "approved"}).json()
    assert approved["role"] == "specialist"
    token = client.post("/api/auth/login", json=sign_in).json()["access_token"]
    specialist = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/reviews/queue", headers=specialist).status_code == 200
    assert client.get("/api/patients", headers=specialist).status_code == 403


def test_admin_can_approve_with_a_different_role(client):
    created = client.post("/api/auth/register", json={**NEW_USER, "requested_role": "specialist"}).json()
    admin = login(client, create_user(client, Role.ADMIN))
    approved = client.patch(f"/api/admin/users/{created['id']}", headers=admin,
                            json={"status": "approved", "role": "health_worker"}).json()
    assert approved["role"] == "health_worker" and approved["status"] == "approved"


def test_admin_role_cannot_be_requested_and_registration_numbers_are_gone(client):
    assert client.post("/api/auth/register", json={**NEW_USER, "requested_role": "admin"}).status_code == 422
    assert client.post("/api/auth/register", json={**NEW_USER, "registration_number": "NC-1"}).status_code == 422


def test_password_needs_a_letter_and_a_number(client):
    for weak in ("onlyletters", "1234567890"):
        assert client.post("/api/auth/register", json={**NEW_USER, "password": weak}).status_code == 422


def test_sign_ups_are_rate_limited_per_device(client):
    limit = client.container.settings.signup_max_per_window
    codes = [client.post("/api/auth/register", json={**NEW_USER, "email": f"n{i}@example.org"}).status_code
             for i in range(limit + 1)]
    assert codes[:limit] == [201] * limit and codes[-1] == 429


def test_rejecting_needs_a_reason_and_every_decision_is_audited(client):
    created = client.post("/api/auth/register", json=NEW_USER).json()
    admin_user = create_user(client, Role.ADMIN)
    admin = login(client, admin_user)
    url = f"/api/admin/users/{created['id']}"
    assert client.patch(url, headers=admin, json={"status": "rejected"}).status_code == 422
    rejected = client.patch(url, headers=admin, json={"status": "rejected", "status_reason": "Unknown at facility."})
    assert rejected.json()["status_reason"] == "Unknown at facility."
    client.patch(url, headers=admin, json={"status": "approved"})
    for session in client.container.database.session():
        actions = [e.action for e in session.query(AuditEvent).filter_by(actor_id=admin_user.id, entity_id=created["id"])]
    assert actions == ["user.rejected", "user.approved"]
