"""Offline V0.4 architecture validation; does not generate simulation records."""

import json

from pydantic import TypeAdapter

from blastbridge.data.priors import load_prior_design
from blastbridge.features.synthetic import FEATURE_CONTRACTS
from blastbridge.simulation.models import (
    AssignmentEpisode,
    CareerEpisode,
    DistributionSpec,
    FiringEvent,
    FiringMission,
    LiveFireSession,
    ParticipantExposure,
    RngStream,
    ScenarioDefinition,
    SimulationConfig,
    SyntheticMember,
    TrainingPeriod,
    require_future_generation_approval,
)
from blastbridge.simulation.outputs import OUTPUT_TABLES, validate_output_schemas


def summarize() -> dict[str, object]:
    validate_output_schemas()
    prior_design = load_prior_design("data/reference")
    try:
        require_future_generation_approval(None)
    except ValueError as error:
        if "blocked" not in str(error):
            raise
    else:
        raise ValueError("production generation must fail closed without V0.5 approval")

    # Force schema generation to catch invalid or unexportable contracts.
    schemas = (
        SimulationConfig.model_json_schema(),
        ScenarioDefinition.model_json_schema(),
        TypeAdapter(DistributionSpec).json_schema(),
        SyntheticMember.model_json_schema(),
        CareerEpisode.model_json_schema(),
        AssignmentEpisode.model_json_schema(),
        TrainingPeriod.model_json_schema(),
        LiveFireSession.model_json_schema(),
        FiringMission.model_json_schema(),
        FiringEvent.model_json_schema(),
        ParticipantExposure.model_json_schema(),
    )
    if any(not schema.get("$defs") and not schema.get("properties") for schema in schemas):
        raise ValueError("one or more architecture schemas are empty")
    return {
        "architecture_version": "0.4.0",
        "prior_design_version": prior_design.priors.metadata.version,
        "distribution_families": [
            "fixed",
            "discrete_uniform",
            "triangular",
            "beta",
            "normal",
            "lognormal",
            "poisson",
            "negative_binomial",
            "categorical",
            "empirical",
        ],
        "rng_streams": [stream.value for stream in RngStream],
        "output_tables": [table.table_name for table in OUTPUT_TABLES],
        "feature_contracts": [feature.name.value for feature in FEATURE_CONTRACTS],
        "generation_enabled": False,
        "medical_or_injury_features": False,
        "schema_validation": "passed",
    }


def main() -> None:
    print(json.dumps(summarize(), indent=2))


if __name__ == "__main__":
    main()
