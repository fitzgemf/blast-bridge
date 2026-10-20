"""Occupational-date features and source-separated readiness precedence."""

import inspect
from datetime import date, timedelta

import numpy as np
import pytest

from blastbridge.models.enums import EventType
from blastbridge.models.training_tempo import ParticipationRole, TrainingContext
from blastbridge.product.followup import FollowUpState
from blastbridge.product.models import CrewPosition, HistoryEntry, IntakeSource
from blastbridge.product.patterns import (
    FEATURE_NAMES,
    PatternResult,
    PatternStatus,
    assess_pattern,
    fit_pattern_model,
    load_baseline,
    occupational_features,
    unknown_count_fraction,
)
from blastbridge.product.readiness import ReadinessStatus, assess_readiness
from blastbridge.product.symptoms import (
    DangerSign,
    FunctionalImpact,
    Persistence,
    Symptom,
    SymptomReport,
    SymptomReportDraft,
    SymptomSource,
    TemporalRelationship,
)

AS_OF = date(2026, 10, 19)
PERSON_ID = "FIC-001"


def days_before(*offsets):
    return [AS_OF - timedelta(days=offset) for offset in offsets]


def history_entry(day, count):
    return HistoryEntry(
        event_id=f"EVT-FICTIONAL-{day.isoformat()}",
        intake_source=IntakeSource.MANUAL,
        event_date=day,
        event_type=EventType.WEAPON_FIRING,
        training_context=TrainingContext.QUALIFICATION,
        weapon_name="Fictional demo system",
        location_unit="Fictional demo location",
        crew_name="Fictional crew",
        position=CrewPosition.CHIEF,
        participation_role=ParticipationRole.SECTION_CHIEF,
        physical_event_count=count,
    )


def report(day=AS_OF, danger=False):
    return SymptomReport(
        report_id="SYM-FICTIONAL",
        confirmed_at="2026-10-19T00:00:00+00:00",
        draft=SymptomReportDraft(
            person_id=PERSON_ID,
            report_date=day,
            source=SymptomSource.SELF_REPORTED,
            symptoms=(Symptom.HEADACHES,),
            danger_signs=(DangerSign.REPEATED_VOMITING,) if danger else (),
            temporal_relationship=TemporalRelationship.NOT_LINKED_TO_EVENT,
            persistence=Persistence.STILL_PRESENT,
            functional_impact=FunctionalImpact.YES,
        ),
    )


def pattern(status):
    return PatternResult(
        status=status,
        score=-0.7 if status is PatternStatus.ATYPICAL_OCCUPATIONAL_PATTERN else -0.2,
        threshold=-0.5,
        analysis_as_of=AS_OF,
        comparisons=(),
        differing=(),
    )


def test_occupational_features_use_only_distinct_dates():
    days = days_before(400, 365, 100, 90, 30, 14, 13, 1, 0, 0)
    expected = (4, 5, 7, 0, 3, 13 / 9)
    assert occupational_features(days, AS_OF) == pytest.approx(expected)
    assert occupational_features(days + days_before(-1), AS_OF) == pytest.approx(expected)
    assert occupational_features([], AS_OF) == (0, 0, 0, 730, 0, 0)
    assert tuple(inspect.signature(occupational_features).parameters) == (
        "event_days",
        "analysis_as_of",
    )
    assert len(FEATURE_NAMES) == 6
    assert not any(
        term in name for name in FEATURE_NAMES for term in ("symptom", "medical", "count")
    )


def test_unknown_counts_are_data_quality_only():
    assert unknown_count_fraction([], AS_OF) is None
    entries = [
        history_entry(AS_OF - timedelta(days=20), None),
        history_entry(AS_OF - timedelta(days=100), 6),
        history_entry(AS_OF - timedelta(days=365), None),
        history_entry(AS_OF + timedelta(days=1), None),
    ]
    assert unknown_count_fraction(entries, AS_OF) == 0.5
    known = [entry.model_copy(update={"physical_event_count": 6}) for entry in entries]
    assert occupational_features([entry.event_date for entry in entries], AS_OF) == (
        occupational_features([entry.event_date for entry in known], AS_OF)
    )
    readiness = assess_readiness(PERSON_ID, entries, [], None, AS_OF)
    assert any("1 of 2 records" in note for note in readiness.data_quality_notes)


def test_committed_fictional_simulation_baseline_is_reproducible():
    rows, metadata = load_baseline()
    first = fit_pattern_model(rows, metadata)
    second = fit_pattern_model(rows, metadata)
    assert first.threshold == second.threshold
    for days in (days_before(300, 180, 60), days_before(11, 8, 5, 3, 1), []):
        assert assess_pattern(first, days, AS_OF).score == assess_pattern(second, days, AS_OF).score
    first_scores = first.forest.score_samples(rows)
    assert np.array_equal(first_scores, second.forest.score_samples(rows))
    flagged_share = float(np.mean(first_scores < first.threshold))
    assert 0.04 <= flagged_share <= 0.06


def test_readiness_precedence_and_future_reports():
    atypical = pattern(PatternStatus.ATYPICAL_OCCUPATIONAL_PATTERN)
    ml_only = assess_readiness(PERSON_ID, [], [], atypical, AS_OF)
    assert ml_only.overall_readiness_status is ReadinessStatus.REVIEW_PRIORITY
    followup = assess_readiness(PERSON_ID, [], [report()], atypical, AS_OF)
    assert followup.overall_readiness_status is ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED
    assert followup.symptom_followup_status is FollowUpState.FOLLOW_UP_SUGGESTED
    for status in PatternStatus:
        result = assess_readiness(PERSON_ID, [], [], pattern(status), AS_OF)
        assert result.overall_readiness_status not in (
            ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED,
            ReadinessStatus.URGENT_EVALUATION,
        )
        urgent = assess_readiness(
            PERSON_ID,
            [],
            [report(), report(danger=True)],
            pattern(status),
            AS_OF,
        )
        assert urgent.overall_readiness_status is ReadinessStatus.URGENT_EVALUATION
        assert urgent.urgent_status
    future = assess_readiness(
        PERSON_ID,
        [],
        [report(day=AS_OF + timedelta(days=1), danger=True)],
        atypical,
        AS_OF,
    )
    assert future.overall_readiness_status is ReadinessStatus.REVIEW_PRIORITY
    assert future.symptom_followup_status is None and not future.urgent_status
