"""Role-based access control is enforced by the backend on every route."""
import pytest

from app.models.enums import Role

from .conftest import auth_headers, register_patient, upload

# (method, path, body) for every protected route; ids are placeholders, RBAC is checked first.
ROUTES = {
    "patients.list": ("get", "/api/patients", None),
    "patients.create": ("post", "/api/patients", {}),
    "screenings.list": ("get", "/api/screenings", None),
    "reviews.queue": ("get", "/api/reviews/queue", None),
    "reviews.create": ("post", "/api/reviews/x", {"action": "comment", "note": "hi"}),
    "sync.push": ("post", "/api/sync/push", {"patients": []}),
    "sync.pull": ("get", "/api/sync/pull", None),
    "admin.users": ("get", "/api/admin/users", None),
    "admin.update": ("patch", "/api/admin/users/x", {"role": "admin"}),
    "admin.analytics": ("get", "/api/admin/analytics", None),
    "admin.create_user": ("post", "/api/admin/users", {"email": "s@example.org", "full_name": "Sp",
                                                       "password": "pass-word-1", "role": "specialist"}),
    "screenings.ask": ("post", "/api/screenings/x/ask-specialist", {"question": "Please check"}),
    "screenings.discard": ("post", "/api/screenings/x/discard", {"reason": "wrong photo"}),
}
ALLOWED = {
    Role.HEALTH_WORKER: {"patients.list", "patients.create", "screenings.list", "screenings.ask",
                         "screenings.discard", "sync.push", "sync.pull"},
    Role.SPECIALIST: {"reviews.queue", "reviews.create"},
    Role.ADMIN: {"admin.users", "admin.update", "admin.analytics", "admin.create_user"},
}


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("route", list(ROUTES))
def test_role_matrix(client, role, route):
    _, headers = auth_headers(client, role)
    method, path, body = ROUTES[route]
    response = getattr(client, method)(path, headers=headers, **({"json": body} if body is not None else {}))
    if route in ALLOWED[role]:
        assert response.status_code not in (401, 403), response.text
    else:
        assert response.status_code == 403, f"{role} should be forbidden from {route}"


@pytest.mark.parametrize("route", list(ROUTES))
def test_every_protected_route_requires_login(client, route):
    method, path, body = ROUTES[route]
    response = getattr(client, method)(path, **({"json": body} if body is not None else {}))
    assert response.status_code == 401


def test_models_endpoint_requires_login(client):
    assert client.get("/api/models").status_code == 401


def test_health_worker_cannot_promote_themselves(client):
    user, headers = auth_headers(client, Role.HEALTH_WORKER)
    response = client.patch(f"/api/admin/users/{user.id}", headers=headers, json={"role": "admin"})
    assert response.status_code == 403
    assert client.get("/api/auth/me", headers=headers).json()["role"] == "health_worker"


def test_admin_can_change_roles_but_not_their_own(client):
    admin, admin_headers = auth_headers(client, Role.ADMIN)
    worker, _ = auth_headers(client, Role.HEALTH_WORKER)
    promoted = client.patch(f"/api/admin/users/{worker.id}", headers=admin_headers, json={"role": "specialist"})
    assert promoted.status_code == 200 and promoted.json()["role"] == "specialist"
    self_change = client.patch(f"/api/admin/users/{admin.id}", headers=admin_headers, json={"role": "health_worker"})
    assert self_change.status_code == 403


def test_health_workers_cannot_see_each_others_patients(client):
    _, owner = auth_headers(client, Role.HEALTH_WORKER)
    _, other = auth_headers(client, Role.HEALTH_WORKER)
    patient = register_patient(client, owner)
    assert client.get(f"/api/patients/{patient['id']}", headers=other).status_code == 404
    assert client.get("/api/patients", headers=other).json() == []


def test_specialist_cannot_open_unreferred_screening(stub_client):
    from .conftest import FixedScoreModel
    FixedScoreModel.score = 0.01  # confidently negative -> no referral
    _, worker = auth_headers(stub_client, Role.HEALTH_WORKER)
    _, specialist = auth_headers(stub_client, Role.SPECIALIST)
    patient = register_patient(stub_client, worker)
    screening = upload(stub_client, worker, patient["id"]).json()
    assert screening["status"] == "completed"
    assert stub_client.get(f"/api/screenings/{screening['id']}", headers=specialist).status_code == 404
