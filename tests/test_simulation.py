import random
from datetime import UTC, date, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from blastbridge.features.synthetic import FEATURE_CONTRACTS
from blastbridge.simulation.distributions import CountRounding, sample, sample_count
from blastbridge.simulation.models import (
    REQUIRED_DEPENDENCY_PAIRS,
    AssignmentConfiguration,
    AssignmentEpisode,
    Branch,
    CareerConfiguration,
    CareerEpisode,
    Component,
    ComponentPopulationConfiguration,
    ComponentTrainingConfiguration,
    DependencyMode,
    DependencySpecification,
    DistributionSpec,
    FiringEvent,
    FiringMission,
    GenerationApproval,
    GenerationMethod,
    GenerationProvenance,
    LiveFireSession,
    MissingnessConfiguration,
    MissingnessMechanism,
    MissingnessRule,
    ParameterBinding,
    ParticipantExposure,
    ParticipationConfiguration,
    ParticipationType,
    PopulationConfiguration,
    QuantityState,
    QuantityValue,
    RngStream,
    ScenarioAssumption,
    ScenarioDefinition,
    ScenarioLabel,
    SimulationConfig,
    SyntheticCareerDataset,
    SyntheticEntityType,
    SyntheticMember,
    TrainingConfiguration,
    TrainingPeriod,
    UncertaintyConfiguration,
    UncertaintyDimension,
    UncertaintyLineage,
    UncertaintyType,
    require_future_generation_approval,
    stable_synthetic_id,
    validate_configuration_references,
    validate_scenario_registry,
)
from blastbridge.simulation.outputs import (
    SyntheticOutput,
    serialize_output,
    validate_output_schemas,
)
from blastbridge.simulation.rng import child_rng, derive_seed, stream_seeds

PARAMETER_IDS = (
    "population-army-active-weight",
    "career-duration",
    "career-episode-count",
    "career-component-transition",
    "assignment-duration",
    "assignment-occupation-selection",
    "assignment-platform-eligibility",
    "training-cycle-context",
    "army-active-event-frequency",
    "army-active-rounds-per-event",
    "participation-role",
    "participation-nearby",
    "participation-instructor",
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
                    population_weight=parameters["population-army-active-weight"],
                ),
            ),
        ),
        career_configuration=CareerConfiguration(
            career_duration=parameters["career-duration"],
            career_episode_count=parameters["career-episode-count"],
            branch_component_transition=parameters["career-component-transition"],
            dependencies=(),
        ),
        assignment_configuration=AssignmentConfiguration(
            assignment_duration=parameters["assignment-duration"],
            occupation_selection=parameters["assignment-occupation-selection"],
            weapon_platform_eligibility=parameters["assignment-platform-eligibility"],
            dependencies=(),
        ),
        training_configuration=TrainingConfiguration(
            cycle_context=parameters["training-cycle-context"],
            component_configurations=(
                ComponentTrainingConfiguration(
                    component=Component.ARMY_ACTIVE,
                    training_event_frequency=parameters["army-active-event-frequency"],
                    rounds_per_event=parameters["army-active-rounds-per-event"],
                    dependencies=(),
                ),
            ),
            dependencies=dependencies,
        ),
        participation_configuration=ParticipationConfiguration(
            role_participation=parameters["participation-role"],
            nearby_participation=parameters["participation-nearby"],
            instructor_repeated_presence=parameters["participation-instructor"],
            dependencies=(),
        ),
        missingness_configuration=MissingnessConfiguration(
            rules=(
                MissingnessRule(
                    target_quantity="training-event-frequency",
                    mechanism=MissingnessMechanism.UNKNOWN_REASON,
                    condition_quantity_ids=(),
                    scenario_assumption_id=None,
                    rationale="Fixture retains unknown missingness mechanism.",
                ),
            )
        ),
        uncertainty_configuration=uncertainty,
    )


def _provenance(
    stream: RngStream = RngStream.FIRING,
    parameter_ids: tuple[str, ...] = ("career-duration",),
) -> GenerationProvenance:
    return GenerationProvenance(
        simulation_id="test-simulation-alpha",
        scenario_id="test-scenario-alpha",
        scenario_version="0.4.0",
        generator_version="0.4.0",
        rng_algorithm="python-mt19937-random-v1",
        master_seed=17,
        rng_stream=stream,
        prior_definition_ids=(),
        evidence_ids=(),
        sme_estimate_ids=(),
        scenario_assumption_ids=("test-assumption-alpha",),
        parameter_ids=parameter_ids,
        generation_method=GenerationMethod.FIXED,
        uncertainty_types=(UncertaintyType.ALEATORY,),
    )


def _dataset() -> SyntheticCareerDataset:
    provenance = _provenance(RngStream.CAREER, ("career-duration",))
    members = tuple(
        SyntheticMember(
            member_id=stable_synthetic_id(SyntheticEntityType.MEMBER, n),
            service_start=date(2020, 1, 1),
            service_end=date(2024, 12, 31),
            provenance=provenance,
        )
        for n in (1, 2)
    )
    careers = tuple(
        CareerEpisode(
            career_episode_id=stable_synthetic_id(SyntheticEntityType.CAREER, n),
            member_id=stable_synthetic_id(SyntheticEntityType.MEMBER, n),
            branch=Branch.ARMY,
            component=Component.ARMY_ACTIVE,
            occupation_id="test-occupation-alpha",
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
            provenance=provenance,
        )
        for n in (1, 2)
    )
    assignments = tuple(
        AssignmentEpisode(
            assignment_id=stable_synthetic_id(SyntheticEntityType.ASSIGNMENT, n),
            career_episode_id=stable_synthetic_id(SyntheticEntityType.CAREER, n),
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
            occupation_id="test-occupation-alpha",
            unit_type="test-unit-alpha",
            weapon_system_ids=("test-weapon-alpha",),
            platform_id="test-platform-alpha",
            crew_role="test-role-alpha",
            instructor_status=False,
            student_status=False,
            training_context="test-training-context",
            deployment_or_training_cycle_status="test-cycle-alpha",
            provenance=_provenance(
                RngStream.ASSIGNMENT,
                (
                    "assignment-duration",
                    "assignment-occupation-selection",
                    "assignment-platform-eligibility",
                ),
            ),
        )
        for n in (1, 2)
    )
    period = TrainingPeriod(
        training_period_id=stable_synthetic_id(SyntheticEntityType.TRAINING, 1),
        assignment_id=stable_synthetic_id(SyntheticEntityType.ASSIGNMENT, 1),
        start_date=date(2021, 1, 1),
        end_date=date(2021, 12, 31),
        training_context="test-training-context",
        provenance=_provenance(RngStream.TRAINING, ("army-active-event-frequency",)),
    )
    session = LiveFireSession(
        session_id=stable_synthetic_id(SyntheticEntityType.SESSION, 1),
        training_period_id=period.training_period_id,
        start_time=datetime(2021, 5, 1, 9, tzinfo=UTC),
        end_time=datetime(2021, 5, 1, 17, tzinfo=UTC),
        provenance=_provenance(RngStream.TRAINING, ("army-active-event-frequency",)),
    )
    mission = FiringMission(
        mission_id=stable_synthetic_id(SyntheticEntityType.MISSION, 1),
        session_id=session.session_id,
        start_time=datetime(2021, 5, 1, 10, tzinfo=UTC),
        end_time=datetime(2021, 5, 1, 11, tzinfo=UTC),
        provenance=_provenance(
            RngStream.FIRING,
            ("army-active-event-frequency", "army-active-rounds-per-event"),
        ),
    )
    event = FiringEvent(
        event_id=stable_synthetic_id(SyntheticEntityType.EVENT, 1),
        timestamp=datetime(2021, 5, 1, 10, 15, tzinfo=UTC),
        weapon_system_id="test-weapon-alpha",
        weapon_family="test-family-alpha",
        training_context="test-training-context",
        session_id=session.session_id,
        mission_id=mission.mission_id,
        round_or_launch_index=1,
        ammunition_configuration_id=None,
        provenance=_provenance(RngStream.FIRING, ("army-active-rounds-per-event",)),
    )
    exposures = tuple(
        ParticipantExposure(
            exposure_id=stable_synthetic_id(SyntheticEntityType.EXPOSURE, n),
            event_id=event.event_id,
            synthetic_member_id=stable_synthetic_id(SyntheticEntityType.MEMBER, n),
            assignment_id=stable_synthetic_id(SyntheticEntityType.ASSIGNMENT, n),
            role="test-role-alpha",
            participation_type=role,
            provenance=_provenance(RngStream.PARTICIPATION, ("participation-role",)),
        )
        for n, role in ((1, ParticipationType.SECTION_CHIEF), (2, ParticipationType.CREW_MEMBER))
    )
    return SyntheticCareerDataset(
        members=members,
        career_episodes=careers,
        assignments=assignments,
        training_periods=(period,),
        live_fire_sessions=(session,),
        firing_missions=(mission,),
        firing_events=(event,),
        participant_exposures=exposures,
    )


def test_distribution_vocabulary_and_deterministic_sampling():
    specs = (
        {"kind": "fixed", "value": 2.0},
        {"kind": "discrete_uniform", "lower": 1, "upper": 4},
        {"kind": "triangular", "lower": 0.0, "mode": 2.0, "upper": 3.0},
        {"kind": "beta", "alpha": 2.0, "beta": 3.0},
        {"kind": "normal", "mean": 0.0, "standard_deviation": 1.0},
        {"kind": "lognormal", "log_mean": 0.0, "log_standard_deviation": 0.5},
        {"kind": "poisson", "rate": 1000.0},
        {"kind": "negative_binomial", "successes": 2.0, "success_probability": 0.5},
        {"kind": "categorical", "categories": ("TEST_A", "TEST_B"), "probabilities": (0.4, 0.6)},
        {"kind": "empirical", "values": (1.0, 2.0, 3.0)},
    )
    adapter = TypeAdapter(DistributionSpec)
    for payload in specs:
        parsed = adapter.validate_python(payload)
        config, scenario = _config(), _scenario()
        rng1 = child_rng(config, scenario, RngStream.TRAINING, "member-1")
        rng2 = child_rng(config, scenario, RngStream.TRAINING, "member-1")
        assert sample(parsed, rng1) == sample(parsed, rng2)


@pytest.mark.parametrize(
    "payload",
    (
        {"kind": "triangular", "lower": 3.0, "mode": 2.0, "upper": 4.0},
        {"kind": "beta", "alpha": 0.0, "beta": 1.0},
        {"kind": "normal", "mean": 0.0, "standard_deviation": 0.0},
        {"kind": "lognormal", "log_mean": 0.0, "log_standard_deviation": -1.0},
        {"kind": "discrete_uniform", "lower": 4, "upper": 3},
        {"kind": "categorical", "categories": ("A", "B"), "probabilities": (0.3, 0.3)},
        {"kind": "empirical", "values": ()},
    ),
)
def test_invalid_distribution_parameters_are_rejected(payload):
    with pytest.raises(ValidationError):
        TypeAdapter(DistributionSpec).validate_python(payload)


def test_count_sampling_does_not_clamp_negative_values_to_zero():
    rng = random.Random(1)
    with pytest.raises(ValueError, match="negative values"):
        sample_count(
            TypeAdapter(DistributionSpec).validate_python({"kind": "fixed", "value": -1.0}),
            rng,
            rounding=CountRounding.REJECT_FRACTIONAL,
            max_attempts=2,
        )
    with pytest.raises(ValueError, match="fractional count"):
        sample_count(
            TypeAdapter(DistributionSpec).validate_python({"kind": "fixed", "value": 2.5}),
            rng,
            rounding=CountRounding.REJECT_FRACTIONAL,
        )
    assert (
        sample_count(
            TypeAdapter(DistributionSpec).validate_python({"kind": "fixed", "value": 2.5}),
            rng,
            rounding=CountRounding.FLOOR,
        )
        == 2
    )


def test_sme_and_scenario_assumptions_cannot_be_mislabeled_empirical():
    with pytest.raises(ValidationError, match="cannot be relabeled"):
        ParameterBinding.model_validate(
            {
                "parameter_id": "test-mislabeled-parameter",
                "distribution": {"kind": "fixed", "value": 2.0},
                "parameter_class": "empirical_prior",
                "prior_definition_ids": ("test-prior-alpha",),
                "evidence_ids": ("test-evidence-alpha",),
                "sme_estimate_ids": (),
                "scenario_assumption_ids": ("test-assumption-alpha",),
                "uncertainty_types": ("epistemic",),
            }
        )
    sme = ParameterBinding.model_validate(
        {
            "parameter_id": "test-sme-parameter",
            "distribution": {"kind": "fixed", "value": 2.0},
            "parameter_class": "sme_estimate",
            "prior_definition_ids": (),
            "evidence_ids": ("test-sme-evidence",),
            "sme_estimate_ids": ("test-sme-estimate",),
            "scenario_assumption_ids": (),
            "uncertainty_types": ("epistemic",),
        }
    )
    assert sme.parameter_class.value == "sme_estimate"


@pytest.mark.parametrize(
    ("branch", "component"),
    (
        (Branch.ARMY, Component.ARMY_ACTIVE),
        (Branch.ARMY, Component.ARMY_NATIONAL_GUARD),
        (Branch.ARMY, Component.ARMY_RESERVE),
        (Branch.MARINE_CORPS, Component.MARINE_ACTIVE),
        (Branch.MARINE_CORPS, Component.MARINE_RESERVE),
    ),
)
def test_all_requested_branch_components_are_distinct_and_valid(branch, component):
    episode = CareerEpisode(
        career_episode_id=stable_synthetic_id(SyntheticEntityType.CAREER, 1),
        member_id=stable_synthetic_id(SyntheticEntityType.MEMBER, 1),
        branch=branch,
        component=component,
        occupation_id="test-occupation-alpha",
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        provenance=_provenance(),
    )
    assert episode.component == component


def test_component_branch_mismatch_and_real_looking_id_fail_closed():
    with pytest.raises(ValidationError, match="Marine component"):
        CareerEpisode(
            career_episode_id=stable_synthetic_id(SyntheticEntityType.CAREER, 1),
            member_id=stable_synthetic_id(SyntheticEntityType.MEMBER, 1),
            branch=Branch.MARINE_CORPS,
            component=Component.ARMY_ACTIVE,
            occupation_id="test-occupation-alpha",
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
            provenance=_provenance(),
        )
    with pytest.raises(ValidationError):
        SyntheticMember(
            member_id="123456789",
            service_start=date(2020, 1, 1),
            service_end=date(2024, 12, 31),
            provenance=_provenance(),
        )


def test_synthetic_ids_are_repeatable_and_require_positive_ordinals():
    assert stable_synthetic_id(SyntheticEntityType.EVENT, 123) == "SYN-EVENT-000123"
    with pytest.raises(ValueError, match="positive"):
        stable_synthetic_id(SyntheticEntityType.EVENT, 0)


def test_config_has_required_fields_and_deterministic_child_streams():
    first = _config()
    second = _config()
    scenario = _scenario()
    assert stream_seeds(first, scenario, "run-root") == stream_seeds(second, scenario, "run-root")
    assert set(stream_seeds(first, scenario, "run-root")) == set(RngStream)
    changed_reference = first.model_copy(update={"reference_dataset_version": "0.1.1"})
    assert stream_seeds(first, scenario, "run-root") != stream_seeds(
        changed_reference, scenario, "run-root"
    )
    assert derive_seed(17, "0.4.0", "0.4.0", "config-a", RngStream.POPULATION, "x") != derive_seed(
        18, "0.4.0", "0.4.0", "config-a", RngStream.POPULATION, "x"
    )
    with pytest.raises(ValidationError):
        SimulationConfig.model_validate({"simulation_id": "missing-everything"})


def test_scenario_and_configuration_references_are_checked():
    scenario = _scenario()
    config = _config()
    validate_scenario_registry(
        scenario,
        prior_definition_ids=set(),
        prior_classifications={},
        evidence_ids=set(),
        sme_estimate_ids=set(),
    )
    validate_configuration_references(
        config,
        scenario,
        prior_definition_ids=set(),
        prior_classifications={},
        evidence_ids=set(),
        sme_estimate_ids=set(),
    )
    with pytest.raises(ValueError, match="unknown PriorDefinition"):
        validate_scenario_registry(
            scenario.model_copy(update={"prior_definition_ids": ("prior-missing",)}),
            prior_definition_ids=set(),
            prior_classifications={},
            evidence_ids=set(),
            sme_estimate_ids=set(),
        )


def test_independence_requires_an_explicit_scenario_assumption():
    payload = {
        "dependency_id": "dependency-alpha",
        "input_quantities": ("component",),
        "output_quantity": "training-activity",
        "mode": DependencyMode.INDEPENDENT_ASSUMPTION,
        "rule_description": "Fixture only.",
        "scenario_assumption_id": None,
        "uncertainty_types": (UncertaintyType.UNKNOWN,),
    }
    with pytest.raises(ValidationError, match="independence"):
        DependencySpecification.model_validate(payload)


def test_mcar_mar_mnar_and_unknown_mechanisms_remain_distinct():
    with pytest.raises(ValidationError, match="scenario assumption"):
        MissingnessRule(
            target_quantity="missing-event-count",
            mechanism=MissingnessMechanism.MCAR,
            condition_quantity_ids=(),
            scenario_assumption_id=None,
            rationale="Fixture.",
        )
    with pytest.raises(ValidationError, match="conditioning quantities"):
        MissingnessRule(
            target_quantity="missing-event-count",
            mechanism=MissingnessMechanism.MAR,
            condition_quantity_ids=(),
            scenario_assumption_id="test-assumption-alpha",
            rationale="Fixture.",
        )
    assert (
        QuantityValue(
            state=QuantityState.UNKNOWN,
            value=None,
            provenance=_provenance(),
        ).value
        is None
    )
    with pytest.raises(ValidationError, match="cannot be encoded"):
        QuantityValue(state=QuantityState.UNKNOWN, value=0.0, provenance=_provenance())


def test_shared_physical_event_has_multiple_participant_rows():
    dataset = _dataset()
    assert len(dataset.firing_events) == 1
    assert {row.event_id for row in dataset.participant_exposures} == {"SYN-EVENT-000001"}
    assert len(dataset.participant_exposures) == 2
    with pytest.raises(ValidationError, match="duplicate event_id"):
        SyntheticCareerDataset.model_validate(
            {
                **dataset.model_dump(),
                "firing_events": (*dataset.firing_events, dataset.firing_events[0]),
            }
        )


def test_hierarchy_rejects_out_of_period_and_orphan_exposures():
    dataset = _dataset()
    bad_event = dataset.firing_events[0].model_copy(
        update={"timestamp": datetime(2022, 1, 1, tzinfo=UTC)}
    )
    with pytest.raises(ValidationError, match="within an existing live-fire session"):
        SyntheticCareerDataset.model_validate(
            {**dataset.model_dump(), "firing_events": (bad_event,)}
        )
    orphan = dataset.participant_exposures[0].model_copy(update={"event_id": "SYN-EVENT-MISSING"})
    with pytest.raises(ValidationError, match="unknown physical firing event"):
        SyntheticCareerDataset.model_validate(
            {
                **dataset.model_dump(),
                "participant_exposures": (orphan, *dataset.participant_exposures[1:]),
            }
        )


def test_production_generation_fails_closed_even_with_gate_metadata():
    with pytest.raises(ValueError, match="V0.5 approval gate is absent"):
        require_future_generation_approval(None)
    approval = GenerationApproval(
        scenario_id="test-scenario-alpha",
        approved_scenario_version="0.4.0",
        population_scope="Fixture only.",
        simulation_purpose="Test architecture.",
        sensitivity_analysis_plan="Fixture only.",
        parameter_bindings=(
            ParameterBinding.model_validate(_binding("population-army-active-weight")),
        ),
        approval_reference="approval-fixture-alpha",
    )
    with pytest.raises(ValueError, match="disabled in V0.4"):
        require_future_generation_approval(approval)


def test_output_schemas_serialization_and_feature_contracts():
    validate_output_schemas()
    output = SyntheticOutput(config=_config(), scenario=_scenario(), records=_dataset())
    tables = serialize_output(output)
    assert len(tables["synthetic_firing_events"]) == 1
    assert len(tables["synthetic_participant_exposures"]) == 2
    assert {feature.medical_or_injury_inference for feature in FEATURE_CONTRACTS} == {False}
