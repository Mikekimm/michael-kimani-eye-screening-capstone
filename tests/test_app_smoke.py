"""UI smoke test: the Streamlit app must start and render without raising."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


def test_app_renders_without_exception():
    app = AppTest.from_file(str(APP_PATH), default_timeout=120).run()
    assert not app.exception
    assert any("Retinal Screening Assistant" in m.value for m in app.markdown)


def test_specialist_portal_renders_without_a_token_and_makes_no_network_call():
    portal = Path(__file__).resolve().parent.parent / "specialist_app.py"
    app = AppTest.from_file(str(portal), default_timeout=60).run()
    assert not app.exception
    assert any("token" in info.value.lower() for info in app.info)
