"""Persistence integrity and the frozen fictional demonstration artifact."""

import importlib.util
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from execution_mapping_fixtures import assembly_fixture

from blastbridge.simulation import engine, persistence
from blastbridge.simulation.fictional import FictionalGenerationApproval
from blastbridge.simulation.models import ExecutionMapping, ScenarioDefinition, SimulationConfig
from blastbridge.simulation.outputs import SyntheticOutput
from blastbridge.simulation.persistence import load_career, save_career

_ROOT = Path(__file__).resolve().parents[1]
_DEMO = _ROOT / "examples" / "fictional" / "demo-career"


@pytest.fixture
def saved_career(tmp_path):
    config, scenario, approval, mapping = assembly_fixture(population_size=2, event_count=2)
    dataset = engine.generate(config, scenario, approval, mapping)
    output = SyntheticOutput(config=config, scenario=scenario, records=dataset)
    path = tmp_path / "career.json"
    save_career(output, mapping, path)
    return path, config, scenario, mapping, dataset, output


@pytest.fixture
def demo_script():
    spec = importlib.util.spec_from_file_location(
        "blastbridge_demo_career", _ROOT / "scripts" / "build_demo_career.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _demo_inputs():
    return (
        SimulationConfig.model_validate_json((_DEMO / "config.json").read_text(encoding="utf-8")),
        ScenarioDefinition.model_validate_json(
            (_DEMO / "scenario.json").read_text(encoding="utf-8")
        ),
        FictionalGenerationApproval.model_validate_json(
            (_DEMO / "approval.json").read_text(encoding="utf-8")
        ),
        ExecutionMapping.model_validate_json((_DEMO / "mapping.json").read_text(encoding="utf-8")),
    )


def test_save_load_round_trip(saved_career):
    path, config, scenario, mapping, dataset, _ = saved_career
    restored = load_career(path, config, scenario, mapping)
    assert restored.model_dump(mode="json") == dataset.model_dump(mode="json")
    assert json.loads(path.read_text(encoding="utf-8"))["header"]["fictional"] is True


def test_save_is_byte_identical_and_leaves_no_temporary_files(saved_career):
    path, _, _, mapping, _, output = saved_career
    another = path.with_name("another.json")
    save_career(output, mapping, another)
    assert path.read_bytes() == another.read_bytes()
    assert set(path.parent.iterdir()) == {path, another}


def test_failed_replace_cleans_temporary_file_and_preserves_existing_career(
    saved_career, monkeypatch
):
    path, _, _, mapping, _, output = saved_career
    before = path.read_bytes()

    def failed(source, destination):
        assert Path(source).parent == path.parent
        assert destination == path
        raise OSError("TEST replacement failure")

    monkeypatch.setattr(persistence.os, "replace", failed)
    with pytest.raises(OSError, match="TEST replacement failure"):
        save_career(output, mapping, path)
    assert path.read_bytes() == before
    assert set(path.parent.iterdir()) == {path}


def test_committed_demo_regenerates_without_seed_search(tmp_path):
    config, scenario, approval, mapping = _demo_inputs()
    dataset = engine.generate(config, scenario, approval, mapping)
    destination = tmp_path / "career.json"
    save_career(
        SyntheticOutput(config=config, scenario=scenario, records=dataset), mapping, destination
    )
    assert destination.read_bytes() == (_DEMO / "career.json").read_bytes()
    assert json.loads(destination.read_text(encoding="utf-8"))["header"]["fictional"] is True


def test_demo_seed_is_frozen_and_inputs_match_builder(demo_script):
    config, scenario, approval, mapping = _demo_inputs()
    header = json.loads((_DEMO / "career.json").read_text(encoding="utf-8"))["header"]
    assert demo_script.DEMO_SEED is not None
    assert demo_script.DEMO_SEED == config.master_seed == header["master_seed"]
    expected = demo_script.build_inputs(demo_script.DEMO_SEED)
    assert [item.model_dump(mode="json") for item in (config, scenario, approval, mapping)] == [
        item.model_dump(mode="json") for item in expected
    ]


def test_committed_demo_quality_and_fictional_header(demo_script):
    config, scenario, _, mapping = _demo_inputs()
    dataset = load_career(_DEMO / "career.json", config, scenario, mapping)
    assert demo_script.demo_quality(dataset) == []
    header = json.loads((_DEMO / "career.json").read_text(encoding="utf-8"))["header"]
    assert header["fictional"] is True


def _tamper(saved_career, change):
    path, config, scenario, mapping, _, _ = saved_career
    payload = json.loads(path.read_text(encoding="utf-8"))
    change(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, config, scenario, mapping


def test_tampered_foreign_key_refused(saved_career):
    def change(payload):
        payload["tables"]["synthetic_assignments"][0]["career_episode_id"] = "SYN-CAREER-999999"

    with pytest.raises(ValueError, match="career validation failed"):
        load_career(*_tamper(saved_career, change))


@pytest.mark.parametrize("representation", ["integer", "datetime"])
def test_noncanonical_date_refused(saved_career, representation):
    def change(payload):
        member = payload["tables"]["synthetic_members"][0]
        value = member["service_start"]
        if representation == "integer":
            member["service_start"] = int(
                datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp()
            )
        else:
            member["service_start"] = value + "T00:00:00"

    with pytest.raises(ValueError, match="career tables are not in canonical serialized form"):
        load_career(*_tamper(saved_career, change))


def test_noncanonical_timestamp_offset_refused(saved_career):
    def change(payload):
        event = payload["tables"]["synthetic_firing_events"][0]
        timestamp = datetime.fromisoformat(event["timestamp"])
        event["timestamp"] = timestamp.astimezone(timezone(timedelta(hours=1))).isoformat()

    with pytest.raises(ValueError):
        load_career(*_tamper(saved_career, change))


def test_tampered_provenance_parameter_refused(saved_career):
    def change(payload):
        payload["tables"]["synthetic_members"][0]["provenance"]["parameter_ids"][0] = (
            "test-tampered-parameter"
        )

    with pytest.raises(ValueError, match="parameter lineage"):
        load_career(*_tamper(saved_career, change))


def test_nonfictional_header_refused(saved_career):
    def change(payload):
        payload["header"]["fictional"] = False

    with pytest.raises(ValueError, match="fictional must be exactly true"):
        load_career(*_tamper(saved_career, change))


def test_config_fingerprint_mismatch_refused(saved_career):
    def change(payload):
        payload["header"]["config_fingerprint"] = "0" * 64

    with pytest.raises(ValueError, match="config_fingerprint mismatch"):
        load_career(*_tamper(saved_career, change))


def test_mapping_fingerprint_mismatch_refused(saved_career):
    def change(payload):
        payload["header"]["mapping_fingerprint"] = "0" * 64

    with pytest.raises(ValueError, match="mapping_fingerprint mismatch"):
        load_career(*_tamper(saved_career, change))


def test_unknown_table_refused(saved_career):
    def change(payload):
        payload["tables"]["test-unknown-table"] = []

    with pytest.raises(ValueError, match="tables:.*unknown keys"):
        load_career(*_tamper(saved_career, change))


def test_removed_parent_row_refused(saved_career):
    def change(payload):
        payload["tables"]["synthetic_career_episodes"].pop(0)

    with pytest.raises(ValueError, match="career validation failed"):
        load_career(*_tamper(saved_career, change))


def test_truncated_json_refused(saved_career):
    path, config, scenario, mapping, _, _ = saved_career
    path.write_text('{"header": ', encoding="utf-8")
    with pytest.raises(ValueError, match="malformed JSON"):
        load_career(path, config, scenario, mapping)


@pytest.mark.parametrize("section", ["top-level", "header", "tables"])
@pytest.mark.parametrize("extra", [False, True])
def test_unknown_or_missing_keys_refused(saved_career, section, extra):
    def change(payload):
        target = payload if section == "top-level" else payload[section]
        if extra:
            target["test-unknown-key"] = None
        else:
            target.pop(next(iter(target)))

    with pytest.raises(ValueError, match=f"{section}:.*keys"):
        load_career(*_tamper(saved_career, change))


@pytest.mark.parametrize(
    "field,value",
    [
        ("format", "test-unknown-format"),
        ("format_version", 2),
        ("format_version", True),
        ("fictional", 1),
        ("generator_version", "0.4.0"),
        ("master_seed", -1),
        ("simulation_id", "test-other-simulation"),
        ("scenario_id", "test-other-scenario"),
        ("scenario_version", "0.0.0"),
        ("mapping_id", "test-other-mapping"),
        ("mapping_version", "0.0.0"),
        ("output_schema_version", "0.0.0"),
    ],
)
def test_header_identity_mismatch_refused(saved_career, field, value):
    def change(payload):
        payload["header"][field] = value

    with pytest.raises(ValueError, match=f"header {field}"):
        load_career(*_tamper(saved_career, change))
