"""SQLite persistence for the recorder slice.

The physical launch count lives once on its crew. Approval links each crew member to the event in
participant_exposures; those rows never copy or multiply the count. Drafts never reach history.
"""

import json
import sqlite3
from collections.abc import Iterable, Iterator, Sequence
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
    IntakeSource,
    Person,
    TrainingEvent,
    TrainingEventDraft,
)
from .symptoms import SymptomReport, SymptomReportDraft, TemporalRelationship

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
    decided_at TEXT,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    intake_source TEXT NOT NULL DEFAULT 'manual'
        CHECK (intake_source IN ('manual', 'ai_live', 'ai_replay')),
    reconstructed_from TEXT NULL
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
CREATE TABLE IF NOT EXISTS symptom_reports (
    report_id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL REFERENCES people(person_id),
    event_id TEXT REFERENCES training_events(event_id),
    report_date TEXT NOT NULL,
    source TEXT NOT NULL,
    symptoms TEXT NOT NULL,
    danger_signs TEXT NOT NULL,
    note TEXT,
    temporal_relationship TEXT NOT NULL,
    persistence TEXT NOT NULL,
    functional_impact TEXT NOT NULL,
    confirmed_at TEXT NOT NULL
);
"""


class StoreError(Exception):
    pass


class ReconstructionExists(StoreError):
    """A live reconstruction already covers one of the sources (e.g. created from another tab)."""

    def __init__(self, event_id: str) -> None:
        super().__init__(f"{event_id} already reconstructs these records")
        self.event_id = event_id


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
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


_SCHEMA_VERSION = 4


def init_db(conn: sqlite3.Connection) -> None:
    """Create or additively upgrade version 2/3 records, retaining their manual provenance."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    existing = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'training_events'"
    ).fetchone()[0]
    if (existing and version not in (2, 3, _SCHEMA_VERSION)) or (
        not existing and version not in (0, 2, 3, _SCHEMA_VERSION)
    ):
        raise StoreError(
            "this database was created by an older BlastBridge build; "
            "delete the demo database file and restart"
        )
    conn.executescript(_SCHEMA)
    with _transaction(conn):
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(training_events)")}
        if "intake_source" not in columns:
            conn.execute(
                "ALTER TABLE training_events ADD COLUMN intake_source TEXT NOT NULL "
                "DEFAULT 'manual' CHECK (intake_source IN ('manual', 'ai_live', 'ai_replay'))"
            )
        if "reconstructed_from" not in columns:
            conn.execute("ALTER TABLE training_events ADD COLUMN reconstructed_from TEXT NULL")
        conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")


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


def _reviewed_state(conn: sqlite3.Connection, event_id: str, revision: int) -> EventStatus:
    """Status of the event, refusing if it changed since the caller's copy (revision)."""
    row = conn.execute(
        "SELECT status, revision FROM training_events WHERE event_id = ?", (event_id,)
    ).fetchone()
    if row is None:
        raise StoreError(f"unknown event {event_id}")
    if row["revision"] != revision:
        raise StoreError(f"{event_id} changed since it was reviewed; review it again")
    return EventStatus(row["status"])


def _require_draft(conn: sqlite3.Connection, event_id: str, revision: int) -> None:
    status = _reviewed_state(conn, event_id, revision)
    if status is not EventStatus.DRAFT:
        raise StoreError(f"{event_id} is {status}, no longer a draft")


def _reconstruction_sources(source_ids: Sequence[str]) -> str:
    return json.dumps(sorted(source_ids), separators=(",", ":"))


def find_reconstruction(
    conn: sqlite3.Connection, source_ids: Sequence[str]
) -> TrainingEvent | None:
    row = conn.execute(
        "SELECT event_id FROM training_events "
        "WHERE reconstructed_from = ? AND status IN ('draft', 'approved') LIMIT 1",
        (_reconstruction_sources(source_ids),),
    ).fetchone()
    return get_event(conn, row["event_id"]) if row is not None else None


def live_reconstruction_for_source(conn: sqlite3.Connection, event_id: str) -> TrainingEvent | None:
    rows = conn.execute(
        "SELECT event_id, reconstructed_from FROM training_events "
        "WHERE reconstructed_from IS NOT NULL AND status IN ('draft', 'approved') "
        "ORDER BY CASE status WHEN 'approved' THEN 0 ELSE 1 END, event_id"
    ).fetchall()
    for row in rows:
        if event_id in json.loads(row["reconstructed_from"]):
            return get_event(conn, row["event_id"])
    return None


def save_draft(
    conn: sqlite3.Connection,
    draft: TrainingEventDraft,
    event_id: str | None = None,
    intake_source: IntakeSource = IntakeSource.MANUAL,
    *,
    reconstructed_from: Sequence[str] | None = None,
) -> str:
    if draft.event_date > date.today():
        raise StoreError("event date cannot be in the future")
    if event_id is None:
        event_id = f"EVT-{uuid4().hex[:8].upper()}"
    with _transaction(conn):
        # Checked inside the write transaction so two tabs cannot both create one.
        for source_id in reconstructed_from or ():
            existing = live_reconstruction_for_source(conn, source_id)
            if existing is not None:
                raise ReconstructionExists(existing.event_id)
        conn.execute(
            "INSERT INTO training_events (event_id, status, event_date, event_type, "
            "training_context, weapon_system_id, weapon_name, location_unit, created_at, "
            "decided_at, revision, intake_source, reconstructed_from) "
            "VALUES (?, 'draft', ?, ?, ?, ?, ?, ?, ?, NULL, 1, ?, ?)",
            (
                event_id,
                *_event_columns(draft),
                _now(),
                intake_source,
                _reconstruction_sources(reconstructed_from)
                if reconstructed_from is not None
                else None,
            ),
        )
        _write_draft(conn, event_id, draft)
    return event_id


def seed_demo_events(
    conn: sqlite3.Connection, events: Iterable[tuple[str, TrainingEventDraft]]
) -> int:
    added = 0
    for event_id, draft in events:
        row = conn.execute(
            "SELECT status, revision FROM training_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        if row is None:
            try:
                save_draft(conn, draft, event_id)
            except sqlite3.IntegrityError:
                row = conn.execute(
                    "SELECT status, revision FROM training_events WHERE event_id = ?", (event_id,)
                ).fetchone()
                if row is None:
                    raise
            else:
                added += 1
                row = conn.execute(
                    "SELECT status, revision FROM training_events WHERE event_id = ?", (event_id,)
                ).fetchone()
        if row is not None and row["status"] == EventStatus.DRAFT:
            approve_event(conn, event_id, row["revision"])
    return added


def seed_demo_drafts(
    conn: sqlite3.Connection,
    drafts: Iterable[tuple[str, TrainingEventDraft, IntakeSource]],
) -> int:
    added = 0
    for event_id, draft, source in drafts:
        row = conn.execute(
            "SELECT 1 FROM training_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if row is None:
            save_draft(conn, draft, event_id, intake_source=source)
            added += 1
    return added


def reset_demo(
    conn: sqlite3.Connection,
    people: Iterable[Person],
    events: Iterable[tuple[str, TrainingEventDraft]],
    symptoms: Iterable[tuple[str, SymptomReportDraft]],
    drafts: Iterable[tuple[str, TrainingEventDraft, IntakeSource]] = (),
) -> None:
    with _transaction(conn):
        conn.execute("DELETE FROM symptom_reports")
        conn.execute("DELETE FROM participant_exposures")
        conn.execute("DELETE FROM crew_members")
        conn.execute("DELETE FROM crews")
        conn.execute("DELETE FROM training_events")
    seed_people(conn, people)
    seed_demo_events(conn, events)
    seed_demo_symptoms(conn, symptoms)
    seed_demo_drafts(conn, drafts)


def update_draft(
    conn: sqlite3.Connection, event_id: str, draft: TrainingEventDraft, revision: int
) -> None:
    """Replace a draft's content and crews; the revision advances so stale reviews are refused."""
    if draft.event_date > date.today():
        raise StoreError("event date cannot be in the future")
    with _transaction(conn):
        _require_draft(conn, event_id, revision)
        conn.execute(
            "DELETE FROM crew_members WHERE crew_id IN "
            "(SELECT crew_id FROM crews WHERE event_id = ?)",
            (event_id,),
        )
        conn.execute("DELETE FROM crews WHERE event_id = ?", (event_id,))
        conn.execute(
            "UPDATE training_events SET event_date = ?, event_type = ?, training_context = ?, "
            "weapon_system_id = ?, weapon_name = ?, location_unit = ?, revision = revision + 1 "
            "WHERE event_id = ?",
            (*_event_columns(draft), event_id),
        )
        _write_draft(conn, event_id, draft)


def reject_event(conn: sqlite3.Connection, event_id: str, revision: int) -> None:
    with _transaction(conn):
        _require_draft(conn, event_id, revision)
        conn.execute(
            "UPDATE training_events SET status = 'rejected', decided_at = ? WHERE event_id = ?",
            (_now(), event_id),
        )


def approve_event(conn: sqlite3.Connection, event_id: str, revision: int) -> bool:
    """Approve exactly the reviewed revision of a draft, atomically.

    Returns False if that revision was already approved (no new history).
    """
    with _transaction(conn):
        status = _reviewed_state(conn, event_id, revision)
        if status is EventStatus.APPROVED:
            return False
        if status is not EventStatus.DRAFT:
            raise StoreError(f"{event_id} is {status}, not a draft")
        replacement = live_reconstruction_for_source(conn, event_id)
        if replacement is not None and replacement.status is EventStatus.APPROVED:
            raise StoreError(
                f"{event_id} was replaced by approved reconstruction {replacement.event_id}; "
                "reject it instead"
            )
        event = get_event(conn, event_id)
        for source_id in event.reconstructed_from or ():
            source = conn.execute(
                "SELECT status FROM training_events WHERE event_id = ?", (source_id,)
            ).fetchone()
            if source is not None and source["status"] == EventStatus.APPROVED:
                raise StoreError("a source of this reconstruction is already approved")
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
    return TrainingEvent(
        event_id=event_id,
        status=row["status"],
        intake_source=row["intake_source"],
        reconstructed_from=(
            tuple(json.loads(row["reconstructed_from"]))
            if row["reconstructed_from"] is not None
            else None
        ),
        revision=row["revision"],
        draft=draft,
    )


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
        "e.weapon_system_id, "
        "e.location_unit, e.intake_source, c.crew_name, x.position, x.participation_role, "
        "c.physical_event_count "
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


def confirm_symptom_report(
    conn: sqlite3.Connection, draft: SymptomReportDraft, report_id: str | None = None
) -> str:
    with _transaction(conn):
        if draft.report_date > date.today():
            raise StoreError("report date cannot be in the future")
        if get_person(conn, draft.person_id) is None:
            raise StoreError("the report person does not exist")
        if draft.event_id is not None:
            event = conn.execute(
                "SELECT status, event_date FROM training_events WHERE event_id = ?",
                (draft.event_id,),
            ).fetchone()
            if event is None or event["status"] != EventStatus.APPROVED:
                raise StoreError("a linked event must be approved")
            if (
                conn.execute(
                    "SELECT 1 FROM participant_exposures WHERE event_id = ? AND person_id = ?",
                    (draft.event_id, draft.person_id),
                ).fetchone()
                is None
            ):
                raise StoreError("the person must have participated in the linked event")
            if (
                draft.temporal_relationship is TemporalRelationship.AFTER_RECORDED_EVENT
                and draft.report_date < date.fromisoformat(event["event_date"])
            ):
                raise StoreError("a report after a recorded event cannot predate that event")
        if report_id is None:
            report_id = f"SYM-{uuid4().hex[:8].upper()}"
        conn.execute(
            "INSERT INTO symptom_reports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                report_id,
                draft.person_id,
                draft.event_id,
                draft.report_date.isoformat(),
                draft.source,
                json.dumps(draft.symptoms),
                json.dumps(draft.danger_signs),
                draft.note,
                draft.temporal_relationship,
                draft.persistence,
                draft.functional_impact,
                _now(),
            ),
        )
    return report_id


def list_symptom_reports(
    conn: sqlite3.Connection, person_id: str | None = None
) -> list[SymptomReport]:
    rows = conn.execute(
        "SELECT * FROM symptom_reports "
        + ("WHERE person_id = ? " if person_id is not None else "")
        + "ORDER BY report_date DESC, confirmed_at DESC",
        (person_id,) if person_id is not None else (),
    ).fetchall()
    reports = []
    for row in rows:
        values = dict(row)
        report_id = values.pop("report_id")
        confirmed_at = values.pop("confirmed_at")
        values["report_date"] = date.fromisoformat(values["report_date"])
        values["symptoms"] = tuple(json.loads(values["symptoms"]))
        values["danger_signs"] = tuple(json.loads(values["danger_signs"]))
        reports.append(
            SymptomReport(
                report_id=report_id,
                draft=SymptomReportDraft(**values),
                confirmed_at=confirmed_at,
            )
        )
    return reports


def seed_demo_symptoms(
    conn: sqlite3.Connection, reports: Iterable[tuple[str, SymptomReportDraft]]
) -> int:
    added = 0
    for report_id, draft in reports:
        if conn.execute(
            "SELECT 1 FROM symptom_reports WHERE report_id = ?", (report_id,)
        ).fetchone():
            continue
        try:
            confirm_symptom_report(conn, draft, report_id)
        except sqlite3.IntegrityError:
            if (
                conn.execute(
                    "SELECT 1 FROM symptom_reports WHERE report_id = ?", (report_id,)
                ).fetchone()
                is None
            ):
                raise
        else:
            added += 1
    return added
