"""SQLite persistence for the recorder slice.

The physical launch count lives once on its crew. Approval links each crew member to the event in
participant_exposures; those rows never copy or multiply the count. Drafts never reach history.
"""

import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from .models import (
    Crew,
    CrewMember,
    CrewPosition,
    EventStatus,
    HistoryEntry,
    Person,
    TrainingEvent,
    TrainingEventDraft,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    person_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    callsign TEXT NOT NULL,
    unit TEXT NOT NULL,
    section TEXT NOT NULL,
    home_position TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS training_events (
    event_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('draft', 'approved', 'rejected')),
    event_date TEXT NOT NULL,
    event_type TEXT NOT NULL,
    training_context TEXT NOT NULL,
    weapon_system_id TEXT NOT NULL,
    weapon_name TEXT NOT NULL,
    location_unit TEXT,
    created_at TEXT NOT NULL,
    decided_at TEXT
);
CREATE TABLE IF NOT EXISTS crews (
    crew_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES training_events(event_id),
    crew_index INTEGER NOT NULL,
    crew_name TEXT NOT NULL,
    physical_event_count INTEGER CHECK (physical_event_count IS NULL OR physical_event_count >= 1),
    UNIQUE (event_id, crew_index)
);
CREATE TABLE IF NOT EXISTS crew_members (
    crew_id TEXT NOT NULL REFERENCES crews(crew_id),
    person_id TEXT NOT NULL REFERENCES people(person_id),
    member_index INTEGER NOT NULL,
    position TEXT NOT NULL,
    PRIMARY KEY (crew_id, person_id)
);
CREATE TABLE IF NOT EXISTS participant_exposures (
    event_id TEXT NOT NULL REFERENCES training_events(event_id),
    crew_id TEXT NOT NULL REFERENCES crews(crew_id),
    person_id TEXT NOT NULL REFERENCES people(person_id),
    position TEXT NOT NULL,
    participation_role TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    PRIMARY KEY (event_id, person_id)
);
"""


class StoreError(Exception):
    pass


def connect(path: str | Path) -> sqlite3.Connection:
    """Autocommit connection; writes use explicit transactions."""
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def _transaction(conn: sqlite3.Connection) -> Iterator[None]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)


def seed_people(conn: sqlite3.Connection, people: Iterable[Person]) -> None:
    with _transaction(conn):
        conn.executemany(
            "INSERT OR IGNORE INTO people VALUES (?, ?, ?, ?, ?, ?)",
            [
                (p.person_id, p.display_name, p.callsign, p.unit, p.section, p.home_position)
                for p in people
            ],
        )


def _person(row: sqlite3.Row) -> Person:
    return Person(**dict(row))


def list_people(conn: sqlite3.Connection) -> list[Person]:
    rows = conn.execute("SELECT * FROM people ORDER BY section, display_name").fetchall()
    return [_person(r) for r in rows]


def get_person(conn: sqlite3.Connection, person_id: str) -> Person | None:
    row = conn.execute("SELECT * FROM people WHERE person_id = ?", (person_id,)).fetchone()
    return None if row is None else _person(row)


def _write_draft(conn: sqlite3.Connection, event_id: str, draft: TrainingEventDraft) -> None:
    for ci, crew in enumerate(draft.crews):
        crew_id = f"{event_id}-C{ci + 1}"
        conn.execute(
            "INSERT INTO crews VALUES (?, ?, ?, ?, ?)",
            (crew_id, event_id, ci, crew.crew_name, crew.physical_event_count),
        )
        conn.executemany(
            "INSERT INTO crew_members VALUES (?, ?, ?, ?)",
            [(crew_id, m.person_id, mi, m.position) for mi, m in enumerate(crew.members)],
        )


def _event_columns(draft: TrainingEventDraft) -> tuple[str, str, str, str, str, str | None]:
    return (
        draft.event_date.isoformat(),
        draft.event_type,
        draft.training_context,
        draft.weapon_system_id,
        draft.weapon_name,
        draft.location_unit,
    )


def _status(conn: sqlite3.Connection, event_id: str) -> EventStatus:
    row = conn.execute(
        "SELECT status FROM training_events WHERE event_id = ?", (event_id,)
    ).fetchone()
    if row is None:
        raise StoreError(f"unknown event {event_id}")
    return EventStatus(row["status"])


def save_draft(conn: sqlite3.Connection, draft: TrainingEventDraft) -> str:
    event_id = f"EVT-{uuid4().hex[:8].upper()}"
    with _transaction(conn):
        conn.execute(
            "INSERT INTO training_events VALUES (?, 'draft', ?, ?, ?, ?, ?, ?, ?, NULL)",
            (event_id, *_event_columns(draft), _now()),
        )
        _write_draft(conn, event_id, draft)
    return event_id


def update_draft(conn: sqlite3.Connection, event_id: str, draft: TrainingEventDraft) -> None:
    with _transaction(conn):
        if _status(conn, event_id) is not EventStatus.DRAFT:
            raise StoreError(f"{event_id} is no longer a draft")
        conn.execute(
            "DELETE FROM crew_members WHERE crew_id IN "
            "(SELECT crew_id FROM crews WHERE event_id = ?)",
            (event_id,),
        )
        conn.execute("DELETE FROM crews WHERE event_id = ?", (event_id,))
        conn.execute(
            "UPDATE training_events SET event_date = ?, event_type = ?, training_context = ?, "
            "weapon_system_id = ?, weapon_name = ?, location_unit = ? WHERE event_id = ?",
            (*_event_columns(draft), event_id),
        )
        _write_draft(conn, event_id, draft)


def reject_event(conn: sqlite3.Connection, event_id: str) -> None:
    with _transaction(conn):
        if _status(conn, event_id) is not EventStatus.DRAFT:
            raise StoreError(f"{event_id} is no longer a draft")
        conn.execute(
            "UPDATE training_events SET status = 'rejected', decided_at = ? WHERE event_id = ?",
            (_now(), event_id),
        )


def approve_event(conn: sqlite3.Connection, event_id: str) -> bool:
    """Approve a draft atomically. Returns False if it was already approved (no new history)."""
    with _transaction(conn):
        status = _status(conn, event_id)
        if status is EventStatus.APPROVED:
            return False
        if status is not EventStatus.DRAFT:
            raise StoreError(f"{event_id} is {status}, not a draft")
        decided = _now()
        conn.execute(
            "UPDATE training_events SET status = 'approved', decided_at = ? WHERE event_id = ?",
            (decided, event_id),
        )
        members = conn.execute(
            "SELECT m.crew_id, m.person_id, m.position FROM crew_members m "
            "JOIN crews c ON c.crew_id = m.crew_id WHERE c.event_id = ?",
            (event_id,),
        ).fetchall()
        conn.executemany(
            "INSERT INTO participant_exposures VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    event_id,
                    m["crew_id"],
                    m["person_id"],
                    m["position"],
                    CrewPosition(m["position"]).participation_role,
                    decided,
                )
                for m in members
            ],
        )
    return True


def get_event(conn: sqlite3.Connection, event_id: str) -> TrainingEvent:
    row = conn.execute("SELECT * FROM training_events WHERE event_id = ?", (event_id,)).fetchone()
    if row is None:
        raise StoreError(f"unknown event {event_id}")
    crews = []
    for c in conn.execute(
        "SELECT * FROM crews WHERE event_id = ? ORDER BY crew_index", (event_id,)
    ).fetchall():
        members = conn.execute(
            "SELECT person_id, position FROM crew_members WHERE crew_id = ? ORDER BY member_index",
            (c["crew_id"],),
        ).fetchall()
        crews.append(
            Crew(
                crew_name=c["crew_name"],
                members=tuple(CrewMember(**dict(m)) for m in members),
                physical_event_count=c["physical_event_count"],
            )
        )
    draft = TrainingEventDraft(
        event_date=date.fromisoformat(row["event_date"]),
        event_type=row["event_type"],
        training_context=row["training_context"],
        weapon_system_id=row["weapon_system_id"],
        weapon_name=row["weapon_name"],
        location_unit=row["location_unit"],
        crews=tuple(crews),
    )
    return TrainingEvent(event_id=event_id, status=row["status"], draft=draft)


def list_events(
    conn: sqlite3.Connection, status: EventStatus, limit: int = 20
) -> list[TrainingEvent]:
    rows = conn.execute(
        "SELECT event_id FROM training_events WHERE status = ? "
        "ORDER BY event_date DESC, created_at DESC LIMIT ?",
        (status, limit),
    ).fetchall()
    return [get_event(conn, r["event_id"]) for r in rows]


def member_history(conn: sqlite3.Connection, person_id: str) -> list[HistoryEntry]:
    """Approved participation only, newest first."""
    rows = conn.execute(
        "SELECT e.event_id, e.event_date, e.event_type, e.training_context, e.weapon_name, "
        "e.location_unit, c.crew_name, x.position, x.participation_role, c.physical_event_count "
        "FROM participant_exposures x "
        "JOIN training_events e ON e.event_id = x.event_id "
        "JOIN crews c ON c.crew_id = x.crew_id "
        "WHERE x.person_id = ? AND e.status = 'approved' "
        "ORDER BY e.event_date DESC, e.decided_at DESC",
        (person_id,),
    ).fetchall()
    return [
        HistoryEntry(**{**dict(r), "event_date": date.fromisoformat(r["event_date"])}) for r in rows
    ]
