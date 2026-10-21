"""Recorder slice: approval gates history; launches are counted once; unknown is not zero."""

from datetime import date, timedelta

import pytest

from blastbridge.models.enums import EventType
from blastbridge.models.training_tempo import ParticipationRole, TrainingContext
from blastbridge.product import store
from blastbridge.product.followup import FollowUpState, evaluate
from blastbridge.product.models import (
    Crew,
    CrewMember,
    CrewPosition,
    EventStatus,
    IntakeSource,
    TrainingEventDraft,
    provenance_text,
)
from blastbridge.product.seed import DEMO_EVENTS, DEMO_PEOPLE, DEMO_SYMPTOMS
from blastbridge.product.symptoms import (
    DangerSign,
    FunctionalImpact,
    Persistence,
    Symptom,
    SymptomReportDraft,
    SymptomSource,
    TemporalRelationship,
)

CREW = ("FIC-001", "FIC-002", "FIC-003")
OUTSIDER = "FIC-005"


@pytest.fixture
def conn(tmp_path):
    connection = store.connect(tmp_path / "product.sqlite")
    store.init_db(connection)
    store.seed_people(connection, DEMO_PEOPLE)
    yield connection
    connection.close()


def draft(count: int | None, crew: tuple[str, ...] = CREW) -> TrainingEventDraft:
    positions = (CrewPosition.CHIEF, CrewPosition.GUNNER, CrewPosition.DRIVER)
    return TrainingEventDraft(
        event_date=date(2026, 10, 14),
        event_type=EventType.WEAPON_FIRING,
        training_context=TrainingContext.QUALIFICATION,
        weapon_system_id="m142-himars",
        weapon_name="M142 HIMARS",
        crews=(
            Crew(
                crew_name="Launcher 1",
                members=tuple(
                    CrewMember(person_id=p, position=pos)
                    for p, pos in zip(crew, positions, strict=True)
                ),
                physical_event_count=count,
            ),
        ),
    )


def exposure_rows(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM participant_exposures").fetchone()[0]


def test_draft_is_not_in_history(conn):
    store.save_draft(conn, draft(6))
    assert all(store.member_history(conn, p) == [] for p in CREW)
    assert exposure_rows(conn) == 0


def test_reconstruction_sources_persist_across_creation_paths(conn):
    source_ids = ["EVT-DEMO-S1", "EVT-DEMO-S2"]
    manual_id = store.save_draft(conn, draft(4))
    assert (
        conn.execute(
            "SELECT reconstructed_from FROM training_events WHERE event_id = ?", (manual_id,)
        ).fetchone()[0]
        is None
    )
    assert store.find_reconstruction(conn, source_ids) is None

    event_id = store.save_draft(conn, draft(6), reconstructed_from=source_ids)
    assert (
        conn.execute(
            "SELECT reconstructed_from FROM training_events WHERE event_id = ?", (event_id,)
        ).fetchone()[0]
        == '["EVT-DEMO-S1","EVT-DEMO-S2"]'
    )
    reversed_ids = list(reversed(source_ids))
    existing = store.find_reconstruction(conn, reversed_ids)
    assert existing is not None
    assert existing.event_id == event_id
    before = len(store.list_events(conn, EventStatus.DRAFT, limit=-1))
    existing = store.find_reconstruction(conn, reversed_ids)
    if existing is None:
        store.save_draft(conn, draft(6), reconstructed_from=reversed_ids)
    assert len(store.list_events(conn, EventStatus.DRAFT, limit=-1)) == before
    assert store.find_reconstruction(conn, ["unrelated-source"]) is None

    assert store.approve_event(conn, event_id, 1)
    assert store.find_reconstruction(conn, reversed_ids).status is EventStatus.APPROVED
    rejected_id = store.save_draft(conn, draft(6), reconstructed_from=["rejected-source"])
    store.reject_event(conn, rejected_id, 1)
    assert store.find_reconstruction(conn, ["rejected-source"]) is None


def test_approval_adds_history_for_crew_only(conn):
    event_id = store.save_draft(conn, draft(6))
    assert store.approve_event(conn, event_id, 1) is True
    roles = {p: store.member_history(conn, p) for p in CREW}
    assert [len(h) for h in roles.values()] == [1, 1, 1]
    assert roles["FIC-001"][0].position is CrewPosition.CHIEF
    assert roles["FIC-002"][0].participation_role is ParticipationRole.WEAPON_OPERATOR
    assert store.member_history(conn, OUTSIDER) == []


def test_launch_count_is_not_multiplied_by_crew_size(conn):
    event_id = store.save_draft(conn, draft(6))
    store.approve_event(conn, event_id, 1)
    event = store.get_event(conn, event_id).draft
    assert (event.physical_event_count, event.participant_count) == (6, 3)
    assert event.association_count == 18
    assert exposure_rows(conn) == 3
    assert [store.member_history(conn, p)[0].physical_event_count for p in CREW] == [6, 6, 6]


def test_unknown_count_stays_unknown(conn):
    event_id = store.save_draft(conn, draft(None))
    store.approve_event(conn, event_id, 1)
    event = store.get_event(conn, event_id).draft
    assert event.physical_event_count is None
    assert event.association_count is None
    assert store.member_history(conn, "FIC-001")[0].physical_event_count is None
    with pytest.raises(ValueError):
        draft(0)


def test_second_approval_does_not_duplicate_history(conn):
    event_id = store.save_draft(conn, draft(6))
    assert store.approve_event(conn, event_id, 1) is True
    assert store.approve_event(conn, event_id, 1) is False
    assert exposure_rows(conn) == 3
    assert len(store.member_history(conn, "FIC-001")) == 1


def test_only_the_reviewed_draft_can_be_approved(conn):
    event_id = store.save_draft(conn, draft(6))
    store.update_draft(conn, event_id, draft(4), revision=1)
    with pytest.raises(store.StoreError):
        store.approve_event(conn, event_id, 1)
    store.reject_event(conn, event_id, 2)
    with pytest.raises(store.StoreError):
        store.approve_event(conn, event_id, 2)
    assert exposure_rows(conn) == 0


def test_edit_replaces_the_crew(conn):
    event_id = store.save_draft(conn, draft(6))
    store.update_draft(conn, event_id, draft(6, crew=("FIC-004", "FIC-002", "FIC-003")), 1)
    assert store.approve_event(conn, event_id, 2) is True
    assert store.member_history(conn, "FIC-001") == []
    assert len(store.member_history(conn, "FIC-004")) == 1
    assert exposure_rows(conn) == 3


def test_multi_crew_counts_stay_with_their_own_people(conn):
    other = ("FIC-005", "FIC-006", "FIC-007")
    second = draft(None, other).crews[0].model_copy(update={"crew_name": "Launcher 2"})
    event = TrainingEventDraft(**{**draft(6).model_dump(), "crews": (draft(6).crews[0], second)})
    event_id = store.save_draft(conn, event)
    store.approve_event(conn, event_id, 1)
    assert exposure_rows(conn) == len(CREW) + len(other)
    assert [store.member_history(conn, p)[0].physical_event_count for p in CREW] == [6] * 3
    assert [store.member_history(conn, p)[0].physical_event_count for p in other] == [None] * 3


def test_demo_events_are_idempotent(conn):
    assert store.seed_demo_events(conn, DEMO_EVENTS) == 12
    before = [tuple(row) for row in conn.execute("SELECT * FROM participant_exposures")]
    assert store.seed_demo_events(conn, DEMO_EVENTS) == 0
    assert [tuple(row) for row in conn.execute("SELECT * FROM participant_exposures")] == before
    assert len(store.list_events(conn, EventStatus.APPROVED)) == 12
    assert all(
        store.get_event(conn, event_id).status is EventStatus.APPROVED
        for event_id, _ in DEMO_EVENTS
    )
    assert {e.position for e in store.member_history(conn, "FIC-002")} == {
        CrewPosition.CHIEF,
        CrewPosition.GUNNER,
    }


def test_future_event_date_is_refused(conn):
    tomorrow = TrainingEventDraft(
        **{
            **draft(6).model_dump(),
            "event_date": date.today() + timedelta(days=1),
        }
    )
    with pytest.raises(store.StoreError, match="event date cannot be in the future"):
        store.save_draft(conn, tomorrow)
    for table in ("training_events", "crews", "crew_members", "participant_exposures"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_person_cannot_appear_in_two_crews():
    second = draft(6).crews[0].model_copy(update={"crew_name": "Launcher 2"})
    with pytest.raises(ValueError, match="only one crew per event"):
        TrainingEventDraft(**{**draft(6).model_dump(), "crews": (draft(6).crews[0], second)})


def test_intake_provenance_survives_reload(tmp_path):
    path = tmp_path / "provenance.sqlite"
    connection = store.connect(path)
    store.init_db(connection)
    store.seed_people(connection, DEMO_PEOPLE)
    event_id = store.save_draft(connection, draft(6), intake_source=IntakeSource.AI_LIVE)
    store.approve_event(connection, event_id, 1)
    connection.close()
    connection = store.connect(path)
    try:
        event = store.get_event(connection, event_id)
        assert event.intake_source is IntakeSource.AI_LIVE
        assert store.member_history(connection, CREW[0])[0].intake_source is IntakeSource.AI_LIVE
        assert provenance_text(event.intake_source, event.status) == (
            "Organizational record — AI-assisted, human approved"
        )
    finally:
        connection.close()


def test_version_three_upgrades_with_manual_provenance(tmp_path):
    connection = store.connect(tmp_path / "version-three.sqlite")
    try:
        connection.executescript("""
            CREATE TABLE training_events (
                event_id TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK (status IN ('draft', 'approved', 'rejected')),
                event_date TEXT NOT NULL,
                event_type TEXT NOT NULL,
                training_context TEXT NOT NULL,
                weapon_system_id TEXT NOT NULL,
                weapon_name TEXT NOT NULL,
                location_unit TEXT,
                created_at TEXT NOT NULL,
                decided_at TEXT,
                revision INTEGER NOT NULL CHECK (revision >= 1)
            );
            INSERT INTO training_events VALUES (
                'EVT-OLD-DEMO', 'draft', '2026-10-14', 'weapon_firing',
                'qualification_certification', 'm142-himars', 'M142 HIMARS',
                'Demo Range North (FICTIONAL)', '2026-10-14T00:00:00+00:00', NULL, 1
            );
            PRAGMA user_version = 3;
        """)
        connection.executescript(store._SCHEMA)
        before = dict(connection.execute("SELECT * FROM training_events").fetchone())
        store.init_db(connection)
        after = dict(connection.execute("SELECT * FROM training_events").fetchone())
        assert after.pop("intake_source") == "manual"
        assert after == before
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 4
    finally:
        connection.close()


def report_draft(event_id: str | None = None, **changes) -> SymptomReportDraft:
    values = {
        "person_id": CREW[0],
        "event_id": event_id,
        "report_date": date(2026, 10, 15),
        "source": SymptomSource.SELF_REPORTED,
        "symptoms": (Symptom.HEADACHES,),
        "temporal_relationship": (
            TemporalRelationship.AFTER_RECORDED_EVENT
            if event_id
            else TemporalRelationship.NOT_LINKED_TO_EVENT
        ),
        "persistence": Persistence.STILL_PRESENT,
        "functional_impact": FunctionalImpact.YES,
    }
    return SymptomReportDraft(**{**values, **changes})


def test_confirm_writes_only_that_persons_report(conn):
    event_id = store.save_draft(conn, draft(6))
    store.approve_event(conn, event_id, 1)
    tables = ("training_events", "crews", "crew_members", "participant_exposures")
    before = {
        table: repr(
            [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
        ).encode()
        for table in tables
    }
    report = report_draft(event_id)
    evaluate(report)
    assert conn.execute("SELECT COUNT(*) FROM symptom_reports").fetchone()[0] == 0
    store.confirm_symptom_report(conn, report)
    assert len(store.list_symptom_reports(conn, CREW[0])) == 1
    assert store.list_symptom_reports(conn, CREW[1]) == []
    assert conn.execute("SELECT COUNT(*) FROM symptom_reports").fetchone()[0] == 1
    after = {
        table: repr(
            [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
        ).encode()
        for table in tables
    }
    assert before == after


def test_followup_rule():
    linked = report_draft("EVT-FICTIONAL")
    unknown = report_draft(
        "EVT-FICTIONAL", persistence=Persistence.UNKNOWN, functional_impact=FunctionalImpact.UNKNOWN
    )
    danger_only = report_draft(symptoms=(), danger_signs=(DangerSign.REPEATED_VOMITING,))
    danger_and_symptoms = report_draft(
        "EVT-FICTIONAL", danger_signs=(DangerSign.REPEATED_VOMITING,)
    )
    results = [evaluate(report) for report in (linked, unknown, danger_only, danger_and_symptoms)]
    assert [result.state for result in results] == [
        FollowUpState.FOLLOW_UP_SUGGESTED,
        FollowUpState.NO_FOLLOWUP_RULE_TRIGGERED,
        FollowUpState.URGENT_EVALUATION_RECOMMENDED,
        FollowUpState.URGENT_EVALUATION_RECOMMENDED,
    ]
    unknown_relationship = evaluate(
        report_draft(
            "EVT-FICTIONAL", temporal_relationship=TemporalRelationship.RELATIONSHIP_UNKNOWN
        )
    )
    assert unknown_relationship.state is FollowUpState.FOLLOW_UP_SUGGESTED
    assert "relationship to recorded exposure is unknown" in unknown_relationship.explanation
    assert "the relationship to a recorded event" in (
        " ".join(unknown_relationship.missing).lower()
    )
    unlinked = evaluate(report_draft())
    assert unlinked.state is FollowUpState.FOLLOW_UP_SUGGESTED
    results.extend((unknown_relationship, unlinked))
    negative_cases = (
        report_draft("EVT-FICTIONAL", persistence=Persistence.RESOLVED),
        report_draft("EVT-FICTIONAL", functional_impact=FunctionalImpact.NO),
        report_draft("EVT-FICTIONAL", symptoms=(), note="Fictional demo note."),
    )
    for report in negative_cases:
        result = evaluate(report)
        assert result.state is FollowUpState.NO_FOLLOWUP_RULE_TRIGGERED
        results.append(result)
    missing = " ".join(results[1].missing).lower()
    assert "persistence" in missing and "functional impact" in missing
    for result in results:
        wording = " ".join((result.headline, result.explanation, *result.missing)).lower()
        assert not any(
            term in wording
            for term in (
                "possible tbi",
                "tbi risk",
                "probability",
                "%",
                "you are safe",
                "no tbi",
                "no follow-up needed",
                "caused by",
                "diagnosed with",
            )
        )


def test_launch_count_does_not_change_followup(conn):
    results = []
    for count in (1, 999, None):
        event_id = store.save_draft(conn, draft(count))
        store.approve_event(conn, event_id, 1)
        report = report_draft(event_id)
        results.append(evaluate(report))
        store.confirm_symptom_report(conn, report)
    assert results[0] == results[1] == results[2]
    assert len(store.list_symptom_reports(conn, CREW[0])) == 3


def test_symptom_seed_is_idempotent(conn):
    store.seed_demo_events(conn, DEMO_EVENTS)
    assert store.seed_demo_symptoms(conn, DEMO_SYMPTOMS) == 3
    assert store.seed_demo_events(conn, DEMO_EVENTS) == 0
    assert store.seed_demo_symptoms(conn, DEMO_SYMPTOMS) == 0
    assert len(store.list_symptom_reports(conn)) == 3
    store.reset_demo(conn, DEMO_PEOPLE, DEMO_EVENTS, DEMO_SYMPTOMS)
    reports = {report.report_id: report for report in store.list_symptom_reports(conn)}
    assert len(reports) == 3
    assert [evaluate(reports[report_id].draft).state for report_id, _ in DEMO_SYMPTOMS] == [
        FollowUpState.FOLLOW_UP_SUGGESTED,
        FollowUpState.NO_FOLLOWUP_RULE_TRIGGERED,
        FollowUpState.NO_FOLLOWUP_RULE_TRIGGERED,
    ]


def test_link_must_be_an_approved_event_the_person_attended(conn):
    approved = store.save_draft(conn, draft(6))
    store.approve_event(conn, approved, 1)
    pending = store.save_draft(conn, draft(6))
    with pytest.raises(store.StoreError, match="participated"):
        store.confirm_symptom_report(conn, report_draft(approved, person_id=OUTSIDER))
    with pytest.raises(store.StoreError, match="approved"):
        store.confirm_symptom_report(conn, report_draft(pending))
    assert store.list_symptom_reports(conn) == []
