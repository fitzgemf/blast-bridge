"""Regression coverage for the app's analyst evidence wiring."""

from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_app_analyst_exposes_draft_and_approved_source_records(tmp_path, monkeypatch):
    monkeypatch.setenv("BLASTBRIDGE_DB", str(tmp_path / "app.sqlite"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.syspath_prepend(str(ROOT / "app"))
    at = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=60)
    at.session_state["analysis_as_of"] = date(2026, 10, 19)

    at.run()
    assert not at.exception
    button = next(
        button for button in at.button if button.label == "Find possible duplicate records"
    )
    button.click().run()

    assert not at.exception
    assert "EVT-DEMO-S1+EVT-DEMO-S2" in at.session_state["reconstructions"]
