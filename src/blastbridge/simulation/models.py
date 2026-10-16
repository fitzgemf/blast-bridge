"""V0.4 synthetic-generation contracts; no generator or military parameters."""

import json
from datetime import date, datetime
from enum import StrEnum
from hashlib import sha256
from math import isclose
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StringConstraints, model_validator

from blastbridge.models.core import NonNegative, ResearchModel, Text
from blastbridge.models.reference import Identifier, SemVer

SimulationVersion = Literal["0.5.0"]
SyntheticIdentifier = Annotated[
    str,
    StringConstraints(
        pattern=r"^SYN-(?:MEMBER|CAREER|ASSIGNMENT|TRAINING|SESSION|MISSION|EVENT|EXPOSURE)-[A-Z0-9][A-Z0-9_-]*$"
    ),
]
Probability = Annotated[float, Field(gt=0, le=1, allow_inf_nan=False, strict=True)]
UnitProbability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False, strict=True)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)]
FiniteFloat = Annotated[float, Field(allow_inf_nan=False, strict=True)]
StrictInteger = Annotated[int, Field(strict=True)]
Count = Annotated[int, Field(ge=0, strict=True)]
PositiveCount = Annotated[int, Field(gt=0, strict=True)]


class Component(StrEnum):
    ARMY_ACTIVE = "army_active"
    ARMY_NATIONAL_GUARD = "army_national_guard"
    ARMY_RESERVE = "army_reserve"
    MARINE_ACTIVE = "marine_active"
    MARINE_RESERVE = "marine_reserve"


class Branch(StrEnum):
    ARMY = "army"
    MARINE_CORPS = "marine_corps"


class ScenarioLabel(StrEnum):
    EXPLORATORY_CONSERVATIVE = "exploratory_conservative"
    EXPLORATORY_CENTRAL = "exploratory_central"
    EXPLORATORY_HIGH_TEMPO = "exploratory_high_tempo"
    CUSTOM = "custom"


class ParameterClass(StrEnum):
    EMPIRICAL_PRIOR = "empirical_prior"
    EVIDENCE_CONSTRAINT = "evidence_constraint"
    SME_ESTIMATE = "sme_estimate"
    SCENARIO_ASSUMPTION = "scenario_assumption"


class UncertaintyType(StrEnum):
    ALEATORY = "aleatory"
    EPISTEMIC = "epistemic"
    UNKNOWN = "unknown_unclassified"


class UncertaintyDimension(StrEnum):
    CAREER_DURATION = "career_duration"
    ASSIGNMENT_DURATION = "assignment_duration"
    TRAINING_EVENT_FREQUENCY = "training_event_frequency"
    ROUNDS_PER_EVENT = "rounds_per_event"
    PARTICIPATION = "participation"
    ROLE = "role"
    MISSING_YEARS = "missing_years"
    SOURCE_SUPPORT = "source_support"


class RngStream(StrEnum):
    POPULATION = "population"
    CAREER = "career"
    ASSIGNMENT = "assignment"
    TRAINING = "training"
    FIRING = "firing"
    PARTICIPATION = "participation"
    MISSINGNESS = "missingness"


class GenerationMethod(StrEnum):
    FIXED = "fixed"
    DISTRIBUTION_SAMPLE = "distribution_sample"
    DERIVED = "derived"
    CARRIED_FORWARD = "carried_forward"
    UNKNOWN = "unknown"


class ParticipationType(StrEnum):
    FIRED_WEAPON = "fired_weapon"
    CREW_MEMBER = "crew_member"
    NEARBY_CREW = "nearby_crew"
    SECTION_CHIEF = "section_chief"
    INSTRUCTOR = "instructor"
    STUDENT = "student"
    SAFETY_PERSONNEL = "safety_personnel"
    OBSERVER = "observer"
    UNKNOWN = "unknown"


class SyntheticEntityType(StrEnum):
    MEMBER = "MEMBER"
    CAREER = "CAREER"
    ASSIGNMENT = "ASSIGNMENT"
    TRAINING = "TRAINING"
    SESSION = "SESSION"
    MISSION = "MISSION"
    EVENT = "EVENT"
    EXPOSURE = "EXPOSURE"


class MissingnessMechanism(StrEnum):
    MCAR = "mcar"
    MAR = "mar"
    MNAR = "mnar"
    STRUCTURAL = "structural_missing"
    NOT_COLLECTED = "not_collected"
    UNKNOWN_REASON = "unknown_reason"


class QuantityState(StrEnum):
    OBSERVED = "observed"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class DistributionKind(StrEnum):
    FIXED = "fixed"
    DISCRETE_UNIFORM = "discrete_uniform"
    TRIANGULAR = "triangular"
    BETA = "beta"
    NORMAL = "normal"
    LOGNORMAL = "lognormal"
    POISSON = "poisson"
    NEGATIVE_BINOMIAL = "negative_binomial"
    CATEGORICAL = "categorical"
    EMPIRICAL = "empirical"


class FixedDistribution(ResearchModel):
    kind: Literal["fixed"]
    value: FiniteFloat


class DiscreteUniformDistribution(ResearchModel):
    kind: Literal["discrete_uniform"]
    lower: StrictInteger
    upper: StrictInteger

    @model_validator(mode="after")
    def valid_bounds(self) -> Self:
        if self.lower > self.upper:
            raise ValueError("discrete_uniform requires lower <= upper")
        return self


class TriangularDistribution(ResearchModel):
    kind: Literal["triangular"]
    lower: FiniteFloat
    mode: FiniteFloat
    upper: FiniteFloat

    @model_validator(mode="after")
    def valid_bounds(self) -> Self:
        if not self.lower <= self.mode <= self.upper or self.lower == self.upper:
            raise ValueError("triangular requires lower <= mode <= upper and nonzero width")
        return self


class BetaDistribution(ResearchModel):
    kind: Literal["beta"]
    alpha: Positive
    beta: Positive


class NormalDistribution(ResearchModel):
    kind: Literal["normal"]
    mean: FiniteFloat
    standard_deviation: Positive


class LognormalDistribution(ResearchModel):
    kind: Literal["lognormal"]
    log_mean: FiniteFloat
    log_standard_deviation: Positive


class PoissonDistribution(ResearchModel):
    kind: Literal["poisson"]
    rate: NonNegative


class NegativeBinomialDistribution(ResearchModel):
    kind: Literal["negative_binomial"]
    successes: Positive
    success_probability: Probability


class CategoricalDistribution(ResearchModel):
    kind: Literal["categorical"]
    categories: tuple[Text, ...] = Field(min_length=1)
    probabilities: tuple[UnitProbability, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_probabilities(self) -> Self:
        if len(self.categories) != len(self.probabilities):
            raise ValueError("categorical categories and probabilities must have equal length")
        if len(set(self.categories)) != len(self.categories):
            raise ValueError("categorical categories must be unique")
        if not isclose(sum(self.probabilities), 1.0, rel_tol=0, abs_tol=1e-12):
            raise ValueError("categorical probabilities must sum to 1")
        return self


class EmpiricalDistribution(ResearchModel):
    kind: Literal["empirical"]
    values: tuple[FiniteFloat, ...] = Field(min_length=1)


type DistributionSpec = Annotated[
    FixedDistribution
    | DiscreteUniformDistribution
    | TriangularDistribution
    | BetaDistribution
    | NormalDistribution
    | LognormalDistribution
    | PoissonDistribution
    | NegativeBinomialDistribution
    | CategoricalDistribution
    | EmpiricalDistribution,
    Field(discriminator="kind"),
]


class ScenarioAssumption(ResearchModel):
    assumption_id: Identifier
    statement: Text
    scope: Text


class ParameterBinding(ResearchModel):
    """A numerical specification with complete, typed justification links."""

    parameter_id: Identifier
    distribution: DistributionSpec
    parameter_class: ParameterClass
    prior_definition_ids: tuple[Identifier, ...]
    evidence_ids: tuple[Identifier, ...]
    sme_estimate_ids: tuple[Identifier, ...]
    scenario_assumption_ids: tuple[Identifier, ...]
    uncertainty_types: tuple[UncertaintyType, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_lineage(self) -> Self:
        if self.parameter_class == ParameterClass.EMPIRICAL_PRIOR and not self.prior_definition_ids:
            raise ValueError("empirical prior parameters require prior definition IDs")
        if self.parameter_class == ParameterClass.EMPIRICAL_PRIOR and not self.evidence_ids:
            raise ValueError("empirical prior parameters require provenance evidence IDs")
        if self.parameter_class == ParameterClass.EVIDENCE_CONSTRAINT and not self.evidence_ids:
            raise ValueError("evidence constraints require evidence IDs")
        if (
            self.parameter_class == ParameterClass.EVIDENCE_CONSTRAINT
            and not self.prior_definition_ids
        ):
            raise ValueError("evidence constraints must identify their V0.3 PriorDefinition")
        if self.parameter_class == ParameterClass.SME_ESTIMATE and not self.sme_estimate_ids:
            raise ValueError("SME parameters require explicit SME estimate IDs")
        if self.parameter_class == ParameterClass.SME_ESTIMATE and not self.evidence_ids:
            raise ValueError("SME parameters require supporting evidence IDs")
        if (
            self.parameter_class == ParameterClass.SCENARIO_ASSUMPTION
            and not self.scenario_assumption_ids
        ):
            raise ValueError("scenario assumptions require assumption IDs")
        forbidden_by_class = {
            ParameterClass.EMPIRICAL_PRIOR: (self.sme_estimate_ids, self.scenario_assumption_ids),
            ParameterClass.EVIDENCE_CONSTRAINT: (
                self.sme_estimate_ids,
                self.scenario_assumption_ids,
            ),
            ParameterClass.SME_ESTIMATE: (
                self.prior_definition_ids,
                self.scenario_assumption_ids,
            ),
            ParameterClass.SCENARIO_ASSUMPTION: (
                self.prior_definition_ids,
                self.evidence_ids,
                self.sme_estimate_ids,
            ),
        }[self.parameter_class]
        if any(forbidden_by_class):
            raise ValueError("parameter provenance cannot be relabeled across source classes")
        lineage_groups = (
            self.prior_definition_ids,
            self.evidence_ids,
            self.sme_estimate_ids,
            self.scenario_assumption_ids,
        )
        if not any(lineage_groups):
            raise ValueError("parameters require source/prior/SME/assumption provenance")
        for values in (*lineage_groups, self.uncertainty_types):
            if len(values) != len(set(values)):
                raise ValueError("parameter lineage values must be unique")
        return self


class ScenarioDefinition(ResearchModel):
    scenario_id: Identifier
    scenario_version: SemVer
    label: ScenarioLabel
    purpose: Text
    population_scope: Text
    prior_definition_ids: tuple[Identifier, ...]
    evidence_constraint_ids: tuple[Identifier, ...]
    sme_estimate_ids: tuple[Identifier, ...]
    supporting_evidence_ids: tuple[Identifier, ...]
    assumptions: tuple[ScenarioAssumption, ...]
    parameters: tuple[ParameterBinding, ...]
    dependency_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def valid_scenario_references(self) -> Self:
        assumption_ids = [assumption.assumption_id for assumption in self.assumptions]
        if len(assumption_ids) != len(set(assumption_ids)):
            raise ValueError("scenario assumption IDs must be unique")
        if len(self.prior_definition_ids) != len(set(self.prior_definition_ids)):
            raise ValueError("prior definition references must be unique")
        if len(self.evidence_constraint_ids) != len(set(self.evidence_constraint_ids)):
            raise ValueError("evidence references must be unique")
        if len(self.sme_estimate_ids) != len(set(self.sme_estimate_ids)):
            raise ValueError("SME estimate references must be unique")
        if len(self.supporting_evidence_ids) != len(set(self.supporting_evidence_ids)):
            raise ValueError("supporting evidence references must be unique")
        if len(self.dependency_ids) != len(set(self.dependency_ids)):
            raise ValueError("dependency references must be unique")
        if not (
            self.prior_definition_ids
            or self.evidence_constraint_ids
            or self.sme_estimate_ids
            or assumption_ids
        ):
            raise ValueError("a scenario must cite a prior, evidence, SME estimate or assumption")
        for binding in self.parameters:
            if not set(binding.scenario_assumption_ids) <= set(assumption_ids):
                raise ValueError("parameter refers to an undeclared scenario assumption")
            if not set(binding.prior_definition_ids) <= set(self.prior_definition_ids):
                raise ValueError("parameter refers to a prior absent from its scenario")
            if not set(binding.evidence_ids) <= set(self.supporting_evidence_ids):
                raise ValueError("parameter refers to evidence absent from its scenario")
            if not set(binding.sme_estimate_ids) <= set(self.sme_estimate_ids):
                raise ValueError("parameter refers to an SME estimate absent from its scenario")
        if len({binding.parameter_id for binding in self.parameters}) != len(self.parameters):
            raise ValueError("scenario parameter IDs must be unique")
        return self


class ComponentPopulationConfiguration(ResearchModel):
    component: Component
    population_weight: ParameterBinding


class PopulationConfiguration(ResearchModel):
    population_scope: Text
    components: tuple[ComponentPopulationConfiguration, ...]

    @model_validator(mode="after")
    def unique_components(self) -> Self:
        components = [row.component for row in self.components]
        if not components or len(components) != len(set(components)):
            raise ValueError("population configuration requires unique explicit components")
        return self


class DependencyMode(StrEnum):
    CONDITIONAL = "conditional"
    JOINT = "joint"
    INDEPENDENT_ASSUMPTION = "independent_assumption"
    UNKNOWN = "unknown"


class DependencySpecification(ResearchModel):
    dependency_id: Identifier
    input_quantities: tuple[Identifier, ...] = Field(min_length=1)
    output_quantity: Identifier
    mode: DependencyMode
    rule_description: Text
    scenario_assumption_id: Identifier | None
    uncertainty_types: tuple[UncertaintyType, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def explicit_independence(self) -> Self:
        if len(self.input_quantities) != len(set(self.input_quantities)):
            raise ValueError("dependency inputs must be unique")
        if self.mode == DependencyMode.INDEPENDENT_ASSUMPTION:
            if self.scenario_assumption_id is None:
                raise ValueError("independence must be an explicit scenario assumption")
        return self


class ComponentTrainingConfiguration(ResearchModel):
    component: Component
    training_event_frequency: ParameterBinding
    rounds_per_event: ParameterBinding
    dependencies: tuple[DependencySpecification, ...]


class ConfigurationBlock(ResearchModel):
    dependencies: tuple[DependencySpecification, ...]


class AssignmentConfiguration(ConfigurationBlock):
    assignment_duration: ParameterBinding
    occupation_selection: ParameterBinding
    weapon_platform_eligibility: ParameterBinding


class CareerConfiguration(ConfigurationBlock):
    career_duration: ParameterBinding
    career_episode_count: ParameterBinding
    branch_component_transition: ParameterBinding


class TrainingConfiguration(ConfigurationBlock):
    cycle_context: ParameterBinding
    component_configurations: tuple[ComponentTrainingConfiguration, ...]

    @model_validator(mode="after")
    def unique_component_configs(self) -> Self:
        components = [item.component for item in self.component_configurations]
        if not components or len(components) != len(set(components)):
            raise ValueError("training requires one independently supplied config per component")
        return self


class ParticipationConfiguration(ConfigurationBlock):
    role_participation: ParameterBinding
    nearby_participation: ParameterBinding
    instructor_repeated_presence: ParameterBinding


class MissingnessRule(ResearchModel):
    target_quantity: Identifier
    mechanism: MissingnessMechanism
    condition_quantity_ids: tuple[Identifier, ...]
    scenario_assumption_id: Identifier | None
    rationale: Text

    @model_validator(mode="after")
    def validate_mechanism(self) -> Self:
        if self.mechanism == MissingnessMechanism.MCAR:
            if self.condition_quantity_ids:
                raise ValueError("MCAR cannot specify conditioning quantities")
            if self.scenario_assumption_id is None:
                raise ValueError("a missingness mechanism requires a scenario assumption")
        elif self.mechanism in {MissingnessMechanism.MAR, MissingnessMechanism.MNAR}:
            if not self.condition_quantity_ids or self.scenario_assumption_id is None:
                raise ValueError("MAR/MNAR require conditioning quantities and an assumption")
        return self


class MissingnessConfiguration(ResearchModel):
    rules: tuple[MissingnessRule, ...] = Field(min_length=1)


class UncertaintyLineage(ResearchModel):
    dimension: UncertaintyDimension
    uncertainty_types: tuple[UncertaintyType, ...] = Field(min_length=1)
    prior_definition_ids: tuple[Identifier, ...]
    evidence_ids: tuple[Identifier, ...]
    sme_estimate_ids: tuple[Identifier, ...]
    scenario_assumption_ids: tuple[Identifier, ...]
    rationale: Text

    @model_validator(mode="after")
    def unique_lineage(self) -> Self:
        for values in (
            self.uncertainty_types,
            self.prior_definition_ids,
            self.evidence_ids,
            self.sme_estimate_ids,
            self.scenario_assumption_ids,
        ):
            if len(values) != len(set(values)):
                raise ValueError("uncertainty lineage references must be unique")
        return self


class UncertaintyConfiguration(ResearchModel):
    dimensions: tuple[UncertaintyLineage, ...]

    @model_validator(mode="after")
    def unique_dimensions(self) -> Self:
        dims = [item.dimension for item in self.dimensions]
        if len(dims) != len(set(dims)) or set(dims) != set(UncertaintyDimension):
            raise ValueError("uncertainty configuration must cover every dimension exactly once")
        return self


class SimulationConfig(ResearchModel):
    simulation_id: Identifier
    simulation_version: SemVer
    scenario_id: Identifier
    scenario_version: SemVer
    generator_version: SimulationVersion
    rng_algorithm: Literal["python-mt19937-random-v1"]
    master_seed: Annotated[int, Field(ge=0, strict=True)]
    population_size: PositiveCount
    simulation_start_date: date
    simulation_end_date: date
    reference_dataset_version: SemVer
    training_tempo_dataset_version: SemVer
    prior_design_version: SemVer
    population_configuration: PopulationConfiguration
    career_configuration: CareerConfiguration
    assignment_configuration: AssignmentConfiguration
    training_configuration: TrainingConfiguration
    participation_configuration: ParticipationConfiguration
    missingness_configuration: MissingnessConfiguration
    uncertainty_configuration: UncertaintyConfiguration
    execution_bindings: tuple[ParameterBinding, ...] = ()

    @model_validator(mode="after")
    def dates_and_version(self) -> Self:
        if self.simulation_end_date < self.simulation_start_date:
            raise ValueError("simulation dates must be ordered")
        if self.generator_version != "0.5.0":
            raise ValueError("generator version must be explicit and supported")
        population_components = {row.component for row in self.population_configuration.components}
        training_components = {
            row.component for row in self.training_configuration.component_configurations
        }
        if training_components != population_components:
            raise ValueError(
                "every selected component requires its own explicit training configuration"
            )
        parameter_ids = [binding.parameter_id for binding in configured_parameter_bindings(self)]
        if len(parameter_ids) != len(set(parameter_ids)):
            raise ValueError("simulation parameter IDs must be unique across quantities")
        dependency_pairs = {
            (quantity, dependency.output_quantity)
            for dependency in _all_dependencies(self)
            for quantity in dependency.input_quantities
        }
        if not set(REQUIRED_DEPENDENCY_PAIRS) <= dependency_pairs:
            raise ValueError(
                "all known dependency choices must be explicit, including unknown links"
            )
        return self


REQUIRED_DEPENDENCY_PAIRS = (
    ("component", "training-configuration"),
    ("occupation", "weapon-platform-eligibility"),
    ("assignment", "training-context"),
    ("training-cycle", "training-event-frequency"),
    ("training-event", "rounds-per-event"),
    ("role", "participation"),
    ("instructor-status", "participation"),
    ("deployment-preparation", "training-event-frequency"),
)


class GenerationProvenance(ResearchModel):
    simulation_id: Identifier
    scenario_id: Identifier
    scenario_version: SemVer
    generator_version: SimulationVersion
    rng_algorithm: Literal["python-mt19937-random-v1"]
    master_seed: Annotated[int, Field(ge=0, strict=True)]
    rng_stream: RngStream
    prior_definition_ids: tuple[Identifier, ...]
    evidence_ids: tuple[Identifier, ...]
    sme_estimate_ids: tuple[Identifier, ...]
    scenario_assumption_ids: tuple[Identifier, ...]
    parameter_ids: tuple[Identifier, ...] = Field(min_length=1)
    generation_method: GenerationMethod
    uncertainty_types: tuple[UncertaintyType, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_lineage(self) -> Self:
        lineage = (
            *self.prior_definition_ids,
            *self.evidence_ids,
            *self.sme_estimate_ids,
            *self.scenario_assumption_ids,
            *self.parameter_ids,
        )
        if not lineage:
            raise ValueError("generated values require prior, evidence or assumption lineage")
        source_lineage = (
            *self.prior_definition_ids,
            *self.evidence_ids,
            *self.sme_estimate_ids,
            *self.scenario_assumption_ids,
        )
        if len(source_lineage) != len(set(source_lineage)):
            raise ValueError("provenance source identifiers must be unique across lineage groups")
        if len(self.parameter_ids) != len(set(self.parameter_ids)):
            raise ValueError("parameter lineage identifiers must be unique")
        if len(self.uncertainty_types) != len(set(self.uncertainty_types)):
            raise ValueError("uncertainty types must be unique")
        return self


class QuantityValue(ResearchModel):
    state: QuantityState
    value: FiniteFloat | None
    provenance: GenerationProvenance

    @model_validator(mode="after")
    def unknown_is_not_zero(self) -> Self:
        if self.state == QuantityState.OBSERVED and self.value is None:
            raise ValueError("observed quantities require a value")
        if self.state != QuantityState.OBSERVED and self.value is not None:
            raise ValueError(
                "unknown/not-applicable quantities cannot be encoded as numeric values"
            )
        return self


class SyntheticMember(ResearchModel):
    member_id: SyntheticIdentifier
    service_start: date
    service_end: date
    provenance: GenerationProvenance

    @model_validator(mode="after")
    def ordered_dates(self) -> Self:
        if self.service_end < self.service_start:
            raise ValueError("member service dates must be ordered")
        return self


class CareerEpisode(ResearchModel):
    career_episode_id: SyntheticIdentifier
    member_id: SyntheticIdentifier
    branch: Branch
    component: Component
    occupation_id: Identifier
    start_date: date
    end_date: date
    provenance: GenerationProvenance

    @model_validator(mode="after")
    def valid_component_and_dates(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("career episode dates must be ordered")
        _validate_component(self.branch, self.component)
        return self


class AssignmentEpisode(ResearchModel):
    assignment_id: SyntheticIdentifier
    career_episode_id: SyntheticIdentifier
    start_date: date
    end_date: date
    occupation_id: Identifier
    unit_type: Identifier
    weapon_system_ids: tuple[Identifier, ...]
    platform_id: Identifier | None
    crew_role: Identifier | None
    instructor_status: StrictBool
    student_status: StrictBool
    training_context: Identifier
    deployment_or_training_cycle_status: Identifier
    provenance: GenerationProvenance

    @model_validator(mode="after")
    def valid_dates_and_ids(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("assignment dates must be ordered")
        if len(self.weapon_system_ids) != len(set(self.weapon_system_ids)):
            raise ValueError("assignment weapon IDs must be unique")
        return self


class TrainingPeriod(ResearchModel):
    training_period_id: SyntheticIdentifier
    assignment_id: SyntheticIdentifier
    start_date: date
    end_date: date
    training_context: Identifier
    provenance: GenerationProvenance

    @model_validator(mode="after")
    def valid_dates(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("training period dates must be ordered")
        return self


class LiveFireSession(ResearchModel):
    session_id: SyntheticIdentifier
    training_period_id: SyntheticIdentifier
    start_time: datetime
    end_time: datetime
    provenance: GenerationProvenance

    @model_validator(mode="after")
    def valid_times(self) -> Self:
        if not _is_aware(self.start_time) or not _is_aware(self.end_time):
            raise ValueError("session timestamps must include timezone offsets")
        if self.end_time < self.start_time:
            raise ValueError("session times must be ordered")
        return self


class FiringMission(ResearchModel):
    mission_id: SyntheticIdentifier
    session_id: SyntheticIdentifier
    start_time: datetime
    end_time: datetime
    provenance: GenerationProvenance

    @model_validator(mode="after")
    def valid_times(self) -> Self:
        if not _is_aware(self.start_time) or not _is_aware(self.end_time):
            raise ValueError("mission timestamps must include timezone offsets")
        if self.end_time < self.start_time:
            raise ValueError("mission times must be ordered")
        return self


class FiringEvent(ResearchModel):
    """One physical discharge, independent of how many people were present."""

    event_id: SyntheticIdentifier
    timestamp: datetime
    weapon_system_id: Identifier
    weapon_family: Identifier
    training_context: Identifier
    session_id: SyntheticIdentifier
    mission_id: SyntheticIdentifier | None
    round_or_launch_index: PositiveCount
    ammunition_configuration_id: Identifier | None
    provenance: GenerationProvenance

    @model_validator(mode="after")
    def aware_timestamp(self) -> Self:
        if not _is_aware(self.timestamp):
            raise ValueError("firing-event timestamps must include a timezone offset")
        return self


class ParticipantExposure(ResearchModel):
    """One person's association with one physical FiringEvent."""

    exposure_id: SyntheticIdentifier
    event_id: SyntheticIdentifier
    synthetic_member_id: SyntheticIdentifier
    assignment_id: SyntheticIdentifier
    role: Identifier
    participation_type: ParticipationType
    provenance: GenerationProvenance


type GeneratedRecord = (
    SyntheticMember
    | CareerEpisode
    | AssignmentEpisode
    | TrainingPeriod
    | LiveFireSession
    | FiringMission
    | FiringEvent
    | ParticipantExposure
)


class SyntheticCareerDataset(ResearchModel):
    """An in-memory validated batch; future generators must create this atomically."""

    members: tuple[SyntheticMember, ...]
    career_episodes: tuple[CareerEpisode, ...]
    assignments: tuple[AssignmentEpisode, ...]
    training_periods: tuple[TrainingPeriod, ...]
    live_fire_sessions: tuple[LiveFireSession, ...]
    firing_missions: tuple[FiringMission, ...]
    firing_events: tuple[FiringEvent, ...]
    participant_exposures: tuple[ParticipantExposure, ...]

    @model_validator(mode="after")
    def validate_graph(self) -> Self:
        _unique_ids(self.members, "member_id")
        _unique_ids(self.career_episodes, "career_episode_id")
        _unique_ids(self.assignments, "assignment_id")
        _unique_ids(self.training_periods, "training_period_id")
        _unique_ids(self.live_fire_sessions, "session_id")
        _unique_ids(self.firing_missions, "mission_id")
        _unique_ids(self.firing_events, "event_id")
        _unique_ids(self.participant_exposures, "exposure_id")

        members = {row.member_id: row for row in self.members}
        careers = {row.career_episode_id: row for row in self.career_episodes}
        assignments = {row.assignment_id: row for row in self.assignments}
        periods = {row.training_period_id: row for row in self.training_periods}
        sessions = {row.session_id: row for row in self.live_fire_sessions}
        missions = {row.mission_id: row for row in self.firing_missions}
        events = {row.event_id: row for row in self.firing_events}

        for career in self.career_episodes:
            member = members.get(career.member_id)
            if member is None or not _within(
                career.start_date, career.end_date, member.service_start, member.service_end
            ):
                raise ValueError("career episode must fit within an existing member's service")
        for assignment in self.assignments:
            career_row = careers.get(assignment.career_episode_id)
            if career_row is None or not _within(
                assignment.start_date,
                assignment.end_date,
                career_row.start_date,
                career_row.end_date,
            ):
                raise ValueError("assignment must fit within an existing career episode")
        for period in self.training_periods:
            assignment_row = assignments.get(period.assignment_id)
            if assignment_row is None or not _within(
                period.start_date,
                period.end_date,
                assignment_row.start_date,
                assignment_row.end_date,
            ):
                raise ValueError("training period must fit within an existing assignment")
        for session in self.live_fire_sessions:
            period_row = periods.get(session.training_period_id)
            if period_row is None or not _within(
                session.start_time.date(),
                session.end_time.date(),
                period_row.start_date,
                period_row.end_date,
            ):
                raise ValueError("live-fire session must fit within an existing training period")
        for mission in self.firing_missions:
            session_row = sessions.get(mission.session_id)
            if session_row is None or not _within(
                mission.start_time,
                mission.end_time,
                session_row.start_time,
                session_row.end_time,
            ):
                raise ValueError("firing mission must fit within an existing live-fire session")
        for event in self.firing_events:
            session_row = sessions.get(event.session_id)
            if (
                session_row is None
                or not session_row.start_time <= event.timestamp <= session_row.end_time
            ):
                raise ValueError("firing event must be within an existing live-fire session")
            if event.mission_id is not None:
                mission_row = missions.get(event.mission_id)
                if mission_row is None or mission_row.session_id != event.session_id:
                    raise ValueError("firing event mission must belong to its parent session")
                if not mission_row.start_time <= event.timestamp <= mission_row.end_time:
                    raise ValueError("firing event must be within its parent mission")
        for exposure in self.participant_exposures:
            event_row = events.get(exposure.event_id)
            assignment_row = assignments.get(exposure.assignment_id)
            career_row = careers.get(assignment_row.career_episode_id) if assignment_row else None
            if event_row is None:
                raise ValueError("participant exposure references an unknown physical firing event")
            if career_row is None or career_row.member_id != exposure.synthetic_member_id:
                raise ValueError("participant member must own the referenced assignment")
            assert assignment_row is not None
            if (
                not assignment_row.start_date
                <= event_row.timestamp.date()
                <= assignment_row.end_date
            ):
                raise ValueError("participant assignment must cover the firing-event date")
            if exposure.provenance.simulation_id != event_row.provenance.simulation_id:
                raise ValueError("participant exposure and physical event must share a simulation")
        _validate_synthetic_provenance(
            (
                *self.members,
                *self.career_episodes,
                *self.assignments,
                *self.training_periods,
                *self.live_fire_sessions,
                *self.firing_missions,
                *self.firing_events,
                *self.participant_exposures,
            )
        )
        return self


class RecordType(StrEnum):
    MEMBER = "SyntheticMember"
    CAREER = "CareerEpisode"
    ASSIGNMENT = "AssignmentEpisode"
    TRAINING = "TrainingPeriod"
    SESSION = "LiveFireSession"
    MISSION = "FiringMission"
    EVENT = "FiringEvent"
    EXPOSURE = "ParticipantExposure"


class BindingValueType(StrEnum):
    INT = "int"
    FLOAT = "float"
    DATE = "date"
    DURATION_HOURS = "duration_hours"
    DEGREES = "degrees"
    METERS = "meters"
    CATEGORICAL = "categorical"
    IDENTIFIER = "identifier"


class ExecutionRounding(StrEnum):
    FLOOR = "floor"
    CEIL = "ceil"
    REJECT = "reject"


class CountMeaning(StrEnum):
    SESSIONS = "sessions"
    MISSIONS = "missions"
    PHYSICAL_DISCHARGES = "physical_discharges"


class FieldBinding(ResearchModel):
    parameter_id: Identifier
    record_type: RecordType
    field_name: Text
    value_type: BindingValueType
    unit: Text | None = None
    rounding: ExecutionRounding | None = None
    count_meaning: CountMeaning | None = None
    counting_interval: Text | None = None

    @property
    def field_ref(self) -> str:
        return f"{self.record_type.value}.{self.field_name}"


class Codebook(ResearchModel):
    field_ref: Text
    permitted_values: tuple[Identifier, ...] | None = None
    numeric_codes: tuple[tuple[StrictInteger, Identifier], ...] | None = None

    @model_validator(mode="after")
    def exactly_one_table(self) -> Self:
        if (self.permitted_values is None) == (self.numeric_codes is None):
            raise ValueError(
                "4f: codebook requires exactly one of permitted_values or numeric_codes"
            )
        return self


class EligibilityRelation(ResearchModel):
    occupation_id: Identifier
    eligible_weapon_ids: tuple[Identifier, ...]
    eligible_platform_ids: tuple[Identifier, ...]


class RolePresenceRule(ResearchModel):
    quantity: Literal["role_participation", "nearby_participation", "instructor_repeated_presence"]
    parameter_id: Identifier
    role_id: Identifier
    participation_type: ParticipationType
    presence_parameter_id: Identifier
    presence_semantics: Literal["boolean_code", "probability"]
    presence_description: Text
    repetition_scope: Literal["per_event", "per_session"]
    instructor_status: StrictBool | None
    student_status: StrictBool | None


class PlacementRule(ResearchModel):
    """Explicit binding references; offsets are relative to the declared parent.

    Dates use day offsets from the configured simulation start; timestamps use
    hour offsets within the declared parent's UTC span. No default shape exists.
    """

    record_type: RecordType
    timezone: Text
    shape: Literal["binding_offsets", "uniform", "evenly_spaced", "midnight"]
    shape_parameter_id: Identifier | None = None
    start_parameter_id: Identifier | None = None
    end_parameter_id: Identifier | None = None
    offset_parameter_id: Identifier | None = None
    duration_parameter_id: Identifier | None = None
    partition_parameter_id: Identifier | None = None
    count_parameter_id: Identifier | None = None
    mission_applicability_parameter_id: Identifier | None = None
    unit: Literal["days", "hours"]
    rounding: ExecutionRounding | None = None
    count_meaning: CountMeaning | None = None
    counting_interval: Text | None = None
    containment: Literal["inclusive"]
    clip: StrictBool
    resample: StrictBool


class MissingnessTarget(ResearchModel):
    target_quantity: Identifier
    field_ref: Literal[
        "AssignmentEpisode.platform_id",
        "AssignmentEpisode.crew_role",
        "FiringEvent.ammunition_configuration_id",
    ]
    latent_never_none: StrictBool
    mcar_probability_parameter_id: Identifier | None = None


class RecordLineage(ResearchModel):
    record_type: RecordType
    parameter_ids: tuple[Identifier, ...] = Field(min_length=1)
    rng_stream: RngStream


class FieldDerivation(ResearchModel):
    """Closed, explicit field operations; no prose or implicit source discovery."""

    record_type: RecordType
    field_name: Text
    operation: Literal[
        "component_selection",
        "branch_from_component",
        "eligibility_weapons",
        "eligibility_platform",
        "assignment_weapon",
        "identifier_codebook",
        "carry_forward",
        "assignment_status",
    ]
    parameter_ids: tuple[Identifier, ...] = Field(min_length=1)
    selector_parameter_id: Identifier | None = None
    source_field_ref: Text | None = None
    codebook_field_ref: Text | None = None
    component_codes: tuple[tuple[StrictInteger, Component], ...] = ()
    status_codes: tuple[tuple[StrictInteger, StrictBool, StrictBool], ...] = ()

    @property
    def field_ref(self) -> str:
        return f"{self.record_type.value}.{self.field_name}"


class ExecutionMapping(ResearchModel):
    mapping_id: Identifier
    mapping_version: SemVer
    execution_generator_version: SimulationVersion
    scenario_id: Identifier
    scenario_version: SemVer
    field_bindings: tuple[FieldBinding, ...]
    codebooks: tuple[Codebook, ...]
    eligibility: tuple[EligibilityRelation, ...]
    role_presence_rules: tuple[RolePresenceRule, ...]
    placement_rules: tuple[PlacementRule, ...]
    missingness_targets: tuple[MissingnessTarget, ...]
    record_lineage: tuple[RecordLineage, ...]
    evaluation_order: tuple[Text, ...]
    derivations: tuple[FieldDerivation, ...] = ()

    def canonical_json(self) -> str:
        """Whole-contract JSON with stable Python float representation."""
        return json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False
        )

    def fingerprint(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()


class FeatureName(StrEnum):
    CAREER_DURATION = "career_duration"
    ASSIGNMENT_DURATION = "assignment_duration"
    TOTAL_FIRING_EVENTS = "total_firing_events"
    PARTICIPANT_EXPOSURE_EVENTS = "participant_exposure_events"
    EVENTS_LAST_7D = "events_last_7d"
    EVENTS_LAST_30D = "events_last_30d"
    EVENTS_LAST_365D = "events_last_365d"
    TIME_SINCE_LAST_EVENT = "time_since_last_event"
    WEAPON_FAMILY_COUNTS = "weapon_family_counts"
    ROLE_SPECIFIC_COUNTS = "role_specific_counts"
    TRAINING_DENSITY = "training_density"


class FeatureContract(ResearchModel):
    name: FeatureName
    unit: Text
    source_tables: tuple[Identifier, ...] = Field(min_length=1)
    definition: Text
    medical_or_injury_inference: Literal[False]


class GenerationApproval(ResearchModel):
    """Future V0.5 gate metadata; its existence does not enable a V0.4 generator."""

    scenario_id: Identifier
    approved_scenario_version: SemVer
    population_scope: Text
    simulation_purpose: Text
    sensitivity_analysis_plan: Text
    parameter_bindings: tuple[ParameterBinding, ...] = Field(min_length=1)
    approval_reference: Identifier


def validate_scenario_registry(
    scenario: ScenarioDefinition,
    *,
    prior_definition_ids: set[str],
    prior_classifications: dict[str, ParameterClass],
    evidence_ids: set[str],
    sme_estimate_ids: set[str],
) -> None:
    """Check scenario references against the supplied, versioned registries."""
    if not set(scenario.prior_definition_ids) <= prior_definition_ids:
        raise ValueError("scenario references an unknown PriorDefinition")
    if not set(scenario.prior_definition_ids) <= prior_classifications.keys():
        raise ValueError("scenario PriorDefinition classification is missing")
    if not set(scenario.evidence_constraint_ids) <= evidence_ids:
        raise ValueError("scenario references an unknown evidence constraint")
    if not set(scenario.sme_estimate_ids) <= sme_estimate_ids:
        raise ValueError("scenario references an unknown SME estimate")
    if not set(scenario.supporting_evidence_ids) <= evidence_ids:
        raise ValueError("scenario references unknown supporting evidence")
    if not set(scenario.evidence_constraint_ids) <= set(scenario.prior_definition_ids):
        raise ValueError("evidence constraints must reference PriorDefinition records")
    if not set(scenario.sme_estimate_ids) <= set(scenario.prior_definition_ids):
        raise ValueError("SME estimates must reference PriorDefinition records")
    if any(
        prior_classifications[prior_id] != ParameterClass.EVIDENCE_CONSTRAINT
        for prior_id in scenario.evidence_constraint_ids
    ):
        raise ValueError("evidence constraint IDs must retain their source classification")
    if any(
        prior_classifications[prior_id] != ParameterClass.SME_ESTIMATE
        for prior_id in scenario.sme_estimate_ids
    ):
        raise ValueError("SME estimate IDs cannot reference empirical or assumption records")


def validate_configuration_references(
    config: SimulationConfig,
    scenario: ScenarioDefinition,
    *,
    prior_definition_ids: set[str],
    prior_classifications: dict[str, ParameterClass],
    evidence_ids: set[str],
    sme_estimate_ids: set[str],
) -> None:
    """Validate config-to-scenario joins and every nested provenance reference."""
    if (config.scenario_id, config.scenario_version) != (
        scenario.scenario_id,
        scenario.scenario_version,
    ):
        raise ValueError("simulation config references a different scenario/version")
    validate_scenario_registry(
        scenario,
        prior_definition_ids=prior_definition_ids,
        prior_classifications=prior_classifications,
        evidence_ids=evidence_ids,
        sme_estimate_ids=sme_estimate_ids,
    )
    assumptions = {item.assumption_id for item in scenario.assumptions}
    priors = set(scenario.prior_definition_ids)
    evidence = set(scenario.supporting_evidence_ids)
    if set(scenario.sme_estimate_ids) - sme_estimate_ids:
        raise ValueError("scenario references an unknown SME estimate")
    blocks = (
        config.career_configuration,
        config.assignment_configuration,
        config.participation_configuration,
    )
    bindings = configured_parameter_bindings(config)
    scenario_parameters = {item.parameter_id: item for item in scenario.parameters}
    if len({binding.parameter_id for binding in bindings}) != len(bindings):
        raise ValueError("configuration parameter IDs must be unique across all quantities")
    for binding in bindings:
        if scenario_parameters.get(binding.parameter_id) != binding:
            raise ValueError("configuration parameter must exactly match the scenario definition")
        if not set(binding.prior_definition_ids) <= priors:
            raise ValueError("configuration references a prior absent from scenario")
        if binding.parameter_class in {
            ParameterClass.EMPIRICAL_PRIOR,
            ParameterClass.EVIDENCE_CONSTRAINT,
        }:
            if any(
                prior_classifications.get(prior_id) != binding.parameter_class
                for prior_id in binding.prior_definition_ids
            ):
                raise ValueError(
                    "parameter classification must match each referenced PriorDefinition"
                )
        if binding.parameter_class == ParameterClass.EVIDENCE_CONSTRAINT and not set(
            binding.prior_definition_ids
        ) <= set(scenario.evidence_constraint_ids):
            raise ValueError("evidence parameter must reference an evidence-constraint record")
        if not set(binding.evidence_ids) <= evidence:
            raise ValueError("configuration references evidence absent from scenario")
        if not set(binding.sme_estimate_ids) <= set(scenario.sme_estimate_ids):
            raise ValueError("configuration references an SME estimate absent from scenario")
        if any(
            prior_classifications.get(sme_id) != ParameterClass.SME_ESTIMATE
            for sme_id in binding.sme_estimate_ids
        ):
            raise ValueError("SME parameter provenance must remain classified as SME")
        if not set(binding.scenario_assumption_ids) <= assumptions:
            raise ValueError("configuration references an undeclared assumption")
    dependencies = [dependency for block in blocks for dependency in block.dependencies]
    dependencies.extend(config.training_configuration.dependencies)
    dependencies.extend(
        dependency
        for component in config.training_configuration.component_configurations
        for dependency in component.dependencies
    )
    configured_dependency_ids = {dependency.dependency_id for dependency in dependencies}
    if configured_dependency_ids != set(scenario.dependency_ids):
        raise ValueError("scenario and configuration dependency references must match exactly")
    for dependency in dependencies:
        if dependency.scenario_assumption_id is not None and (
            dependency.scenario_assumption_id not in assumptions
        ):
            raise ValueError("dependency references an undeclared scenario assumption")
    for rule in config.missingness_configuration.rules:
        if (
            rule.scenario_assumption_id is not None
            and rule.scenario_assumption_id not in assumptions
        ):
            raise ValueError("missingness rule references an undeclared assumption")
    for dimension in config.uncertainty_configuration.dimensions:
        if not set(dimension.prior_definition_ids) <= priors:
            raise ValueError("uncertainty lineage references a prior absent from scenario")
        if not set(dimension.evidence_ids) <= evidence:
            raise ValueError("uncertainty lineage references evidence absent from scenario")
        if not set(dimension.sme_estimate_ids) <= set(scenario.sme_estimate_ids):
            raise ValueError("uncertainty lineage references an SME estimate absent from scenario")
        if not set(dimension.scenario_assumption_ids) <= assumptions:
            raise ValueError("uncertainty lineage references an undeclared assumption")


def require_future_generation_approval(approval: GenerationApproval | None) -> None:
    """Fail closed: V0.4 has no production generator, even with gate metadata."""
    if approval is None:
        raise ValueError("production generation is blocked: V0.5 approval gate is absent")
    raise ValueError("production generation is disabled in V0.4 architecture-only release")


def stable_synthetic_id(entity_type: SyntheticEntityType, ordinal: int) -> SyntheticIdentifier:
    """Create a deterministic synthetic-only ID from a stable generation ordinal."""
    if ordinal < 1:
        raise ValueError("synthetic ID ordinals must be positive")
    return f"SYN-{entity_type.value}-{ordinal:06d}"


def _validate_component(branch: Branch, component: Component) -> None:
    if branch == Branch.ARMY and component not in {
        Component.ARMY_ACTIVE,
        Component.ARMY_NATIONAL_GUARD,
        Component.ARMY_RESERVE,
    }:
        raise ValueError("Army career episode requires an Army component")
    if branch == Branch.MARINE_CORPS and component not in {
        Component.MARINE_ACTIVE,
        Component.MARINE_RESERVE,
    }:
        raise ValueError("Marine Corps career episode requires a Marine component")


def _within(
    start: date | datetime,
    end: date | datetime,
    outer_start: date | datetime,
    outer_end: date | datetime,
) -> bool:
    if isinstance(outer_start, datetime) and isinstance(outer_end, datetime):
        return (
            isinstance(start, datetime)
            and isinstance(end, datetime)
            and outer_start <= start <= end <= outer_end
        )
    start_date = start.date() if isinstance(start, datetime) else start
    end_date = end.date() if isinstance(end, datetime) else end
    start_bound = outer_start.date() if isinstance(outer_start, datetime) else outer_start
    end_bound = outer_end.date() if isinstance(outer_end, datetime) else outer_end
    return start_bound <= start_date <= end_date <= end_bound


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _unique_ids(rows: tuple[ResearchModel, ...], field: str) -> None:
    values = [getattr(row, field) for row in rows]
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {field}; physical record identity must be stable")


def _validate_synthetic_provenance(rows: tuple[GeneratedRecord, ...]) -> None:
    run_keys = {
        (
            row.provenance.simulation_id,
            row.provenance.scenario_id,
            row.provenance.scenario_version,
            row.provenance.generator_version,
            row.provenance.rng_algorithm,
            row.provenance.master_seed,
        )
        for row in rows
    }
    if len(run_keys) > 1:
        raise ValueError("synthetic records from different simulations cannot be mixed")


def _all_dependencies(config: SimulationConfig) -> tuple[DependencySpecification, ...]:
    return (
        *config.career_configuration.dependencies,
        *config.assignment_configuration.dependencies,
        *config.training_configuration.dependencies,
        *config.participation_configuration.dependencies,
        *(
            dependency
            for component in config.training_configuration.component_configurations
            for dependency in component.dependencies
        ),
    )


def configured_parameter_bindings(config: SimulationConfig) -> tuple[ParameterBinding, ...]:
    """Flatten required typed inputs without losing their stable parameter IDs."""
    return (
        *config.execution_bindings,
        config.career_configuration.career_duration,
        config.career_configuration.career_episode_count,
        config.career_configuration.branch_component_transition,
        config.assignment_configuration.assignment_duration,
        config.assignment_configuration.occupation_selection,
        config.assignment_configuration.weapon_platform_eligibility,
        config.training_configuration.cycle_context,
        config.participation_configuration.role_participation,
        config.participation_configuration.nearby_participation,
        config.participation_configuration.instructor_repeated_presence,
        *(row.population_weight for row in config.population_configuration.components),
        *(
            binding
            for component in config.training_configuration.component_configurations
            for binding in (component.training_event_frequency, component.rounds_per_event)
        ),
    )
