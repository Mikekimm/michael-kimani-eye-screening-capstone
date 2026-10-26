"""Authentication: sign-up, hashing, login, token refresh/rotation, logout, validation errors."""
from app.models import User
from app.models.enums import Role

from .conftest import PASSWORD, create_user, login

NEW_USER = {"email": "nurse@example.org", "full_name": "Amina Nurse", "password": "s3cure-pass-word"}


def test_public_sign_up_creates_health_worker(client):
    response = client.post("/api/auth/register", json=NEW_USER)
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "health_worker"
    assert "password" not in body and "password_hash" not in body


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
