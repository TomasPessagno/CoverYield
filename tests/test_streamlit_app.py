"""Smoke test: the Streamlit app renders without errors (no network needed)."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parent.parent / "streamlit_app.py"


def test_app_renders() -> None:
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert at.title[0].value == "ThetaScout"
    assert [b.label for b in at.button] == ["Scan Options", "Find Opportunities"]
