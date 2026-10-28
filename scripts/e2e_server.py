"""Start a throwaway backend for the Playwright end-to-end tests.

Creates a fresh SQLite database (data/e2e.db) with Alembic, seeds one admin and one specialist
from the E2E_* environment variables set by frontend/playwright.config.ts, and serves the API on
port 8001. Never point this at real data: it deletes data/e2e.db and data/e2e-uploads on start.
"""
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def main() -> int:
    DATA.mkdir(exist_ok=True)
    (DATA / "e2e.db").unlink(missing_ok=True)
    shutil.rmtree(DATA / "e2e-uploads", ignore_errors=True)
    shutil.rmtree(DATA / "e2e-outbox", ignore_errors=True)
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{(DATA / 'e2e.db').as_posix()}",
        "UPLOAD_DIR": str(DATA / "e2e-uploads"),
        "EMAIL_OUTBOX_DIR": str(DATA / "e2e-outbox"),
        "JWT_SECRET": secrets.token_hex(32),
        "SIGNUP_MAX_PER_WINDOW": "100",  # every E2E sign-up comes from 127.0.0.1
        "SEED_ADMIN_EMAIL": os.environ["E2E_ADMIN_EMAIL"],
        "SEED_ADMIN_PASSWORD": os.environ["E2E_PASSWORD"],
        "SEED_SPECIALIST_EMAIL": os.environ["E2E_SPECIALIST_EMAIL"],
        "SEED_SPECIALIST_PASSWORD": os.environ["E2E_PASSWORD"],
        "SEED_HEALTH_WORKER_EMAIL": os.environ["E2E_SEEDED_WORKER_EMAIL"],
        "SEED_HEALTH_WORKER_PASSWORD": os.environ["E2E_PASSWORD"],
    }
    python = sys.executable
    subprocess.run([python, "-m", "alembic", "upgrade", "head"], cwd=ROOT / "backend", env=env, check=True)
    subprocess.run([python, str(ROOT / "scripts" / "seed.py")], env=env, check=True)
    return subprocess.call([python, "-m", "uvicorn", "app.main:app", "--port", "8001"], cwd=ROOT / "backend", env=env)


if __name__ == "__main__":
    sys.exit(main())
