"""Minimal deterministic persistence for validated fictional career tables."""

import json
import os
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Any

from .execution import validate_execution_mapping
from .fictional import validate_fictional_scenario
from .models import ExecutionMapping, ScenarioDefinition, SimulationConfig, SyntheticCareerDataset
from .outputs import SyntheticOutput, serialize_output
from .rng import _fingerprint

_TABLE_FIELDS = {
    "synthetic_members": "members",
    "synthetic_career_episodes": "career_episodes",
    "synthetic_assignments": "assignments",
    "synthetic_training_periods": "training_periods",
    "synthetic_live_fire_sessions": "live_fire_sessions",
    "synthetic_firing_missions": "firing_missions",
    "synthetic_firing_events": "firing_events",
    "synthetic_participant_exposures": "participant_exposures",
}


def _header(
    config: SimulationConfig, scenario: ScenarioDefinition, mapping: ExecutionMapping
) -> dict[str, str | int | bool]:
    return {
        "format": "blastbridge-fictional-career",
        "format_version": 1,
        "fictional": True,
        "generator_version": config.generator_version,
        "master_seed": config.master_seed,
        "simulation_id": config.simulation_id,
        "scenario_id": scenario.scenario_id,
        "scenario_version": scenario.scenario_version,
        "config_fingerprint": _fingerprint(config, scenario),
        "mapping_id": mapping.mapping_id,
        "mapping_version": mapping.mapping_version,
        "mapping_fingerprint": mapping.fingerprint(),
        "output_schema_version": "0.4.0",
    }


def _validate_inputs(
    config: SimulationConfig, scenario: ScenarioDefinition, mapping: ExecutionMapping
) -> None:
    validate_fictional_scenario(config, scenario)
    validate_execution_mapping(config, scenario, mapping)


def save_career(output: SyntheticOutput, mapping: ExecutionMapping, path: Path) -> None:
    """Atomically replace one fictional career JSON file in its existing directory."""
    # Revalidate copies too: model_copy can bypass the models' validation boundary.
    output = SyntheticOutput.model_validate(output.model_dump(mode="json"))
    _validate_inputs(output.config, output.scenario, mapping)
    payload = {
        "header": _header(output.config, output.scenario, mapping),
        "tables": serialize_output(output),
    }
    data = (
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _keys(value: object, expected: set[str], context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context}: expected an object")
    missing, unknown = expected - value.keys(), value.keys() - expected
    if missing or unknown:
        raise ValueError(
            f"{context}: missing keys {sorted(missing)}, unknown keys {sorted(unknown)}"
        )
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"duplicate key {name}")
        result[name] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value}")


def load_career(
    path: Path,
    config: SimulationConfig,
    scenario: ScenarioDefinition,
    mapping: ExecutionMapping,
) -> SyntheticCareerDataset:
    """Load exact tables, check their input identity, then validate the complete graph."""
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
    except ValueError as error:
        raise ValueError(f"malformed JSON: {error}") from error
    payload = _keys(payload, {"header", "tables"}, "top-level")
    _validate_inputs(config, scenario, mapping)
    expected = _header(config, scenario, mapping)
    header = _keys(payload["header"], set(expected), "header")
    if header["fictional"] is not True:
        raise ValueError("header fictional must be exactly true")
    for name, value in expected.items():
        if type(header[name]) is not type(value) or header[name] != value:
            raise ValueError(f"header {name} mismatch")
    tables = _keys(payload["tables"], set(_TABLE_FIELDS), "tables")
    for name, rows in tables.items():
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"table {name}: expected an array of row objects")
    try:
        dataset = SyntheticCareerDataset.model_validate(
            {field: tables[name] for name, field in _TABLE_FIELDS.items()}
        )
        output = SyntheticOutput(config=config, scenario=scenario, records=dataset)
    except ValueError as error:
        raise ValueError(f"career validation failed: {error}") from error
    if {name: list(rows) for name, rows in serialize_output(output).items()} != tables:
        raise ValueError("career tables are not in canonical serialized form")
    timestamps = (
        *(value for row in dataset.live_fire_sessions for value in (row.start_time, row.end_time)),
        *(value for row in dataset.firing_missions for value in (row.start_time, row.end_time)),
        *(row.timestamp for row in dataset.firing_events),
    )
    if any(value.utcoffset() != timedelta(0) for value in timestamps):
        raise ValueError("career timestamps must be UTC")
    return dataset
