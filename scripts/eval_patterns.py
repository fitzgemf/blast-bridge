"""Report fixed occupational-pattern hypotheses against a fictional simulation baseline."""

import json
from datetime import date, timedelta

import numpy as np

from blastbridge.models.enums import EventType
from blastbridge.models.training_tempo import ParticipationRole, TrainingContext
from blastbridge.product import store
from blastbridge.product.models import CrewPosition, HistoryEntry, IntakeSource
from blastbridge.product.patterns import (
    ANOMALY_PERCENTILE,
    BASELINE_DIR,
    BASELINE_LABEL,
    DELIBERATELY_EXCLUDED,
    FEATURE_LABELS,
    FEATURE_NAMES,
    MODEL_PARAMS,
    PATTERN_DISCLAIMER,
    PatternStatus,
    assess_pattern,
    fit_pattern_model,
    load_baseline,
    occupational_features,
)
from blastbridge.product.readiness import assess_readiness
from blastbridge.product.seed import DEMO_EVENTS, DEMO_PEOPLE

ANALYSIS_AS_OF = date(2026, 10, 19)


def missing_count_entry(day: date, index: int) -> HistoryEntry:
    return HistoryEntry(
        event_id=f"EVT-FICTIONAL-{index}",
        intake_source=IntakeSource.MANUAL,
        event_date=day,
        event_type=EventType.WEAPON_FIRING,
        training_context=TrainingContext.QUALIFICATION,
        weapon_name="Fictional demo system",
        location_unit="Fictional demo location",
        crew_name="Fictional crew",
        position=CrewPosition.CHIEF,
        participation_role=ParticipationRole.SECTION_CHIEF,
        physical_event_count=None,
    )


def main() -> None:
    rows, metadata = load_baseline()
    first = fit_pattern_model(rows, metadata)
    second = fit_pattern_model(rows, metadata)
    scores = np.asarray(first.forest.score_samples(rows), dtype=np.float64)
    other_scores = np.asarray(second.forest.score_samples(rows), dtype=np.float64)
    identical = np.array_equal(scores, other_scores) and first.threshold == second.threshold
    difference = float(np.max(np.abs(scores - other_scores)))
    flagged_share = float(np.mean(scores < first.threshold) * 100)
    lines = [
        "# Prototype longitudinal-pattern evaluation",
        "",
        BASELINE_LABEL,
        "",
        PATTERN_DISCLAIMER,
        "",
        f"Fictional simulation baseline windows: {first.baseline_rows}.",
        f"Model parameters: `{json.dumps(MODEL_PARAMS, sort_keys=True)}`.",
        "Threshold rule: 5th percentile of fictional-baseline score_samples "
        f"({ANOMALY_PERCENTILE:g}th percentile; fitted threshold {first.threshold:.9f}).",
        "Expected flagged share of fictional simulation baseline windows by construction: 5%. "
        f"Actual share: {flagged_share:.3f}%.",
        "Two independent fits: "
        + ("identical." if identical else f"maximum absolute score difference {difference:.12g}."),
        "",
        "Features:",
    ]
    lines.extend(f"- `{name}`: {FEATURE_LABELS[name]}" for name in FEATURE_NAMES)
    lines.extend(["", "Deliberately excluded:"])
    lines.extend(f"- {name}: {reason}" for name, reason in DELIBERATELY_EXCLUDED.items())
    lines.extend(
        [
            "",
            f"Analysis as of: {ANALYSIS_AS_OF.isoformat()}.",
            "Expected labels are pre-registered hypotheses; observed mismatches are retained.",
            "",
            "| Scenario | Expected | Actual | PASS/MISMATCH |",
            "| --- | --- | --- | --- |",
        ]
    )
    scenarios = (
        ("distributed", (300, 180, 60), PatternStatus.TYPICAL_RECORDED_PATTERN),
        ("tightly clustered recent", (11, 8, 5, 3, 1), PatternStatus.ATYPICAL_OCCUPATIONAL_PATTERN),
        ("missing-count history", (150, 120, 90), PatternStatus.TYPICAL_RECORDED_PATTERN),
        ("sparse", (400,), PatternStatus.TYPICAL_RECORDED_PATTERN),
        ("recent cadence change", (25, 18, 10, 2), PatternStatus.ATYPICAL_OCCUPATIONAL_PATTERN),
    )
    for name, offsets, expected in scenarios:
        days = [ANALYSIS_AS_OF - timedelta(days=offset) for offset in offsets]
        result = assess_pattern(first, days, ANALYSIS_AS_OF)
        outcome = "PASS" if result.status is expected else "MISMATCH"
        lines.append(f"| {name} | {expected.label} | {result.status.label} | {outcome} |")
    missing_days = [ANALYSIS_AS_OF - timedelta(days=offset) for offset in (150, 120, 90)]
    missing_history = [missing_count_entry(day, i) for i, day in enumerate(missing_days)]
    quality = assess_readiness(
        "FIC-EVAL",
        missing_history,
        [],
        assess_pattern(first, missing_days, ANALYSIS_AS_OF),
        ANALYSIS_AS_OF,
    )
    lines.extend(
        [
            "",
            "Missing-count scenario data-quality note: "
            + "; ".join(quality.data_quality_notes)
            + ".",
            "",
            "There are no medical labels; this evaluation does not measure injury prediction.",
            "",
            "Seeded fictional roster (approved training event days only):",
            "",
            "| Person | " + " | ".join(FEATURE_NAMES) + " | Status |",
            "| --- | " + " | ".join("---" for _ in FEATURE_NAMES) + " | --- |",
        ]
    )
    conn = store.connect(":memory:")
    try:
        store.init_db(conn)
        store.seed_people(conn, DEMO_PEOPLE)
        store.seed_demo_events(conn, DEMO_EVENTS)
        for person in DEMO_PEOPLE:
            days = [entry.event_date for entry in store.member_history(conn, person.person_id)]
            features = occupational_features(days, ANALYSIS_AS_OF)
            result = assess_pattern(first, days, ANALYSIS_AS_OF)
            values = " | ".join(f"{value:.6f}" for value in features)
            lines.append(
                f"| {person.display_name} (FICTIONAL) | {values} | {result.status.label} |"
            )
    finally:
        conn.close()
    report = "\n".join(lines) + "\n"
    (BASELINE_DIR / "eval_report.md").write_text(report, encoding="utf-8", newline="\n")
    print(report)


if __name__ == "__main__":
    main()
