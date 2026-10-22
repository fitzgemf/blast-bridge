"""Navigation, badge and attention presentation follow deterministic application state."""

import importlib
from datetime import date
from pathlib import Path

import pytest

from blastbridge.product import store
from blastbridge.product.agent import IntakeResult
from blastbridge.product.analyst_tools import SymptomProposal
from blastbridge.product.models import EventStatus
from blastbridge.product.readiness import ReadinessStatus
from blastbridge.product.seed import DEMO_EVENTS, DEMO_PEOPLE
from blastbridge.product.symptoms import DangerSign, Symptom


@pytest.fixture
def ui(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "app"))
    return importlib.import_module("ui")


def test_navigation_sections_cover_visible_and_nested_pages(ui):
    expected = {
        "dashboard": "dashboard",
        "new": "dashboard",
        "history": "history",
        "person": "history",
        "followup": "history",
        "inbox": "inbox",
        "review": "inbox",
    }
    assert {page: ui.navigation_section(page) for page in expected} == expected
    assert ui.navigation_section("unknown") is None


def test_review_badge_counts_only_pending_training_drafts(tmp_path, ui):
    conn = store.connect(tmp_path / "badge.sqlite")
    try:
        store.init_db(conn)
        store.seed_people(conn, DEMO_PEOPLE)
        pending = store.list_events(conn, EventStatus.DRAFT, limit=-1)
        assert ui.review_badge(len(pending)) == "Review"
        event_ids = [store.save_draft(conn, DEMO_EVENTS[0][1]) for _ in range(3)]
        pending = store.list_events(conn, EventStatus.DRAFT, limit=-1)
        assert ui.review_badge(len(pending)) == "Review 3"
        assert store.approve_event(conn, event_ids[0], 1)
        store.reject_event(conn, event_ids[1], 1)
        assert len(store.list_events(conn, EventStatus.APPROVED, limit=-1)) == 1
        assert len(store.list_events(conn, EventStatus.REJECTED, limit=-1)) == 1
        pending = store.list_events(conn, EventStatus.DRAFT, limit=-1)
        assert ui.review_badge(len(pending)) == "Review 1"
        assert store.approve_event(conn, event_ids[2], 1)
        pending = store.list_events(conn, EventStatus.DRAFT, limit=-1)
        assert ui.review_badge(len(pending)) == "Review"
    finally:
        conn.close()


def test_attention_tones_come_only_from_deterministic_readiness_status(ui):
    assert ui.attention_tone(ReadinessStatus.URGENT_EVALUATION) == "urgent"
    assert ui.attention_tone(ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED) == "followup"
    assert ui.attention_tone(ReadinessStatus.REVIEW_PRIORITY) == "review"
    assert ui.attention_tone(ReadinessStatus.ROUTINE_MONITORING) == "routine"


def test_ai_symptom_prefill_never_checks_danger_signs(ui):
    proposal = SymptomProposal(
        person_id="FIC-002",
        report_date=date(2026, 10, 19),
        symptoms=(Symptom.HEADACHES,),
        danger_signs=tuple(DangerSign),
    )
    values, labels = ui.symptom_prefill(proposal)
    assert values["sym_w_date"] == proposal.report_date
    assert values["sym_w_s_headaches"] is True
    assert "Report date" in labels and "Symptoms" in labels
    assert not any(key.startswith("sym_w_d_") for key in values)
    assert "Danger signs" not in labels
    assert proposal.danger_signs == tuple(DangerSign)


def test_intake_results_are_selected_only_for_their_tagged_entry_mode(ui):
    result = IntakeResult(narrative="A fictional record", mode="replay")
    assert ui.intake_result_for_mode(result, "image", "image") is result
    assert ui.intake_result_for_mode(result, "text", "text") is result
    assert ui.intake_result_for_mode(result, "image", "text") is None
    assert ui.intake_result_for_mode(result, "text", "image") is None
    assert ui.intake_result_for_mode(result, None, "text") is None
    assert ui.intake_result_for_mode(None, "image", "image") is None
