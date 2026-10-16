"""Numbered execution refusals are deterministic and precede RNG/record creation."""

import json
import re
from datetime import date

import pytest
from execution_mapping_fixtures import execution_fixture, replace_parameter
from pydantic import ValidationError

from blastbridge.simulation import engine, fictional
from blastbridge.simulation.execution import MESSAGES, validate_execution_mapping
from blastbridge.simulation.fictional import authorize_fictional_execution
from blastbridge.simulation.models import (
    Codebook,
    EligibilityRelation,
    ExecutionMapping,
    ExecutionRounding,
    FieldBinding,
    FieldDerivation,
    GenerationMethod,
    GenerationProvenance,
    MissingnessMechanism,
    MissingnessTarget,
    ParameterBinding,
    PlacementRule,
    RecordLineage,
    RecordType,
    RngStream,
    RolePresenceRule,
    ScenarioLabel,
    SyntheticCareerDataset,
    SyntheticMember,
)
from blastbridge.simulation.outputs import SyntheticOutput


@pytest.fixture(autouse=True)
def no_engine_execution(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("execution mapping validation constructed RNG/record")

    names = (
        "child_rng",
        "SyntheticMember",
        "CareerEpisode",
        "AssignmentEpisode",
        "TrainingPeriod",
        "LiveFireSession",
        "FiringMission",
        "FiringEvent",
        "ParticipantExposure",
    )
    for name in names:
        monkeypatch.setattr(engine, name, unexpected)
        assert engine.generate.__globals__[name] is unexpected
    assert all(operation is unexpected for operation in engine._execution_operations())


def change_first(mapping, collection, **update):
    values = getattr(mapping, collection)
    return mapping.model_copy(
        update={collection: (values[0].model_copy(update=update), *values[1:])}
    )


def make_invalid(rule, config, scenario, mapping, monkeypatch):
    if rule == "1a":
        mapping = mapping.model_copy(
            update={
                "field_bindings": tuple(
                    field
                    for field in mapping.field_bindings
                    if field.field_ref != "AssignmentEpisode.unit_type"
                )
            }
        )
    elif rule == "1b":
        mapping = mapping.model_copy(
            update={"field_bindings": (*mapping.field_bindings, mapping.field_bindings[0])}
        )
    elif rule == "1c":
        mapping = change_first(mapping, "field_bindings", parameter_id="test-unconfigured")
    elif rule == "1d":
        mapping = change_first(mapping, "field_bindings", field_name="imaginary")
    elif rule == "1e":
        mapping = change_first(mapping, "field_bindings", field_name="career_episode_id")
    elif rule == "1f":
        mapping = mapping.model_copy(
            update={
                "derivations": tuple(
                    item
                    for item in mapping.derivations
                    if item.field_ref != "AssignmentEpisode.occupation_id"
                )
            }
        )
    elif rule == "2a":
        mapping = change_first(mapping, "field_bindings", unit="meters")
    elif rule == "2b":
        config, scenario = replace_parameter(
            config,
            scenario,
            "test-career-duration",
            {"kind": "categorical", "categories": ("TEST_DURATION",), "probabilities": (1.0,)},
        )
    elif rule in {"3a", "3c", "3d"}:
        updates = {
            "3a": {"rounding": None},
            "3c": {"counting_interval": None},
            "3d": {"count_meaning": "missions"},
        }
        mapping = mapping.model_copy(
            update={
                "placement_rules": tuple(
                    item.model_copy(update=updates[rule])
                    if item.record_type == RecordType.SESSION
                    else item
                    for item in mapping.placement_rules
                )
            }
        )
    elif rule == "3b":
        mapping = change_first(mapping, "placement_rules", unit=None)
    elif rule == "4a":
        mapping = mapping.model_copy(update={"codebooks": mapping.codebooks[1:]})
    elif rule == "4b":
        mapping = change_first(mapping, "codebooks", numeric_codes=((2, "fictional-no-prefix"),))
    elif rule == "4c":
        config, scenario = replace_parameter(
            config,
            scenario,
            "test-assignment-platform-eligibility",
            {"kind": "normal", "mean": 2.0, "standard_deviation": 1.0},
        )
    elif rule == "4d":
        config, scenario = replace_parameter(
            config,
            scenario,
            "test-assignment-platform-eligibility",
            {"kind": "categorical", "categories": ("TEST_PLATFORM",), "probabilities": (1.0,)},
        )
    elif rule == "4e":
        monkeypatch.setattr(fictional, "_catalog_ids", lambda: {"test-platform-alpha"})
    elif rule == "4f":
        mapping = change_first(mapping, "codebooks", permitted_values=("test-occupation-alpha",))
    elif rule == "4g":
        mapping = change_first(
            mapping, "eligibility", eligible_weapon_ids=("test-unlisted-weapon",)
        )
    elif rule == "4h":
        mapping = mapping.model_copy(update={"eligibility": ()})
    elif rule == "4i":
        mapping = change_first(mapping, "eligibility", eligible_platform_ids=())
    elif rule == "5e":
        mapping = change_first(
            mapping, "role_presence_rules", instructor_status=False, student_status=True
        )
    elif rule == "5a":
        values = list(mapping.role_presence_rules)
        values[1] = values[1].model_copy(update={"quantity": "role_participation"})
        mapping = mapping.model_copy(update={"role_presence_rules": tuple(values)})
    elif rule == "5b":
        mapping = change_first(
            mapping, "role_presence_rules", participation_type="test-not-an-enum"
        )
    elif rule == "5c":
        mapping = change_first(mapping, "role_presence_rules", presence_description="")
    elif rule == "5d":
        mapping = change_first(
            mapping, "role_presence_rules", instructor_status=True, student_status=True
        )
    elif rule == "6a":
        mapping = mapping.model_copy(
            update={
                "placement_rules": tuple(
                    item
                    for item in mapping.placement_rules
                    if item.record_type != RecordType.MISSION
                )
            }
        )
    elif rule == "6b":
        mapping = change_first(mapping, "placement_rules", timezone="America/New_York")
    elif rule == "6c":
        rules = tuple(
            item.model_copy(update={"shape": "uniform", "shape_parameter_id": None})
            if item.record_type == RecordType.SESSION
            else item
            for item in mapping.placement_rules
        )
        mapping = mapping.model_copy(update={"placement_rules": rules})
    elif rule == "7a":
        mapping = change_first(
            mapping, "missingness_targets", field_ref="AssignmentEpisode.imaginary"
        )
    elif rule == "7b":
        mapping = change_first(
            mapping, "missingness_targets", field_ref="AssignmentEpisode.weapon_system_ids"
        )
    elif rule == "7c":
        rule_value = config.missingness_configuration.rules[0].model_copy(
            update={"mechanism": MissingnessMechanism.NOT_COLLECTED}
        )
        missingness = config.missingness_configuration.model_copy(update={"rules": (rule_value,)})
        config = config.model_copy(update={"missingness_configuration": missingness})
    elif rule == "7d":
        config, mapping = mcar_mapping(config, mapping)
        mapping = change_first(
            mapping, "missingness_targets", mcar_probability_parameter_id="test-placement-end"
        )
    elif rule == "7e":
        mapping = change_first(
            mapping,
            "missingness_targets",
            mcar_probability_parameter_id="test-placement-probability",
        )
    elif rule == "7f":
        mapping = mapping.model_copy(
            update={
                "missingness_targets": (
                    *mapping.missingness_targets,
                    mapping.missingness_targets[0],
                )
            }
        )
    elif rule == "7g":
        rule_value = config.missingness_configuration.rules[0].model_copy(
            update={"condition_quantity_ids": ("role",)}
        )
        missingness = config.missingness_configuration.model_copy(update={"rules": (rule_value,)})
        config = config.model_copy(update={"missingness_configuration": missingness})
    elif rule == "7h":
        mapping = mapping.model_copy(update={"missingness_targets": ()})
    elif rule == "7i":
        mapping = mapping.model_copy(update={"evaluation_order": mapping.evaluation_order[:-1]})
    elif rule == "7j":
        mapping = mapping.model_copy(
            update={"evaluation_order": tuple(reversed(mapping.evaluation_order))}
        )
    elif rule == "8a":
        mapping = change_first(mapping, "record_lineage", parameter_ids=("test-placement-zero",))
    elif rule == "9a":
        mapping = mapping.model_copy(update={"scenario_version": "0.4.1"})
    elif rule == "9b":
        scenario = scenario.model_copy(update={"label": ScenarioLabel.EXPLORATORY_CENTRAL})
    else:
        raise AssertionError(rule)
    return config, scenario, mapping


def mcar_mapping(config, mapping):
    rule = config.missingness_configuration.rules[0].model_copy(
        update={
            "mechanism": MissingnessMechanism.MCAR,
            "scenario_assumption_id": "test-assumption-alpha",
        }
    )
    config = config.model_copy(
        update={
            "missingness_configuration": config.missingness_configuration.model_copy(
                update={"rules": (rule,)}
            )
        }
    )
    mapping = change_first(
        mapping,
        "missingness_targets",
        latent_never_none=True,
        mcar_probability_parameter_id="test-placement-probability",
    )
    return config, mapping


@pytest.mark.parametrize("rule", tuple(MESSAGES))
def test_numbered_refusal(rule, monkeypatch):
    config, scenario, _, mapping = execution_fixture()
    config, scenario, mapping = make_invalid(rule, config, scenario, mapping, monkeypatch)
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES[rule])}$"):
        validate_execution_mapping(config, scenario, mapping)


def test_complete_fictional_mapping_authorizes_without_generation():
    config, scenario, approval, mapping = execution_fixture()
    validate_execution_mapping(config, scenario, mapping)
    authorize_fictional_execution(config, scenario, approval, mapping)


def test_explicit_mcar_mapping_authorizes_and_engine_executes(monkeypatch):
    from blastbridge.simulation import models, rng

    # Restore real operations only for this positive execution test; the autouse
    # fixture continues to forbid execution in every other mapping test.
    for name in (
        "SyntheticMember",
        "CareerEpisode",
        "AssignmentEpisode",
        "TrainingPeriod",
        "LiveFireSession",
        "FiringMission",
        "FiringEvent",
        "ParticipantExposure",
    ):
        monkeypatch.setattr(engine, name, getattr(models, name))
    monkeypatch.setattr(engine, "child_rng", rng.child_rng)
    config, scenario, approval, mapping = execution_fixture()
    config, mapping = mcar_mapping(config, mapping)
    authorize_fictional_execution(config, scenario, approval, mapping)
    assert isinstance(engine.generate(config, scenario, approval, mapping), SyntheticCareerDataset)


@pytest.mark.parametrize("where", ["mapping_id", "permitted_values", "evaluation_order", "catalog"])
def test_mapping_content_gate_refuses_nonfictional_identifiers(where):
    config, scenario, approval, mapping = execution_fixture()
    if where == "mapping_id":
        mapping = mapping.model_copy(update={"mapping_id": "unprefixed-mapping"})
    elif where == "permitted_values":
        mapping = change_first(
            mapping,
            "codebooks",
            numeric_codes=None,
            permitted_values=("unprefixed-occupation",),
        )
    elif where == "evaluation_order":
        mapping = mapping.model_copy(
            update={"evaluation_order": (*mapping.evaluation_order, "unprefixed-step")}
        )
    else:
        catalog_id = sorted(fictional._catalog_ids())[0]
        mapping = mapping.model_copy(
            update={
                "eligibility": (
                    mapping.eligibility[0].model_copy(update={"occupation_id": catalog_id}),
                )
            }
        )
    with pytest.raises(ValueError, match="fictional identifier must start with test-"):
        authorize_fictional_execution(config, scenario, approval, mapping)


@pytest.mark.parametrize(
    "violation", ["empirical_lineage", "empirical_distribution", "non_test_id"]
)
def test_execution_bindings_pass_through_fictional_content_gate(violation):
    config, scenario, approval, mapping = execution_fixture()
    binding = config.execution_bindings[0]
    updates = {
        "empirical_lineage": {"prior_definition_ids": ("test-forbidden-prior",)},
        "empirical_distribution": {"distribution": {"kind": "empirical", "values": (1.0,)}},
        "non_test_id": {"parameter_id": "nonfictional-parameter"},
    }[violation]
    if violation == "empirical_distribution":
        payload = binding.model_dump()
        payload.update(updates)
        binding = ParameterBinding.model_validate(payload)
    else:
        binding = binding.model_copy(update=updates)
    config = config.model_copy(
        update={"execution_bindings": (binding, *config.execution_bindings[1:])}
    )
    expected = {
        "empirical_lineage": "fictional prior_definition_ids must be empty",
        "empirical_distribution": "fictional empirical distribution refused",
        "non_test_id": "fictional identifier must start with test-",
    }[violation]
    with pytest.raises(ValueError, match=expected):
        authorize_fictional_execution(config, scenario, approval, mapping)


def test_execution_binding_exact_scenario_match_is_required():
    config, scenario, approval, mapping = execution_fixture()
    binding = config.execution_bindings[0].model_copy(update={"uncertainty_types": ("epistemic",)})
    config = config.model_copy(
        update={"execution_bindings": (binding, *config.execution_bindings[1:])}
    )
    with pytest.raises(
        ValueError, match="^configuration parameter must exactly match the scenario definition$"
    ):
        authorize_fictional_execution(config, scenario, approval, mapping)


def test_execution_binding_undeclared_assumption_is_refused():
    config, scenario, approval, mapping = execution_fixture()
    binding = config.execution_bindings[0].model_copy(
        update={"scenario_assumption_ids": ("test-undeclared-assumption",)}
    )
    config = config.model_copy(
        update={"execution_bindings": (binding, *config.execution_bindings[1:])}
    )
    parameters = tuple(
        binding if item.parameter_id == binding.parameter_id else item
        for item in scenario.parameters
    )
    # model_copy deliberately bypasses ScenarioDefinition's own join check, so
    # validate_configuration_references must reject the execution binding itself.
    scenario = scenario.model_copy(update={"parameters": parameters})
    with pytest.raises(ValueError, match="^configuration references an undeclared assumption$"):
        authorize_fictional_execution(config, scenario, approval, mapping)


def test_execution_binding_provenance_is_accepted_by_output_validation():
    config, scenario, _, mapping = execution_fixture()
    validate_execution_mapping(config, scenario, mapping)
    binding = config.execution_bindings[0]
    member_lineage = next(
        item for item in mapping.record_lineage if item.record_type == RecordType.MEMBER
    )
    provenance = GenerationProvenance(
        simulation_id=config.simulation_id,
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.scenario_version,
        generator_version=config.generator_version,
        rng_algorithm=config.rng_algorithm,
        master_seed=config.master_seed,
        rng_stream=RngStream.POPULATION,
        generation_method=GenerationMethod.FIXED,
        prior_definition_ids=(),
        evidence_ids=(),
        sme_estimate_ids=(),
        scenario_assumption_ids=binding.scenario_assumption_ids,
        parameter_ids=member_lineage.parameter_ids,
        uncertainty_types=binding.uncertainty_types,
    )
    member = SyntheticMember(
        member_id="SYN-MEMBER-000001",
        service_start=date(2020, 1, 1),
        service_end=date(2020, 1, 31),
        provenance=provenance,
    )
    records = SyntheticCareerDataset(
        members=(member,),
        career_episodes=(),
        assignments=(),
        training_periods=(),
        live_fire_sessions=(),
        firing_missions=(),
        firing_events=(),
        participant_exposures=(),
    )
    SyntheticOutput(config=config, scenario=scenario, records=records)
    execution_ids = {item.parameter_id for item in config.execution_bindings}
    assert execution_ids <= set(provenance.parameter_ids)


def test_whole_mapping_fingerprint_is_canonical_and_sensitive():
    _, _, _, mapping = execution_fixture()
    round_trip = ExecutionMapping.model_validate(json.loads(mapping.canonical_json()))
    assert mapping.fingerprint() == round_trip.fingerprint()
    changed = change_first(mapping, "missingness_targets", latent_never_none=True)
    assert changed.fingerprint() != mapping.fingerprint()
    assert mapping.canonical_json() == json.dumps(
        mapping.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False
    )


@pytest.mark.parametrize(
    "model,collection",
    [
        (ExecutionMapping, None),
        (FieldBinding, "field_bindings"),
        (FieldDerivation, "derivations"),
        (Codebook, "codebooks"),
        (EligibilityRelation, "eligibility"),
        (RolePresenceRule, "role_presence_rules"),
        (PlacementRule, "placement_rules"),
        (MissingnessTarget, "missingness_targets"),
        (RecordLineage, "record_lineage"),
    ],
)
def test_contract_models_reject_undeclared_fields(model, collection):
    _, _, _, mapping = execution_fixture()
    payload = (
        mapping.model_dump() if collection is None else getattr(mapping, collection)[0].model_dump()
    )
    payload["undeclared"] = "TEST_EXTRA"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        model.model_validate(payload)


@pytest.mark.parametrize("rounding", ["nearest", "truncate"])
def test_rounding_contract_is_closed(rounding):
    _, _, _, mapping = execution_fixture()
    payload = mapping.placement_rules[4].model_dump()
    payload["rounding"] = rounding
    with pytest.raises(ValidationError):
        PlacementRule.model_validate(payload)
    assert {item.value for item in ExecutionRounding} == {"floor", "ceil", "reject"}


@pytest.mark.parametrize(
    "collection",
    ["placement_rules", "role_presence_rules", "missingness_targets", "record_lineage"],
)
def test_all_execution_references_require_the_configured_scenario_intersection(collection):
    config, scenario, _, mapping = execution_fixture()
    fields = {
        "placement_rules": "start_parameter_id",
        "role_presence_rules": "presence_parameter_id",
        "missingness_targets": "mcar_probability_parameter_id",
        "record_lineage": "parameter_ids",
    }
    value = ("test-unconfigured",) if collection == "record_lineage" else "test-unconfigured"
    mapping = change_first(mapping, collection, **{fields[collection]: value})
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES['1c'])}$"):
        validate_execution_mapping(config, scenario, mapping)


@pytest.mark.parametrize("probability", [0.0, 1.0])
def test_mcar_endpoint_probabilities_are_valid_declarations(probability):
    config, scenario, approval, mapping = execution_fixture()
    config, scenario = replace_parameter(
        config, scenario, "test-placement-probability", {"kind": "fixed", "value": probability}
    )
    config, mapping = mcar_mapping(config, mapping)
    authorize_fictional_execution(config, scenario, approval, mapping)


def test_documented_bounded_role_probability_can_be_variable():
    config, scenario, approval, mapping = execution_fixture()
    config, scenario = replace_parameter(
        config, scenario, "test-placement-probability", {"kind": "beta", "alpha": 1.0, "beta": 1.0}
    )
    authorize_fictional_execution(config, scenario, approval, mapping)


def test_wrong_execution_generator_version_is_refused():
    config, scenario, _, mapping = execution_fixture()
    mapping = mapping.model_copy(update={"execution_generator_version": "0.5.0"})
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES['9b'])}$"):
        validate_execution_mapping(config, scenario, mapping)


def test_structural_evaluation_order_is_enforced():
    config, scenario, _, mapping = execution_fixture()
    mapping = mapping.model_copy(
        update={"evaluation_order": tuple(reversed(mapping.evaluation_order))}
    )
    with pytest.raises(
        ValueError,
        match=f"^{re.escape(MESSAGES['7j'])}$",
    ):
        validate_execution_mapping(config, scenario, mapping)


@pytest.mark.parametrize(
    "field_ref",
    [
        "CareerEpisode.branch",
        "CareerEpisode.component",
        "AssignmentEpisode.occupation_id",
        "AssignmentEpisode.unit_type",
        "AssignmentEpisode.weapon_system_ids",
        "AssignmentEpisode.crew_role",
        "AssignmentEpisode.training_context",
        "AssignmentEpisode.deployment_or_training_cycle_status",
        "AssignmentEpisode.instructor_status",
        "AssignmentEpisode.student_status",
        "FiringEvent.weapon_system_id",
        "FiringEvent.weapon_family",
        "FiringEvent.training_context",
        "FiringEvent.ammunition_configuration_id",
    ],
)
def test_dropping_required_field_source_is_refused(field_ref):
    config, scenario, _, mapping = execution_fixture()
    # Keep parameter consumption intact in another explicit source, so this
    # isolates field coverage rather than the earlier required-quantity rule.
    fields = tuple(item for item in mapping.field_bindings if item.field_ref != field_ref)
    derivations = tuple(
        item
        for item in mapping.derivations
        if item.field_ref != field_ref
        and not (
            field_ref == "AssignmentEpisode.student_status"
            and item.operation == "assignment_status"
        )
    )
    removed_ids = {
        item.parameter_id for item in mapping.field_bindings if item.field_ref == field_ref
    }
    for item in mapping.derivations:
        if item not in derivations:
            removed_ids.update(item.parameter_ids)
    surviving = list(derivations)
    surviving[0] = surviving[0].model_copy(
        update={
            "parameter_ids": tuple(
                dict.fromkeys((*surviving[0].parameter_ids, *sorted(removed_ids)))
            )
        }
    )
    mapping = mapping.model_copy(update={"field_bindings": fields, "derivations": tuple(surviving)})
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES['1f'])}$"):
        validate_execution_mapping(config, scenario, mapping)


def test_all_coverable_fields_have_exactly_one_source():
    from blastbridge.simulation.execution import (
        ENGINE_FIELDS,
        RECORD_MODELS,
        declared_field_sources,
    )

    _, _, _, mapping = execution_fixture()
    sources = declared_field_sources(mapping)
    expected = {
        f"{kind.value}.{name}"
        for kind, model in RECORD_MODELS.items()
        for name in model.model_fields
        if name not in ENGINE_FIELDS
    }
    assert set(sources) == expected
    assert all(len(writers) == 1 for writers in sources.values())


@pytest.mark.parametrize("writer", ["role", "derivation", "placement"])
def test_writer_conflicts_are_refused_across_source_kinds(writer):
    config, scenario, _, mapping = execution_fixture()
    if writer == "placement":
        mapping = mapping.model_copy(
            update={"placement_rules": (*mapping.placement_rules, mapping.placement_rules[0])}
        )
    else:
        target = "role" if writer == "role" else "occupation_id"
        kind = RecordType.EXPOSURE if writer == "role" else RecordType.ASSIGNMENT
        field = FieldBinding(
            parameter_id="test-assignment-occupation-selection",
            record_type=kind,
            field_name=target,
            value_type="identifier",
        )
        mapping = mapping.model_copy(update={"field_bindings": (*mapping.field_bindings, field)})
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES['1b'])}$"):
        validate_execution_mapping(config, scenario, mapping)


@pytest.mark.parametrize(
    "field_ref",
    ["CareerEpisode.end_date", "FiringEvent.timestamp", "FiringEvent.round_or_launch_index"],
)
def test_time_and_round_index_cannot_be_written_by_bindings(field_ref):
    config, scenario, _, mapping = execution_fixture()
    record, _, name = field_ref.partition(".")
    field = FieldBinding(
        parameter_id="test-placement-one",
        record_type=record,
        field_name=name,
        value_type="int",
        unit="count",
        rounding="reject",
        count_meaning="physical_discharges",
        counting_interval="per_session",
    )
    mapping = mapping.model_copy(update={"field_bindings": (*mapping.field_bindings, field)})
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES['1e'])}$"):
        validate_execution_mapping(config, scenario, mapping)


@pytest.mark.parametrize("statuses", [(True, True), (None, False)])
def test_each_role_rule_refuses_conflicting_or_missing_status(statuses):
    config, scenario, _, mapping = execution_fixture()
    mapping = change_first(
        mapping, "role_presence_rules", instructor_status=statuses[0], student_status=statuses[1]
    )
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES['5d'])}$"):
        validate_execution_mapping(config, scenario, mapping)


@pytest.mark.parametrize(
    "kind,statuses", [("instructor", (False, False)), ("student", (True, False))]
)
def test_role_type_requires_its_own_status_pair(kind, statuses):
    from blastbridge.simulation.models import ParticipationType

    config, scenario, _, mapping = execution_fixture()
    mapping = change_first(
        mapping,
        "role_presence_rules",
        participation_type=ParticipationType(kind),
        instructor_status=statuses[0],
        student_status=statuses[1],
    )
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES['5d'])}$"):
        validate_execution_mapping(config, scenario, mapping)


@pytest.mark.parametrize(
    "parameter", ["test-army-active-event-frequency", "test-army-active-rounds-per-event"]
)
@pytest.mark.parametrize("destination", [RecordType.SESSION, RecordType.MISSION, RecordType.EVENT])
def test_frequency_and_rounds_have_only_their_declared_count_route(parameter, destination):
    config, scenario, _, mapping = execution_fixture()
    expected = RecordType.SESSION if "event-frequency" in parameter else RecordType.EVENT
    if destination == expected:
        validate_execution_mapping(config, scenario, mapping)
        return
    meanings = {
        RecordType.SESSION: "sessions",
        RecordType.MISSION: "missions",
        RecordType.EVENT: "physical_discharges",
    }
    placements = tuple(
        item.model_copy(
            update={"count_parameter_id": parameter, "count_meaning": meanings[destination]}
        )
        if item.record_type == destination
        else item
        for item in mapping.placement_rules
    )
    # A SESSION/EVENT swap retains consumption of both quantities, so the
    # rejection isolates routing instead of first failing required-quantity coverage.
    if destination in {RecordType.SESSION, RecordType.EVENT}:
        opposite = RecordType.EVENT if destination == RecordType.SESSION else RecordType.SESSION
        displaced = (
            "test-army-active-event-frequency"
            if opposite == RecordType.EVENT
            else "test-army-active-rounds-per-event"
        )
        placements = tuple(
            item.model_copy(update={"count_parameter_id": displaced})
            if item.record_type == opposite
            else item
            for item in placements
        )
    mapping = mapping.model_copy(update={"placement_rules": placements})
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES['3d'])}$"):
        validate_execution_mapping(config, scenario, mapping)


def test_event_placement_requires_physical_discharge_count():
    config, scenario, _, mapping = execution_fixture()
    placements = tuple(
        item.model_copy(update={"count_parameter_id": None})
        if item.record_type == RecordType.EVENT
        else item
        for item in mapping.placement_rules
    )
    mapping = mapping.model_copy(update={"placement_rules": placements})
    # Preserve rounds consumption to isolate missing event placement semantics.
    # _placement_checks itself validates declarations without constructing rows.
    from blastbridge.simulation.execution import _placement_checks
    from blastbridge.simulation.models import configured_parameter_bindings

    parameters = {item.parameter_id: item for item in configured_parameter_bindings(config)}
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES['6a'])}$"):
        _placement_checks(mapping, parameters)


@pytest.mark.parametrize(
    "reference",
    [
        "AssignmentEpisode.platform_id",
        "FiringEvent.weapon_system_id",
    ],
)
def test_eligibility_selection_is_derivation_only(reference):
    config, scenario, approval, mapping = execution_fixture()
    source = next(item for item in mapping.derivations if item.field_ref == reference)
    field = FieldBinding(
        parameter_id=source.selector_parameter_id,
        record_type=source.record_type,
        field_name=source.field_name,
        value_type="identifier",
    )
    mapping = mapping.model_copy(
        update={
            "field_bindings": (*mapping.field_bindings, field),
            "derivations": tuple(item for item in mapping.derivations if item != source),
        }
    )
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES['1e'])}$"):
        authorize_fictional_execution(config, scenario, approval, mapping)


@pytest.mark.parametrize(
    "reference",
    [
        "AssignmentEpisode.platform_id",
        "FiringEvent.weapon_system_id",
    ],
)
def test_plain_codebook_derivation_cannot_bypass_eligibility(reference):
    config, scenario, approval, mapping = execution_fixture()
    mapping = mapping.model_copy(
        update={
            "derivations": tuple(
                item.model_copy(update={"operation": "identifier_codebook"})
                if item.field_ref == reference
                else item
                for item in mapping.derivations
            )
        }
    )
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES['1e'])}$"):
        authorize_fictional_execution(config, scenario, approval, mapping)


@pytest.mark.parametrize(
    "source_reference",
    [
        "AssignmentEpisode.weapon_system_ids",
        "AssignmentEpisode.unit_type",
    ],
)
def test_carry_forward_requires_matching_scalar_fields(source_reference):
    config, scenario, approval, mapping = execution_fixture()
    mapping = mapping.model_copy(
        update={
            "derivations": tuple(
                item.model_copy(update={"source_field_ref": source_reference})
                if item.field_ref == "FiringEvent.training_context"
                else item
                for item in mapping.derivations
            )
        }
    )
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES['2a'])}$"):
        authorize_fictional_execution(config, scenario, approval, mapping)


@pytest.mark.parametrize("eligible_field", ["eligible_platform_ids", "eligible_weapon_ids"])
def test_selector_cannot_choose_outside_occupation_eligibility(eligible_field):
    config, scenario, approval, mapping = execution_fixture()
    mapping = change_first(mapping, "eligibility", **{eligible_field: ()})
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES['4i'])}$"):
        authorize_fictional_execution(config, scenario, approval, mapping)


def test_every_occupation_codebook_value_requires_eligibility():
    config, scenario, approval, mapping = execution_fixture()
    mapping = change_first(
        mapping,
        "codebooks",
        numeric_codes=(
            (2, "test-occupation-alpha"),
            (3, "test-occupation-unmapped"),
        ),
    )
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES['4h'])}$"):
        authorize_fictional_execution(config, scenario, approval, mapping)


def test_role_status_pair_must_be_declared_by_assignment_status():
    config, scenario, approval, mapping = execution_fixture()
    mapping = change_first(
        mapping, "role_presence_rules", instructor_status=False, student_status=True
    )
    with pytest.raises(ValueError, match=f"^{re.escape(MESSAGES['5e'])}$"):
        authorize_fictional_execution(config, scenario, approval, mapping)
