"""Recorded calendar marks and small contextual-entry presentation helpers."""

from calendar import Calendar
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date

from .followup import FollowUpState, evaluate
from .models import EventStatus, HistoryEntry, TrainingEvent
from .readiness import ReadinessStatus
from .symptoms import SymptomReport

DEMO_STORY_DATE = date(2026, 10, 19)


def month_weeks(year: int, month: int) -> list[list[date | None]]:
    return [
        [date(year, month, day) if day else None for day in week]
        for week in Calendar(firstweekday=6).monthdayscalendar(year, month)
    ]


def can_record_on(day: date, today: date) -> bool:
    return day <= today


def calendar_form_values(day: date) -> dict[str, object]:
    """Prefill only; this helper has no persistence access."""
    return {"f_date": day}


def next_action(status: ReadinessStatus) -> str:
    return {
        ReadinessStatus.URGENT_EVALUATION: (
            "An urgent danger sign was recorded. Follow the emergency guidance in Follow-up."
        ),
        ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED: (
            "Medical follow-up recommended: persistent, function-affecting symptoms were reported."
        ),
        ReadinessStatus.REVIEW_PRIORITY: (
            "Recent HIMARS training cadence differs from the fictional scenario reference. "
            "Review the record."
        ),
        ReadinessStatus.ROUTINE_MONITORING: (
            "No current rule-based or pattern signal from the recorded information."
        ),
    }[status]


@dataclass(frozen=True)
class DayMarks:
    training: int = 0
    symptom: int = 0
    attention: bool = False
    urgent: bool = False
    people: frozenset[str] = frozenset()


def organization_marks(
    events: Sequence[TrainingEvent],
    reports: Sequence[SymptomReport],
    analysis_as_of: date,
) -> dict[date, DayMarks]:
    marks: dict[date, DayMarks] = {}
    for event in events:
        if event.status is not EventStatus.APPROVED:
            continue
        day = event.draft.event_date
        people = frozenset(
            member.person_id for crew in event.draft.crews for member in crew.members
        )
        current = marks.get(day, DayMarks())
        marks[day] = replace(
            current,
            training=current.training + 1,
            people=current.people | people,
        )
    for report in reports:
        day = report.draft.report_date
        if (
            day <= analysis_as_of
            and evaluate(report.draft).state is FollowUpState.URGENT_EVALUATION_RECOMMENDED
        ):
            marks[day] = replace(marks.get(day, DayMarks()), urgent=True)
    return marks


def person_marks(
    history: Sequence[HistoryEntry], reports: Sequence[SymptomReport], analysis_as_of: date
) -> dict[date, DayMarks]:
    marks: dict[date, DayMarks] = {}
    for entry in history:
        current = marks.get(entry.event_date, DayMarks())
        marks[entry.event_date] = replace(current, training=current.training + 1)
    for report in reports:
        day = report.draft.report_date
        state = evaluate(report.draft).state
        current = marks.get(day, DayMarks())
        marks[day] = replace(
            current,
            symptom=current.symptom + 1,
            urgent=day <= analysis_as_of
            and (current.urgent or state is FollowUpState.URGENT_EVALUATION_RECOMMENDED),
            people=current.people | frozenset((report.draft.person_id,)),
        )
    return marks
