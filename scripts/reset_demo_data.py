"""Reset the LOCAL demo database: every patient, screening and photo goes; the demo accounts and synthetic
patients are seeded again. For recording the video or a fresh demo, never for real data.

Approved user accounts that are not demo accounts (for example your own) are carried over unchanged, with
their password hash, role and facility, so you can still sign in. Pending and rejected sign-up requests are
removed. Use --drop-accounts to remove every account except the seeded demo ones.

Review history is append-only by design (the code never deletes review events), so this script does not
delete rows: it backs up the SQLite file, removes it and the stored photos, re-runs the Alembic migrations
and the seed script. It refuses to run against anything but the SQLite file under data/.

Usage (repo root):  .venv\Scripts\python scripts\reset_demo_data.py --yes
"""
import argparse
import shutil
import sqlite3
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


def carry_over_accounts(backup: Path, database: Path) -> list[str]:
    """Copies approved accounts from the backup that the new database does not have (by email). Only the
    users table: their old patients and screenings are gone with the rest of the demo data."""
    old, new = sqlite3.connect(backup), sqlite3.connect(database)
    try:
        columns = [row[1] for row in new.execute("PRAGMA table_info(users)")]
        present = {email.lower() for (email,) in new.execute("SELECT email FROM users")}
        rows = old.execute(f"SELECT {', '.join(columns)} FROM users WHERE status = 'approved'").fetchall()
        kept = [row for row in rows if row[columns.index("email")].lower() not in present]
        new.executemany(f"INSERT INTO users ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})", kept)
        new.commit()
        return [row[columns.index("email")] for row in kept]
    finally:
        old.close()
        new.close()


def reset(database: Path, uploads: Path, run=subprocess.run, keep_accounts: bool = True) -> tuple[Path | None, list[str]]:
    """Backs up and removes the database and photos, then migrates, seeds and (by default) carries approved
    accounts over. Returns the backup path and the emails carried over."""
    backup = None
    if database.exists():
        backup = database.with_name(f"{database.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(database, backup)
        database.unlink()
    shutil.rmtree(uploads, ignore_errors=True)
    run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT / "backend", check=True)
    run([sys.executable, str(ROOT / "scripts" / "seed.py")], check=True)
    kept = carry_over_accounts(backup, database) if keep_accounts and backup else []
    return backup, kept


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="confirm: delete all local demo data")
    parser.add_argument("--drop-accounts", action="store_true",
                        help="also remove approved non-demo accounts (by default they are kept)")
    args = parser.parse_args()
    settings = Settings()
    database = local_database(settings.database_url)
    if not args.yes:
        print(f"This deletes every patient, screening and photo in {database}. Re-run with --yes to confirm.")
        return 1
    backup, kept = reset(database, settings.upload_dir, keep_accounts=not args.drop_accounts)
    print(f"Reset done. Backup of the old database: {backup}" if backup else "Reset done (there was no database).")
    print(f"Accounts kept: {', '.join(kept)}" if kept else "No non-demo accounts kept.")
    print("Stop and restart the API so it opens the new database.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
