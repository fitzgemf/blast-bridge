"""Fictional-only authorization: no generation occurs in these tests."""

from datetime import date

import pytest
from pydantic import ValidationError

from blastbridge.simulation import fictional
from blastbridge.simulation.fictional import (
    FictionalGenerationApproval,
    authorize_fictional_generation,
    validate_fictional_entity_ids,
    validate_fictional_scenario,
)
from blastbridge.simulation.models import (
    REQUIRED_DEPENDENCY_PAIRS,
    AssignmentConfiguration,
    CareerConfiguration,
    Component,
    ComponentPopulationConfiguration,
    ComponentTrainingConfiguration,
    DependencyMode,
    DependencySpecification,
    GenerationApproval,
    MissingnessConfiguration,
    MissingnessMechanism,
    MissingnessRule,
    ParameterBinding,
    ParticipationConfiguration,
    PopulationConfiguration,
    ScenarioAssumption,
    ScenarioDefinition,
    ScenarioLabel,
    SimulationConfig,
    TrainingConfiguration,
    UncertaintyConfiguration,
    UncertaintyDimension,
    UncertaintyLineage,
    UncertaintyType,
)

PARAMETER_IDS = (
    "test-population-army-active-weight",
    "test-career-duration",
    "test-career-episode-count",
    "test-career-component-transition",
    "test-assignment-duration",
    "test-assignment-occupation-selection",
    "test-assignment-platform-eligibility",
    "test-training-cycle-context",
    "test-army-active-event-frequency",
    "test-army-active-rounds-per-event",
    "test-participation-role",
    "test-participation-nearby",
    "test-participation-instructor",
)


def _binding(parameter_id: str) -> dict[str, object]:
    return {
        "parameter_id": parameter_id,
        "distribution": {"kind": "fixed", "value": 2},
        "parameter_class": "scenario_assumption",
        "prior_definition_ids": (),
        "evidence_ids": (),
        "sme_estimate_ids": (),
        "scenario_assumption_ids": ("test-assumption-alpha",),
        "uncertainty_types": ("aleatory",),
    }


def _scenario() -> ScenarioDefinition:
    assumption = ScenarioAssumption(
        assumption_id="test-assumption-alpha",
        statement="Clearly fictional fixture value; not a military parameter.",
        scope="Unit tests only.",
    )
    return ScenarioDefinition(
        scenario_id="test-scenario-alpha",
        scenario_version="0.4.0",
        label=ScenarioLabel.CUSTOM,
        purpose="Test software behavior only.",
        population_scope="TEST_OCCUPATION_ALPHA only.",
        prior_definition_ids=(),
        evidence_constraint_ids=(),
        sme_estimate_ids=(),
        supporting_evidence_ids=(),
        assumptions=(assumption,),
        parameters=tuple(ParameterBinding.model_validate(_binding(item)) for item in PARAMETER_IDS),
        dependency_ids=tuple(
            f"test-dependency-{n:02}" for n in range(len(REQUIRED_DEPENDENCY_PAIRS))
        ),
    )


def _config(master_seed: int = 17) -> SimulationConfig:
    uncertainty = UncertaintyConfiguration(
        dimensions=tuple(
            UncertaintyLineage(
                dimension=dimension,
                uncertainty_types=(UncertaintyType.ALEATORY,),
                prior_definition_ids=(),
                evidence_ids=(),
                sme_estimate_ids=(),
                scenario_assumption_ids=("test-assumption-alpha",),
                rationale="Fictional software fixture.",
            )
            for dimension in UncertaintyDimension
        )
    )
    parameters = {name: ParameterBinding.model_validate(_binding(name)) for name in PARAMETER_IDS}
    dependencies = tuple(
        DependencySpecification(
            dependency_id=f"test-dependency-{index:02}",
            input_quantities=(source,),
            output_quantity=target,
            mode=DependencyMode.UNKNOWN,
            rule_description="Relationship is represented but its form is unknown in this fixture.",
            scenario_assumption_id=None,
            uncertainty_types=(UncertaintyType.UNKNOWN,),
        )
        for index, (source, target) in enumerate(REQUIRED_DEPENDENCY_PAIRS)
    )
    return SimulationConfig(
        simulation_id="test-simulation-alpha",
        simulation_version="0.4.0",
        scenario_id="test-scenario-alpha",
        scenario_version="0.4.0",
        generator_version="0.4.0",
        rng_algorithm="python-mt19937-random-v1",
        master_seed=master_seed,
        population_size=2,
        simulation_start_date=date(2020, 1, 1),
        simulation_end_date=date(2024, 12, 31),
        reference_dataset_version="0.1.0",
        training_tempo_dataset_version="0.2.0",
        prior_design_version="0.3.0",
        population_configuration=PopulationConfiguration(
            population_scope="TEST_OCCUPATION_ALPHA only.",
            components=(
                ComponentPopulationConfiguration(
                    component=Component.ARMY_ACTIVE,
                    population_weight=parameters["test-population-army-active-weight"],
                ),
            ),
        ),
        career_configuration=CareerConfiguration(
            career_duration=parameters["test-career-duration"],
            career_episode_count=parameters["test-career-episode-count"],
            branch_component_transition=parameters["test-career-component-transition"],
            dependencies=(),
        ),
        assignment_configuration=AssignmentConfiguration(
            assignment_duration=parameters["test-assignment-duration"],
            occupation_selection=parameters["test-assignment-occupation-selection"],
            weapon_platform_eligibility=parameters["test-assignment-platform-eligibility"],
            dependencies=(),
        ),
        training_configuration=TrainingConfiguration(
            cycle_context=parameters["test-training-cycle-context"],
            component_configurations=(
                ComponentTrainingConfiguration(
                    component=Component.ARMY_ACTIVE,
                    training_event_frequency=parameters["test-army-active-event-frequency"],
                    rounds_per_event=parameters["test-army-active-rounds-per-event"],
                    dependencies=(),
                ),
            ),
            dependencies=dependencies,
        ),
        participation_configuration=ParticipationConfiguration(
            role_participation=parameters["test-participation-role"],
            nearby_participation=parameters["test-participation-nearby"],
            instructor_repeated_presence=parameters["test-participation-instructor"],
            dependencies=(),
        ),
        missingness_configuration=MissingnessConfiguration(
            rules=(
                MissingnessRule(
                    target_quantity="platform-id",
                    mechanism=MissingnessMechanism.STRUCTURAL,
                    condition_quantity_ids=(),
                    scenario_assumption_id=None,
                    rationale="Fictional platform is structurally not applicable.",
                ),
            )
        ),
        uncertainty_configuration=uncertainty,
    )


def _approval():
    scenario = _scenario()
    return FictionalGenerationApproval(
        scenario_id=scenario.scenario_id,
        approved_scenario_version=scenario.scenario_version,
        population_scope=scenario.population_scope,
        simulation_purpose=scenario.purpose,
        fictional_acknowledgement=True,
    )


def test_valid_fictional_authorization_passes():
    authorize_fictional_generation(_config(), _scenario(), _approval())


@pytest.mark.parametrize("location", ["scenario", "config"])
def test_non_assumption_parameter_refused_before_generation(location):
    config, scenario = _config(), _scenario()
    binding = scenario.parameters[0].model_copy(update={"parameter_class": "empirical_prior"})
    if location == "scenario":
        scenario = scenario.model_copy(update={"parameters": (binding, *scenario.parameters[1:])})
    else:
        career = config.career_configuration.model_copy(update={"career_duration": binding})
        config = config.model_copy(update={"career_configuration": career})
    with pytest.raises(ValueError, match="must be scenario_assumption"):
        validate_fictional_scenario(config, scenario)


@pytest.mark.parametrize("field", ["prior_definition_ids", "evidence_ids", "sme_estimate_ids"])
def test_binding_source_lineage_refused_before_generation(field):
    scenario = _scenario()
    # model_copy bypasses schema validation to exercise the guard independently.
    binding = scenario.parameters[0].model_copy(update={field: ("test-source-alpha",)})
    scenario = scenario.model_copy(update={"parameters": (binding, *scenario.parameters[1:])})
    with pytest.raises(ValueError, match=f"fictional {field} must be empty"):
        validate_fictional_scenario(_config(), scenario)


def test_empty_binding_assumptions_refused_before_generation():
    scenario = _scenario()
    binding = scenario.parameters[0].model_copy(update={"scenario_assumption_ids": ()})
    scenario = scenario.model_copy(update={"parameters": (binding, *scenario.parameters[1:])})
    with pytest.raises(ValueError, match="requires assumptions"):
        validate_fictional_scenario(_config(), scenario)


@pytest.mark.parametrize(
    "field",
    [
        "prior_definition_ids",
        "evidence_constraint_ids",
        "sme_estimate_ids",
        "supporting_evidence_ids",
    ],
)
def test_scenario_source_registry_refused_before_generation(field):
    scenario = _scenario().model_copy(update={field: ("test-source-alpha",)})
    with pytest.raises(ValueError, match=f"fictional {field} must be empty"):
        validate_fictional_scenario(_config(), scenario)


@pytest.mark.parametrize(
    "location", ["scenario", "config", "scenario-assumption", "config-missingness"]
)
def test_non_test_identifier_refused_before_generation(location):
    # A valid Identifier deliberately omits the fictional test- prefix.
    config, scenario = _config(), _scenario()
    identifier = "fictional-without-prefix"
    if location == "scenario":
        scenario = scenario.model_copy(update={"scenario_id": identifier})
    elif location == "config":
        config = config.model_copy(update={"simulation_id": identifier})
    elif location == "scenario-assumption":
        assumption = scenario.assumptions[0].model_copy(update={"assumption_id": identifier})
        scenario = scenario.model_copy(update={"assumptions": (assumption,)})
    else:
        rule = config.missingness_configuration.rules[0].model_copy(
            update={"scenario_assumption_id": identifier}
        )
        missingness = MissingnessConfiguration(rules=(rule,))
        config = config.model_copy(update={"missingness_configuration": missingness})
    with pytest.raises(
        ValueError, match=f"^fictional identifier must start with test-: {identifier}$"
    ):
        validate_fictional_scenario(config, scenario)


def test_category_without_fictional_prefix_refused_before_generation():
    scenario = _scenario()
    payload = scenario.parameters[0].model_dump()
    payload["distribution"] = {
        "kind": "categorical",
        "categories": ("fictional-without-prefix",),
        "probabilities": (1.0,),
    }
    binding = ParameterBinding.model_validate(payload)
    scenario = scenario.model_copy(update={"parameters": (binding, *scenario.parameters[1:])})
    with pytest.raises(ValueError, match="^fictional category must start with"):
        validate_fictional_scenario(_config(), scenario)


def test_catalog_denylist_is_populated_with_nonfictional_ids():
    catalog_ids = fictional._catalog_ids()
    assert catalog_ids
    assert all(not identifier.startswith(("test-", "TEST_")) for identifier in catalog_ids)


def test_empirical_family_refused_before_generation():
    scenario = _scenario()
    payload = scenario.parameters[0].model_dump()
    payload["distribution"] = {"kind": "empirical", "values": (1.0, 2.0)}
    binding = ParameterBinding.model_validate(payload)
    scenario = scenario.model_copy(update={"parameters": (binding, *scenario.parameters[1:])})
    with pytest.raises(ValueError, match="empirical distribution refused"):
        validate_fictional_scenario(_config(), scenario)


def test_catalog_collision_refused_before_generation(monkeypatch):
    # A simulated catalog collision uses test- IDs, never a real catalog ID.
    monkeypatch.setattr(fictional, "_catalog_ids", lambda: {"test-occupation-alpha"})
    scenario = _scenario()
    payload = scenario.parameters[0].model_dump()
    payload["distribution"] = {
        "kind": "categorical",
        "categories": ("test-occupation-alpha",),
        "probabilities": (1.0,),
    }
    binding = ParameterBinding.model_validate(payload)
    scenario = scenario.model_copy(update={"parameters": (binding, *scenario.parameters[1:])})
    with pytest.raises(ValueError, match="collides with reference catalog"):
        validate_fictional_scenario(_config(), scenario)


def test_entity_resolution_boundary_refuses_catalog_collision(monkeypatch):
    monkeypatch.setattr(fictional, "_catalog_ids", lambda: {"test-platform-alpha"})
    with pytest.raises(ValueError, match="collides with reference catalog"):
        validate_fictional_entity_ids(("test-platform-alpha",))


def test_non_custom_label_refused_before_generation():
    scenario = _scenario().model_copy(update={"label": ScenarioLabel.EXPLORATORY_CENTRAL})
    with pytest.raises(ValueError, match="label must be custom"):
        validate_fictional_scenario(_config(), scenario)


def test_acknowledgement_must_be_explicit_true():
    payload = _approval().model_dump()
    payload.pop("fictional_acknowledgement")
    with pytest.raises(ValidationError):
        FictionalGenerationApproval.model_validate(payload)
    payload["fictional_acknowledgement"] = False
    with pytest.raises(ValidationError):
        FictionalGenerationApproval.model_validate(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("scenario_id", "test-other-scenario"),
        ("approved_scenario_version", "0.4.1"),
        ("population_scope", "TEST_OTHER_SCOPE"),
        ("simulation_purpose", "TEST_OTHER_PURPOSE"),
    ],
)
def test_mismatched_approval_refused_before_generation(field, value):
    approval = _approval().model_copy(update={field: value})
    with pytest.raises(ValueError, match="mismatch"):
        authorize_fictional_generation(_config(), _scenario(), approval)


def test_real_approval_is_not_fictional_authorization():
    real = GenerationApproval(
        scenario_id="test-scenario-alpha",
        approved_scenario_version="0.4.0",
        population_scope="test-scope",
        simulation_purpose="test-purpose",
        sensitivity_analysis_plan="test-plan",
        parameter_bindings=_scenario().parameters,
        approval_reference="test-approval",
    )
    assert not isinstance(real, FictionalGenerationApproval)
    assert not isinstance(_approval(), GenerationApproval)
    with pytest.raises(ValueError, match="requires FictionalGenerationApproval"):
        authorize_fictional_generation(_config(), _scenario(), real)  # type: ignore[arg-type]


def test_content_guard_precedes_approval_check():
    scenario = _scenario().model_copy(update={"label": ScenarioLabel.EXPLORATORY_CENTRAL})
    with pytest.raises(ValueError, match="label must be custom"):
        authorize_fictional_generation(_config(), scenario, None)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["prior_definition_ids", "evidence_ids", "sme_estimate_ids"])
def test_uncertainty_source_lineage_refused_before_generation(field):
    config = _config()
    dimensions = config.uncertainty_configuration.dimensions
    dimension = dimensions[0].model_copy(update={field: ("test-source-alpha",)})
    uncertainty = config.uncertainty_configuration.model_copy(
        update={"dimensions": (dimension, *dimensions[1:])}
    )
    config = config.model_copy(update={"uncertainty_configuration": uncertainty})
    with pytest.raises(ValueError, match=f"fictional {field} must be empty"):
        validate_fictional_scenario(config, _scenario())


def test_catalog_unavailable_fails_closed(monkeypatch):
    def unavailable(_directory):
        raise OSError("test-catalog-unavailable")

    monkeypatch.setattr(fictional, "load_reference_bundle", unavailable)
    with pytest.raises(ValueError, match="catalog collision check unavailable"):
        validate_fictional_scenario(_config(), _scenario())


def test_config_scenario_mismatch_refused_before_generation():
    config = _config().model_copy(update={"scenario_id": "test-other-scenario"})
    with pytest.raises(ValueError, match="different scenario/version"):
        authorize_fictional_generation(config, _scenario(), _approval())


def test_acknowledgement_rejects_numeric_true():
    payload = _approval().model_dump()
    payload["fictional_acknowledgement"] = 1
    with pytest.raises(ValidationError, match="explicitly true"):
        FictionalGenerationApproval.model_validate(payload)


def test_no_supported_missingness_rule_refused_before_generation():
    config = _config()
    rule = config.missingness_configuration.rules[0].model_copy(
        update={"mechanism": MissingnessMechanism.UNKNOWN_REASON}
    )
    missingness = MissingnessConfiguration(rules=(rule,))
    config = config.model_copy(update={"missingness_configuration": missingness})
    with pytest.raises(ValueError, match="at least one supported missingness rule"):
        validate_fictional_scenario(config, _scenario())
