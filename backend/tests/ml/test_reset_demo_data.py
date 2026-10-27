"""scripts/reset_demo_data.py: only the local SQLite demo file, always with a backup."""
import sys

import pytest

from app.core.config import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from reset_demo_data import local_database, reset  # noqa: E402


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
    backup = reset(database, uploads, run=lambda cmd, **kw: commands.append(cmd))
    assert backup.read_bytes() == b"old data" and not database.exists() and not uploads.exists()
    assert ["alembic", "upgrade", "head"] == commands[0][2:5] and commands[1][1].endswith("seed.py")
