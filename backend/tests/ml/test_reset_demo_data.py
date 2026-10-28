"""scripts/reset_demo_data.py: only the local SQLite demo file, always with a backup."""
import sqlite3
import sys

import pytest

from app.core.config import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from reset_demo_data import carry_over_accounts, local_database, reset  # noqa: E402


@pytest.mark.parametrize("url", ["postgresql+psycopg://u:p@db:5432/screening", "sqlite:///C:/elsewhere/app.db"])
def test_refuses_anything_but_the_local_demo_file(url):
    with pytest.raises(SystemExit):
        local_database(url)


def test_accepts_the_local_demo_file():
    assert local_database(f"sqlite:///{(REPO_ROOT / 'data' / 'app.db').as_posix()}") == (REPO_ROOT / "data" / "app.db").resolve()


def test_backs_up_then_removes_database_and_photos_before_migrating_and_seeding(tmp_path):
    database, uploads = tmp_path / "app.db", tmp_path / "uploads"
    database.write_bytes(b"old data")
    uploads.mkdir()
    (uploads / "photo.png").write_bytes(b"x")
    commands = []
    backup, kept = reset(database, uploads, run=lambda cmd, **kw: commands.append(cmd), keep_accounts=False)
    assert backup.read_bytes() == b"old data" and not database.exists() and not uploads.exists() and kept == []
    assert ["alembic", "upgrade", "head"] == commands[0][2:5] and commands[1][1].endswith("seed.py")


def _users_db(path, rows):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE users (id TEXT, email TEXT, full_name TEXT, password_hash TEXT, role TEXT, status TEXT)")
    db.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", rows)
    db.commit()
    db.close()


def test_approved_own_accounts_survive_a_reset_unchanged(tmp_path):
    """A reset once deleted a real approved account; approved non-demo accounts are now carried over."""
    backup, database = tmp_path / "old.db", tmp_path / "new.db"
    _users_db(backup, [("1", "admin@example.org", "Admin", "h-admin", "admin", "approved"),
                       ("2", "me@example.org", "Me", "h-me", "health_worker", "approved"),
                       ("3", "stranger@example.org", "S", "h-s", "health_worker", "pending")])
    _users_db(database, [("9", "admin@example.org", "Admin", "h-new", "admin", "approved")])
    assert carry_over_accounts(backup, database) == ["me@example.org"]
    rows = sqlite3.connect(database).execute("SELECT id, email, password_hash, status FROM users ORDER BY id").fetchall()
    assert rows == [("2", "me@example.org", "h-me", "approved"), ("9", "admin@example.org", "h-new", "approved")]
