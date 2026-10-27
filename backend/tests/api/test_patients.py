"""Patient registration: the app generates every patient code, so codes are unique and never names."""
from app.core import patient_codes
from app.models.enums import Role

from .conftest import auth_headers, register_patient


def test_server_generates_a_valid_code_when_none_is_given(client):
    _, worker = auth_headers(client, Role.HEALTH_WORKER)
    patient = register_patient(client, worker)
    assert patient_codes.is_valid(patient["code"])


def test_every_patient_gets_a_different_code(client):
    _, worker = auth_headers(client, Role.HEALTH_WORKER)
    codes = {register_patient(client, worker)["code"] for _ in range(25)}
    assert len(codes) == 25


def test_a_device_generated_code_is_kept_when_it_is_free(client):
    _, worker = auth_headers(client, Role.HEALTH_WORKER)
    code = patient_codes.generate()
    assert register_patient(client, worker, code=code.lower())["code"] == code


def test_typed_or_mistyped_codes_are_refused(client):
    _, worker = auth_headers(client, Role.HEALTH_WORKER)
    good = patient_codes.generate()
    mistyped = good[:-1] + next(c for c in patient_codes.ALPHABET if c != good[-1])
    for code in ("Jane Doe", "PHC-0042", mistyped):
        response = client.post("/api/patients", headers=worker, json={"code": code})
        assert response.status_code == 422, code


def test_a_taken_device_code_is_replaced_not_duplicated(client):
    _, worker = auth_headers(client, Role.HEALTH_WORKER)
    first = register_patient(client, worker)
    second = register_patient(client, worker, code=first["code"])
    assert second["code"] != first["code"] and patient_codes.is_valid(second["code"])
