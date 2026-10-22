"""Navigation, badge and attention presentation follow deterministic application state."""

import importlib
from datetime import date
from pathlib import Path

import pytest

from blastbridge.product import store
from blastbridge.product.agent import IntakeResult, ProviderError, ScriptedProvider
from blastbridge.product.analyst import AnalystRun
from blastbridge.product.analyst_tools import SymptomProposal
from blastbridge.product.evidence import Signal
from blastbridge.product.image_intake import load_image_replay
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


def test_fresh_analysis_uses_demo_anchor_and_preserves_presenter_date(ui):
    assert ui.analysis_date() == date(2026, 10, 19)
    assert ui.analysis_date(date(2026, 10, 21)) == date(2026, 10, 21)


def test_presentation_mode_forces_suggested_replay_even_with_live_key(ui, monkeypatch):
    from blastbridge.product import anthropic_provider

    monkeypatch.setenv("ANTHROPIC_API_KEY", "fictional-test-key")
    monkeypatch.setenv("BLASTBRIDGE_DEMO_MODE", "replay")
    monkeypatch.setattr(anthropic_provider, "live_available", lambda: True)
    assert ui.use_suggested_replay(True, anthropic_provider.live_available())
    assert not ui.use_suggested_replay(False, anthropic_provider.live_available())
    monkeypatch.delenv("BLASTBRIDGE_DEMO_MODE")
    assert not ui.use_suggested_replay(True, anthropic_provider.live_available())


def test_suggested_live_failure_chooses_recorded_response(ui):
    provider = ScriptedProvider([])
    recorded = AnalystRun(date(2026, 10, 19), "replay", grounded=True)
    calls = []

    def live():
        provider.complete(system="", messages=[], tools=[], output_schema=None, allow_tools=False)
        raise AssertionError("The scripted provider must fail")

    def replay():
        calls.append("replay")
        return recorded

    result, fallback = ui.with_demo_fallback(live, replay)
    assert result is recorded and fallback
    assert calls == ["replay"]
    ungrounded = AnalystRun(date(2026, 10, 19), "live", grounded=False)
    assert ui.with_demo_fallback(lambda: ungrounded, replay) == (ungrounded, False)
    grounded = AnalystRun(date(2026, 10, 19), "live", grounded=True)
    assert ui.with_demo_fallback(lambda: grounded, replay) == (grounded, False)
    assert calls == ["replay"]
    failed = AnalystRun(date(2026, 10, 19), "live", provider_error=True)
    assert ui.with_demo_fallback(lambda: failed, replay) == (recorded, True)


def test_evidence_display_uses_human_names_and_labels(ui):
    names = {"FIC-001": "Avery Kestrel", "FIC-002": "Jordan Pike"}
    people = ui.signal_display(Signal("participant_overlap", tuple(names)), names)
    context = ui.signal_display(
        Signal("same_context", ("weapon_firing", "routine_home_station")), names
    )
    assert people == "Shared participants: Avery Kestrel, Jordan Pike"
    assert context == "Same activity and context: Weapon firing · Routine home station"
    weapon = ui.evidence_display("weapon_system_id", "m142-himars", {"m142-himars": "M142 HIMARS"})
    assert weapon == "M142 HIMARS"
    assert ui.source_label(0, date(2026, 10, 17)) == "Range record A · 17 Oct 2026"
    role = ui.evidence_display("member:FIC-001", ("Launcher 1", "chief"), {})
    assert role == "Launcher 1 · Launcher chief"
    text = " ".join((people, context, weapon, role, ui.source_label(1, date(2026, 10, 17))))
    for internal in ("FIC-", "EVT-", "weapon_firing", "routine_home_station", "m142-himars"):
        assert internal not in text


def test_presentation_mode_chooses_digest_matched_board_replay_with_live_available(ui, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "examples/fictional/intake/demo_range_board.png"
    data = path.read_bytes()
    load_image_replay(data)
    monkeypatch.setenv("BLASTBRIDGE_DEMO_MODE", "replay")
    recorded = IntakeResult(narrative="Fictional board", mode="replay")

    def live():
        raise AssertionError("Presentation mode must not call live AI for the demo board")

    result, fallback = ui.image_with_demo_fallback(live, lambda: recorded, live_available=True)
    assert result is recorded and not fallback


def test_demo_board_live_failure_uses_replay_and_sets_fallback_flag(ui, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "examples/fictional/intake/demo_range_board.png"
    data = path.read_bytes()
    load_image_replay(data)
    monkeypatch.delenv("BLASTBRIDGE_DEMO_MODE", raising=False)
    provider = ScriptedProvider([])
    recorded = IntakeResult(narrative="Fictional board", mode="replay")

    def live():
        provider.complete(system="", messages=[], tools=[], output_schema=None, allow_tools=False)
        raise AssertionError("The scripted provider must fail")

    result, fallback = ui.image_with_demo_fallback(live, lambda: recorded, live_available=True)
    assert result is recorded and fallback
    failed = IntakeResult(
        narrative="", mode="live", error="Provider unavailable", provider_error=True
    )
    assert ui.image_with_demo_fallback(lambda: failed, lambda: recorded, live_available=True) == (
        recorded,
        True,
    )


def test_non_demo_image_never_uses_replay_even_in_presentation_mode(ui, monkeypatch):
    with pytest.raises(ValueError, match="Use manual entry"):
        load_image_replay(b"not the demo board")
    monkeypatch.setenv("BLASTBRIDGE_DEMO_MODE", "replay")

    def live():
        raise ProviderError("Live provider unavailable")

    with pytest.raises(ProviderError, match="Live provider unavailable"):
        ui.image_with_demo_fallback(live, None, live_available=True)
    failed = IntakeResult(narrative="", mode="live", error="Provider unavailable")
    assert ui.image_with_demo_fallback(lambda: failed, None, live_available=True) == (failed, False)


@pytest.mark.parametrize("error", [ValueError("content error"), AssertionError("bug")])
def test_fallback_does_not_hide_non_provider_exceptions(ui, monkeypatch, error):
    monkeypatch.delenv("BLASTBRIDGE_DEMO_MODE", raising=False)

    def live():
        raise error

    def replay():
        raise AssertionError("Replay must not be called")

    with pytest.raises(type(error), match=str(error)):
        ui.with_demo_fallback(live, replay)
    with pytest.raises(type(error), match=str(error)):
        ui.image_with_demo_fallback(live, replay, live_available=True)


@pytest.mark.parametrize("name,index", [("log_event", 0), ("log_event", 1), ("attention", 1)])
def test_multistep_requests_never_fall_back(ui, name, index):
    def live():
        raise ProviderError("Provider unavailable")

    with pytest.raises(ProviderError):
        ui.with_demo_fallback(live, live, replay_name=name, replay_index=index)


def test_image_content_error_is_not_replaced_by_replay(ui, monkeypatch):
    monkeypatch.delenv("BLASTBRIDGE_DEMO_MODE", raising=False)
    failed = IntakeResult(narrative="", mode="live", error="The record isn't clear enough")
    recorded = IntakeResult(narrative="Fictional board", mode="replay")
    assert ui.image_with_demo_fallback(lambda: failed, lambda: recorded, live_available=True) == (
        failed,
        False,
    )
