"""Reset the LOCAL demo database: every patient, screening, photo and test account goes; the demo accounts
and synthetic patients are seeded again. For recording the video or a fresh demo, never for real data.

Review history is append-only by design (the code never deletes review events), so this script does not
delete rows: it backs up the SQLite file, removes it and the stored photos, re-runs the Alembic migrations
and the seed script. It refuses to run against anything but the SQLite file under data/.

Usage (repo root):  .venv\Scripts\python scripts\reset_demo_data.py --yes
"""
import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings  # noqa: E402


def local_database(database_url: str) -> Path:
    """The SQLite file under data/, or SystemExit for anything else (PostgreSQL, another folder)."""
    prefix = "sqlite:///"
    path = Path(database_url.removeprefix(prefix)).resolve() if database_url.startswith(prefix) else None
    if path is None or path.parent != (ROOT / "data").resolve():
        raise SystemExit(f"Refusing to reset {database_url!r}: only the local SQLite file under data/ can be reset.")
    return path


def reset(database: Path, uploads: Path, run=subprocess.run) -> Path | None:
    """Backs up and removes the database and photos, then migrates and seeds. Returns the backup path."""
    backup = None
    if database.exists():
        backup = database.with_name(f"{database.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(database, backup)
        database.unlink()
    shutil.rmtree(uploads, ignore_errors=True)
    run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT / "backend", check=True)
    run([sys.executable, str(ROOT / "scripts" / "seed.py")], check=True)
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="confirm: delete all local demo data")
    args = parser.parse_args()
    settings = Settings()
    database = local_database(settings.database_url)
    if not args.yes:
        print(f"This deletes every patient, screening and photo in {database}. Re-run with --yes to confirm.")
        return 1
    backup = reset(database, settings.upload_dir)
    print(f"Reset done. Backup of the old database: {backup}" if backup else "Reset done (there was no database).")
    print("Stop and restart the API so it opens the new database.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
