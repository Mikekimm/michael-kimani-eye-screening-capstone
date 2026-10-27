"""Fixtures for API tests: a throwaway database, real or test-double models, and users per role.

Each test gets a fresh SQLite file by default. Setting TEST_DATABASE_URL (used by CI) runs the same
tests against PostgreSQL instead; every table is dropped and recreated before each test.
"""
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import REPO_ROOT, Settings
from app.core.database import Base
from app.main import build_container, create_app
from app.ml.condition_model import ConditionModel
from app.ml.model_card import ModelCard
from app.ml.registry import ModelRegistry, ModelStatus
from app.models import User
from app.models.enums import Role

from ..conftest import encode, make_fundus_like

PASSWORD = "correct-horse-42"


class FixedScoreModel(ConditionModel):
    """TEST DOUBLE ONLY. Returns a score chosen by the test so referral and review paths are
    deterministic. Never used outside the test suite; real screenings use TFLiteConditionModel."""

    score = 0.9

    def predict_proba(self, batch):
        return type(self).score


class FixedScoreRegistry(ModelRegistry):
    """Registers FixedScoreModel for 'dr' using the real DR model card (glaucoma/cataract stay unavailable)."""

    def __init__(self, conditions):
        super().__init__(conditions)
        card = ModelCard.load(REPO_ROOT / "models" / "dr" / "model_card.json")
        self._models["dr"] = FixedScoreModel(card)
        self._statuses["dr"] = ModelStatus("dr", True, "test double", card)


def _settings(tmp_path: Path) -> Settings:
    database_url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    return Settings(jwt_secret=secrets.token_hex(32), database_url=database_url, upload_dir=tmp_path / "uploads",
                    email_outbox_dir=tmp_path / "outbox")


@pytest.fixture(scope="session")
def real_registry():
    """The real, checksum-verified model registry (loaded once per test session)."""
    return ModelRegistry(("dr", "glaucoma", "cataract")).discover(REPO_ROOT / "models")


def _make_client(tmp_path, registry):
    container = build_container(_settings(tmp_path), registry=registry)
    engine = container.database.engine
    if engine.dialect.name != "sqlite":
        Base.metadata.drop_all(engine)  # shared PostgreSQL test database: start every test clean
    Base.metadata.create_all(engine)  # tests only; the app relies on Alembic
    client = TestClient(create_app(container))
    client.container = container
    return client


@pytest.fixture
def client(tmp_path, real_registry):
    with _make_client(tmp_path, real_registry) as c:
        yield c
    c.container.database.engine.dispose()


@pytest.fixture
def stub_client(tmp_path):
    """Client whose DR model is the FixedScoreModel test double."""
    FixedScoreModel.score = 0.9
    with _make_client(tmp_path, FixedScoreRegistry(("dr", "glaucoma", "cataract"))) as c:
        yield c
    c.container.database.engine.dispose()


def create_user(client, role: Role, email: str | None = None, active: bool = True) -> User:
    container = client.container
    for session in container.database.session():
        user = User(email=email or f"{role.value}-{uuid.uuid4().hex[:6]}@example.org",
                    full_name=f"Test {role.value}", password_hash=container.hasher.hash(PASSWORD),
                    role=role, is_active=active)
        session.add(user)
        session.commit()
    return user


def login(client, user: User) -> dict:
    response = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def auth_headers(client, role: Role) -> tuple[User, dict]:
    user = create_user(client, role)
    return user, login(client, user)


def register_patient(client, headers, code: str | None = None) -> dict:
    """Registers a patient; the server generates the code unless a device-generated ``code`` is given."""
    body = {"year_of_birth": 1970, "sex": "female", "has_diabetes": True} | ({"code": code} if code else {})
    response = client.post("/api/patients", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def fundus_jpeg(seed: int = 0) -> bytes:
    """Synthetic fundus-like fixture (a textured disc). Exercises code paths; it is not a retinal photo."""
    return encode(make_fundus_like(seed=seed), "JPEG")


def upload(client, headers, patient_id: str, *, data: bytes | None = None, client_uuid: str | None = None,
           eye: str = "left", content_type: str = "image/jpeg", captured_at: datetime | None = None,
           attempt: int | None = None, consent: bool = True):
    extra = {"X-Sync-Attempt": str(attempt)} if attempt else {}
    return client.post(
        "/api/screenings", headers={**headers, **extra},
        files={"image": ("eye.jpg", data if data is not None else fundus_jpeg(), content_type)},
        data={"patient_id": patient_id, "eye": eye, "client_uuid": client_uuid or str(uuid.uuid4()),
              "captured_at": (captured_at or datetime.now(timezone.utc)).isoformat(),
              "patient_consent": "true" if consent else "false"},
    )
