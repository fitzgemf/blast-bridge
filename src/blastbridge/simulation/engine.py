"""Fictional execution boundary; assembler pending V5-2."""

from .execution import EXECUTION_GENERATOR_VERSION as EXECUTION_GENERATOR_VERSION
from .fictional import FictionalGenerationApproval, authorize_fictional_execution
from .models import (
    AssignmentEpisode,
    CareerEpisode,
    ComponentTrainingConfiguration,
    ConfigurationBlock,
    DependencyMode,
    ExecutionMapping,
    FiringEvent,
    FiringMission,
    LiveFireSession,
    MissingnessMechanism,
    ParticipantExposure,
    ScenarioDefinition,
    SimulationConfig,
    SyntheticCareerDataset,
    SyntheticMember,
    TrainingPeriod,
)
from .rng import child_rng


def generate(
    config: SimulationConfig,
    scenario: ScenarioDefinition,
    approval: FictionalGenerationApproval,
    mapping: ExecutionMapping,
) -> SyntheticCareerDataset:
    """Authorize the mapping first; no rows until the V5-2 assembler is supplied.

    No partial dataset, hierarchy row, or child RNG exists on refusal. MCAR is
    still refused here until V5-2 consumes its fixed-p/target mapping.
    """
    authorize_fictional_execution(config, scenario, approval, mapping)
    _preflight(config)
    raise ValueError("assembler pending V5-2")


def _execution_operations() -> tuple[object, ...]:
    """Names bound by this engine, exposed for refusal-boundary instrumentation.

    Returning the operations creates neither RNG nor record. The future
    assembler must call these same module globals, which tests replace.
    """
    return (
        child_rng,
        SyntheticMember,
        CareerEpisode,
        AssignmentEpisode,
        TrainingPeriod,
        LiveFireSession,
        FiringMission,
        FiringEvent,
        ParticipantExposure,
    )


def _preflight(config: SimulationConfig) -> None:
    blocks: tuple[ConfigurationBlock | ComponentTrainingConfiguration, ...] = (
        config.career_configuration,
        config.assignment_configuration,
        config.training_configuration,
        config.participation_configuration,
        *config.training_configuration.component_configurations,
    )
    for block in blocks:
        for dependency in block.dependencies:
            if dependency.mode != DependencyMode.INDEPENDENT_ASSUMPTION:
                raise ValueError(
                    f"dependency {dependency.dependency_id}: mode {dependency.mode} refused; "
                    "only independent_assumption has executable semantics"
                )

    targets: set[str] = set()
    for rule in config.missingness_configuration.rules:
        if rule.target_quantity in targets:
            raise ValueError(
                f"missingness target {rule.target_quantity}: duplicate/overlapping rules refused"
            )
        targets.add(rule.target_quantity)
        if rule.mechanism == MissingnessMechanism.MCAR:
            raise ValueError(
                f"missingness target {rule.target_quantity}: mcar refused; "
                "missingness sampler pending V5-2"
            )
        if rule.mechanism not in {
            MissingnessMechanism.STRUCTURAL,
            MissingnessMechanism.NOT_COLLECTED,
        }:
            raise ValueError(
                f"missingness target {rule.target_quantity}: mechanism {rule.mechanism} refused"
            )
        if rule.condition_quantity_ids:
            raise ValueError(
                f"missingness target {rule.target_quantity}: "
                "conditional deterministic scope refused"
            )
