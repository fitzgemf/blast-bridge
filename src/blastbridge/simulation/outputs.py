"""Tabular output contracts and serializers without dataframe dependencies."""

from typing import Literal, Self

from pydantic import Field, model_validator

from blastbridge.models.core import ResearchModel
from blastbridge.models.reference import Identifier

from .models import (
    AssignmentEpisode,
    CareerEpisode,
    FiringEvent,
    FiringMission,
    GeneratedRecord,
    LiveFireSession,
    ParticipantExposure,
    ScenarioDefinition,
    SimulationConfig,
    SyntheticCareerDataset,
    SyntheticMember,
    TrainingPeriod,
    configured_parameter_bindings,
)


class OutputColumn(ResearchModel):
    name: Identifier
    logical_type: Literal[
        "string", "integer", "number", "boolean", "date", "timestamp", "list", "struct"
    ]
    nullable: bool


class OutputTableSchema(ResearchModel):
    table_name: Identifier
    schema_version: Literal["0.4.0"]
    synthetic_only: Literal[True]
    primary_key: Identifier
    columns: tuple[OutputColumn, ...] = Field(min_length=1)


class SyntheticOutput(ResearchModel):
    """Validated future output envelope; this model does not generate records."""

    config: SimulationConfig
    scenario: ScenarioDefinition
    records: SyntheticCareerDataset

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        config, scenario, records = self.config, self.scenario, self.records
        if scenario.scenario_id != config.scenario_id:
            raise ValueError("configuration scenario ID does not match scenario definition")
        if scenario.scenario_version != config.scenario_version:
            raise ValueError("configuration scenario version does not match definition")
        if len(records.members) != config.population_size:
            raise ValueError("member count must equal the explicitly configured population size")
        configured_bindings = {
            binding.parameter_id: binding for binding in configured_parameter_bindings(config)
        }
        configured_parameter_ids = set(configured_bindings)
        scenario_parameter_ids = {binding.parameter_id for binding in scenario.parameters}
        scenario_bindings = {binding.parameter_id: binding for binding in scenario.parameters}
        if any(
            scenario_bindings.get(parameter_id) != binding
            for parameter_id, binding in configured_bindings.items()
        ):
            raise ValueError("simulation configuration parameters must match scenario definitions")
        expected = (
            config.simulation_id,
            config.scenario_id,
            config.scenario_version,
            config.generator_version,
            config.rng_algorithm,
            config.master_seed,
        )
        for record in _all_records(records):
            provenance = record.provenance
            actual = (
                provenance.simulation_id,
                provenance.scenario_id,
                provenance.scenario_version,
                provenance.generator_version,
                provenance.rng_algorithm,
                provenance.master_seed,
            )
            if actual != expected:
                raise ValueError("record provenance does not match the simulation configuration")
            if (
                not set(provenance.parameter_ids)
                <= configured_parameter_ids & scenario_parameter_ids
            ):
                raise ValueError(
                    "record parameter lineage must reference configured scenario values"
                )
            bound = [configured_bindings[key] for key in provenance.parameter_ids]
            expected_lineage = {
                "prior_definition_ids": {
                    value for item in bound for value in item.prior_definition_ids
                },
                "evidence_ids": {value for item in bound for value in item.evidence_ids},
                "sme_estimate_ids": {value for item in bound for value in item.sme_estimate_ids},
                "scenario_assumption_ids": {
                    value for item in bound for value in item.scenario_assumption_ids
                },
                "uncertainty_types": {value for item in bound for value in item.uncertainty_types},
            }
            for field, expected_values in expected_lineage.items():
                if set(getattr(provenance, field)) != expected_values:
                    raise ValueError(f"record provenance {field} must match parameter lineage")
            if isinstance(record, SyntheticMember):
                starts, ends = record.service_start, record.service_end
            elif isinstance(record, CareerEpisode):
                starts, ends = record.start_date, record.end_date
            elif isinstance(record, AssignmentEpisode):
                starts, ends = record.start_date, record.end_date
            elif isinstance(record, TrainingPeriod):
                starts, ends = record.start_date, record.end_date
            elif isinstance(record, (LiveFireSession, FiringMission)):
                starts, ends = record.start_time.date(), record.end_time.date()
            elif isinstance(record, FiringEvent):
                starts = ends = record.timestamp.date()
            else:
                continue
            if starts < config.simulation_start_date or ends > config.simulation_end_date:
                raise ValueError("record dates must fit within configured simulation dates")
        return self


OUTPUT_TABLES: tuple[OutputTableSchema, ...] = (
    OutputTableSchema(
        table_name="synthetic_members",
        schema_version="0.4.0",
        synthetic_only=True,
        primary_key="member_id",
        columns=(
            OutputColumn(name="member_id", logical_type="string", nullable=False),
            OutputColumn(name="service_start", logical_type="date", nullable=False),
            OutputColumn(name="service_end", logical_type="date", nullable=False),
            OutputColumn(name="provenance", logical_type="struct", nullable=False),
        ),
    ),
    OutputTableSchema(
        table_name="synthetic_career_episodes",
        schema_version="0.4.0",
        synthetic_only=True,
        primary_key="career_episode_id",
        columns=(
            OutputColumn(name="career_episode_id", logical_type="string", nullable=False),
            OutputColumn(name="member_id", logical_type="string", nullable=False),
            OutputColumn(name="branch", logical_type="string", nullable=False),
            OutputColumn(name="component", logical_type="string", nullable=False),
            OutputColumn(name="occupation_id", logical_type="string", nullable=False),
            OutputColumn(name="start_date", logical_type="date", nullable=False),
            OutputColumn(name="end_date", logical_type="date", nullable=False),
            OutputColumn(name="provenance", logical_type="struct", nullable=False),
        ),
    ),
    OutputTableSchema(
        table_name="synthetic_assignments",
        schema_version="0.4.0",
        synthetic_only=True,
        primary_key="assignment_id",
        columns=(
            OutputColumn(name="assignment_id", logical_type="string", nullable=False),
            OutputColumn(name="career_episode_id", logical_type="string", nullable=False),
            OutputColumn(name="start_date", logical_type="date", nullable=False),
            OutputColumn(name="end_date", logical_type="date", nullable=False),
            OutputColumn(name="occupation_id", logical_type="string", nullable=False),
            OutputColumn(name="unit_type", logical_type="string", nullable=False),
            OutputColumn(name="weapon_system_ids", logical_type="list", nullable=False),
            OutputColumn(name="platform_id", logical_type="string", nullable=True),
            OutputColumn(name="crew_role", logical_type="string", nullable=True),
            OutputColumn(name="instructor_status", logical_type="boolean", nullable=False),
            OutputColumn(name="student_status", logical_type="boolean", nullable=False),
            OutputColumn(name="training_context", logical_type="string", nullable=False),
            OutputColumn(
                name="deployment_or_training_cycle_status", logical_type="string", nullable=False
            ),
            OutputColumn(name="provenance", logical_type="struct", nullable=False),
        ),
    ),
    OutputTableSchema(
        table_name="synthetic_training_periods",
        schema_version="0.4.0",
        synthetic_only=True,
        primary_key="training_period_id",
        columns=(
            OutputColumn(name="training_period_id", logical_type="string", nullable=False),
            OutputColumn(name="assignment_id", logical_type="string", nullable=False),
            OutputColumn(name="start_date", logical_type="date", nullable=False),
            OutputColumn(name="end_date", logical_type="date", nullable=False),
            OutputColumn(name="training_context", logical_type="string", nullable=False),
            OutputColumn(name="provenance", logical_type="struct", nullable=False),
        ),
    ),
    OutputTableSchema(
        table_name="synthetic_live_fire_sessions",
        schema_version="0.4.0",
        synthetic_only=True,
        primary_key="session_id",
        columns=(
            OutputColumn(name="session_id", logical_type="string", nullable=False),
            OutputColumn(name="training_period_id", logical_type="string", nullable=False),
            OutputColumn(name="start_time", logical_type="timestamp", nullable=False),
            OutputColumn(name="end_time", logical_type="timestamp", nullable=False),
            OutputColumn(name="provenance", logical_type="struct", nullable=False),
        ),
    ),
    OutputTableSchema(
        table_name="synthetic_firing_missions",
        schema_version="0.4.0",
        synthetic_only=True,
        primary_key="mission_id",
        columns=(
            OutputColumn(name="mission_id", logical_type="string", nullable=False),
            OutputColumn(name="session_id", logical_type="string", nullable=False),
            OutputColumn(name="start_time", logical_type="timestamp", nullable=False),
            OutputColumn(name="end_time", logical_type="timestamp", nullable=False),
            OutputColumn(name="provenance", logical_type="struct", nullable=False),
        ),
    ),
    OutputTableSchema(
        table_name="synthetic_firing_events",
        schema_version="0.4.0",
        synthetic_only=True,
        primary_key="event_id",
        columns=(
            OutputColumn(name="event_id", logical_type="string", nullable=False),
            OutputColumn(name="timestamp", logical_type="timestamp", nullable=False),
            OutputColumn(name="weapon_system_id", logical_type="string", nullable=False),
            OutputColumn(name="weapon_family", logical_type="string", nullable=False),
            OutputColumn(name="training_context", logical_type="string", nullable=False),
            OutputColumn(name="session_id", logical_type="string", nullable=False),
            OutputColumn(name="mission_id", logical_type="string", nullable=True),
            OutputColumn(name="round_or_launch_index", logical_type="integer", nullable=False),
            OutputColumn(name="ammunition_configuration_id", logical_type="string", nullable=True),
            OutputColumn(name="provenance", logical_type="struct", nullable=False),
        ),
    ),
    OutputTableSchema(
        table_name="synthetic_participant_exposures",
        schema_version="0.4.0",
        synthetic_only=True,
        primary_key="exposure_id",
        columns=(
            OutputColumn(name="exposure_id", logical_type="string", nullable=False),
            OutputColumn(name="event_id", logical_type="string", nullable=False),
            OutputColumn(name="synthetic_member_id", logical_type="string", nullable=False),
            OutputColumn(name="assignment_id", logical_type="string", nullable=False),
            OutputColumn(name="role", logical_type="string", nullable=False),
            OutputColumn(name="participation_type", logical_type="string", nullable=False),
            OutputColumn(name="provenance", logical_type="struct", nullable=False),
        ),
    ),
)


def serialize_output(output: SyntheticOutput) -> dict[str, tuple[dict[str, object], ...]]:
    """Return JSON-compatible rows using stable names for later Parquet/DuckDB adapters."""
    dataset = output.records
    records_by_table: dict[str, tuple[ResearchModel, ...]] = {
        "synthetic_members": dataset.members,
        "synthetic_career_episodes": dataset.career_episodes,
        "synthetic_assignments": dataset.assignments,
        "synthetic_training_periods": dataset.training_periods,
        "synthetic_live_fire_sessions": dataset.live_fire_sessions,
        "synthetic_firing_missions": dataset.firing_missions,
        "synthetic_firing_events": dataset.firing_events,
        "synthetic_participant_exposures": dataset.participant_exposures,
    }
    return {
        table: tuple(row.model_dump(mode="json") for row in records)
        for table, records in records_by_table.items()
    }


def validate_output_schemas() -> None:
    """Ensure table contracts exactly match their Pydantic record models."""
    rows: tuple[tuple[OutputTableSchema, type[ResearchModel]], ...] = (
        (OUTPUT_TABLES[0], SyntheticMember),
        (OUTPUT_TABLES[1], CareerEpisode),
        (OUTPUT_TABLES[2], AssignmentEpisode),
        (OUTPUT_TABLES[3], TrainingPeriod),
        (OUTPUT_TABLES[4], LiveFireSession),
        (OUTPUT_TABLES[5], FiringMission),
        (OUTPUT_TABLES[6], FiringEvent),
        (OUTPUT_TABLES[7], ParticipantExposure),
    )
    if len({table.table_name for table, _ in rows}) != len(OUTPUT_TABLES):
        raise ValueError("synthetic output table names must be unique")
    for table, model in rows:
        names = [column.name for column in table.columns]
        if len(names) != len(set(names)) or set(names) != set(model.model_fields):
            raise ValueError(f"schema columns do not match model fields for {table.table_name}")
        if table.primary_key not in model.model_fields:
            raise ValueError(f"schema primary key is not a model field: {table.table_name}")
        primary_key = next(column for column in table.columns if column.name == table.primary_key)
        if primary_key.nullable:
            raise ValueError(f"primary key cannot be nullable: {table.table_name}")
        if not table.synthetic_only:
            raise ValueError("all V0.4 output tables must be marked synthetic-only")


def _all_records(dataset: SyntheticCareerDataset) -> tuple[GeneratedRecord, ...]:
    return (
        *dataset.members,
        *dataset.career_episodes,
        *dataset.assignments,
        *dataset.training_periods,
        *dataset.live_fire_sessions,
        *dataset.firing_missions,
        *dataset.firing_events,
        *dataset.participant_exposures,
    )
