"""Report pre-registered fictional HIMARS cadence hypotheses without tuning."""

import json
import random
from datetime import date, timedelta

import numpy as np

from blastbridge.models.enums import EventType
from blastbridge.models.training_tempo import ParticipationRole, TrainingContext
from blastbridge.product import store
from blastbridge.product.models import CrewPosition, HistoryEntry, IntakeSource
from blastbridge.product.patterns import (
    COVERAGE_RULE,
    DELIBERATELY_EXCLUDED,
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
from blastbridge.product.seed import DEMO_EVENTS, DEMO_PEOPLE

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
    atypical = PatternStatus.ATYPICAL_OCCUPATIONAL_PATTERN
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
