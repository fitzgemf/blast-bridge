"""Recorded sources, deterministic comparison and session-only reconstruction workflows."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from blastbridge.data.catalog import load_weapon_catalog
from blastbridge.models.training_tempo import TrainingContext
from blastbridge.product import store
from blastbridge.product.agent import ScriptedProvider
from blastbridge.product.analyst import (
    AgentContext,
    AgentResponse,
    Conversation,
    ask,
    load_analyst_replay,
    recommendation_action,
    replay_providers,
    validate_response,
)
from blastbridge.product.analyst_tools import (
    TOOL_DEFINITIONS,
    AnalystData,
    EventPairInput,
    ToolSession,
    evidence_fingerprint,
)
from blastbridge.product.calendar_view import DEMO_STORY_DATE
from blastbridge.product.evidence import (
    can_create_draft,
    compare_sources,
    participants,
    possible_shared_events,
    prepare_reconstruction,
    resolve,
    to_draft,
    verification_queue,
)
from blastbridge.product.models import EventStatus, IntakeSource, TrainingEvent, TrainingEventDraft
from blastbridge.product.patterns import fit_pattern_model, load_reference
from blastbridge.product.seed import DEMO_EVENTS, DEMO_PEOPLE, DEMO_SOURCE_DRAFTS, DEMO_SYMPTOMS

ROOT = Path(__file__).resolve().parents[1]
TODAY = DEMO_STORY_DATE


def source_pair(count_a=6, count_b=None):
    sources = [
        TrainingEvent(
            event_id=event_id,
            status=EventStatus.DRAFT,
            intake_source=source,
            revision=1,
            draft=draft,
        )
        for event_id, draft, source in DEMO_SOURCE_DRAFTS
    ]
    result = []
    for source, count in zip(sources, (count_a, count_b), strict=True):
        payload = source.draft.model_dump()
        payload["crews"][0]["physical_event_count"] = count
        result.append(
            source.model_copy(update={"draft": TrainingEventDraft.model_validate(payload)})
        )
    return result


@pytest.fixture
def env(tmp_path):
    conn = store.connect(tmp_path / "evidence.sqlite")
    store.init_db(conn)
    store.seed_people(conn, DEMO_PEOPLE)
    store.seed_demo_events(conn, DEMO_EVENTS)
    store.seed_demo_symptoms(conn, DEMO_SYMPTOMS)
    rows, metadata = load_reference()
    model = fit_pattern_model(rows, metadata)
    catalog = load_weapon_catalog(ROOT / "data/reference/weapons.json")
    data = AnalystData.from_connection(conn, model, catalog)
    context = AgentContext(TODAY, TODAY)
    yield conn, data, context
    conn.close()


def test_demo_is_a_strong_candidate_without_colliding_approved_sources():
    sources = source_pair()
    candidates = possible_shared_events(sources)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_ids == ("EVT-DEMO-S1", "EVT-DEMO-S2")
    assert {signal.name for signal in candidate.signals} == {
        "same_location",
        "same_context",
        "participant_overlap",
    }
    for _, draft in DEMO_EVENTS:
        assert (draft.event_date, draft.weapon_system_id) != (
            sources[0].draft.event_date,
            sources[0].draft.weapon_system_id,
        )


def test_weak_signal_and_contradictory_locations_do_not_group():
    a, b = source_pair()
    payload = b.draft.model_dump()
    payload.update(location_unit=None, training_context=TrainingContext.ANNUAL_TRAINING)
    weak = b.model_copy(update={"draft": TrainingEventDraft.model_validate(payload)})
    assert possible_shared_events([a, weak]) == []
    payload["location_unit"] = "Another known range"
    payload["training_context"] = a.draft.training_context
    blocked = b.model_copy(update={"draft": TrainingEventDraft.model_validate(payload)})
    assert possible_shared_events([a, blocked]) == []


def test_disjoint_crews_with_different_known_counts_block_candidates():
    a, b = source_pair(6, 8)
    payload = b.draft.model_dump()
    payload["crews"] = [payload["crews"][1]]
    payload["crews"][0].update(crew_name="Launcher 1", physical_event_count=8)
    b = b.model_copy(update={"draft": TrainingEventDraft.model_validate(payload)})
    assert possible_shared_events([a, b]) == []


@pytest.mark.parametrize(
    "a,b,state,value",
    [
        (6, 6, "AGREED", 6),
        (6, None, "COMPLEMENTARY", 6),
        (None, 6, "COMPLEMENTARY", 6),
        (None, None, "UNKNOWN", None),
    ],
)
def test_counts_agree_complement_or_remain_unknown(a, b, state, value):
    sources = source_pair(a, b)
    proposal = prepare_reconstruction(compare_sources(*sources))
    count = next(item for item in proposal.fields if item.field == "count:Launcher 1")
    assert count.state == state and count.value == value
    draft = to_draft(proposal)
    assert draft.crews[0].physical_event_count == value
    assert draft.crews[1].physical_event_count is None
    assert draft.physical_event_count is None
    assert draft.participant_count == 6
    assert can_create_draft(proposal, sources)


def test_conflicting_count_needs_human_choice_and_keeps_conflicting_refs():
    sources = source_pair(6, 8)
    proposal = prepare_reconstruction(compare_sources(*sources))
    item = next(item for item in proposal.fields if item.field == "count:Launcher 1")
    assert item.state == "UNRESOLVED" and item.value is None
    assert not can_create_draft(proposal, sources)
    with pytest.raises(ValueError):
        to_draft(proposal)
    with pytest.raises(ValueError):
        resolve(proposal, item.field, "average")
    resolved = resolve(proposal, item.field, sources[0].event_id)
    changed = next(part for part in resolved.fields if part.field == item.field)
    assert changed.state == "HUMAN_RESOLVED" and changed.value == 6
    assert changed.conflicting_source_ids == item.conflicting_source_ids
    assert changed.evidence_refs == item.evidence_refs
    assert proposal.fields != resolved.fields
    assert to_draft(resolved).crews[0].physical_event_count == 6
    unknown = resolve(proposal, item.field, "unknown")
    assert to_draft(unknown).crews[0].physical_event_count is None


def test_participant_role_and_crew_conflicts_are_explicit():
    a, b = source_pair()
    payload = b.draft.model_dump()
    payload["crews"][0]["members"][0]["position"] = "driver"
    b = b.model_copy(update={"draft": TrainingEventDraft.model_validate(payload)})
    comparison = compare_sources(a, b)
    row = next(item for item in comparison.rows if item.field == "member:FIC-001")
    assert row.state == "CONFLICTS" and row.finding_code == "CONFLICTING_PARTICIPANT_ROLE"
    proposal = prepare_reconstruction(comparison)
    assert not can_create_draft(proposal, [a, b])
    assert comparison.rows[-1].state == "UNSUPPORTED"


def test_verification_queue_has_workflow_order_and_excludes_future_and_rejected():
    sources = source_pair(6, 8)
    findings = verification_queue(sources, TODAY)
    assert [item.code for item in findings] == [
        "CONFLICTING_ACTIVITY_COUNT",
        "POSSIBLE_SHARED_EVENT",
    ]
    assert (
        verification_queue(
            [source.model_copy(update={"status": EventStatus.REJECTED}) for source in sources],
            TODAY,
        )
        == []
    )
    assert verification_queue(sources, sources[0].draft.event_date - timedelta(days=1)) == []


def test_proposals_and_demo_drafts_do_not_change_approved_analytics(env):
    conn, data, context = env
    history = {
        person.person_id: list(data.member_history(person.person_id)) for person in data.people
    }
    fingerprints = {
        person.person_id: evidence_fingerprint(person.person_id, context, data)
        for person in data.people
    }
    before = ToolSession(context, data, ScriptedProvider([]), Conversation("before"), {})
    attention = before.execute("get_attention_queue", {})[0]
    assert store.seed_demo_drafts(conn, DEMO_SOURCE_DRAFTS) == 2
    assert store.seed_demo_drafts(conn, DEMO_SOURCE_DRAFTS) == 0
    proposals = {}
    session = ToolSession(
        context, data, ScriptedProvider([]), Conversation("prepare"), {}, reconstructions=proposals
    )
    assert not session.execute("find_possible_shared_events", {})[1]
    args = {"event_ids": ["EVT-DEMO-S1", "EVT-DEMO-S2"]}
    assert not session.execute("prepare_reconstruction_proposal", args)[1]
    proposal = session.reconstruction
    assert to_draft(proposal).crews[0].physical_event_count == 6
    assert len(store.list_events(conn, EventStatus.DRAFT)) == 2
    assert history == {
        person.person_id: list(data.member_history(person.person_id)) for person in data.people
    }
    assert fingerprints == {
        person.person_id: evidence_fingerprint(person.person_id, context, data)
        for person in data.people
    }
    assert attention == session.execute("get_attention_queue", {})[0]


def test_resolved_proposal_saves_only_a_draft_and_approved_source_blocks_creation(env):
    conn, _, _ = env
    store.seed_demo_drafts(conn, DEMO_SOURCE_DRAFTS)
    sources = [store.get_event(conn, event_id) for event_id, _, _ in DEMO_SOURCE_DRAFTS]
    proposal = prepare_reconstruction(compare_sources(*sources))
    event_id = store.save_draft(conn, to_draft(proposal), intake_source=IntakeSource.MANUAL)
    assert store.get_event(conn, event_id).status == EventStatus.DRAFT
    assert all(store.get_event(conn, source.event_id) == source for source in sources)
    approved = sources[0].model_copy(update={"status": EventStatus.APPROVED})
    assert not can_create_draft(proposal, [approved, sources[1]])
    proposal = replace(proposal, created_draft_id=event_id)
    with pytest.raises(ValueError):
        resolve(proposal, "count:Launcher 1", "unknown")


def test_repeated_prepare_reuses_human_decisions(env):
    _, data, context = env
    sources = source_pair(6, 8)
    data = replace(data, events=lambda: sources)
    fingerprint = evidence_fingerprint("FIC-002", context, data)
    proposals = {}
    session = ToolSession(
        context, data, ScriptedProvider([]), Conversation("one"), {}, reconstructions=proposals
    )
    args = {"event_ids": [source.event_id for source in sources]}
    assert session.execute("prepare_reconstruction_proposal", args)[1]
    assert not session.execute("find_possible_shared_events", {})[1]
    assert not session.execute("prepare_reconstruction_proposal", args)[1]
    proposal = resolve(session.reconstruction, "count:Launcher 1", sources[1].event_id)
    proposals[proposal.key] = proposal
    again = ToolSession(
        context, data, ScriptedProvider([]), Conversation("two"), {}, reconstructions=proposals
    )
    assert not again.execute("prepare_reconstruction_proposal", args)[1]
    assert again.reconstruction is proposal
    assert evidence_fingerprint("FIC-002", context, data) == fingerprint


def test_shared_event_replay_is_grounded_and_actions_are_code_derived(env):
    conn, data, context = env
    store.seed_demo_drafts(conn, DEMO_SOURCE_DRAFTS)
    fixture = load_analyst_replay("shared_event", analysis_as_of=TODAY)
    step = fixture.steps[0]
    provider, intake = replay_providers(step)
    proposals = {}
    result = ask(
        step.utterance,
        context=context,
        data=data,
        provider=provider,
        intake_provider=intake,
        conversation=Conversation("replay"),
        ledger={},
        reconstructions=proposals,
    )
    assert result.grounded and result.validation == [] and not result.fallback
    assert result.response.intent == "RECONCILE_EVIDENCE"
    assert result.counts.outer_tool_calls == 3 and result.counts.outer_model_turns == 3
    assert result.reconstruction is proposals["EVT-DEMO-S1+EVT-DEMO-S2"]
    assert result.comparisons[0].source_ids == result.reconstruction.source_ids
    action = recommendation_action(result.response.recommendations[0], result)
    assert action.kind == "OPEN_EVIDENCE_COMPARISON"
    assert action.evidence_key == result.reconstruction.key
    assert result.response.symptom_followup_summary is None
    assert len(store.list_events(conn, EventStatus.DRAFT)) == 2
    assert participants(result.comparisons[0].sources[0]) == {"FIC-001", "FIC-002", "FIC-003"}


def test_evidence_refs_keep_global_scope_without_weakening_person_refs(env):
    conn, data, context = env
    store.seed_demo_drafts(conn, DEMO_SOURCE_DRAFTS)
    session = ToolSession(context, data, ScriptedProvider([]), Conversation("refs"), {})
    payload, error = session.execute("find_evidence_issues", {})
    assert not error
    refs = [item["evidence_ref"] for item in payload["untrusted_record_data"]["items"]]
    response = AgentResponse(
        intent="AUDIT_RECORDS", answer_summary="Review the cited records.", evidence_refs=refs
    )
    assert validate_response(response, session) == []
    unknown = response.model_copy(update={"evidence_refs": ["candidate:missing"]})
    assert any(item.code == "UNKNOWN_REF" for item in validate_response(unknown, session))


def test_person_scope_includes_a_candidate_when_only_one_source_names_the_person(env):
    conn, data, context = env
    store.seed_demo_drafts(conn, DEMO_SOURCE_DRAFTS)
    session = ToolSession(context, data, ScriptedProvider([]), Conversation("person-scope"), {})
    payload, error = session.execute("find_possible_shared_events", {"person_id": "FIC-003"})
    assert not error
    assert [item["source_ids"] for item in payload["untrusted_record_data"]["items"]] == [
        ("EVT-DEMO-S1", "EVT-DEMO-S2")
    ]


def test_all_tool_schemas_use_supported_array_constraints():
    def check(value):
        if isinstance(value, dict):
            assert "maxItems" not in value
            assert value.get("minItems", 0) <= 1
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)

    for tool in TOOL_DEFINITIONS:
        check(tool["input_schema"])
    draft = next(tool for tool in TOOL_DEFINITIONS if tool["name"] == "create_training_event_draft")
    assert draft["input_schema"]["properties"]["utterance_ids"]["minItems"] == 1


@pytest.mark.parametrize("event_ids", [[], ["A"], ["A", "B", "C"]])
def test_event_pair_runtime_still_requires_exactly_two_ids(event_ids):
    with pytest.raises(ValidationError):
        EventPairInput.model_validate({"event_ids": event_ids})
