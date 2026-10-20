"""Occupational-date features and source-separated readiness precedence."""

import inspect
from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pytest

from blastbridge.models.enums import EventType
from blastbridge.models.training_tempo import ParticipationRole, TrainingContext
from blastbridge.product.followup import FollowUpState
from blastbridge.product.models import CrewPosition, HistoryEntry, IntakeSource
from blastbridge.product.patterns import (
    ELEVATION_FEATURES,
    ELEVATION_QUANTILE,
    FEATURE_NAMES,
    REFERENCE_DIR,
    PatternResult,
    PatternStatus,
    assess_pattern,
    fit_pattern_model,
    load_reference,
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
from scripts.build_himars_reference import (
    build_reference_rows,
    reference_csv,
    reference_fingerprint,
)
from scripts.eval_patterns import sanity_histories, semantic_cases

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
        weapon_system_id="m142-himars",
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
    anomalous = status in (
        PatternStatus.ATYPICAL_REDUCED_ACTIVITY,
        PatternStatus.ATYPICAL_ELEVATED_ACTIVITY,
    )
    return PatternResult(
        status=status,
        score=(
            None if status is PatternStatus.PATTERN_NOT_AVAILABLE else (-0.7 if anomalous else -0.2)
        ),
        threshold=None if status is PatternStatus.PATTERN_NOT_AVAILABLE else -0.5,
        analysis_as_of=AS_OF,
        comparisons=(),
        differing=(),
        anomalous=anomalous,
        elevated_features=("events_90d",)
        if status is PatternStatus.ATYPICAL_ELEVATED_ACTIVITY
        else (),
        reason=(
            "pattern reference unavailable"
            if status is PatternStatus.PATTERN_NOT_AVAILABLE
            else None
        ),
    )


def test_occupational_features_use_only_distinct_dates():
    days = days_before(400, 365, 100, 90, 30, 14, 13, 1, 0, 0)
    expected = (4, 5, 7, 0, 3, 13 / 9)
    assert occupational_features(days, AS_OF) == pytest.approx(expected)
    assert occupational_features(days + days_before(-1), AS_OF) == pytest.approx(expected)
    assert occupational_features([], AS_OF) == (0, 0, 0, 730, 0, 0)
    assert occupational_features(days_before(30), AS_OF)[:2] == (0, 1)
    assert occupational_features(days_before(29), AS_OF)[:2] == (1, 1)
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


def test_committed_fictional_himars_reference_is_reproducible():
    built = build_reference_rows()
    assert built == build_reference_rows()
    csv_bytes = reference_csv(built).encode("utf-8")
    assert (REFERENCE_DIR / "reference_features.csv").read_bytes() == csv_bytes
    rows, metadata = load_reference()
    assert metadata["fingerprint"] == reference_fingerprint(csv_bytes)
    first = fit_pattern_model(rows, metadata)
    second = fit_pattern_model(rows, metadata)
    assert first.threshold == second.threshold
    for days in (days_before(500, 300, 180, 60), days_before(500, 11, 8, 5, 3, 1), []):
        entries = [history_entry(day, None) for day in days]
        assert assess_pattern(first, entries, AS_OF).score == (
            assess_pattern(second, entries, AS_OF).score
        )
    first_scores = first.forest.score_samples(rows)
    assert np.array_equal(first_scores, second.forest.score_samples(rows))
    flagged_share = float(np.mean(first_scores < first.threshold))
    assert 0.04 <= flagged_share <= 0.06


def test_pre_registered_sanity_gates_and_scope_coverage():
    rows, metadata = load_reference()
    model = fit_pattern_model(rows, metadata)
    for name, entries, expected in sanity_histories():
        result = assess_pattern(model, entries, AS_OF)
        assert result.status is expected, (name, result)
        if expected is PatternStatus.PATTERN_NOT_AVAILABLE:
            assert result.score is None and result.threshold is None
            assert result.comparisons == () and result.differing == ()
    _, applicable, _ = sanity_histories()[0]
    unavailable = assess_pattern(None, applicable, AS_OF)
    assert unavailable.reason == "pattern reference unavailable"
    assert unavailable.status is PatternStatus.PATTERN_NOT_AVAILABLE
    for offsets, weapon, reason in (
        ((200, 10), "m142-himars", "recorded history shorter than the 365-day comparison window"),
        ((600, 400), "m142-himars", "no HIMARS record in the prior 365 days"),
        ((600, 10), "m270-mlrs", "outside the HIMARS prototype scope"),
    ):
        entries = [
            history_entry(day, None).model_copy(update={"weapon_system_id": weapon})
            for day in days_before(*offsets)
        ]
        result = assess_pattern(model, entries, AS_OF)
        assert result.reason == reason
        assert result.status is PatternStatus.PATTERN_NOT_AVAILABLE
    other = history_entry(AS_OF, 999).model_copy(update={"weapon_system_id": "m270-mlrs"})
    original = assess_pattern(model, applicable, AS_OF)
    mixed = assess_pattern(model, applicable + [other], AS_OF)
    assert mixed.excluded_non_scope_records == 1
    assert mixed.comparisons == original.comparisons
    assert mixed.score == original.score
    future = history_entry(AS_OF + timedelta(days=1), 1)
    assert assess_pattern(model, applicable + [future], AS_OF) == original


def test_readiness_precedence_and_future_reports():
    atypical = pattern(PatternStatus.ATYPICAL_ELEVATED_ACTIVITY)
    ml_only = assess_readiness(PERSON_ID, [], [], atypical, AS_OF)
    assert ml_only.overall_readiness_status is ReadinessStatus.REVIEW_PRIORITY
    followup = assess_readiness(PERSON_ID, [], [report()], atypical, AS_OF)
    assert followup.overall_readiness_status is ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED
    assert followup.symptom_followup_status is FollowUpState.FOLLOW_UP_SUGGESTED
    for status in PatternStatus:
        result = assess_readiness(PERSON_ID, [], [], pattern(status), AS_OF)
        if status is PatternStatus.PATTERN_NOT_AVAILABLE:
            assert result.overall_readiness_status is ReadinessStatus.ROUTINE_MONITORING
            assert any("comparison not available" in line for line in result.evidence_lines)
        if status is PatternStatus.ATYPICAL_REDUCED_ACTIVITY:
            assert result.overall_readiness_status is ReadinessStatus.ROUTINE_MONITORING
            assert any("not a review signal" in line for line in result.evidence_lines)
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


def test_pre_registered_directional_semantics_and_future_leakage():
    rows, metadata = load_reference()
    model = fit_pattern_model(rows, metadata)
    assert ELEVATION_QUANTILE == 0.95
    assert model.elevation_bounds == {
        name: float(np.quantile(rows[:, FEATURE_NAMES.index(name)], 0.95))
        for name in ELEVATION_FEATURES
    }
    assert "days_since_previous_event" not in model.elevation_bounds
    cases = {case.case_id: case for case in semantic_cases()}
    results = {}
    readiness = {}
    for case in cases.values():
        result = assess_pattern(model, case.entries, AS_OF)
        overall = assess_readiness("FIC-EVAL", case.entries, case.reports, result, AS_OF)
        assert result.status in case.expected_patterns, (case.case_id, result)
        assert overall.overall_readiness_status is case.expected_readiness, case.case_id
        if result.score is not None:
            assert result.anomalous == (result.score < result.threshold)
        if result.status is PatternStatus.ATYPICAL_ELEVATED_ACTIVITY:
            assert result.anomalous and result.elevated_features
            values = {item.name: item.value for item in result.comparisons}
            assert result.elevated_features == tuple(
                name for name in ELEVATION_FEATURES if values[name] > model.elevation_bounds[name]
            )
        else:
            assert not result.elevated_features
        results[case.case_id] = result
        readiness[case.case_id] = overall
    assert results["J"].comparisons == results["E"].comparisons
    assert results["J"].excluded_non_scope_records == sum(
        entry.weapon_system_id == "m270-mlrs" for entry in cases["J"].entries
    )
    assert results["K"] == results["C"]
    assert readiness["K"] == readiness["C"]

    # Equality at every bound is not elevated; a strict exceedance is required.
    values = {item.name: item.value for item in results["E"].comparisons}
    equal_bounds = {name: values[name] for name in ELEVATION_FEATURES}
    equal = assess_pattern(replace(model, elevation_bounds=equal_bounds), cases["E"].entries, AS_OF)
    assert equal.anomalous and equal.status is PatternStatus.ATYPICAL_REDUCED_ACTIVITY
    exceeded = {**equal_bounds, "events_30d": float(np.nextafter(values["events_30d"], -np.inf))}
    strict = assess_pattern(replace(model, elevation_bounds=exceeded), cases["E"].entries, AS_OF)
    assert strict.status is PatternStatus.ATYPICAL_ELEVATED_ACTIVITY
    assert strict.elevated_features == ("events_30d",)
