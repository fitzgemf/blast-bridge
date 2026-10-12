"""Content-enforced authorization for fictional scenarios; no generation."""

from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from pydantic import field_validator

from blastbridge.data.reference import load_reference_bundle
from blastbridge.models.core import ResearchModel, Text
from blastbridge.models.reference import Identifier, SemVer

from .models import (
    CategoricalDistribution,
    EmpiricalDistribution,
    ExecutionMapping,
    MissingnessMechanism,
    ParameterBinding,
    ParameterClass,
    ScenarioDefinition,
    ScenarioLabel,
    SimulationConfig,
    validate_configuration_references,
)


class FictionalGenerationApproval(ResearchModel):
    """Separate nominal type: never authorizes real generation."""

    scenario_id: Identifier
    approved_scenario_version: SemVer
    population_scope: Text
    simulation_purpose: Text
    fictional_acknowledgement: Literal[True]

    @field_validator("fictional_acknowledgement", mode="before")
    @classmethod
    def explicitly_true(cls, value: object) -> Literal[True]:
        if value is not True:
            raise ValueError("fictional acknowledgement must be explicitly true")
        return True


def _models(value: object) -> Iterator[ResearchModel]:
    if isinstance(value, ResearchModel):
        yield value
        for field in type(value).model_fields:
            yield from _models(getattr(value, field))
    elif isinstance(value, tuple):
        for item in value:
            yield from _models(item)


def _test_identifier(value: str) -> None:
    if not value.startswith("test-"):
        raise ValueError(f"fictional identifier must start with test-: {value}")


def _catalog_ids() -> set[str]:
    # Resolve against this checkout, never the caller's cwd. Read-only denylist;
    # catalog contents cannot supply fictional values or eligibility relations.
    directory = Path(__file__).resolve().parents[3] / "data" / "reference"
    try:
        bundle = load_reference_bundle(directory)
    except (OSError, ValueError) as error:
        raise ValueError(f"fictional catalog collision check unavailable: {error}") from error
    # Platforms are catalog weapon records (including primary-platform relations).
    return {row.weapon_system_id for row in bundle.weapons.records} | {
        row.occupation_id for row in bundle.occupations.records
    }


def validate_fictional_entity_ids(entity_ids: tuple[str, ...]) -> None:
    """Engine resolution boundary: check passed-in occupation/weapon/platform IDs.

    Current config/scenario models have no dedicated entity reference fields.
    Numeric codebooks and eligibility mappings must call this before resolution;
    they must come from fictional inputs, never be built from the catalog.
    """
    for entity_id in entity_ids:
        _test_identifier(entity_id)
    catalog_ids = _catalog_ids()
    for entity_id in entity_ids:
        if entity_id in catalog_ids:
            raise ValueError(f"fictional entity collides with reference catalog: {entity_id}")


def validate_fictional_scenario(config: SimulationConfig, scenario: ScenarioDefinition) -> None:
    """Reject the first content violation before any execution can begin."""
    entities: list[str] = []
    for root in (scenario, config):
        for model in _models(root):
            if isinstance(model, ParameterBinding):
                if model.parameter_class != ParameterClass.SCENARIO_ASSUMPTION:
                    raise ValueError(
                        "fictional parameter must be scenario_assumption: " + model.parameter_id
                    )
                if not model.scenario_assumption_ids:
                    raise ValueError(
                        f"fictional parameter requires assumptions: {model.parameter_id}"
                    )
                if isinstance(model.distribution, EmpiricalDistribution):
                    raise ValueError(
                        f"fictional empirical distribution refused: {model.parameter_id}"
                    )
                if isinstance(model.distribution, CategoricalDistribution):
                    entities.extend(model.distribution.categories)
            for field in type(model).model_fields:
                value = getattr(model, field)
                if (
                    field
                    in {
                        "prior_definition_ids",
                        "evidence_ids",
                        "sme_estimate_ids",
                        "evidence_constraint_ids",
                        "supporting_evidence_ids",
                    }
                    and value
                ):
                    raise ValueError(f"fictional {field} must be empty")
                # Quantity IDs are contract names, not scenario-created entities.
                if field.endswith("_id") or field.endswith("_ids"):
                    if field == "condition_quantity_ids":
                        continue
                    if isinstance(value, str):
                        _test_identifier(value)
                    elif isinstance(value, tuple):
                        for identifier in value:
                            if isinstance(identifier, str):
                                _test_identifier(identifier)
    for category in entities:
        if not category.startswith(("test-", "TEST_")):
            raise ValueError(f"fictional category must start with test- or TEST_: {category}")
    catalog_ids = _catalog_ids()
    for category in entities:
        if category in catalog_ids:
            raise ValueError(f"fictional entity collides with reference catalog: {category}")
    if scenario.label != ScenarioLabel.CUSTOM:
        raise ValueError("fictional scenario label must be custom")
    if not any(
        rule.mechanism
        in {
            MissingnessMechanism.MCAR,
            MissingnessMechanism.STRUCTURAL,
            MissingnessMechanism.NOT_COLLECTED,
        }
        for rule in config.missingness_configuration.rules
    ):
        raise ValueError("fictional configuration requires at least one supported missingness rule")


def authorize_fictional_generation(
    config: SimulationConfig,
    scenario: ScenarioDefinition,
    approval: FictionalGenerationApproval,
) -> None:
    """Fictional content guard FIRST; no rows or RNG are created here."""
    validate_fictional_scenario(config, scenario)
    if not isinstance(approval, FictionalGenerationApproval):
        raise ValueError("fictional generation requires FictionalGenerationApproval")
    if approval.fictional_acknowledgement is not True:
        raise ValueError("fictional acknowledgement must be explicitly true")
    if (approval.scenario_id, approval.approved_scenario_version) != (
        scenario.scenario_id,
        scenario.scenario_version,
    ):
        raise ValueError("fictional approval scenario/version mismatch")
    if (approval.population_scope, approval.simulation_purpose) != (
        scenario.population_scope,
        scenario.purpose,
    ):
        raise ValueError("fictional approval scope/purpose mismatch")
    validate_configuration_references(
        config,
        scenario,
        prior_definition_ids=set(),
        prior_classifications={},
        evidence_ids=set(),
        sme_estimate_ids=set(),
    )


def authorize_fictional_execution(
    config: SimulationConfig,
    scenario: ScenarioDefinition,
    approval: FictionalGenerationApproval,
    mapping: ExecutionMapping,
) -> None:
    """Mandatory mapping, with fictional content checked before its semantics."""
    from .execution import mapping_entity_ids, validate_execution_mapping

    validate_fictional_scenario(config, scenario)
    if not isinstance(mapping, ExecutionMapping):
        raise ValueError("fictional execution requires ExecutionMapping")
    identifiers = list(mapping_entity_ids(mapping))
    for root in (config, scenario):
        for model in _models(root):
            for field in type(model).model_fields:
                if field == "condition_quantity_ids":
                    continue
                if field.endswith("_id") or field.endswith("_ids"):
                    value = getattr(model, field)
                    if isinstance(value, str):
                        identifiers.append(value)
                    elif isinstance(value, tuple):
                        identifiers.extend(item for item in value if isinstance(item, str))
    validate_fictional_entity_ids(tuple(identifiers))
    authorize_fictional_generation(config, scenario, approval)
    validate_execution_mapping(config, scenario, mapping)
