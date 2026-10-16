"""Atomic in-memory execution of explicitly mapped fictional scenarios."""

import math
from datetime import UTC, datetime, time, timedelta
from random import Random
from typing import Any, NoReturn

from . import distributions
from .execution import EXECUTION_GENERATOR_VERSION as EXECUTION_GENERATOR_VERSION
from .execution import RECORD_STREAMS
from .fictional import FictionalGenerationApproval, authorize_fictional_execution
from .models import (
    AssignmentEpisode,
    BindingValueType,
    Branch,
    CareerEpisode,
    Component,
    ComponentTrainingConfiguration,
    ConfigurationBlock,
    DependencyMode,
    ExecutionMapping,
    FiringEvent,
    FiringMission,
    GenerationMethod,
    GenerationProvenance,
    LiveFireSession,
    MissingnessMechanism,
    ParticipantExposure,
    RecordType,
    RngStream,
    ScenarioDefinition,
    SimulationConfig,
    SyntheticCareerDataset,
    SyntheticEntityType,
    SyntheticMember,
    TrainingPeriod,
    configured_parameter_bindings,
    stable_synthetic_id,
)
from .outputs import SyntheticOutput
from .rng import child_rng


def generate(
    config: SimulationConfig,
    scenario: ScenarioDefinition,
    approval: FictionalGenerationApproval,
    mapping: ExecutionMapping,
) -> SyntheticCareerDataset:
    """Authorize, preflight, assemble latent rows, mask, and validate atomically."""
    authorize_fictional_execution(config, scenario, approval, mapping)
    _preflight(config, mapping)
    return _Assembler(config, scenario, mapping).assemble()


def _execution_operations() -> tuple[object, ...]:
    """Names bound by this engine, exposed for refusal-boundary instrumentation.

    Returning the operations creates neither RNG nor record. The
    assembler calls these same module globals, which tests replace.
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


def _preflight(config: SimulationConfig, mapping: ExecutionMapping) -> None:
    if len(config.population_configuration.components) > 1:
        raise ValueError(
            "multiple population components: per-component placement selection undefined in V5-2"
        )
    operations = {"sample", "place", "mask", *(kind.value for kind in RecordType)}
    for operation in mapping.evaluation_order:
        if operation not in operations:
            raise ValueError(
                f"evaluation operation {operation}: no executable algorithm in V5-2"
            )
    for rule in mapping.placement_rules:
        if rule.shape != "binding_offsets":
            raise ValueError(
                f"placement shape {rule.shape} for {rule.record_type}: "
                "no executable algorithm in V5-2"
            )
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
        if rule.mechanism not in {
            MissingnessMechanism.MCAR,
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


# Keys are seed encodings only. Table traversal and ordering use integer tuples.
def _entity_key(path: tuple[int, ...], operation: str, parameter_id: str) -> str:
    return "|".join(f"{len(part)}:{part}" for part in (*map(str, path), operation, parameter_id))


class _Assembler:
    def __init__(
        self, config: SimulationConfig, scenario: ScenarioDefinition, mapping: ExecutionMapping
    ) -> None:
        self.config, self.scenario, self.mapping = config, scenario, mapping
        self.fingerprint = mapping.fingerprint()
        self.parameters = {p.parameter_id: p for p in configured_parameter_bindings(config)}
        self.placements = {r.record_type: r for r in mapping.placement_rules}
        self.books = {b.field_ref: b for b in mapping.codebooks}
        self.eligibility = {e.occupation_id: e for e in mapping.eligibility}
        self.rows: dict[RecordType, list[tuple[tuple[int, ...], dict[str, Any]]]] = {
            kind: [] for kind in RecordType
        }
        self.provenance: dict[RecordType, GenerationProvenance] = {}
        for lineage in mapping.record_lineage:
            ids = tuple(dict.fromkeys(lineage.parameter_ids))
            bindings = [self.parameters[key] for key in ids]
            self.provenance[lineage.record_type] = GenerationProvenance(
                simulation_id=config.simulation_id,
                scenario_id=config.scenario_id,
                scenario_version=config.scenario_version,
                generator_version=config.generator_version,
                rng_algorithm=config.rng_algorithm,
                master_seed=config.master_seed,
                rng_stream=lineage.rng_stream,
                parameter_ids=ids,
                scenario_assumption_ids=tuple(dict.fromkeys(
                    value for b in bindings for value in b.scenario_assumption_ids
                )),
                uncertainty_types=tuple(dict.fromkeys(
                    value for b in bindings for value in b.uncertainty_types
                )),
                prior_definition_ids=(), evidence_ids=(), sme_estimate_ids=(),
                generation_method=GenerationMethod.DISTRIBUTION_SAMPLE,
            )

    @staticmethod
    def fail(path: tuple[int, ...], parameter: str, reason: str) -> NoReturn:
        raise ValueError(f"record path {path}, parameter {parameter}: {reason}")

    def rng(
        self, kind: RecordType, path: tuple[int, ...], operation: str, parameter: str,
        *, stream: RngStream | None = None,
    ) -> Random:
        return child_rng(
            self.config, self.scenario, stream or RECORD_STREAMS[kind],
            _entity_key(path, operation, parameter), execution_fingerprint=self.fingerprint,
        )

    def draw(
        self, kind: RecordType, path: tuple[int, ...], operation: str, parameter: str,
    ) -> Any:
        try:
            return distributions.sample(
                self.parameters[parameter].distribution, self.rng(kind, path, operation, parameter)
            )
        except (ValueError, TypeError, OverflowError) as error:
            self.fail(path, parameter, str(error))

    def integer(
        self, value: Any, rounding: Any, path: tuple[int, ...], parameter: str,
        *, nonnegative: bool = True,
    ) -> int:
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            self.fail(path, parameter, f"expected finite numeric value, got {value!r}")
        if nonnegative and value < 0:
            self.fail(path, parameter, f"negative value {value}")
        if float(value).is_integer():
            return int(value)
        if rounding == "floor":
            return math.floor(value)
        if rounding == "ceil":
            return math.ceil(value)
        self.fail(
            path, parameter,
            f"fractional value {value}: rounding {rounding} has no executable conversion",
        )

    def boolean(self, value: Any, path: tuple[int, ...], parameter: str) -> bool:
        if value not in (0, 1):
            self.fail(path, parameter, f"boolean_code value {value!r} outside {{0,1}}")
        return bool(value)

    def select(self, reference: str, value: Any, path: tuple[int, ...], parameter: str) -> str:
        book = self.books[reference]
        if book.permitted_values is not None:
            if value in book.permitted_values:
                return str(value)
        else:
            for code, identifier in book.numeric_codes or ():
                if value == code:
                    return identifier
        self.fail(path, parameter, f"value {value!r} outside codebook {reference}")

    def count(self, kind: RecordType, parent_path: tuple[int, ...]) -> int:
        rule = self.placements[kind]
        parameter = rule.partition_parameter_id or rule.count_parameter_id
        assert parameter is not None  # Authorized complete placement contract.
        value = self.draw(kind, parent_path, f"count:{kind.value}", parameter)
        return self.integer(value, rule.rounding, parent_path, parameter)

    def fields(
        self, kind: RecordType, path: tuple[int, ...], row: dict[str, Any],
        ancestors: dict[RecordType, dict[str, Any]],
    ) -> None:
        for field in self.mapping.field_bindings:
            if field.record_type != kind:
                continue
            value = self.draw(
                kind, path, f"field:{kind.value}:{field.field_name}", field.parameter_id
            )
            if field.value_type == BindingValueType.INT:
                value = self.integer(
                    value, field.rounding, path, field.parameter_id, nonnegative=False
                )
            elif field.value_type in {BindingValueType.IDENTIFIER, BindingValueType.CATEGORICAL}:
                value = self.select(field.field_ref, value, path, field.parameter_id)
            row[field.field_name] = value

        pending = [source for source in self.mapping.derivations if source.record_type == kind]
        while pending:
            progressed = False
            for source in tuple(pending):
                source_value: Any = None
                if source.source_field_ref:
                    record, name = source.source_field_ref.split(".")
                    owner = row if record == kind.value else ancestors.get(RecordType(record), {})
                    if name not in owner:
                        continue
                    source_value = owner[name]
                operation = source.operation
                parameter = source.selector_parameter_id
                selector: Any = None
                if parameter is not None:
                    selector = self.draw(
                        kind, path, f"derive:{kind.value}:{source.field_name}", parameter
                    )
                if operation == "component_selection":
                    choices = dict(source.component_codes)
                    if selector not in choices:
                        self.fail(path, str(parameter), f"component code {selector!r} not declared")
                    value = choices[selector]
                elif operation == "branch_from_component":
                    branches = {
                        Component.ARMY_ACTIVE: Branch.ARMY,
                        Component.ARMY_NATIONAL_GUARD: Branch.ARMY,
                        Component.ARMY_RESERVE: Branch.ARMY,
                        Component.MARINE_ACTIVE: Branch.MARINE_CORPS,
                        Component.MARINE_RESERVE: Branch.MARINE_CORPS,
                    }
                    value = branches[source_value]
                elif operation == "carry_forward":
                    value = source_value
                elif operation == "eligibility_weapons":
                    value = self.eligibility[source_value].eligible_weapon_ids
                elif operation in {
                    "identifier_codebook", "eligibility_platform", "assignment_weapon"
                }:
                    value = self.select(
                        source.codebook_field_ref or source.field_ref,
                        selector, path, str(parameter),
                    )
                    eligible = (
                        self.eligibility[source_value].eligible_platform_ids
                        if operation == "eligibility_platform" else source_value
                    )
                    if operation != "identifier_codebook" and value not in eligible:
                        self.fail(path, str(parameter), f"selection {value} outside eligible set")
                elif operation == "assignment_status":
                    statuses = {code: (i, s) for code, i, s in source.status_codes}
                    if selector not in statuses:
                        self.fail(
                            path, str(parameter),
                            f"assignment status code {selector!r} not declared",
                        )
                    row["instructor_status"], row["student_status"] = statuses[selector]
                    value = row[source.field_name]
                else:
                    self.fail(
                        path, ",".join(source.parameter_ids), f"unsupported derivation {operation}"
                    )
                row[source.field_name] = value
                pending.remove(source)
                progressed = True
            if not progressed:
                source = pending[0]
                self.fail(path, ",".join(source.parameter_ids),
                          f"unresolved derivation source {source.source_field_ref}")

    def place(
        self, kind: RecordType, path: tuple[int, ...], row: dict[str, Any],
        parent: dict[str, Any] | None,
    ) -> None:
        rule = self.placements[kind]

        def draw(reference: str | None, operation: str) -> Any:
            assert reference is not None
            value = self.draw(kind, path, f"place:{kind.value}:{operation}", reference)
            if rule.unit == "days":
                return self.integer(value, rule.rounding, path, reference)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                self.fail(path, reference, f"expected finite hours, got {value!r}")
            return value

        parameter = ",".join(p for p in (
            rule.start_parameter_id, rule.end_parameter_id,
            rule.offset_parameter_id, rule.duration_parameter_id,
        ) if p)
        try:
            if kind == RecordType.MEMBER:
                lower, upper = self.config.simulation_start_date, self.config.simulation_end_date
                start = lower + timedelta(days=draw(rule.start_parameter_id, "start"))
                end = lower + timedelta(days=draw(rule.end_parameter_id, "end"))
                row.update(service_start=start, service_end=end)
            else:
                assert parent is not None
                if kind in {RecordType.CAREER, RecordType.ASSIGNMENT, RecordType.TRAINING}:
                    lower = parent["service_start" if kind == RecordType.CAREER else "start_date"]
                    upper = parent["service_end" if kind == RecordType.CAREER else "end_date"]
                    start = lower + timedelta(days=draw(rule.offset_parameter_id, "offset"))
                    end = start + timedelta(days=draw(rule.duration_parameter_id, "duration"))
                    row.update(start_date=start, end_date=end)
                else:
                    if kind == RecordType.SESSION:
                        lower = datetime.combine(parent["start_date"], time.min, UTC)
                        # Inclusive calendar days; use the final representable UTC instant.
                        upper = datetime.combine(parent["end_date"], time.max, UTC)
                    else:
                        lower, upper = parent["start_time"], parent["end_time"]
                    start = lower + timedelta(hours=draw(rule.offset_parameter_id, "offset"))
                    if kind == RecordType.EVENT:
                        end = start
                        row["timestamp"] = start
                    else:
                        end = start + timedelta(hours=draw(rule.duration_parameter_id, "duration"))
                        row.update(start_time=start, end_time=end)
            if not lower <= start <= end <= upper:
                self.fail(
                    path, parameter, f"{kind.value} outside parent containment or unordered span"
                )
        except (OverflowError, TypeError) as error:
            self.fail(path, parameter, str(error))

    def add(
        self, kind: RecordType, path: tuple[int, ...], ancestors: dict[RecordType, dict[str, Any]],
        identity: dict[str, Any], parent: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = dict(identity)
        self.fields(kind, path, row, ancestors)
        if kind != RecordType.EXPOSURE:
            self.place(kind, path, row, parent)
        id_field = _TABLES[kind][1]
        row[id_field] = stable_synthetic_id(
            SyntheticEntityType[kind.name], len(self.rows[kind]) + 1
        )
        row["provenance"] = self.provenance[kind]
        self.rows[kind].append((path, row))
        return row

    def participants(
        self, path: tuple[int, ...], ancestors: dict[RecordType, dict[str, Any]],
        session_decisions: dict[str, bool],
    ) -> None:
        assignment = ancestors[RecordType.ASSIGNMENT]
        present = []
        for rule in self.mapping.role_presence_rules:
            if (assignment["instructor_status"], assignment["student_status"]) != (
                rule.instructor_status, rule.student_status
            ):
                continue
            decision_path = path[:-1] if rule.repetition_scope == "per_session" else path
            if rule.repetition_scope == "per_session" and rule.quantity in session_decisions:
                decision = session_decisions[rule.quantity]
            else:
                operation = f"presence:{rule.quantity}"
                rng = self.rng(
                    RecordType.EXPOSURE, decision_path, operation, rule.presence_parameter_id
                )
                try:
                    value = distributions.sample(
                        self.parameters[rule.presence_parameter_id].distribution, rng
                    )
                except (ValueError, TypeError, OverflowError) as error:
                    self.fail(decision_path, rule.presence_parameter_id, str(error))
                if rule.presence_semantics == "boolean_code":
                    decision = self.boolean(value, decision_path, rule.presence_parameter_id)
                else:
                    if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                        self.fail(decision_path, rule.presence_parameter_id,
                                  f"probability {value!r} outside [0,1]")
                    decision = rng.random() < value
                if rule.repetition_scope == "per_session":
                    session_decisions[rule.quantity] = decision
            if decision:
                present.append(rule)
        if len(present) > 1:
            conflicts = ", ".join(
                f"{r.quantity}/{r.role_id}/{r.participation_type}" for r in present
            )
            self.fail(path, ",".join(r.presence_parameter_id for r in present),
                      "multiple applicable role/presence rules present for member "
                      f"{path[:1]} event {path}: {conflicts}")
        for rule in present:
            self.add(RecordType.EXPOSURE, path, ancestors, {
                "event_id": ancestors[RecordType.EVENT]["event_id"],
                "synthetic_member_id": ancestors[RecordType.MEMBER]["member_id"],
                "assignment_id": assignment["assignment_id"],
                "role": rule.role_id, "participation_type": rule.participation_type,
            })

    def descend(
        self, kind: RecordType, path: tuple[int, ...], ancestors: dict[RecordType, dict[str, Any]],
        identity: dict[str, Any], parent: dict[str, Any] | None = None,
    ) -> None:
        row = self.add(kind, path, ancestors, identity, parent)
        ancestors = {**ancestors, kind: row}
        if kind == RecordType.SESSION:
            self.session(path, ancestors)
            return
        children = {
            RecordType.MEMBER: (RecordType.CAREER, "member_id"),
            RecordType.CAREER: (RecordType.ASSIGNMENT, "career_episode_id"),
            RecordType.ASSIGNMENT: (RecordType.TRAINING, "assignment_id"),
            RecordType.TRAINING: (RecordType.SESSION, "training_period_id"),
        }
        child, foreign_key = children[kind]
        for ordinal in range(1, self.count(child, path) + 1):
            self.descend(child, (*path, ordinal), ancestors, {foreign_key: row[foreign_key]}, row)

    def session(self, path: tuple[int, ...], ancestors: dict[RecordType, dict[str, Any]]) -> None:
        session = ancestors[RecordType.SESSION]
        mission_rule = self.placements[RecordType.MISSION]
        parameter = mission_rule.mission_applicability_parameter_id
        assert parameter is not None
        applicable = self.boolean(
            self.draw(RecordType.MISSION, path, "applicability:mission", parameter), path, parameter
        )
        count = self.count(RecordType.MISSION, path)
        if count > 1:
            self.fail(path, str(mission_rule.count_parameter_id),
                      "multiple missions per session: "
                      "event-to-mission assignment undefined in V5-2")
        mission = None
        if applicable and count:
            mission = self.add(RecordType.MISSION, (*path, 1), ancestors,
                               {"session_id": session["session_id"]}, session)
        session_decisions: dict[str, bool] = {}
        for ordinal in range(1, self.count(RecordType.EVENT, path) + 1):
            event_path = (*path, ordinal)
            event_rule = self.placements[RecordType.EVENT]
            parameter = event_rule.mission_applicability_parameter_id
            assert parameter is not None
            applicable = self.boolean(
                self.draw(RecordType.EVENT, event_path, "applicability:event", parameter),
                event_path, parameter,
            )
            if applicable and mission is None:
                self.fail(
                    event_path, parameter,
                    "event applicability requires a mission; session has none",
                )
            event_ancestors = {**ancestors, **({RecordType.MISSION: mission} if mission else {})}
            event = self.add(RecordType.EVENT, event_path, event_ancestors, {
                "session_id": session["session_id"],
                "mission_id": mission["mission_id"] if applicable and mission else None,
                "round_or_launch_index": ordinal,
            }, session)
            if (
                applicable and mission
                and not mission["start_time"] <= event["timestamp"] <= mission["end_time"]
            ):
                self.fail(
                    event_path, str(event_rule.offset_parameter_id),
                    "event outside mission containment",
                )
            self.participants(
                event_path, {**event_ancestors, RecordType.EVENT: event}, session_decisions
            )

    def mask(self) -> None:
        rules = {r.target_quantity: r for r in self.config.missingness_configuration.rules}
        for target in self.mapping.missingness_targets:
            record, name = target.field_ref.split(".")
            rule = rules[target.target_quantity]
            for path, row in self.rows[RecordType(record)]:
                if target.latent_never_none and row[name] is None:
                    self.fail(path, target.target_quantity,
                              f"latent None in latent_never_none target {target.field_ref}")
                masked = True
                if rule.mechanism == MissingnessMechanism.MCAR:
                    parameter = target.mcar_probability_parameter_id
                    assert parameter is not None
                    probability = self.parameters[parameter].distribution
                    # Authorization guarantees a fixed binding; no probability sampling operation.
                    p = probability.model_dump()["value"]
                    rng = self.rng(RecordType(record), path, "mask", target.target_quantity,
                                   stream=RngStream.MISSINGNESS)
                    masked = rng.random() < p
                if masked:
                    row[name] = None

    def assemble(self) -> SyntheticCareerDataset:
        for ordinal in range(1, self.config.population_size + 1):
            self.descend(RecordType.MEMBER, (ordinal,), {}, {})
        self.mask()
        tables: dict[str, Any] = {}
        # Resolve model names through globals here, preserving refusal instrumentation.
        models = {
            RecordType.MEMBER: SyntheticMember, RecordType.CAREER: CareerEpisode,
            RecordType.ASSIGNMENT: AssignmentEpisode, RecordType.TRAINING: TrainingPeriod,
            RecordType.SESSION: LiveFireSession, RecordType.MISSION: FiringMission,
            RecordType.EVENT: FiringEvent, RecordType.EXPOSURE: ParticipantExposure,
        }
        for kind, entries in self.rows.items():
            records = []
            # Preorder already assigns table IDs in integer tuple order; never sort seed keys.
            for path, row in entries:
                try:
                    records.append(models[kind](**row))
                except ValueError as error:
                    self.fail(path, ",".join(self.provenance[kind].parameter_ids), str(error))
            tables[_TABLES[kind][0]] = tuple(records)
        try:
            dataset = SyntheticCareerDataset(**tables)
            SyntheticOutput(config=self.config, scenario=self.scenario, records=dataset)
        except ValueError as error:
            self.fail((), self.mapping.mapping_id, f"assembled graph/output validation: {error}")
        return dataset


_TABLES = {
    RecordType.MEMBER: ("members", "member_id"),
    RecordType.CAREER: ("career_episodes", "career_episode_id"),
    RecordType.ASSIGNMENT: ("assignments", "assignment_id"),
    RecordType.TRAINING: ("training_periods", "training_period_id"),
    RecordType.SESSION: ("live_fire_sessions", "session_id"),
    RecordType.MISSION: ("firing_missions", "mission_id"),
    RecordType.EVENT: ("firing_events", "event_id"),
    RecordType.EXPOSURE: ("participant_exposures", "exposure_id"),
}
