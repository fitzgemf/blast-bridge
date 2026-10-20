"""Recorded calendar marks; readiness assessments are supplied, never predicted here."""

from calendar import Calendar
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date

from .followup import FollowUpState, evaluate
from .models import EventStatus, HistoryEntry, TrainingEvent
from .readiness import ReadinessAssessment, ReadinessStatus
from .symptoms import SymptomReport

DEMO_STORY_DATE = date(2026, 10, 19)


def month_weeks(year: int, month: int) -> list[list[date | None]]:
    return [
        [date(year, month, day) if day else None for day in week]
        for week in Calendar(firstweekday=6).monthdayscalendar(year, month)
    ]


def can_record_on(day: date, today: date) -> bool:
    return day <= today


@dataclass(frozen=True)
class DayMarks:
    training: int = 0
    symptom: int = 0
    attention: bool = False
    urgent: bool = False
    people: frozenset[str] = frozenset()


def organization_marks(
    events: Sequence[TrainingEvent],
    assessments: Mapping[str, ReadinessAssessment],
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
        statuses = [
            assessments[person].overall_readiness_status
            for person in people
            if person in assessments
        ]
        current = marks.get(day, DayMarks())
        marks[day] = replace(
            current,
            training=current.training + 1,
            attention=day <= analysis_as_of
            and (
                current.attention
                or any(
                    status
                    in (
                        ReadinessStatus.REVIEW_PRIORITY,
                        ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED,
                    )
                    for status in statuses
                )
            ),
            urgent=day <= analysis_as_of
            and (current.urgent or ReadinessStatus.URGENT_EVALUATION in statuses),
            people=current.people | people,
        )
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
            attention=day <= analysis_as_of
            and (current.attention or state is FollowUpState.FOLLOW_UP_SUGGESTED),
            urgent=day <= analysis_as_of
            and (current.urgent or state is FollowUpState.URGENT_EVALUATION_RECOMMENDED),
            people=current.people | frozenset((report.draft.person_id,)),
        )
    return marks
