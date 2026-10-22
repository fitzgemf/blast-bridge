"""An explicit human decision saves once and never retries a failed approval."""

import pytest

from blastbridge.product import store
from blastbridge.product.models import EventStatus, IntakeSource
from blastbridge.product.review_flow import (
    APPROVAL_FAILURE,
    APPROVED_STATUS,
    DRAFT_STATUS,
    PROPOSAL_STATUS,
    REJECTED_STATUS,
    save_reviewed_event,
)
from blastbridge.product.seed import DEMO_EVENTS, DEMO_PEOPLE


@pytest.fixture
def conn(tmp_path):
    connection = store.connect(tmp_path / "review.sqlite")
    store.init_db(connection)
    store.seed_people(connection, DEMO_PEOPLE)
    yield connection
    connection.close()


def test_direct_approve_saves_exact_proposal_and_adds_personnel_history(conn):
    draft = DEMO_EVENTS[0][1]
    result = save_reviewed_event(conn, draft, IntakeSource.AI_REPLAY, approve=True)
    assert result.approved and result.error is None
    event = store.get_event(conn, result.event_id)
    assert event.status is EventStatus.APPROVED
    assert event.draft == draft and event.revision == 1
    assert event.intake_source is IntakeSource.AI_REPLAY
    assert store.list_events(conn, EventStatus.DRAFT) == []
    assert len(store.list_events(conn, EventStatus.APPROVED)) == 1
    for crew in draft.crews:
        for member in crew.members:
            assert [row.event_id for row in store.member_history(conn, member.person_id)] == [
                result.event_id
            ]


def test_save_for_later_remains_draft_and_out_of_personnel_history(conn):
    draft = DEMO_EVENTS[0][1]
    result = save_reviewed_event(conn, draft, IntakeSource.MANUAL, approve=False)
    assert not result.approved and result.error is None
    event = store.get_event(conn, result.event_id)
    assert event.status is EventStatus.DRAFT
    assert event.draft == draft
    assert event.intake_source is IntakeSource.MANUAL
    for crew in draft.crews:
        for member in crew.members:
            assert store.member_history(conn, member.person_id) == []


def test_failed_approval_keeps_saved_draft_and_reports_it_without_retry(conn, monkeypatch):
    calls = []

    def stale_approval(connection, event_id, revision):
        calls.append((event_id, revision))
        store.update_draft(connection, event_id, DEMO_EVENTS[0][1], revision)
        raise store.StoreError("The reviewed revision changed")

    monkeypatch.setattr(store, "approve_event", stale_approval)
    result = save_reviewed_event(conn, DEMO_EVENTS[0][1], IntakeSource.AI_LIVE, approve=True)
    assert result.event_id is not None and not result.approved
    assert result.error == APPROVAL_FAILURE
    assert calls == [(result.event_id, 1)]
    event = store.get_event(conn, result.event_id)
    assert event.status is EventStatus.DRAFT and event.revision == 2
    assert event.intake_source is IntakeSource.AI_LIVE
    assert len(store.list_events(conn, EventStatus.DRAFT)) == 1
    assert store.list_events(conn, EventStatus.APPROVED) == []
    assert store.member_history(conn, "FIC-001") == []


def test_proposal_draft_approved_and_rejected_wording_describe_distinct_states():
    assert PROPOSAL_STATUS == "Not yet saved"
    assert DRAFT_STATUS == "Draft · awaiting approval"
    assert APPROVED_STATUS == "Approved · in personnel history"
    assert REJECTED_STATUS == "Rejected · not in personnel history"
    assert len({PROPOSAL_STATUS, DRAFT_STATUS, APPROVED_STATUS, REJECTED_STATUS}) == 4
