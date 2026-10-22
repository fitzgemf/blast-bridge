"""Stub-only intake checks; training records still require human save and approval."""

import inspect
import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from blastbridge.data.catalog import load_weapon_catalog
from blastbridge.product import agent, store
from blastbridge.product.agent import (
    GOLDEN_NARRATIVE,
    ProviderError,
    ProviderTurn,
    ScriptedProvider,
    run_intake,
)
from blastbridge.product.agent_tools import search_roster, search_weapon_catalog
from blastbridge.product.seed import DEMO_PEOPLE

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 10, 19)


@pytest.fixture
def catalog():
    return load_weapon_catalog(ROOT / "data/reference/weapons.json")


@pytest.fixture
def golden():
    dataset = json.loads((ROOT / "examples/fictional/intake/eval_cases.json").read_text())
    return dataset["cases"][0]


@pytest.fixture
def conn(tmp_path):
    connection = store.connect(tmp_path / "agent.sqlite")
    store.init_db(connection)
    store.seed_people(connection, DEMO_PEOPLE)
    yield connection
    connection.close()


def text_turn(text):
    blocks = [{"type": "text", "text": text}]
    return ProviderTurn("end_turn", blocks, blocks, "stub-model")


def test_blank_or_short_narrative_never_calls_provider(catalog):
    class CountingProvider:
        name = "stub"
        calls = 0

        def complete(self, **kwargs):
            self.calls += 1
            raise AssertionError("Short input must not call the provider")

    provider = CountingProvider()
    for narrative in ("", "   \n\t", "  fired  6 \n rockets  "):
        result = run_intake(narrative, provider, catalog, DEMO_PEOPLE, TODAY)
        assert result.error == "Paste or type a training record before drafting."
        assert result.model_calls == 0 and result.proposal is None
    assert provider.calls == 0


def proposal_provider(proposal, queries=(("search_weapon_catalog", "HIMARS"),), name="stub"):
    turns = []
    if queries:
        blocks = [
            {"type": "tool_use", "id": f"tool-{i}", "name": tool, "input": {"query": query}}
            for i, (tool, query) in enumerate(queries)
        ]
        turns.append(ProviderTurn("tool_use", blocks, blocks, "stub-model"))
    turns.append(text_turn(json.dumps(proposal)))
    return ScriptedProvider(turns, name=name)


def test_tools_are_deterministic(catalog):
    for query in ("HIMARS", "High Mobility Artillery Rocket System"):
        results = search_weapon_catalog(query, catalog)
        assert results[0]["weapon_system_id"] == "m142-himars"
        assert set(results[0]) == {
            "weapon_system_id",
            "canonical_name",
            "aliases",
            "weapon_family",
        }
        assert search_weapon_catalog(query, catalog) == results
    people = search_roster("Pike", DEMO_PEOPLE)
    assert people[0]["person_id"] == "FIC-002"
    assert set(people[0]) == {"person_id", "display_name", "section"}
    assert search_roster("Pike", DEMO_PEOPLE) == people
    assert search_weapon_catalog("laser cannon", catalog) == []


def test_golden_run_stays_in_memory(conn, catalog, golden):
    tables = (
        "training_events",
        "crews",
        "crew_members",
        "participant_exposures",
        "symptom_reports",
    )
    before = [conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables]
    result = run_intake(
        GOLDEN_NARRATIVE,
        proposal_provider(golden["stub_proposal"], golden["stub_tool_queries"]),
        catalog,
        DEMO_PEOPLE,
        TODAY,
    )
    assert result.error is None and result.draft is not None
    assert result.draft.crews[1].physical_event_count is None
    assert not any(issue.blocking for issue in result.issues)
    trace = " ".join(step.text for step in result.trace)
    assert "weapon catalog" in trace and "Searched roster" in trace
    assert result.origins["Weapon"] == "weapon catalog"
    assert result.origins["Activity"] == "AI interpretation"
    assert result.origins["Training context"] == "AI interpretation"
    assert result.origins["Date"] == "narrative"
    assert result.origins["Launcher 1 · Gunner"] == "demo roster"
    assert before == [
        conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables
    ]
    assert "store" not in vars(agent) and "sqlite3" not in vars(agent)
    source = inspect.getsource(agent)
    assert "import store" not in source and "import sqlite3" not in source


def test_gate_refuses_bad_output(catalog, golden):
    proposals = []
    invented_person = deepcopy(golden["stub_proposal"])
    invented_person["crews"][0]["members"][0]["person_id"] = "FIC-INVENTED"
    proposals.append(invented_person)
    invented_weapon = deepcopy(golden["stub_proposal"])
    invented_weapon["weapon_system_id"] = "made-up-system"
    proposals.append(invented_weapon)
    future = deepcopy(golden["stub_proposal"])
    future["event_date"] = "2099-01-05"
    proposals.append(future)
    duplicate = deepcopy(golden["stub_proposal"])
    duplicate["crews"][1]["members"][0]["person_id"] = "FIC-001"
    duplicate["crews"][1]["members"][0]["name_text"] = "Avery Kestrel"
    proposals.append(duplicate)
    approximate = deepcopy(golden["stub_proposal"])
    approximate["crews"][0].update(
        count_status="approximate_or_ambiguous",
        launch_count=6,
        count_text="about six rockets",
    )
    proposals.append(approximate)
    for proposal in proposals:
        result = run_intake(
            GOLDEN_NARRATIVE,
            proposal_provider(proposal),
            catalog,
            DEMO_PEOPLE,
            TODAY,
        )
        assert result.draft is None and any(issue.blocking for issue in result.issues)
    assert result.form_values["f_c0_count"] is None
    assert result.form_values["f_c0_known"] is None


def test_gate_requires_exact_counts_and_crew_names_written_in_the_record(catalog, golden):
    invented_count = deepcopy(golden["stub_proposal"])
    invented_count["crews"][0].update(launch_count=9, count_text="9 rockets")
    unstated_number = deepcopy(golden["stub_proposal"])
    unstated_number["crews"][0].update(launch_count=7, count_text="6 rockets")
    for proposal in (invented_count, unstated_number):
        result = run_intake(
            GOLDEN_NARRATIVE, proposal_provider(proposal), catalog, DEMO_PEOPLE, TODAY
        )
        assert result.draft is None
        assert result.form_values["f_c0_count"] is None
        assert any("not written in the record" in issue.message for issue in result.issues)
    renamed = deepcopy(golden["stub_proposal"])
    renamed["crews"][0]["crew_name"] = "Alpha Section"
    result = run_intake(GOLDEN_NARRATIVE, proposal_provider(renamed), catalog, DEMO_PEOPLE, TODAY)
    assert result.form_values["f_c0_name"] == "Launcher 1"
    assert result.origins["Crew 1 name"] == "default label"


@pytest.mark.parametrize(
    ("count_text", "launch_count", "stated"),
    [
        ("6 rockets", 6, True),
        ("fired 6.", 6, True),
        ("We fired six", 6, True),
        ("6.5 rockets", 6, False),
        ("v6 rockets", 6, False),
        ("about 6", 6, False),
        ("6?", 6, False),
        ("twenty rockets", 0, False),
    ],
)
def test_exact_count_stated(count_text, launch_count, stated):
    source = f"Launcher 1: {count_text} today"
    assert agent.exact_count_stated(count_text, launch_count, source) is stated
    assert agent.exact_count_stated(count_text, launch_count, "unrelated text") is False


def test_gate_refuses_name_id_mismatch_and_missing_weapon_lookup(catalog, golden):
    proposal = deepcopy(golden["stub_proposal"])
    proposal["crews"][0]["members"][2].update(name_text="Alex", person_id="FIC-008")
    result = run_intake(
        GOLDEN_NARRATIVE,
        proposal_provider(proposal),
        catalog,
        DEMO_PEOPLE,
        TODAY,
    )
    assert result.draft is None and any(issue.blocking for issue in result.issues)
    assert result.form_values["f_c0_driver"] is None
    assert any("'Alex'" in issue.message for issue in result.issues)
    proposal["crews"][0]["members"][2].update(name_text="Sam", person_id="FIC-004")
    shortened = run_intake(
        GOLDEN_NARRATIVE.replace("Riley Marsh", "Samantha"),
        proposal_provider(proposal),
        catalog,
        DEMO_PEOPLE,
        TODAY,
    )
    assert shortened.draft is None and shortened.form_values["f_c0_driver"] is None
    no_lookup = run_intake(
        GOLDEN_NARRATIVE,
        proposal_provider(golden["stub_proposal"], queries=()),
        catalog,
        DEMO_PEOPLE,
        TODAY,
    )
    assert no_lookup.draft is None and no_lookup.form_values["f_weapon"] is None
    assert any("not returned by a catalog lookup" in issue.message for issue in no_lookup.issues)


def test_bounds_and_provider_failures(catalog, golden):
    blocks = [
        {
            "type": "tool_use",
            "id": "again",
            "name": "search_weapon_catalog",
            "input": {"query": "HIMARS"},
        }
    ]
    repeated = ScriptedProvider([ProviderTurn("tool_use", blocks, blocks, "stub")] * 5)
    result = run_intake(GOLDEN_NARRATIVE, repeated, catalog, DEMO_PEOPLE, TODAY)
    assert result.error and result.model_calls <= 4 and result.narrative == GOLDEN_NARRATIVE

    class FailedProvider:
        name = "stub"

        def complete(self, **kwargs):
            raise ProviderError("Provider unavailable. Please enter manually.")

    failed = run_intake(GOLDEN_NARRATIVE, FailedProvider(), catalog, DEMO_PEOPLE, TODAY)
    assert failed.error == "Provider unavailable. Please enter manually."
    assert failed.narrative == GOLDEN_NARRATIVE
    fixed = ScriptedProvider(
        [
            ProviderTurn("tool_use", blocks, blocks, "stub"),
            text_turn("not JSON"),
            text_turn(json.dumps(golden["stub_proposal"])),
        ]
    )
    result = run_intake(GOLDEN_NARRATIVE, fixed, catalog, DEMO_PEOPLE, TODAY)
    assert result.model_calls == 3 and result.draft is not None
    invalid = ScriptedProvider([text_turn("not JSON")] * 4)
    result = run_intake(GOLDEN_NARRATIVE, invalid, catalog, DEMO_PEOPLE, TODAY)
    assert result.error and result.model_calls == 2
    fourth_call = ScriptedProvider(
        [
            ProviderTurn("tool_use", blocks, blocks, "stub"),
            ProviderTurn("tool_use", blocks, blocks, "stub"),
            text_turn("not JSON"),
            text_turn(json.dumps(golden["stub_proposal"])),
        ]
    )
    result = run_intake(GOLDEN_NARRATIVE, fourth_call, catalog, DEMO_PEOPLE, TODAY)
    assert result.model_calls == 4 and result.draft is not None


def test_replay_uses_normal_human_path(conn, catalog, golden):
    result = run_intake(
        GOLDEN_NARRATIVE,
        proposal_provider(golden["stub_proposal"], golden["stub_tool_queries"], name="replay"),
        catalog,
        DEMO_PEOPLE,
        TODAY,
    )
    assert result.mode == "replay" and result.draft is not None
    assert store.member_history(conn, "FIC-002") == []
    event_id = store.save_draft(conn, result.draft)
    assert store.member_history(conn, "FIC-002") == []
    store.approve_event(conn, event_id, 1)
    assert store.member_history(conn, "FIC-002")[0].event_id == event_id
