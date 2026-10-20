"""Report pre-registered fictional HIMARS cadence hypotheses without tuning."""

import json
import random
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from blastbridge.models.enums import EventType
from blastbridge.models.training_tempo import ParticipationRole, TrainingContext
from blastbridge.product import store
from blastbridge.product.models import CrewPosition, HistoryEntry, IntakeSource
from blastbridge.product.patterns import (
    COVERAGE_RULE,
    DELIBERATELY_EXCLUDED,
    ELEVATION_RULE_TEXT,
    FEATURE_NAMES,
    HIMARS_SCOPE,
    MODEL_PARAMS,
    PATTERN_DISCLAIMER,
    REFERENCE_DIR,
    REFERENCE_LABEL,
    PatternStatus,
    assess_pattern,
    fit_pattern_model,
    load_baseline,
    load_reference,
    occupational_features,
)
from blastbridge.product.readiness import ReadinessStatus, assess_readiness
from blastbridge.product.seed import DEMO_EVENTS, DEMO_PEOPLE
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

ANALYSIS_AS_OF = date(2026, 10, 19)


def fictional_entry(day: date, index: int, weapon: str = "m142-himars") -> HistoryEntry:
    return HistoryEntry(
        event_id=f"EVT-FICTIONAL-{index}",
        intake_source=IntakeSource.MANUAL,
        event_date=day,
        event_type=EventType.WEAPON_FIRING,
        training_context=TrainingContext.QUALIFICATION,
        weapon_system_id=weapon,
        weapon_name="Fictional demo system",
        location_unit="Fictional demo location",
        crew_name="Fictional crew",
        position=CrewPosition.CHIEF,
        participation_role=ParticipationRole.SECTION_CHIEF,
        physical_event_count=None,
    )


def distributed_days(rate: int, years: int = 3) -> list[date]:
    """Held-out phase .35 and jitter ±7; not drawn from the reference placement."""
    rng = random.Random(20261021 + rate)
    start = ANALYSIS_AS_OF - timedelta(days=years * 365)
    return [
        start + timedelta(days=y * 365 + round((j + 0.35) * 365 / rate) + rng.randint(-7, 7))
        for y in range(years)
        for j in range(rate)
    ]


def sanity_histories() -> list[tuple[str, list[HistoryEntry], PatternStatus]]:
    typical = PatternStatus.TYPICAL_RECORDED_PATTERN
    atypical = PatternStatus.ATYPICAL_ELEVATED_ACTIVITY
    unavailable = PatternStatus.PATTERN_NOT_AVAILABLE
    four = distributed_days(4)
    older_two = [day for day in distributed_days(2) if day <= ANALYSIS_AS_OF - timedelta(days=365)]
    scenarios = [
        ("distributed 4/year", four, "m142-himars", typical),
        ("distributed 5/year", distributed_days(5), "m142-himars", typical),
        (
            "clearly clustered recent",
            four + [ANALYSIS_AS_OF - timedelta(days=d) for d in (11, 8, 5, 2)],
            "m142-himars",
            atypical,
        ),
        (
            "sharp recent increase",
            older_two + [ANALYSIS_AS_OF - timedelta(days=d) for d in (85, 68, 51, 34, 17, 1)],
            "m142-himars",
            atypical,
        ),
        (
            "history only 200 days long",
            [ANALYSIS_AS_OF - timedelta(days=d) for d in (200, 100, 10)],
            "m142-himars",
            unavailable,
        ),
        (
            "no recent HIMARS record",
            [ANALYSIS_AS_OF - timedelta(days=d) for d in (600, 400)],
            "m142-himars",
            unavailable,
        ),
        ("M270-only history", four, "m270-mlrs", unavailable),
    ]
    return [
        (name, [fictional_entry(day, i, weapon) for i, day in enumerate(days)], expected)
        for name, days, weapon, expected in scenarios
    ]


@dataclass(frozen=True)
class SemanticCase:
    case_id: str
    title: str
    entries: list[HistoryEntry]
    reports: list[SymptomReport]
    expected_patterns: tuple[PatternStatus, ...]
    expected_readiness: ReadinessStatus


def semantic_report(*, danger: bool = False, future: bool = False) -> SymptomReport:
    return SymptomReport(
        report_id="SYM-FICTIONAL-SEMANTIC",
        confirmed_at="2026-10-19T00:00:00+00:00",
        draft=SymptomReportDraft(
            person_id="FIC-EVAL",
            report_date=ANALYSIS_AS_OF + timedelta(days=1 if future else -1),
            source=SymptomSource.SELF_REPORTED,
            symptoms=(Symptom.HEADACHES,),
            danger_signs=(DangerSign.REPEATED_VOMITING,) if danger else (),
            temporal_relationship=TemporalRelationship.NOT_LINKED_TO_EVENT,
            persistence=Persistence.STILL_PRESENT,
            functional_impact=FunctionalImpact.YES,
        ),
    )


def semantic_cases() -> list[SemanticCase]:
    """Fixed A–M adversarial histories; no demo-person evaluation enters their construction."""
    gates = sanity_histories()
    typical = (PatternStatus.TYPICAL_RECORDED_PATTERN,)
    lower_or_typical = (PatternStatus.ATYPICAL_REDUCED_ACTIVITY, *typical)
    elevated = (PatternStatus.ATYPICAL_ELEVATED_ACTIVITY,)
    unavailable = (PatternStatus.PATTERN_NOT_AVAILABLE,)
    routine = ReadinessStatus.ROUTINE_MONITORING
    review = ReadinessStatus.REVIEW_PRIORITY
    a = [
        fictional_entry(ANALYSIS_AS_OF - timedelta(days=d), i)
        for i, d in enumerate((700, 600, 500, 400, 300))
    ]
    b = [
        fictional_entry(ANALYSIS_AS_OF - timedelta(days=d), i)
        for i, d in enumerate((700, 600, 500, 400, 20))
    ]
    declining = [
        fictional_entry(ANALYSIS_AS_OF - timedelta(days=d), i)
        for i, d in enumerate((700, 657, 614, 571, 529, 486, 443, 400, 200))
    ]
    c, d, e, f = [gate[1] for gate in gates[:4]]
    mixed = e + [
        fictional_entry(ANALYSIS_AS_OF - timedelta(days=offset), 1000 + i, "m270-mlrs")
        for i, offset in enumerate(range(1, 361, 9))
    ]
    future = c + [
        fictional_entry(ANALYSIS_AS_OF + timedelta(days=offset), 1000 + offset)
        for offset in range(1, 7)
    ]
    return [
        SemanticCase("A", "Long history, one older recent event", a, [], lower_or_typical, routine),
        SemanticCase("B", "Long history, one event 20 days ago", b, [], lower_or_typical, routine),
        SemanticCase("C", "Distributed 4/year", c, [], typical, routine),
        SemanticCase("D", "Distributed 5/year", d, [], typical, routine),
        SemanticCase("E", "Tightly clustered recent", e, [], elevated, review),
        SemanticCase("F", "Sharp recent increase", f, [], elevated, review),
        SemanticCase("G", "Declining cadence", declining, [], lower_or_typical, routine),
        SemanticCase("H", "Only 200 days of history", gates[4][1], [], unavailable, routine),
        SemanticCase("I", "M270-only history", gates[6][1], [], unavailable, routine),
        SemanticCase("J", "Clustered HIMARS plus M270", mixed, [], elevated, review),
        SemanticCase(
            "K",
            "Future events and future danger sign",
            future,
            [semantic_report(danger=True, future=True)],
            typical,
            routine,
        ),
        SemanticCase(
            "L",
            "Follow-up report plus reduced history",
            a,
            [semantic_report()],
            lower_or_typical,
            ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED,
        ),
        SemanticCase(
            "M",
            "Danger sign plus clustered history",
            e,
            [semantic_report(danger=True)],
            elevated,
            ReadinessStatus.URGENT_EVALUATION,
        ),
    ]


def main() -> None:
    rows, metadata = load_reference()
    first = fit_pattern_model(rows, metadata)
    second = fit_pattern_model(rows, metadata)
    scores = np.asarray(first.forest.score_samples(rows), dtype=np.float64)
    identical = np.array_equal(scores, second.forest.score_samples(rows))
    identical = identical and first.threshold == second.threshold
    lines = [
        "# Prototype longitudinal-pattern evaluation — " + REFERENCE_LABEL,
        "",
        metadata["label"],
        "",
        PATTERN_DISCLAIMER,
        "",
        metadata["construction_route"],
        "",
        "## Reference revision",
        "",
        metadata["revision_note"],
        "",
        f"Evidence: {metadata['evidence_id']}; prior design: {metadata['prior_design_id']}.",
        f"Source wording: {metadata['source_wording']}.",
        "",
        "Source limitations:",
    ]
    lines.extend(f"- {item}" for item in metadata["source_limitations"])
    lines.extend(["", "Scenario assumptions:"])
    lines.extend(
        f"- {key}: {json.dumps(value['value'], ensure_ascii=False)} — {value['basis']}"
        for key, value in metadata["scenario_assumptions"].items()
    )
    lines.extend(
        [
            "",
            metadata["unit_mapping"],
            f"Independent fictional careers: {metadata['independent_fictional_careers']}; "
            f"repeated analysis windows: {metadata['repeated_analysis_windows']}.",
            metadata["observation_note"],
            f"Sessions per career-year: {json.dumps(metadata['sessions_per_career_year'])}.",
            f"Zero shares: {json.dumps(metadata['zero_share'], sort_keys=True)}.",
            f"Fingerprint: `{json.dumps(metadata['fingerprint'], sort_keys=True)}`.",
            f"Model parameters: `{json.dumps(MODEL_PARAMS, sort_keys=True)}`.",
            metadata["threshold_rule"],
            COVERAGE_RULE,
            ELEVATION_RULE_TEXT,
            "Elevation bounds (reference rows only; strict greater-than comparison): "
            + json.dumps(first.elevation_bounds, sort_keys=True),
            "Expected flagged reference-window share by construction: 5%. "
            f"Actual share: {float(np.mean(scores < first.threshold)) * 100:.3f}%.",
            "Two independent fits: " + ("identical." if identical else "different scores."),
            "",
            "| Feature | Median | IQR q25–q75 |",
            "| --- | --- | --- |",
        ]
    )
    for name in FEATURE_NAMES:
        summary = metadata["feature_summaries"][name]
        lines.append(
            f"| {name} | {summary['median']:.6f} | {summary['q25']:.6f}–{summary['q75']:.6f} |"
        )
    lines.extend(["", "Deliberately excluded:"])
    lines.extend(f"- {name}: {reason}" for name, reason in DELIBERATELY_EXCLUDED.items())
    lines.extend(
        [
            "",
            f"Analysis as of {ANALYSIS_AS_OF}. Expectations are pre-registered; no tuning.",
            "The clustered and increase gates were also used once to diagnose reference v1 "
            "(see Reference revision), so they are not strictly held out from v2.",
            "Held-out histories retain phase .35 and jitter ±7; they are not drawn from "
            "the reference's uniform within-year placement.",
            "",
            "| Scenario | Expected | Actual | PASS/MISMATCH | Reason |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for name, entries, expected in sanity_histories():
        result = assess_pattern(first, entries, ANALYSIS_AS_OF)
        outcome = "PASS" if result.status is expected else "MISMATCH"
        lines.append(
            f"| {name} | {expected.label} | {result.status.label} | {outcome} | "
            f"{result.reason or 'Applicable HIMARS history'} |"
        )
    lines.extend(
        [
            "",
            "## Pre-registered directional semantic cases",
            "",
            "The raw forest anomaly is separate from direction. Only elevated atypical cadence "
            "can create Review priority; reduced activity is informational.",
            "",
            "| Case | Expected pattern | Actual pattern | Expected readiness | "
            "Actual readiness | PASS/MISMATCH |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    observed = {}
    for case in semantic_cases():
        result = assess_pattern(first, case.entries, ANALYSIS_AS_OF)
        readiness = assess_readiness("FIC-EVAL", case.entries, case.reports, result, ANALYSIS_AS_OF)
        passed = (
            result.status in case.expected_patterns
            and readiness.overall_readiness_status is case.expected_readiness
        )
        if case.case_id == "J":
            passed = passed and result.comparisons == observed["E"][0].comparisons
            passed = passed and result.excluded_non_scope_records == sum(
                entry.weapon_system_id == "m270-mlrs" for entry in case.entries
            )
        elif case.case_id == "K":
            passed = passed and (result, readiness) == observed["C"]
        observed[case.case_id] = (result, readiness)
        expected = " or ".join(status.label for status in case.expected_patterns)
        lines.append(
            f"| {case.case_id}: {case.title} | {expected} | {result.status.label} | "
            f"{case.expected_readiness.label} | {readiness.overall_readiness_status.label} | "
            f"{'PASS' if passed else 'MISMATCH'} |"
        )
    lines.extend(
        [
            "",
            "There are no medical labels; this evaluation does not measure injury prediction.",
            "",
            "Seeded fictional roster (HIMARS-scope event days only):",
            "",
            "| Person | " + " | ".join(FEATURE_NAMES) + " | Status | Reason |",
            "| --- | " + " | ".join("---" for _ in FEATURE_NAMES) + " | --- | --- |",
        ]
    )
    conn = store.connect(":memory:")
    try:
        store.init_db(conn)
        store.seed_people(conn, DEMO_PEOPLE)
        store.seed_demo_events(conn, DEMO_EVENTS)
        for person in DEMO_PEOPLE:
            entries = store.member_history(conn, person.person_id)
            days = [entry.event_date for entry in entries if entry.weapon_system_id in HIMARS_SCOPE]
            features = occupational_features(days, ANALYSIS_AS_OF)
            result = assess_pattern(first, entries, ANALYSIS_AS_OF)
            values = " | ".join(f"{value:.6f}" for value in features)
            lines.append(
                f"| {person.display_name} (FICTIONAL) | {values} | {result.status.label} | "
                f"{result.reason or 'Applicable HIMARS history'} |"
            )
    finally:
        conn.close()
    sparse_rows, _ = load_baseline()
    sparse_scores = first.forest.score_samples(sparse_rows)
    lines.extend(
        [
            "",
            "V0.5 sparse demo scenario — secondary stress test only; not the reference",
            "Windows flagged by the new model: "
            f"{float(np.mean(sparse_scores < first.threshold)) * 100:.3f}%.",
        ]
    )
    report = "\n".join(lines) + "\n"
    (REFERENCE_DIR / "reference_report.md").write_text(report, encoding="utf-8", newline="\n")
    print(report)


if __name__ == "__main__":
    main()
