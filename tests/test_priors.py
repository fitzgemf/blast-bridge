"""V0.3 boundary tests: fail closed against provenance and numerical laundering."""

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from blastbridge.data.priors import (
    PRIOR_FILES,
    PRIOR_RELEASE_FILES,
    load_prior_design,
)
from blastbridge.data.reference import load_reference_bundle, read_json
from blastbridge.data.training_tempo import load_training_tempo
from blastbridge.models.priors import (
    DistributionFamily,
    PriorDefinition,
    PriorDesignBundle,
    PriorManifest,
)
from blastbridge.validation.priors import summarize

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/reference"


@pytest.fixture
def design():
    return {key: read_json(DATA / name) for key, name in PRIOR_FILES.items()}


@pytest.fixture
def design_copy(tmp_path):
    for path in DATA.glob("*.json"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    return tmp_path


def get_row(design, suffix):
    return next(row for row in design["priors"]["records"] if row["prior_id"] == "design-" + suffix)


def scenario(design):
    return next(row for row in design["priors"]["records"] if row["scenario"] == "central")


def validate(design):
    result = PriorDesignBundle.model_validate(design)
    result.validate_evidence(load_training_tempo(DATA), load_reference_bundle(DATA))
    return result


def write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_complete_design_and_no_numeric_distributions():
    bundle = load_prior_design(DATA)
    assert PriorDesignBundle.model_validate_json(bundle.model_dump_json()) == bundle
    assert len(bundle.priors.records) == 39
    assert len(bundle.gaps.records) == 13
    assert len(bundle.priors.uncertainties) == 8
    assert bundle.priors.empirical_priors is None
    assert all(
        p.distribution_family == "none" and p.parameters is None for p in bundle.priors.records
    )
    assert {p.scenario for p in bundle.priors.records if p.scenario} == {
        "conservative",
        "central",
        "high-tempo",
    }
    assert read_json(DATA / "prior_design.schema.json") == PriorDesignBundle.model_json_schema()


@pytest.mark.parametrize("support", ["A", "B", "C", "D", "E", "F", "R"])
def test_empirical_type_unavailable_even_with_citations(design, support):
    row = get_row(design, "estonia-himars")
    row.update(prior_type="empirical_prior", support_level=support)
    with pytest.raises(ValidationError, match="qualifying representative"):
        validate(design)


@pytest.mark.parametrize("family", [f.value for f in DistributionFamily if f.value != "none"])
@pytest.mark.parametrize("row_kind", ["scenario", "sme", "constraint"])
def test_distribution_vocabulary_does_not_authorize_use(design, family, row_kind):
    row = {
        "scenario": scenario(design),
        "sme": get_row(design, "sme-active-himars"),
        "constraint": get_row(design, "fa-requirement-active"),
    }[row_kind]
    row["distribution_family"] = family
    with pytest.raises(ValidationError, match="numerical distributions"):
        validate(design)


@pytest.mark.parametrize(
    "field,value",
    [
        ("parameters", {"mode": 6}),
        ("parameters", {}),
        ("parameters", []),
        ("lower_bound", 0),
        ("upper_bound", 12),
        ("lower_bound", False),
        ("parameters", {"rate": float("nan")}),
        ("upper_bound", float("inf")),
        ("status", "approved"),
        ("confidence_class", "high"),
        ("confidence", 0.9),
        ("empirical", True),
        ("distribution_family", "invented"),
        ("version", "0.2.0"),
        ("individual_exposure_inference", "established"),
    ],
)
def test_no_hidden_parameters_or_unsupported_fields(design, field, value):
    scenario(design)[field] = value
    with pytest.raises(ValidationError):
        validate(design)


@pytest.mark.parametrize(
    "field,value",
    [
        ("support_level", "E"),
        ("scope_binding", "source_only"),
        ("status", "source_bound"),
        ("scenario", None),
        ("representativeness", "service_wide_requirement"),
        ("anchor_evidence_id", "tempo-sme-active-himars"),
        ("quantity_being_modeled", "recalled_tempo"),
    ],
)
def test_scenarios_cannot_claim_source_or_empirical_status(design, field, value):
    scenario(design)[field] = value
    with pytest.raises(ValidationError):
        validate(design)


def test_scenario_cannot_embed_sme_as_distribution(design):
    scenario(design)["evidence_payload"] = get_row(design, "sme-active-himars")["evidence_payload"]
    with pytest.raises(ValidationError, match="design-only"):
        validate(design)


def test_sme_values_and_weak_guard_recollection_are_unchanged(design):
    bundle = validate(design)
    active = next(p for p in bundle.priors.records if p.prior_id == "design-sme-active-himars")
    guard = next(p for p in bundle.priors.records if p.prior_id == "design-sme-guard-himars")
    assert active.prior_type == guard.prior_type == "sme_estimate"
    count = active.evidence_payload.estimated_frequency.count
    assert (count.lower, count.upper) == (4, 5)
    rockets = active.evidence_payload.estimated_rounds_per_event.count
    assert (rockets.lower, rockets.upper, rockets.recalled_central) == (3, 12, 6)
    assert guard.evidence_payload.estimated_frequency is None
    assert guard.evidence_payload.estimated_rounds_per_event is None


@pytest.mark.parametrize("support", ["A", "B", "C", "D", "F", "R"])
def test_sme_cannot_change_support_type(design, support):
    get_row(design, "sme-active-himars")["support_level"] = support
    with pytest.raises(ValidationError):
        validate(design)


def test_sme_cannot_be_promoted_to_official_observation(design):
    row = get_row(design, "sme-active-himars")
    row.update(
        prior_type="evidence_constraint",
        support_level="D",
        quantity_being_modeled="reported_activity",
        evidence_payload=get_row(design, "estonia-himars")["evidence_payload"],
    )
    with pytest.raises(ValueError, match="differs"):
        validate(design)


@pytest.mark.parametrize(
    "suffix,path,value",
    [
        ("sme-active-himars", ("estimated_frequency", "count", "lower"), 3),
        ("sme-active-himars", ("estimated_rounds_per_event", "count", "recalled_central"), 7),
        ("fa-requirement-active", ("minimum_required_frequency", "per", "value"), 12),
        ("western-strike-himars", ("observed_round_count", "count", "precision"), "exact"),
        ("active-m119-diamond", ("observed_round_count", "population_denominator"), "crew"),
        ("marine-active-himars", ("observed_round_count", "scope"), "All rockets"),
        ("active-abrams-table6", ("live_fire_confirmed",), None),
    ],
)
def test_exact_payload_binding_prevents_new_numbers_and_allocations(design, suffix, path, value):
    payload = get_row(design, suffix)["evidence_payload"]
    for key in path[:-1]:
        payload = payload[key]
    payload[path[-1]] = value
    with pytest.raises(ValueError, match="differs"):
        validate(design)


def test_guard_cannot_inherit_active_numeric_recollection(design):
    get_row(design, "sme-guard-himars")["evidence_payload"] = deepcopy(
        get_row(design, "sme-active-himars")["evidence_payload"]
    )
    with pytest.raises(ValueError, match="differs"):
        validate(design)


@pytest.mark.parametrize(
    "field,value",
    [
        ("population_scope", "All current Army personnel"),
        ("component", "army_national_guard"),
        ("occupation_ids", ["army-13b"]),
        ("weapon_system_ids", ["m270-mlrs"]),
        ("unit_type", "All units"),
        ("role_scope", ["weapon_operator"]),
        ("training_context", ["routine_home_station"]),
        ("counting_unit", "exposure_event"),
        ("time_window", {"description": "Every year", "year": 2026}),
        ("representativeness", "service_wide_requirement"),
    ],
)
def test_scope_cannot_expand_or_change_from_source(design, field, value):
    get_row(design, "estonia-himars")[field] = value
    with pytest.raises(ValueError, match="differs"):
        validate(design)


def test_original_limitations_cannot_be_discarded(design):
    get_row(design, "estonia-himars")["limitations"] = ["No limitations"]
    with pytest.raises(ValueError, match="limitations"):
        validate(design)


@pytest.mark.parametrize(
    "field,value",
    [
        ("evidence_ids", ["missing-evidence"]),
        ("source_ids", ["missing-source"]),
        ("source_ids", []),
        ("occupation_ids", ["missing-occupation"]),
        ("occupation_ids", ["usmc-0811"]),
        ("weapon_system_ids", ["missing-weapon"]),
        ("uncertainty_ids", ["missing-uncertainty"]),
        ("support_level", "unknown"),
        ("component", "marine_corps_reserve"),
    ],
)
def test_references_and_explicit_support(design, field, value):
    scenario(design)[field] = value
    with pytest.raises(ValueError):
        validate(design)


@pytest.mark.parametrize(
    "field",
    [
        "evidence_ids",
        "source_ids",
        "occupation_ids",
        "weapon_system_ids",
        "role_scope",
        "training_context",
        "uncertainty_ids",
    ],
)
def test_duplicate_links_rejected(design, field):
    scenario(design)[field] *= 2
    with pytest.raises(ValidationError, match="duplicate"):
        validate(design)


@pytest.mark.parametrize("collection", ["records", "uncertainties"])
def test_duplicate_design_ids(design, collection):
    design["priors"][collection][1] = deepcopy(design["priors"][collection][0])
    with pytest.raises(ValidationError, match="duplicate"):
        validate(design)


def test_requirement_plus_observation_support_c_is_scoped(design):
    row = get_row(design, "fa-requirement-active")
    row["support_level"] = "C"
    row["evidence_ids"].append("tempo-estonia-himars")
    row["source_ids"].append("tempo-army-himars-estonia-2025")
    validate(design)
    assert row["evidence_payload"]["kind"] == "requirement"
    assert row["parameters"] is None


def test_c_without_observation_is_rejected(design):
    get_row(design, "fa-requirement-active")["support_level"] = "C"
    with pytest.raises(ValueError, match="C needs"):
        validate(design)


def test_c_cannot_smuggle_an_unrelated_requirement(design):
    row = get_row(design, "fa-requirement-active")
    row.update(support_level="C")
    row["evidence_ids"] += ["tempo-estonia-himars", "tempo-marine-0811-sustainment"]
    row["source_ids"] += ["tempo-army-himars-estonia-2025", "tempo-usmc-artillery-2018"]
    with pytest.raises(ValueError, match="C needs"):
        validate(design)


@pytest.mark.parametrize(
    "eid,sid",
    [
        ("tempo-marine-active-himars", "tempo-marine-himars-active-2019"),
        ("tempo-western-strike-himars", "tempo-guard-western-strike-2018"),
        ("tempo-active-m120-training", "tempo-army-mortar-2013"),
        ("tempo-active-mlrs-exercise", "tempo-army-mlrs-2013"),
    ],
)
def test_scenario_citations_need_compatible_populations(design, eid, sid):
    row = scenario(design)
    row["evidence_ids"].append(eid)
    row["source_ids"].append(sid)
    with pytest.raises(ValueError, match="population mapping"):
        validate(design)


@pytest.mark.parametrize(
    "eid,sid",
    [
        ("tempo-marine-active-himars", "tempo-marine-himars-active-2019"),
        ("tempo-western-strike-himars", "tempo-guard-western-strike-2018"),
        ("tempo-active-m120-training", "tempo-army-mortar-2013"),
        ("tempo-sme-active-himars", "tempo-sme-13m"),
    ],
)
def test_c_requires_compatible_official_observations(design, eid, sid):
    row = get_row(design, "fa-requirement-active")
    row.update(support_level="C")
    row["evidence_ids"].append(eid)
    row["source_ids"].append(sid)
    with pytest.raises(ValueError, match="C needs"):
        validate(design)


def test_single_observation_cannot_be_independent_multi_source_support(design):
    get_row(design, "estonia-himars")["support_level"] = "B"
    with pytest.raises(ValidationError, match="independence"):
        validate(design)


def test_plans_cannot_become_constraints(design):
    row = get_row(design, "active-m120-training")
    plan = next(
        e
        for e in load_training_tempo(DATA).evidence.records
        if e.tempo_evidence_id == "tempo-active-m120-plan"
    )
    row["evidence_payload"] = plan.claim.model_dump(mode="json")
    with pytest.raises(ValidationError, match="not plans"):
        validate(design)


@pytest.mark.parametrize("field", ["support_level", "uncertainty_ids", "parameters", "prior_type"])
def test_missing_prior_fields_rejected(design, field):
    del scenario(design)[field]
    with pytest.raises(ValidationError):
        validate(design)


@pytest.mark.parametrize(
    "field,value",
    [
        ("uncertainty_type", "mixed"),
        ("uncertainty_type", None),
        ("numerical_weight", 0.5),
        ("dimension", "injury_probability"),
        ("rationale", " "),
    ],
)
def test_uncertainty_must_be_explicit_and_not_one_confidence_number(design, field, value):
    design["priors"]["uncertainties"][0][field] = value
    with pytest.raises(ValidationError):
        validate(design)


def test_missing_uncertainty_classification(design):
    del design["priors"]["uncertainties"][0]["uncertainty_type"]
    with pytest.raises(ValidationError):
        validate(design)


def test_scenario_cannot_drop_an_uncertainty_dimension(design):
    scenario(design)["uncertainty_ids"].pop()
    with pytest.raises(ValidationError, match="all uncertainty"):
        validate(design)


@pytest.mark.parametrize("mode", ["duplicate_id", "dangling", "closed", "blank", "duplicate_link"])
def test_gap_register_integrity(design, mode):
    gaps = design["gaps"]["records"]
    if mode == "duplicate_id":
        gaps[1]["gap_id"] = gaps[0]["gap_id"]
    elif mode == "dangling":
        gaps[0]["current_evidence"] = ["missing-evidence"]
    elif mode == "closed":
        gaps[0]["status"] = "resolved"
    elif mode == "blank":
        gaps[0]["why_needed"] = " "
    else:
        gaps[0]["current_evidence"] *= 2
    with pytest.raises(ValueError):
        validate(design)


@pytest.mark.parametrize(
    "field,value", [("empirical_priors", []), ("numerical_scenarios_authorized", True)]
)
def test_release_cannot_enable_empirical_or_numeric_scenarios(design, field, value):
    design["priors"][field] = value
    with pytest.raises(ValidationError):
        validate(design)


@pytest.mark.parametrize("filename", PRIOR_RELEASE_FILES)
def test_partial_prior_release_fails(design_copy, filename):
    (design_copy / filename).unlink()
    with pytest.raises(FileNotFoundError):
        load_prior_design(design_copy)


@pytest.mark.parametrize("filename", PRIOR_FILES.values())
def test_design_byte_hashes_and_candidate_validation(design_copy, filename):
    path = design_copy / filename
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_prior_design(design_copy)
    load_prior_design(design_copy, verify_manifest=False)


def test_candidate_mode_still_rejects_provenance_edits(design_copy):
    path = design_copy / "prior_definitions.json"
    payload = read_json(path)
    payload["records"][0]["source_ids"] = ["fake"]
    write(path, payload)
    with pytest.raises(ValueError, match="provenance"):
        load_prior_design(design_copy, verify_manifest=False)


def test_duplicate_json_keys_are_rejected(design_copy):
    path = design_copy / "research_gaps.json"
    path.write_text('{"metadata": {}, "metadata": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        load_prior_design(design_copy)


@pytest.mark.parametrize("filename", ["prior_definitions.json", "research_gaps.json"])
def test_partial_json_rejected(design_copy, filename):
    path = design_copy / filename
    path.write_bytes(path.read_bytes()[:-10])
    with pytest.raises(ValueError):
        load_prior_design(design_copy)


def test_stale_schema_rejected_even_with_updated_hash(design_copy):
    path = design_copy / "prior_design.schema.json"
    schema = read_json(path)
    schema["title"] = "Stale"
    write(path, schema)
    with pytest.raises(ValueError, match="schema hash"):
        load_prior_design(design_copy)
    manifest_path = design_copy / "prior_design_manifest.json"
    manifest = read_json(manifest_path)
    manifest["schema_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    write(manifest_path, manifest)
    with pytest.raises(ValueError, match="schema export is stale"):
        load_prior_design(design_copy)


@pytest.mark.parametrize(
    "filename",
    [
        "training_tempo_manifest.json",
        "training_tempo_evidence.json",
        "release_manifest.json",
        "weapons.json",
    ],
)
def test_frozen_dependencies_enforced_in_candidate_mode(design_copy, filename):
    path = design_copy / filename
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="changed|hash mismatch"):
        load_prior_design(design_copy, verify_manifest=False)


@pytest.mark.parametrize("field", ["baseline_commit", "baseline_manifest_sha256", "baseline_tag"])
def test_manifest_pins(design_copy, field):
    path = design_copy / "prior_design_manifest.json"
    manifest = read_json(path)
    manifest[field] = "0" * (64 if field.endswith("sha256") else 40)
    write(path, manifest)
    with pytest.raises(ValueError):
        load_prior_design(design_copy)


def test_manifest_requires_exact_files():
    manifest = read_json(DATA / "prior_design_manifest.json")
    manifest["files"][1] = manifest["files"][0]
    with pytest.raises(ValidationError, match="every design dataset"):
        PriorManifest.model_validate(manifest)


def test_prior_cli_reports_unavailable_empirical_priors(design_copy):
    result = subprocess.run(
        [sys.executable, "-m", "blastbridge.validation.priors", str(design_copy)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == summarize(load_prior_design(design_copy))


def test_reserved_empirical_vocabulary_remains_documented():
    schema = PriorDefinition.model_json_schema()
    assert "empirical_prior" in schema["$defs"]["PriorType"]["enum"]
    assert schema["properties"]["parameters"]["type"] == "null"
    assert schema["properties"]["lower_bound"]["type"] == "null"
