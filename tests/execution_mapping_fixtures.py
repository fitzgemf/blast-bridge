"""Fictional execution declarations, without an assembler or career dataset."""

from test_fictional_guard import _approval, _binding, _config, _scenario

from blastbridge.simulation.execution import RECORD_STREAMS
from blastbridge.simulation.models import (
    BindingValueType,
    Codebook,
    Component,
    DependencyMode,
    EligibilityRelation,
    ExecutionMapping,
    FieldBinding,
    FieldDerivation,
    MissingnessTarget,
    ParameterBinding,
    ParticipationType,
    PlacementRule,
    RecordLineage,
    RecordType,
    RolePresenceRule,
    ScenarioDefinition,
    SimulationConfig,
    UncertaintyType,
    configured_parameter_bindings,
)


def execution_fixture():
    config, scenario = _config(), _scenario()
    training = config.training_configuration
    dependencies = tuple(
        item.model_copy(
            update={
                "mode": DependencyMode.INDEPENDENT_ASSUMPTION,
                "scenario_assumption_id": "test-assumption-alpha",
                "uncertainty_types": (UncertaintyType.ALEATORY,),
            }
        )
        for item in training.dependencies
    )
    training = training.model_copy(update={"dependencies": dependencies})
    extra = []
    for name, value in (("zero", 0.0), ("end", 30.0), ("one", 1.0), ("probability", 0.5)):
        payload = _binding(f"test-placement-{name}")
        payload["distribution"] = {"kind": "fixed", "value": value}
        extra.append(ParameterBinding.model_validate(payload))
    for name in ("unit", "crew-role", "cycle-status", "weapon", "weapon-family", "ammunition"):
        payload = _binding(f"test-field-{name}")
        extra.append(ParameterBinding.model_validate(payload))
    config = config.model_copy(
        update={
            "training_configuration": training,
            "execution_bindings": tuple(extra),
            "population_size": 1,
        }
    )
    scenario = scenario.model_copy(update={"parameters": (*scenario.parameters, *extra)})
    declarations = (
        (
            RecordType.CAREER,
            "occupation_id",
            "test-assignment-occupation-selection",
            "test-occupation-alpha",
        ),
        (
            RecordType.ASSIGNMENT,
            "platform_id",
            "test-assignment-platform-eligibility",
            "test-platform-alpha",
        ),
        (
            RecordType.ASSIGNMENT,
            "training_context",
            "test-training-cycle-context",
            "test-context-alpha",
        ),
        (RecordType.ASSIGNMENT, "unit_type", "test-field-unit", "test-unit-alpha"),
        (RecordType.ASSIGNMENT, "crew_role", "test-field-crew-role", "test-crew-role-alpha"),
        (
            RecordType.ASSIGNMENT,
            "deployment_or_training_cycle_status",
            "test-field-cycle-status",
            "test-cycle-alpha",
        ),
        (RecordType.EVENT, "weapon_system_id", "test-field-weapon", "test-weapon-alpha"),
        (
            RecordType.EVENT,
            "ammunition_configuration_id",
            "test-field-ammunition",
            "test-ammunition-alpha",
        ),
    )
    fields = tuple(
        FieldBinding(
            parameter_id=parameter,
            record_type=kind,
            field_name=name,
            value_type=BindingValueType.IDENTIFIER,
        )
        for kind, name, parameter, value in declarations
    )
    codebooks = tuple(
        Codebook(field_ref=field.field_ref, numeric_codes=((2, value),))
        for field, (_, _, _, value) in zip(fields, declarations, strict=True)
    ) + (
        Codebook(field_ref="FiringEvent.weapon_family", numeric_codes=((2, "test-family-alpha"),)),
        Codebook(field_ref="ParticipantExposure.role", numeric_codes=((2, "test-role-alpha"),)),
    )
    derivations = (
        FieldDerivation(
            record_type=RecordType.CAREER,
            field_name="component",
            operation="component_selection",
            parameter_ids=(
                "test-population-army-active-weight",
                "test-career-component-transition",
            ),
            selector_parameter_id="test-career-component-transition",
            component_codes=((2, Component.ARMY_ACTIVE),),
        ),
        FieldDerivation(
            record_type=RecordType.CAREER,
            field_name="branch",
            operation="branch_from_component",
            parameter_ids=(
                "test-population-army-active-weight",
                "test-career-component-transition",
            ),
            source_field_ref="CareerEpisode.component",
        ),
        FieldDerivation(
            record_type=RecordType.ASSIGNMENT,
            field_name="occupation_id",
            operation="carry_forward",
            parameter_ids=("test-assignment-occupation-selection",),
            source_field_ref="CareerEpisode.occupation_id",
        ),
        FieldDerivation(
            record_type=RecordType.ASSIGNMENT,
            field_name="weapon_system_ids",
            operation="eligibility_weapons",
            parameter_ids=(
                "test-assignment-occupation-selection",
                "test-assignment-platform-eligibility",
            ),
            source_field_ref="AssignmentEpisode.occupation_id",
        ),
        FieldDerivation(
            record_type=RecordType.ASSIGNMENT,
            field_name="instructor_status",
            operation="assignment_status",
            parameter_ids=("test-placement-one",),
            selector_parameter_id="test-placement-one",
            status_codes=((0, False, False), (1, True, False)),
        ),
        FieldDerivation(
            record_type=RecordType.TRAINING,
            field_name="training_context",
            operation="carry_forward",
            parameter_ids=("test-training-cycle-context",),
            source_field_ref="AssignmentEpisode.training_context",
        ),
        FieldDerivation(
            record_type=RecordType.EVENT,
            field_name="training_context",
            operation="carry_forward",
            parameter_ids=("test-training-cycle-context",),
            source_field_ref="AssignmentEpisode.training_context",
        ),
        FieldDerivation(
            record_type=RecordType.EVENT,
            field_name="weapon_family",
            operation="identifier_codebook",
            parameter_ids=("test-field-weapon-family",),
            selector_parameter_id="test-field-weapon-family",
            codebook_field_ref="FiringEvent.weapon_family",
        ),
    )
    fields = tuple(
        field
        for field in fields
        if field.field_ref not in {"AssignmentEpisode.platform_id", "FiringEvent.weapon_system_id"}
    )
    derivations += (
        FieldDerivation(
            record_type=RecordType.ASSIGNMENT,
            field_name="platform_id",
            operation="eligibility_platform",
            parameter_ids=("test-assignment-platform-eligibility",),
            selector_parameter_id="test-assignment-platform-eligibility",
            source_field_ref="AssignmentEpisode.occupation_id",
            codebook_field_ref="AssignmentEpisode.platform_id",
        ),
        FieldDerivation(
            record_type=RecordType.EVENT,
            field_name="weapon_system_id",
            operation="assignment_weapon",
            parameter_ids=("test-field-weapon",),
            selector_parameter_id="test-field-weapon",
            source_field_ref="AssignmentEpisode.weapon_system_ids",
            codebook_field_ref="FiringEvent.weapon_system_id",
        ),
    )
    roles = tuple(
        RolePresenceRule(
            quantity=quantity,
            parameter_id=f"test-participation-{suffix}",
            role_id="test-role-alpha",
            participation_type=kind,
            presence_parameter_id="test-placement-probability"
            if quantity == "role_participation"
            else "test-placement-one",
            presence_semantics="probability"
            if quantity == "role_participation"
            else "boolean_code",
            presence_description="TEST explicit fixed presence probability"
            if quantity == "role_participation"
            else "TEST 0 absent; 1 present",
            repetition_scope="per_event",
            instructor_status=kind == ParticipationType.INSTRUCTOR,
            student_status=False,
        )
        for quantity, suffix, kind in (
            ("role_participation", "role", ParticipationType.FIRED_WEAPON),
            ("nearby_participation", "nearby", ParticipationType.NEARBY_CREW),
            ("instructor_repeated_presence", "instructor", ParticipationType.INSTRUCTOR),
        )
    )
    placements = []
    date_records = {
        RecordType.MEMBER,
        RecordType.CAREER,
        RecordType.ASSIGNMENT,
        RecordType.TRAINING,
    }
    for kind in RecordType:
        if kind == RecordType.EXPOSURE:
            continue
        data = {
            "record_type": kind,
            "timezone": "UTC",
            "shape": "binding_offsets",
            "unit": "days" if kind in date_records else "hours",
            "containment": "inclusive",
            "clip": False,
            "resample": False,
            "rounding": "reject",
        }
        if kind == RecordType.MEMBER:
            data.update(
                start_parameter_id="test-placement-zero",
                end_parameter_id="test-placement-end",
            )
        else:
            data.update(offset_parameter_id="test-placement-zero")
            if kind != RecordType.EVENT:
                data.update(duration_parameter_id="test-placement-one")
            if kind == RecordType.CAREER:
                data.update(
                    duration_parameter_id="test-career-duration",
                    partition_parameter_id="test-career-episode-count",
                )
            if kind in {RecordType.ASSIGNMENT, RecordType.TRAINING}:
                data.update(partition_parameter_id="test-placement-one")
            if kind == RecordType.ASSIGNMENT:
                data.update(duration_parameter_id="test-assignment-duration")
            if kind in {RecordType.MISSION, RecordType.EVENT}:
                data.update(mission_applicability_parameter_id="test-placement-one")
            if kind == RecordType.SESSION:
                data.update(
                    count_parameter_id="test-army-active-event-frequency",
                    rounding="reject",
                    count_meaning="sessions",
                    counting_interval="per_training_period",
                )
            if kind == RecordType.MISSION:
                data.update(
                    count_parameter_id="test-placement-one",
                    count_meaning="missions",
                    counting_interval="per_session",
                )
            if kind == RecordType.EVENT:
                data.update(
                    count_parameter_id="test-army-active-rounds-per-event",
                    count_meaning="physical_discharges",
                    counting_interval="per_session",
                )
        placements.append(PlacementRule.model_validate(data))
    parameter_ids = tuple(
        sorted(item.parameter_id for item in configured_parameter_bindings(config))
    )
    mapping = ExecutionMapping(
        mapping_id="test-mapping-alpha",
        mapping_version="0.5.0",
        execution_generator_version="0.4.0",
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.scenario_version,
        field_bindings=fields,
        derivations=derivations,
        codebooks=codebooks,
        eligibility=(
            EligibilityRelation(
                occupation_id="test-occupation-alpha",
                eligible_weapon_ids=("test-weapon-alpha",),
                eligible_platform_ids=("test-platform-alpha",),
            ),
        ),
        role_presence_rules=roles,
        placement_rules=tuple(placements),
        missingness_targets=(
            MissingnessTarget(
                target_quantity="platform-id",
                field_ref="AssignmentEpisode.platform_id",
                latent_never_none=False,
            ),
        ),
        record_lineage=tuple(
            RecordLineage(
                record_type=kind, parameter_ids=parameter_ids, rng_stream=RECORD_STREAMS[kind]
            )
            for kind in RecordType
        ),
        evaluation_order=("sample", *(kind.value for kind in RecordType), "place", "mask"),
    )
    return config, scenario, _approval(), mapping


def replace_parameter(config, scenario, parameter_id, distribution):
    """Keep the exact config/scenario join when changing a distribution."""

    def replace(value):
        if isinstance(value, dict):
            result = {key: replace(item) for key, item in value.items()}
            if result.get("parameter_id") == parameter_id:
                result["distribution"] = distribution
            return result
        if isinstance(value, tuple):
            return tuple(replace(item) for item in value)
        return value

    return (
        SimulationConfig.model_validate(replace(config.model_dump())),
        ScenarioDefinition.model_validate(replace(scenario.model_dump())),
    )


def assembly_fixture(population_size=1, event_count=12):
    """Additive executable fixture: one status-matched role and variable event ownership."""
    config, scenario, approval, mapping = execution_fixture()
    additions = []
    for suffix, distribution in (
        ("status", {"kind": "fixed", "value": 0}),
        ("event-applicability", {"kind": "discrete_uniform", "lower": 0, "upper": 1}),
    ):
        payload = _binding(f"test-assembly-{suffix}")
        payload["distribution"] = distribution
        additions.append(ParameterBinding.model_validate(payload))
    config = config.model_copy(
        update={
            "population_size": population_size,
            "execution_bindings": (*config.execution_bindings, *additions),
        }
    )
    scenario = scenario.model_copy(update={"parameters": (*scenario.parameters, *additions)})
    for parameter, value in (
        ("test-career-episode-count", 1),
        ("test-army-active-event-frequency", 1),
        ("test-army-active-rounds-per-event", event_count),
    ):
        config, scenario = replace_parameter(
            config, scenario, parameter, {"kind": "fixed", "value": value}
        )
    config, scenario = replace_parameter(
        config,
        scenario,
        "test-placement-probability",
        {"kind": "triangular", "lower": 0, "upper": 0.25, "mode": 0.1},
    )
    mapping = mapping.model_copy(
        update={
            "role_presence_rules": tuple(
                rule.model_copy(
                    update={
                        "presence_parameter_id": "test-placement-zero",
                        "presence_semantics": "boolean_code",
                    }
                )
                if rule.quantity == "role_participation"
                else rule
                for rule in mapping.role_presence_rules
            ),
            "derivations": tuple(
                source.model_copy(
                    update={
                        "selector_parameter_id": "test-assembly-status",
                        "parameter_ids": ("test-assembly-status",),
                    }
                )
                if source.operation == "assignment_status"
                else source
                for source in mapping.derivations
            ),
            "placement_rules": tuple(
                rule.model_copy(
                    update={
                        "mission_applicability_parameter_id": "test-assembly-event-applicability",
                    }
                )
                if rule.record_type == RecordType.EVENT
                else (
                    rule.model_copy(update={"offset_parameter_id": "test-placement-probability"})
                    if rule.record_type == RecordType.SESSION
                    else rule
                )
                for rule in mapping.placement_rules
            ),
            "record_lineage": tuple(
                lineage.model_copy(
                    update={
                        "parameter_ids": (
                            *lineage.parameter_ids,
                            *(p.parameter_id for p in additions),
                        ),
                    }
                )
                for lineage in mapping.record_lineage
            ),
        }
    )
    return config, scenario, approval, mapping


def assembly_missingness_fixture(mechanism, probability=0):
    """Keep lineage/contract joins intact for all supported platform masks."""
    config, scenario, approval, mapping = assembly_fixture()
    config, scenario = replace_parameter(
        config, scenario, "test-placement-probability", {"kind": "fixed", "value": probability}
    )
    # Role presence remains absent regardless of the mask probability.
    mapping = mapping.model_copy(
        update={
            "role_presence_rules": tuple(
                rule.model_copy(
                    update={
                        "presence_parameter_id": "test-placement-zero",
                        "presence_semantics": "boolean_code",
                    }
                )
                if rule.quantity == "role_participation"
                else rule
                for rule in mapping.role_presence_rules
            ),
            "missingness_targets": tuple(
                target.model_copy(
                    update={
                        "latent_never_none": True,
                        "mcar_probability_parameter_id": "test-placement-probability"
                        if mechanism == "mcar"
                        else None,
                    }
                )
                for target in mapping.missingness_targets
            ),
        }
    )
    config = config.model_copy(
        update={
            "missingness_configuration": config.missingness_configuration.model_copy(
                update={
                    "rules": tuple(
                        rule.model_copy(
                            update={
                                "mechanism": mechanism,
                                "scenario_assumption_id": "test-assumption-alpha",
                            }
                        )
                        for rule in config.missingness_configuration.rules
                    ),
                }
            ),
        }
    )
    return config, scenario, approval, mapping
