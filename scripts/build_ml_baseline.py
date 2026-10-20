"""Build deterministic occupational windows from the fictional simulation baseline scenario."""

import csv
import json
from datetime import date, timedelta
from hashlib import sha256

from build_demo_career import build_inputs

from blastbridge.product.patterns import (
    ANOMALY_PERCENTILE,
    BASELINE_DIR,
    BASELINE_LABEL,
    DAYS_CAP,
    FEATURE_NAMES,
    MODEL_PARAMS,
    occupational_features,
)
from blastbridge.simulation.engine import generate
from blastbridge.simulation.outputs import OUTPUT_TABLES

BASELINE_SEED = 20261019
POPULATION = 30
STEP_DAYS = 45
FIRST_WINDOW_OFFSET_DAYS = 365


def main() -> None:
    config, scenario, approval, mapping = build_inputs(BASELINE_SEED)
    config = config.model_copy(update={"population_size": POPULATION})
    dataset = generate(config, scenario, approval, mapping)
    session_days = {
        session.session_id: session.start_time.date() for session in dataset.live_fire_sessions
    }
    event_sessions = {event.event_id: event.session_id for event in dataset.firing_events}
    member_days: dict[str, set[date]] = {member.member_id: set() for member in dataset.members}
    for exposure in dataset.participant_exposures:
        session_id = event_sessions[exposure.event_id]
        member_days[exposure.synthetic_member_id].add(session_days[session_id])
    rows = []
    for member in sorted(dataset.members, key=lambda item: item.member_id):
        analysis_date = member.service_start + timedelta(days=FIRST_WINDOW_OFFSET_DAYS)
        end = min(member.service_end or config.simulation_end_date, config.simulation_end_date)
        while analysis_date <= end:
            rows.append(occupational_features(member_days[member.member_id], analysis_date))
            analysis_date += timedelta(days=STEP_DAYS)

    metadata = {
        "label": BASELINE_LABEL,
        "generator_version": config.generator_version,
        "output_schema_version": OUTPUT_TABLES[0].schema_version,
        "scenario_id": scenario.scenario_id,
        "scenario_version": scenario.scenario_version,
        "master_seed": BASELINE_SEED,
        "population_size": POPULATION,
        "config_fingerprint": sha256(config.model_dump_json().encode("utf-8")).hexdigest(),
        "config_fingerprint_method": (
            "sha256 of config.model_dump_json(); persistence exposes no public fingerprint helper"
        ),
        "mapping_id": mapping.mapping_id,
        "mapping_version": mapping.mapping_version,
        "row_count": len(rows),
        "feature_names": list(FEATURE_NAMES),
        "window_semantics": {
            "events_30d": (
                "Distinct occupational event days in (analysis_as_of - 30 days, analysis_as_of]."
            ),
            "events_90d": (
                "Distinct occupational event days in (analysis_as_of - 90 days, analysis_as_of]."
            ),
            "events_365d": (
                "Distinct occupational event days in (analysis_as_of - 365 days, analysis_as_of]."
            ),
            "days_since_previous_event": (
                "Days since the most recent event day at or before analysis_as_of, capped at "
                "730; 730 when none is recorded."
            ),
            "max_events_14d": (
                "For each event day d in the prior 365 days, count distinct event days in "
                "(d - 14 days, d] and retain the maximum, or zero if no endpoint exists."
            ),
            "recent_vs_earlier_cadence": "events_90d / 3 minus (events_365d - events_90d) / 9.",
        },
        "unit_mapping": (
            "One distinct attended live-fire session day is one occupational event day; "
            "one distinct approved product training event day is one occupational event day."
        ),
        "step_days": STEP_DAYS,
        "first_window_offset_days": FIRST_WINDOW_OFFSET_DAYS,
        "days_cap": DAYS_CAP,
        "model_params": MODEL_PARAMS,
        "anomaly_percentile": ANOMALY_PERCENTILE,
        "sklearn_version_pinned": "1.6.1",
        "scenario_note": (
            "Uses the V0.5 fictional demo scenario assumptions with population_size 30. "
            "Not an empirical military population model; not medical ground truth."
        ),
    }
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    with (BASELINE_DIR / "baseline_features.csv").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(FEATURE_NAMES)
        writer.writerows([[f"{value:.6f}" for value in row] for row in rows])
    (BASELINE_DIR / "metadata.json").write_text(
        json.dumps(metadata, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Wrote {len(rows)} occupational windows for the fictional simulation baseline.")


if __name__ == "__main__":
    main()
