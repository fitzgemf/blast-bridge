"""A recorder's explicit save/approve decision, using the existing revision protections."""

import sqlite3
from dataclasses import dataclass

from . import store
from .models import IntakeSource, TrainingEventDraft

PROPOSAL_STATUS = "Not yet saved"
DRAFT_STATUS = "Draft · awaiting approval"
APPROVED_STATUS = "Approved · in personnel history"
REJECTED_STATUS = "Rejected · not in personnel history"
APPROVAL_FAILURE = "Event was saved to Review but could not be approved."


@dataclass(frozen=True)
class ReviewDecision:
    event_id: str | None
    approved: bool
    error: str | None = None


def save_reviewed_event(
    conn: sqlite3.Connection,
    draft: TrainingEventDraft,
    intake_source: IntakeSource,
    *,
    approve: bool,
) -> ReviewDecision:
    try:
        event_id = store.save_draft(conn, draft, intake_source=intake_source)
    except (store.StoreError, sqlite3.Error) as exc:
        return ReviewDecision(None, False, f"Could not save this event: {exc}")
    if not approve:
        return ReviewDecision(event_id, False)
    try:
        approved = store.approve_event(conn, event_id, 1)
    except (store.StoreError, sqlite3.Error):
        return ReviewDecision(event_id, False, APPROVAL_FAILURE)
    return ReviewDecision(event_id, approved, None if approved else APPROVAL_FAILURE)
