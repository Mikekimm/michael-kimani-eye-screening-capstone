"""Seed demo accounts and 5 synthetic patients. Safe to run more than once.

Credentials come only from environment variables / .env (SEED_*), never from code.
Patients are synthetic pseudonymous codes with no real-world identity.

Usage (from the repo root, after `alembic upgrade head`):
    .venv\\Scripts\\python scripts\\seed.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from pydantic_settings import BaseSettings, SettingsConfigDict  # noqa: E402

from app.core.config import BACKEND_ROOT, REPO_ROOT, DatabaseSettings  # noqa: E402
from app.core.database import Database  # noqa: E402
from app.core.security import PasswordHasher  # noqa: E402
from app.models import Patient, User  # noqa: E402
from app.models.enums import Role, Sex  # noqa: E402
from app.repositories import PatientRepository, UserRepository  # noqa: E402


class SeedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"), extra="ignore")
    seed_admin_email: str
    seed_admin_password: str
    seed_specialist_email: str
    seed_specialist_password: str
    seed_health_worker_email: str
    seed_health_worker_password: str


SYNTHETIC_PATIENTS = [
    ("DEMO-0001", 1961, Sex.FEMALE, True),
    ("DEMO-0002", 1975, Sex.MALE, True),
    ("DEMO-0003", 1958, Sex.FEMALE, False),
    ("DEMO-0004", 1989, Sex.MALE, True),
    ("DEMO-0005", 1970, Sex.OTHER, None),
]


def main() -> int:
    seed = SeedSettings()
    if "change-me" in {seed.seed_admin_password, seed.seed_specialist_password, seed.seed_health_worker_password}:
        print("Seed passwords are still placeholders. Run scripts/init_env.py or edit .env first.")
        return 1
    hasher = PasswordHasher()
    database = Database(DatabaseSettings().database_url)
    for session in database.session():
        users = UserRepository(session)
        accounts = {}
        for role, email, password, name in [
            (Role.ADMIN, seed.seed_admin_email, seed.seed_admin_password, "Demo Administrator"),
            (Role.SPECIALIST, seed.seed_specialist_email, seed.seed_specialist_password, "Demo Specialist"),
            (Role.HEALTH_WORKER, seed.seed_health_worker_email, seed.seed_health_worker_password, "Demo Health Worker"),
        ]:
            user = users.by_email(email)
            if user is None:
                user = users.add(User(email=email.lower(), full_name=name, role=role,
                                      password_hash=hasher.hash(password)))
                print(f"created {role.value}: {email}")
            else:
                print(f"exists  {role.value}: {email}")
            accounts[role] = user

        patients = PatientRepository(session)
        for code, year, sex, diabetic in SYNTHETIC_PATIENTS:
            if patients.by_code(code) is None:
                patients.add(Patient(code=code, year_of_birth=year, sex=sex, has_diabetes=diabetic,
                                     created_by_id=accounts[Role.HEALTH_WORKER].id))
                print(f"created patient {code}")
        session.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
