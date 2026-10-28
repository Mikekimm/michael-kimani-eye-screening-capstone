"""Create (or update the password of) a personal administrator account from the local .env.

Put these two lines in .env (git-ignored; never commit them):
    PERSONAL_ADMIN_EMAIL=you@example.org
    PERSONAL_ADMIN_PASSWORD=<a password you use nowhere else>
then run (repo root, backend stopped or running):  .venv\\Scripts\\python scripts\\create_admin.py
The password is never printed. The account is approved and active straight away, and the demo reset
(scripts/reset_demo_data.py) keeps it because it is an approved account.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from pydantic_settings import BaseSettings, SettingsConfigDict  # noqa: E402

from app.core.config import DatabaseSettings  # noqa: E402
from app.core.database import Database  # noqa: E402
from app.core.security import PasswordHasher  # noqa: E402
from app.models import User  # noqa: E402
from app.models.enums import AccountStatus, Role  # noqa: E402
from app.repositories import UserRepository  # noqa: E402


class PersonalAdmin(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    personal_admin_email: str = ""
    personal_admin_password: str = ""


def main() -> int:
    wanted = PersonalAdmin()
    email = wanted.personal_admin_email.strip().lower()
    password = wanted.personal_admin_password
    if not email or len(password) < 8:
        print("Set PERSONAL_ADMIN_EMAIL and PERSONAL_ADMIN_PASSWORD (8+ characters) in .env first.")
        return 1
    hasher = PasswordHasher()
    for session in Database(DatabaseSettings().database_url).session():
        users = UserRepository(session)
        user = users.by_email(email)
        if user is None:
            users.add(User(email=email, full_name="Administrator", role=Role.ADMIN, status=AccountStatus.APPROVED,
                           is_active=True, password_hash=hasher.hash(password)))
            print(f"created admin: {email}")
        else:
            user.role, user.status, user.is_active = Role.ADMIN, AccountStatus.APPROVED, True
            user.password_hash = hasher.hash(password)
            print(f"updated admin (role, approval and password): {email}")
        session.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
