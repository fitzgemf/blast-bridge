"""Separate occupational-pattern context from existing report-guidance rules."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from .followup import FollowUpState, evaluate
from .models import HistoryEntry
from .patterns import PatternResult, PatternStatus, unknown_count_fraction
from .symptoms import SymptomReport


class ReadinessStatus(StrEnum):
    ROUTINE_MONITORING = "routine_monitoring"
    REVIEW_PRIORITY = "review_priority"
    MEDICAL_FOLLOWUP_RECOMMENDED = "medical_followup_recommended"
    URGENT_EVALUATION = "urgent_evaluation"

    @property
    def label(self) -> str:
        return {
            self.ROUTINE_MONITORING: "Routine monitoring",
            self.REVIEW_PRIORITY: "Review priority",
            self.MEDICAL_FOLLOWUP_RECOMMENDED: "Medical follow-up recommended",
            self.URGENT_EVALUATION: "Urgent evaluation",
        }[self]


ATTENTION_PRECEDENCE: dict[ReadinessStatus, int] = {
    ReadinessStatus.URGENT_EVALUATION: 0,
    ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED: 1,
    ReadinessStatus.REVIEW_PRIORITY: 2,
}


@dataclass(frozen=True)
class ReadinessAssessment:
    person_id: str
    analysis_as_of: date
    ml_pattern: PatternResult | None
    symptom_followup_status: FollowUpState | None
    urgent_status: bool
    data_quality_notes: tuple[str, ...]
    overall_readiness_status: ReadinessStatus
    evidence_lines: tuple[str, ...]


def assess_readiness(
    person_id: str,
    history: Sequence[HistoryEntry],
    reports: Sequence[SymptomReport],
    pattern: PatternResult | None,
    analysis_as_of: date,
) -> ReadinessAssessment:
    visible_history = [entry for entry in history if entry.event_date <= analysis_as_of]
    recent = [
        entry
        for entry in visible_history
        if entry.event_date > analysis_as_of - timedelta(days=365)
    ]
    notes = []
    fraction = unknown_count_fraction(visible_history, analysis_as_of)
    if fraction is not None and fraction > 0:
        unknown = sum(entry.physical_event_count is None for entry in recent)
        notes.append(
            f"{unknown} of {len(recent)} records in the prior 365 days have an unknown activity "
            "count (not used by the pattern model)"
        )
    event_days = {entry.event_date for entry in recent}
    if len(event_days) <= 1:
        notes.append(
            f"Limited recorded history: {len(event_days)} occupational events in the prior 365 days"
        )
    if not visible_history:
        notes.append("No approved occupational records")

    states = []
    evidence = []
    for report in sorted(reports, key=lambda item: item.draft.report_date, reverse=True):
        draft = report.draft
        if draft.person_id != person_id or draft.report_date > analysis_as_of:
            continue
        state = evaluate(draft).state
        states.append(state)
        recorded = f"{draft.report_date.day} {draft.report_date:%b %Y}"
        if state is FollowUpState.URGENT_EVALUATION_RECOMMENDED:
            evidence.append(f"Danger sign (CDC): recorded {recorded}")
        elif state is FollowUpState.FOLLOW_UP_SUGGESTED:
            evidence.append(
                "Symptom guidance (TBICoE): persistent, function-affecting symptoms reported "
                + recorded
            )

    elevated = pattern is not None and pattern.status is PatternStatus.ATYPICAL_ELEVATED_ACTIVITY
    if pattern is not None:
        if pattern.status is PatternStatus.PATTERN_NOT_AVAILABLE:
            evidence.append(
                f"Occupational pattern (ML): comparison not available — {pattern.reason}"
            )
        elif pattern.status is PatternStatus.ATYPICAL_REDUCED_ACTIVITY:
            evidence.append(
                "Occupational pattern (ML): unusual lower activity — informational only, "
                "not a review signal"
            )
        else:
            evidence.append(
                "Occupational pattern (ML): atypical elevated cadence vs the SME-informed "
                "fictional HIMARS scenario reference"
                if elevated
                else "Occupational pattern (ML): typical recorded pattern"
            )
        if pattern.excluded_non_scope_records:
            notes.append(
                f"{pattern.excluded_non_scope_records} non-HIMARS records excluded from "
                "the prototype occupational-pattern comparison"
            )
    urgent = FollowUpState.URGENT_EVALUATION_RECOMMENDED in states
    followup: FollowUpState | None
    if urgent:
        followup = FollowUpState.URGENT_EVALUATION_RECOMMENDED
        overall = ReadinessStatus.URGENT_EVALUATION
    elif FollowUpState.FOLLOW_UP_SUGGESTED in states:
        followup = FollowUpState.FOLLOW_UP_SUGGESTED
        overall = ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED
    else:
        followup = FollowUpState.NO_FOLLOWUP_RULE_TRIGGERED if states else None
        overall = (
            ReadinessStatus.REVIEW_PRIORITY if elevated else ReadinessStatus.ROUTINE_MONITORING
        )
    return ReadinessAssessment(
        person_id=person_id,
        analysis_as_of=analysis_as_of,
        ml_pattern=pattern,
        symptom_followup_status=followup,
        urgent_status=urgent,
        data_quality_notes=tuple(notes),
        overall_readiness_status=overall,
        evidence_lines=tuple(evidence),
    )
