"""Recorder slice: approval gates history; launches are counted once; unknown is not zero."""

from datetime import date

import pytest

from blastbridge.models.enums import EventType
from blastbridge.models.training_tempo import ParticipationRole, TrainingContext
from blastbridge.product import store
from blastbridge.product.models import Crew, CrewMember, CrewPosition, TrainingEventDraft
from blastbridge.product.seed import DEMO_PEOPLE

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
