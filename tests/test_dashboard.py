"""Smoke test: both dashboard pages render without an exception (headless, real bundled data)."""
from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")
ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("page", ["app.py", "pages/2_Volatility_Selection.py", "pages/3_Live_Market.py"])
def test_page_renders(page, monkeypatch):
    monkeypatch.chdir(ROOT)
    at = st_testing.AppTest.from_file(str(ROOT / page), default_timeout=180).run()
    assert not at.exception, [e.message for e in at.exception]
