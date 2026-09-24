"""Protect evidence meaning as well as release bytes and reference joins."""

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from blastbridge.data.reference import load_reference_bundle, read_json
from blastbridge.data.training_tempo import (
    BASELINE_MANIFEST_SHA256,
    TEMPO_FILES,
    TEMPO_RELEASE_FILES,
    load_training_tempo,
    verify_source_originals,
)
from blastbridge.models.training_tempo import (
    CountValue,
    Interval,
    TempoEvidence,
    TempoManifest,
    TempoSource,
    TimeWindow,
    TrainingTempoBundle,
)
from blastbridge.validation.training_tempo import summarize

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/reference"


@pytest.fixture
def payload():
    return {key: read_json(DATA / filename) for key, filename in TEMPO_FILES.items()}


@pytest.fixture
def release_copy(tmp_path):
    for path in DATA.glob("*.json"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    return tmp_path


def row(payload, suffix):
    return next(
        r for r in payload["evidence"]["records"] if r["tempo_evidence_id"] == "tempo-" + suffix
    )


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_release_roundtrip_and_research_boundaries():
    bundle = load_training_tempo(DATA)
    assert TrainingTempoBundle.model_validate_json(bundle.model_dump_json()) == bundle
    assert len(bundle.evidence.records) == 40
    assert len(bundle.sources.records) == 31
    assert len(bundle.taxonomy.records) == 8
    assert all(r.confidence is None for r in bundle.evidence.records)
    assert all(
        r.individual_exposure_inference == "not_established" for r in bundle.evidence.records
    )
    assert all(
        r.claim.observed_frequency is None
        for r in bundle.evidence.records
        if r.claim.kind == "observation"
    )
    assert read_json(DATA / "training_tempo.schema.json") == TrainingTempoBundle.model_json_schema()


def test_sme_preserved_without_guard_numeric_inference(payload):
    active = TempoEvidence.model_validate(row(payload, "sme-active-himars"))
    guard = TempoEvidence.model_validate(row(payload, "sme-guard-himars"))
    assert active.claim.kind == guard.claim.kind == "estimate"
    assert active.claim.estimated_frequency.count.lower == 4
    assert active.claim.estimated_frequency.count.upper == 5
    count = active.claim.estimated_rounds_per_event.count
    assert (count.lower, count.upper, count.recalled_central) == (3, 12, 6)
    assert active.claim.event_unit != active.normalized_activity_type
    assert guard.claim.estimated_frequency is None
    assert guard.claim.estimated_rounds_per_event is None
    assert active.source_id == guard.source_id


def test_requirements_observations_and_plans_stay_distinct(payload):
    active = row(payload, "fa-requirement-active")["claim"]
    guard = row(payload, "fa-requirement-army_national_guard")["claim"]
    assert active["minimum_required_frequency"]["per"]["value"] == 6
    assert guard["minimum_required_frequency"]["per"]["value"] == 12
    validity = row(payload, "mortar-validity-active")["claim"]
    assert validity["minimum_required_frequency"] is None
    assert validity["qualification_validity"]["value"] == 12
    task = row(payload, "marine-0811-sustainment")["claim"]
    assert task["live_fire_required"] is False
    assert task["minimum_required_frequency"] is None
    plan = row(payload, "active-m120-plan")["claim"]
    assert plan["kind"] == "schedule" and plan["completion_verified"] is False


def test_ambiguous_counts_and_denominators_preserved(payload):
    assert row(payload, "active-m121-mortep")["claim"]["observed_round_count"] is None
    claim = row(payload, "marine-active-himars")["claim"]
    assert claim["observed_round_count"]["count"]["value"] == 2
    assert claim["reported_launcher_count"]["value"] == 3
    assert claim["observed_round_count"]["population_denominator"] == "unit_total"
    assert "subset" in claim["observed_round_count"]["scope"]
    assert row(payload, "marine-reserve-mortars")["weapon_system_ids"] == []
    assert row(payload, "marine-active-himars")["occupation_ids"] == []


@pytest.mark.parametrize("collection", list(TEMPO_FILES))
def test_duplicate_ids(payload, collection):
    payload[collection]["records"].append(deepcopy(payload[collection]["records"][0]))
    with pytest.raises(ValidationError):
        TrainingTempoBundle.model_validate(payload)


@pytest.mark.parametrize("collection", list(TEMPO_FILES))
@pytest.mark.parametrize("field", ["dataset_version", "schema_version", "source_registry_version"])
def test_incompatible_metadata(payload, collection, field):
    payload[collection]["metadata"][field] = "0.1.0"
    with pytest.raises(ValidationError):
        TrainingTempoBundle.model_validate(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("component", "marine_corps_reserve"),
        ("component", "invented_component"),
        ("branch", "space_force"),
        ("evidence_type", "assumption"),
        ("representativeness", "service_wide_requirement"),
        ("normalized_activity_type", "exposure_event"),
        ("individual_exposure_inference", "rounds_equal_exposures"),
        ("occupation_link_basis", "unknown"),
        ("weapon_link_basis", "unknown"),
        ("participation_roles", ["unknown", "instructor"]),
        ("training_context", ["unknown", "annual_training"]),
        ("weapon_system_ids", ["m142-himars", "m142-himars"]),
        ("occupation_ids", ["army-13m", "army-13m"]),
        ("participation_roles", []),
        ("training_context", []),
        ("limitations", []),
        ("source_wording", "  "),
        ("confidence", 0.9),
        ("confidence_rationale", "Official does not imply numeric certainty."),
    ],
)
def test_invalid_population_and_evidence(payload, field, value):
    record = row(payload, "estonia-himars")
    record[field] = value
    with pytest.raises(ValidationError):
        TempoEvidence.model_validate(record)


@pytest.mark.parametrize("missing", ["evidence_type", "representativeness", "source_id"])
def test_required_provenance_cannot_be_omitted(payload, missing):
    record = row(payload, "estonia-himars")
    del record[missing]
    with pytest.raises(ValidationError):
        TempoEvidence.model_validate(record)


@pytest.mark.parametrize("kind", ["requirement", "observation", "assumption", "schedule"])
def test_sme_cannot_be_retyped_as_official_claim(payload, kind):
    record = row(payload, "sme-active-himars")
    record["claim"]["kind"] = kind
    with pytest.raises(ValidationError):
        TempoEvidence.model_validate(record)


@pytest.mark.parametrize(
    "suffix,field,value",
    [
        ("fa-requirement-active", "observed_round_count", None),
        ("estonia-himars", "minimum_required_frequency", None),
        ("active-m120-plan", "completion_verified", True),
        ("sme-active-himars", "event_unit", None),
        ("estonia-himars", "live_fire_confirmed", None),
        ("estonia-himars", "live_fire_confirmed", False),
    ],
)
def test_claim_specific_fields_cannot_cross_boundaries(payload, suffix, field, value):
    record = row(payload, suffix)
    record["claim"][field] = value
    with pytest.raises(ValidationError):
        TempoEvidence.model_validate(record)


def test_frequency_requires_consistent_unit(payload):
    record = row(payload, "fa-requirement-active")
    record["claim"]["minimum_required_frequency"]["counting_unit"] = "firing_event"
    with pytest.raises(ValidationError, match="frequency unit"):
        TempoEvidence.model_validate(record)


@pytest.mark.parametrize("suffix", ["estonia-himars", "fa-requirement-active"])
def test_recalled_central_values_cannot_become_observations_or_requirements(payload, suffix):
    record = row(payload, suffix)
    field = "observed_round_count" if suffix == "estonia-himars" else "minimum_required_frequency"
    record["claim"][field]["count"] = {
        "precision": "range",
        "lower": 3,
        "upper": 12,
        "recalled_central": 6,
    }
    with pytest.raises(ValidationError, match="recalled central"):
        TempoEvidence.model_validate(record)


@pytest.mark.parametrize("value", [-1, 1.5, "3", True, float("nan"), float("inf")])
def test_counts_reject_coercion_and_invalid_numbers(value):
    with pytest.raises(ValidationError):
        CountValue(precision="exact", value=value)


@pytest.mark.parametrize(
    "data",
    [
        {"precision": "exact"},
        {"precision": "exact", "value": 2, "upper": 3},
        {"precision": "range", "lower": 3},
        {"precision": "range", "lower": 4, "upper": 3},
        {"precision": "range", "lower": 3, "upper": 12, "value": 6},
        {"precision": "range", "lower": 3, "upper": 12, "recalled_central": 13},
    ],
)
def test_count_precision_shape(data):
    with pytest.raises(ValidationError):
        CountValue.model_validate(data)


def test_unknown_is_distinct_from_documented_zero(payload):
    record = row(payload, "estonia-himars")
    record["claim"]["observed_round_count"]["count"]["value"] = 0
    zero = TempoEvidence.model_validate(record)
    record["claim"]["observed_round_count"] = None
    unknown = TempoEvidence.model_validate(record)
    assert zero.claim.observed_round_count.count.value == 0
    assert unknown.claim.observed_round_count is None
    assert zero.model_dump_json() != unknown.model_dump_json()


@pytest.mark.parametrize("value", [0, -1, "6", True, 0.5])
def test_time_intervals_require_strict_positive_numbers(value):
    with pytest.raises(ValidationError):
        Interval(value=value, unit="month")


@pytest.mark.parametrize(
    "dates",
    [
        {"start_date": "2025-02-01", "end_date": "2025-01-01"},
        {"start_date": "2025-02-01", "year": 2024},
    ],
)
def test_time_window_consistency(dates):
    with pytest.raises(ValidationError):
        TimeWindow(description="Test historical window", **dates)


@pytest.mark.parametrize("target", ["primary", "citation", "definition", "term"])
def test_missing_source_and_mapping_links(payload, target):
    record = row(payload, "estonia-himars")
    if target == "primary":
        record["source_id"] = "missing-source"
        record["citations"][0]["source_id"] = "missing-source"
    elif target == "citation":
        record["citations"].append({"source_id": "missing-source", "locator": "Example locator"})
    elif target == "definition":
        payload["taxonomy"]["records"][0]["source_id"] = "missing-source"
    else:
        payload["taxonomy"]["source_term_mappings"][0]["evidence_id"] = "missing-evidence"
    with pytest.raises(ValidationError):
        TrainingTempoBundle.model_validate(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("occupation_ids", ["missing-occupation"]),
        ("weapon_system_ids", ["missing-weapon"]),
        ("occupation_ids", ["usmc-0811"]),
    ],
)
def test_reference_links(payload, field, value):
    row(payload, "estonia-himars")[field] = value
    bundle = TrainingTempoBundle.model_validate(payload)
    with pytest.raises(ValueError):
        bundle.validate_reference_links(load_reference_bundle(DATA))


def test_source_ids_cannot_collide_with_baseline(payload):
    baseline = load_reference_bundle(DATA)
    existing = baseline.sources.records[0].source_id
    record = row(payload, "estonia-himars")
    source = next(s for s in payload["sources"]["records"] if s["source_id"] == record["source_id"])
    source["source_id"] = record["source_id"] = existing
    record["citations"][0]["source_id"] = existing
    bundle = TrainingTempoBundle.model_validate(payload)
    with pytest.raises(ValueError, match="collide"):
        bundle.validate_reference_links(baseline)


@pytest.mark.parametrize("mode", ["sme_primary", "mixed_citation", "unit_as_requirement"])
def test_provenance_impersonation(payload, mode):
    record = row(payload, "fa-requirement-active")
    if mode == "mixed_citation":
        record["citations"].append({"source_id": "tempo-sme-13m", "locator": "User note"})
    else:
        sid = "tempo-sme-13m" if mode == "sme_primary" else "tempo-army-himars-estonia-2025"
        record["source_id"] = sid
        record["citations"] = [{"source_id": sid, "locator": "Example locator"}]
    with pytest.raises(ValidationError, match="masquerade|separate|normative"):
        TrainingTempoBundle.model_validate(payload)


@pytest.mark.parametrize("mode", ["missing_primary", "duplicate", "blank_locator"])
def test_citation_integrity(payload, mode):
    record = row(payload, "estonia-himars")
    if mode == "missing_primary":
        record["citations"][0]["source_id"] = "tempo-tc-fa-2020"
    elif mode == "duplicate":
        record["citations"] *= 2
    else:
        record["citations"][0]["locator"] = " "
    with pytest.raises(ValidationError):
        TempoEvidence.model_validate(record)


@pytest.mark.parametrize(
    "field", ["evidence_types", "components", "participation_roles", "representativeness_values"]
)
def test_taxonomy_vocabulary_must_be_complete(payload, field):
    payload["taxonomy"][field].pop()
    with pytest.raises(ValidationError, match="vocabulary"):
        TrainingTempoBundle.model_validate(payload)


@pytest.mark.parametrize(
    "change",
    [
        {"url": "https://army.mil.example.org/fake"},
        {"url": "https://user:password@army.mil/page"},
        {"url": "https://army.mil/page#citation"},
        {"url": None},
        {"retrieval_method": "downloaded"},
        {"content_sha256": "a" * 64},
        {"retrieval_limitation": None},
        {"local_filename": "../outside.pdf"},
        {"publication_date": "2099-01-01"},
        {"document_kind": "user_note"},
    ],
)
def test_published_source_integrity(payload, change):
    source = deepcopy(payload["sources"]["records"][0])
    source.update(change)
    with pytest.raises(ValidationError):
        TempoSource.model_validate(source)


def test_assumptions_have_separate_non_evidence_model(payload):
    source = next(s for s in payload["sources"]["records"] if s["source_id"] == "tempo-sme-13m")
    source.update(
        source_type="assumption", document_kind="assumption", retrieval_method="local_note"
    )
    for suffix in ("sme-active-himars", "sme-guard-himars"):
        record = row(payload, suffix)
        record["evidence_type"] = "assumption"
        record["claim"] = {
            "kind": "assumption",
            "assumption": "Test only, not a curated fact.",
            "justification": "Exercise separate representation.",
            "usable_as_evidence": False,
        }
    TrainingTempoBundle.model_validate(payload)
    row(payload, "sme-active-himars")["claim"]["usable_as_evidence"] = True
    with pytest.raises(ValidationError):
        TrainingTempoBundle.model_validate(payload)


def test_official_source_cannot_be_an_sme_download(payload):
    source = next(s for s in payload["sources"]["records"] if s["source_id"] == "tempo-sme-13m")
    source.update(url="https://army.mil/report", retrieval_method="downloaded")
    with pytest.raises(ValidationError):
        TempoSource.model_validate(source)


@pytest.mark.parametrize("filename", list(TEMPO_FILES.values()))
def test_byte_changes_require_manifest_update(release_copy, filename):
    with (release_copy / filename).open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(ValueError, match="release hash mismatch"):
        load_training_tempo(release_copy)
    load_training_tempo(release_copy, verify_manifest=False)


def test_candidate_mode_still_checks_relations(release_copy):
    path = release_copy / TEMPO_FILES["evidence"]
    data = read_json(path)
    data["records"][0]["weapon_system_ids"] = ["missing-weapon"]
    write_json(path, data)
    with pytest.raises(ValueError, match="unknown weapon"):
        load_training_tempo(release_copy, verify_manifest=False)


def test_schema_byte_and_semantic_integrity(release_copy):
    path = release_copy / "training_tempo.schema.json"
    schema = read_json(path)
    schema["title"] = "StaleSchema"
    write_json(path, schema)
    with pytest.raises(ValueError, match="schema hash"):
        load_training_tempo(release_copy)
    manifest_path = release_copy / "training_tempo_manifest.json"
    manifest = read_json(manifest_path)
    manifest["schema_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="schema export is stale"):
        load_training_tempo(release_copy)


@pytest.mark.parametrize("field", ["baseline_manifest_sha256", "baseline_git_commit"])
def test_baseline_dependency_pins(release_copy, field):
    path = release_copy / "training_tempo_manifest.json"
    data = read_json(path)
    data[field] = "0" * (64 if "sha256" in field else 40)
    write_json(path, data)
    with pytest.raises(ValueError, match="mismatch"):
        load_training_tempo(release_copy)


def test_baseline_byte_mutation_rejected_even_in_candidate_mode(release_copy):
    path = release_copy / "release_manifest.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == BASELINE_MANIFEST_SHA256
    with path.open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(ValueError, match="baseline manifest changed"):
        load_training_tempo(release_copy, verify_manifest=False)


def test_manifest_requires_every_dataset_once():
    data = read_json(DATA / "training_tempo_manifest.json")
    data["files"][1] = data["files"][0]
    with pytest.raises(ValidationError, match="exactly once"):
        TempoManifest.model_validate(data)


def test_original_archive_audit_and_tamper_detection(payload, tmp_path):
    original = b"Official test document bytes, not an actual publication."
    source = payload["sources"]["records"][0]
    source.update(
        retrieval_method="downloaded",
        local_filename="test-original.pdf",
        content_sha256=hashlib.sha256(original).hexdigest(),
    )
    bundle = TrainingTempoBundle.model_validate(payload)
    with pytest.raises(ValueError, match="missing or hash mismatch"):
        verify_source_originals(bundle, tmp_path)
    path = tmp_path / source["local_filename"]
    path.write_bytes(original)
    result = verify_source_originals(bundle, tmp_path)
    assert result == {"verified_downloads": 1, "unavailable_originals": 28, "local_notes": 2}
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="missing or hash mismatch"):
        verify_source_originals(bundle, tmp_path)


def test_cli_summary_and_overlapping_link_counts(release_copy):
    result = subprocess.run(
        [sys.executable, "-m", "blastbridge.validation.training_tempo", str(release_copy)],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    summary = json.loads(result.stdout)
    assert summary == summarize(load_training_tempo(release_copy))
    assert sum(summary["by_branch"].values()) == summary["evidence_records"]
    assert sum(summary["by_component"].values()) == summary["evidence_records"]
    assert sum(summary["by_occupation"].values()) > summary["evidence_records"]


@pytest.mark.parametrize("filename", TEMPO_RELEASE_FILES)
def test_partial_extension_cannot_silently_downgrade(release_copy, filename):
    (release_copy / filename).unlink()
    result = subprocess.run(
        [sys.executable, "-m", "blastbridge.validation.reference", str(release_copy)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode != 0


def test_v01_only_release_still_validates(release_copy):
    for filename in TEMPO_RELEASE_FILES:
        (release_copy / filename).unlink()
    result = subprocess.run(
        [sys.executable, "-m", "blastbridge.validation.reference", str(release_copy)],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    assert json.loads(result.stdout)["training_tempo_evidence_records"] is None
