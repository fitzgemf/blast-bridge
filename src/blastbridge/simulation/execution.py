"""Fail-closed execution semantics. No sampling or hierarchy construction."""

import re
from collections.abc import Iterable
from datetime import date, datetime
from typing import NoReturn, get_args, get_origin

from blastbridge.models.core import ResearchModel

from .models import (
    REQUIRED_DEPENDENCY_PAIRS,
    AssignmentEpisode,
    BetaDistribution,
    BindingValueType,
    CareerEpisode,
    CategoricalDistribution,
    Codebook,
    CountMeaning,
    DiscreteUniformDistribution,
    ExecutionMapping,
    FieldBinding,
    FiringEvent,
    FiringMission,
    FixedDistribution,
    LiveFireSession,
    MissingnessMechanism,
    ParameterBinding,
    ParameterClass,
    ParticipantExposure,
    ParticipationType,
    PlacementRule,
    RecordType,
    RngStream,
    ScenarioDefinition,
    SimulationConfig,
    SyntheticMember,
    TrainingPeriod,
    TriangularDistribution,
    UncertaintyDimension,
    _all_dependencies,
    configured_parameter_bindings,
    validate_configuration_references,
)

EXECUTION_GENERATOR_VERSION = "0.4.0"
RECORD_MODELS: dict[RecordType, type[ResearchModel]] = {
    RecordType.MEMBER: SyntheticMember,
    RecordType.CAREER: CareerEpisode,
    RecordType.ASSIGNMENT: AssignmentEpisode,
    RecordType.TRAINING: TrainingPeriod,
    RecordType.SESSION: LiveFireSession,
    RecordType.MISSION: FiringMission,
    RecordType.EVENT: FiringEvent,
    RecordType.EXPOSURE: ParticipantExposure,
}
RECORD_STREAMS = {
    RecordType.MEMBER: RngStream.POPULATION,
    RecordType.CAREER: RngStream.CAREER,
    RecordType.ASSIGNMENT: RngStream.ASSIGNMENT,
    RecordType.TRAINING: RngStream.TRAINING,
    RecordType.SESSION: RngStream.TRAINING,
    RecordType.MISSION: RngStream.FIRING,
    RecordType.EVENT: RngStream.FIRING,
    RecordType.EXPOSURE: RngStream.PARTICIPATION,
}
TIME_RECORDS = tuple(record for record in RecordType if record != RecordType.EXPOSURE)
MISSINGNESS_FIELDS = frozenset(
    {
        "AssignmentEpisode.platform_id",
        "AssignmentEpisode.crew_role",
        "FiringEvent.ammunition_configuration_id",
    }
)
ENGINE_FIELDS = frozenset(
    {
        "provenance",
        "member_id",
        "career_episode_id",
        "assignment_id",
        "training_period_id",
        "session_id",
        "mission_id",
        "event_id",
        "exposure_id",
        "synthetic_member_id",
        "round_or_launch_index",
    }
)
PLACEMENT_FIELDS = {
    RecordType.MEMBER: ("service_start", "service_end"),
    RecordType.CAREER: ("start_date", "end_date"),
    RecordType.ASSIGNMENT: ("start_date", "end_date"),
    RecordType.TRAINING: ("start_date", "end_date"),
    RecordType.SESSION: ("start_time", "end_time"),
    RecordType.MISSION: ("start_time", "end_time"),
    RecordType.EVENT: ("timestamp",),
}
TIME_FIELDS = frozenset(name for names in PLACEMENT_FIELDS.values() for name in names)
PLACEMENT_REFERENCES = (
    "shape_parameter_id",
    "start_parameter_id",
    "end_parameter_id",
    "offset_parameter_id",
    "duration_parameter_id",
    "partition_parameter_id",
    "count_parameter_id",
    "mission_applicability_parameter_id",
)
# These are contract names, not fictional identifiers. A caller-created operation
# must still be a test- Identifier and is validated by the fictional entity gate.
CONTRACT_OPERATIONS = frozenset(
    {
        *(record.value for record in RecordType),
        *(quantity for pair in REQUIRED_DEPENDENCY_PAIRS for quantity in pair),
        *(dimension.value for dimension in UncertaintyDimension),
        "sample",
        "place",
        "mask",
        "platform-id",
        "crew-role",
        "ammunition-configuration-id",
        "role_participation",
        "nearby_participation",
        "instructor_repeated_presence",
    }
)
DERIVATION_ONLY = {
    "AssignmentEpisode.platform_id": "eligibility_platform",
    "AssignmentEpisode.weapon_system_ids": "eligibility_weapons",
    "FiringEvent.weapon_system_id": "assignment_weapon",
}

MESSAGES = {
    "1a": "1a: required quantity has no execution mapping",
    "1b": "1b: multiple bindings write the same record field",
    "1c": "1c: parameter is outside configured/scenario intersection",
    "1d": "1d: field does not exist on the record model",
    "1e": "1e: binding writes an engine-owned field",
    "1f": "1f: every coverable record field requires exactly one declared source",
    "2a": "2a: value type or unit is incompatible with the record field",
    "2b": "2b: distribution cannot produce the declared value type",
    "3a": "3a: integer or count binding requires explicit rounding",
    "3b": "3b: numeric binding requires an explicit unit",
    "3c": "3c: count binding requires count meaning and counting interval",
    "3d": "3d: cross-quantity frequency/tempo conversion is refused",
    "4a": "4a: identifier or categorical field requires a codebook",
    "4b": "4b: codebook value must be a valid test- Identifier",
    "4c": "4c: numeric distribution support is outside the codebook",
    "4d": "4d: TEST_ category cannot populate an Identifier field",
    "4e": "4e: mapping identifier collides with the reference catalog",
    "4f": "4f: codebook requires exactly one of permitted_values or numeric_codes",
    "4g": "4g: eligibility identifiers must be declared in codebooks",
    "4h": "4h: occupation codebook values require exactly one eligibility relation",
    "4i": "4i: selector support is outside the occupation eligible set",
    "5e": "5e: role status pair is absent from assignment status codes",
    "5a": "5a: required participation quantity has no role/presence rule",
    "5b": "5b: participation type and presence/status decisions must use contract types",
    "5c": "5c: presence semantics must be explicit and documented",
    "5d": "5d: instructor/student status is missing or ambiguous",
    "6a": "6a: complete placement is required for every time-bearing record",
    "6b": "6b: placement must be UTC, ordered, inclusive, and never clip or resample",
    "6c": "6c: built-in placement shape requires a scenario parameter",
    "7a": "7a: missingness target is outside the nullable-scalar allowlist",
    "7b": "7b: missingness cannot delete records or mask required/collection/identity fields",
    "7c": "7c: only structural missingness may mask nullable latent values",
    "7d": "7d: MCAR requires a fixed execution probability in [0,1] citing the rule assumption",
    "7e": "7e: MCAR probability mapping must correspond exactly to an MCAR rule",
    "7f": "7f: duplicate or overlapping missingness targets are refused",
    "7g": "7g: supported missingness cannot specify conditioning quantities",
    "7h": "7h: at least one supported rule must map to an allowlist field",
    "7i": "7i: evaluation_order must include each structural operation exactly once",
    "7j": "7j: evaluation_order must put parents and sampling before placement/masking",
    "8a": "8a: record lineage does not represent governing bindings and registered lineage",
    "9a": "9a: mapping scenario/version does not match the supplied scenario",
    "9b": "9b: mapping version or fictional content is invalid",
}


def _refuse(rule: str) -> NoReturn:
    raise ValueError(MESSAGES[rule])


def _placement_ids(rule: PlacementRule) -> tuple[str, ...]:
    return tuple(
        value for name in PLACEMENT_REFERENCES if isinstance(value := getattr(rule, name), str)
    )


def mapping_entity_ids(mapping: ExecutionMapping) -> tuple[str, ...]:
    """Enumerate every scenario-created identifier; exclude contract field names."""
    identifiers = [mapping.mapping_id, mapping.scenario_id]
    identifiers.extend(field.parameter_id for field in mapping.field_bindings)
    for book in mapping.codebooks:
        identifiers.extend(book.permitted_values or ())
        identifiers.extend(value for _, value in book.numeric_codes or ())
    for relation in mapping.eligibility:
        identifiers.extend(
            (relation.occupation_id, *relation.eligible_weapon_ids, *relation.eligible_platform_ids)
        )
    for role in mapping.role_presence_rules:
        identifiers.extend((role.parameter_id, role.role_id, role.presence_parameter_id))
    for placement in mapping.placement_rules:
        identifiers.extend(_placement_ids(placement))
    for target in mapping.missingness_targets:
        # target_quantity may be a contract quantity or a scenario-made quantity.
        if target.target_quantity not in {
            "platform-id",
            "crew-role",
            "ammunition-configuration-id",
        }:
            identifiers.append(target.target_quantity)
        if target.mcar_probability_parameter_id is not None:
            identifiers.append(target.mcar_probability_parameter_id)
    for lineage in mapping.record_lineage:
        identifiers.extend(lineage.parameter_ids)
    for source in mapping.derivations:
        identifiers.extend(source.parameter_ids)
        if source.selector_parameter_id is not None:
            identifiers.append(source.selector_parameter_id)
    identifiers.extend(item for item in mapping.evaluation_order if item not in CONTRACT_OPERATIONS)
    return tuple(identifiers)


def _numeric_support(binding: ParameterBinding) -> tuple[int, int] | None:
    distribution = binding.distribution
    if isinstance(distribution, FixedDistribution):
        if distribution.value.is_integer():
            return int(distribution.value), int(distribution.value)
    elif isinstance(distribution, DiscreteUniformDistribution):
        return distribution.lower, distribution.upper
    return None


def _codebook_values(book: Codebook) -> tuple[str, ...]:
    return book.permitted_values or tuple(value for _, value in book.numeric_codes or ())


def _probability_support(binding: ParameterBinding) -> bool:
    distribution = binding.distribution
    if isinstance(distribution, FixedDistribution):
        return 0 <= distribution.value <= 1
    if isinstance(distribution, (DiscreteUniformDistribution, TriangularDistribution)):
        return 0 <= distribution.lower <= distribution.upper <= 1
    return isinstance(distribution, BetaDistribution)


def _contains(annotation: object, target: object) -> bool:
    return (
        annotation == target
        or get_origin(annotation) == target
        or any(_contains(arg, target) for arg in get_args(annotation))
    )


def _field_checks(field: FieldBinding, binding: ParameterBinding) -> None:
    annotation = RECORD_MODELS[field.record_type].model_fields[field.field_name].annotation
    identifier = field.value_type in {BindingValueType.IDENTIFIER, BindingValueType.CATEGORICAL}
    numeric = not identifier
    if identifier:
        if not _contains(annotation, str) or _contains(annotation, tuple):
            _refuse("2a")
        if field.unit is not None:
            _refuse("2a")
    elif field.value_type == BindingValueType.INT:
        if not _contains(annotation, int) or _contains(annotation, bool):
            _refuse("2a")
    elif field.value_type in {BindingValueType.DATE, BindingValueType.DURATION_HOURS}:
        target_type = date if field.value_type == BindingValueType.DATE else datetime
        if not _contains(annotation, target_type):
            _refuse("2a")
        expected_unit = "days" if field.value_type == BindingValueType.DATE else "hours"
        if field.unit is not None and field.unit != expected_unit:
            _refuse("2a")
    elif not _contains(annotation, float):
        _refuse("2a")
    if field.value_type == BindingValueType.DEGREES and field.unit not in {None, "degrees"}:
        _refuse("2a")
    if field.value_type == BindingValueType.METERS and field.unit not in {None, "meters"}:
        _refuse("2a")
    categorical = isinstance(binding.distribution, CategoricalDistribution)
    if numeric and categorical:
        _refuse("2b")
    if field.value_type == BindingValueType.INT and field.rounding is None:
        _refuse("3a")
    if numeric and not field.unit:
        _refuse("3b")
    if field.value_type == BindingValueType.INT and (
        field.count_meaning is None or not field.counting_interval
    ):
        _refuse("3c")


def _codebook_checks(mapping: ExecutionMapping, parameters: dict[str, ParameterBinding]) -> None:
    from .fictional import validate_fictional_entity_ids

    books = {book.field_ref: book for book in mapping.codebooks}
    if len(books) != len(mapping.codebooks):
        _refuse("4a")
    for book in mapping.codebooks:
        record_name, _, field_name = book.field_ref.partition(".")
        model = next(
            (model for kind, model in RECORD_MODELS.items() if kind.value == record_name), None
        )
        if model is None or field_name not in model.model_fields:
            _refuse("1d")
        if field_name in ENGINE_FIELDS:
            _refuse("1e")
        if not _contains(model.model_fields[field_name].annotation, str):
            _refuse("2a")
        if (book.permitted_values is None) == (book.numeric_codes is None):
            _refuse("4f")
        values = _codebook_values(book)
        if not values or len(values) != len(set(values)):
            _refuse("4b")
        # Identifier grammar is already enforced at model construction. Recheck
        # here as model_copy can deliberately bypass it in boundary tests.
        if any(not re.fullmatch(r"test-[a-z0-9]+(?:[-_][a-z0-9]+)*", value) for value in values):
            _refuse("4b")
    selectors = tuple(
        FieldBinding(
            parameter_id=source.selector_parameter_id or "",
            record_type=source.record_type,
            field_name=source.field_name,
            value_type=BindingValueType.IDENTIFIER,
        )
        for source in mapping.derivations
        if source.operation in {"identifier_codebook", "eligibility_platform", "assignment_weapon"}
    )
    for field in (*mapping.field_bindings, *selectors):
        if field.value_type not in {BindingValueType.IDENTIFIER, BindingValueType.CATEGORICAL}:
            continue
        matched_book = books.get(field.field_ref)
        if matched_book is None:
            _refuse("4a")
        binding = parameters[field.parameter_id]
        if isinstance(binding.distribution, CategoricalDistribution):
            if any(value.startswith("TEST_") for value in binding.distribution.categories):
                _refuse("4d")
            if matched_book.permitted_values is None or not set(
                binding.distribution.categories
            ) <= set(matched_book.permitted_values):
                _refuse("4c")
        else:
            support = _numeric_support(binding)
            codes = tuple(code for code, _ in matched_book.numeric_codes or ())
            if support is None or len(codes) != len(set(codes)):
                _refuse("4c")
            elif len({code for code in codes if support[0] <= code <= support[1]}) != (
                support[1] - support[0] + 1
            ):
                _refuse("4c")
    try:
        validate_fictional_entity_ids(mapping_entity_ids(mapping))
    except ValueError as error:
        if "collides with reference catalog" in str(error):
            _refuse("4e")
        raise
    allowed = {value for book in mapping.codebooks for value in _codebook_values(book)}
    for relation in mapping.eligibility:
        if (
            not set(
                (
                    relation.occupation_id,
                    *relation.eligible_weapon_ids,
                    *relation.eligible_platform_ids,
                )
            )
            <= allowed
        ):
            _refuse("4g")

    occupations = {
        value
        for book in mapping.codebooks
        if book.field_ref.endswith(".occupation_id")
        for value in _codebook_values(book)
    }
    for occupation in occupations:
        relations = [row for row in mapping.eligibility if row.occupation_id == occupation]
        if len(relations) != 1:
            _refuse("4h")
    for source in mapping.derivations:
        if source.operation not in {"eligibility_platform", "assignment_weapon"}:
            continue
        binding = parameters[source.selector_parameter_id or ""]
        book = books[source.field_ref]
        if isinstance(binding.distribution, CategoricalDistribution):
            selected = set(binding.distribution.categories)
        else:
            support = _numeric_support(binding)
            if support is None:
                _refuse("4c")
            selected = {
                value
                for code, value in book.numeric_codes or ()
                if support[0] <= code <= support[1]
            }
        for relation in mapping.eligibility:
            if relation.occupation_id not in occupations:
                continue
            eligible = (
                relation.eligible_platform_ids
                if source.operation == "eligibility_platform"
                else relation.eligible_weapon_ids
            )
            if not selected <= set(eligible):
                _refuse("4i")


def _role_checks(
    config: SimulationConfig,
    mapping: ExecutionMapping,
    parameters: dict[str, ParameterBinding],
) -> None:
    required = {
        "role_participation": config.participation_configuration.role_participation.parameter_id,
        "nearby_participation": (
            config.participation_configuration.nearby_participation.parameter_id
        ),
        "instructor_repeated_presence": (
            config.participation_configuration.instructor_repeated_presence.parameter_id
        ),
    }
    if {rule.quantity for rule in mapping.role_presence_rules} != set(required) or len(
        mapping.role_presence_rules
    ) != len(required):
        _refuse("5a")
    for rule in mapping.role_presence_rules:
        if required[rule.quantity] != rule.parameter_id:
            _refuse("5a")
        if not isinstance(rule.participation_type, ParticipationType) or any(
            value is not None and type(value) is not bool
            for value in (rule.instructor_status, rule.student_status)
        ):
            _refuse("5b")
        if (
            not rule.presence_description.strip()
            or rule.presence_semantics not in {"boolean_code", "probability"}
            or rule.repetition_scope not in {"per_event", "per_session"}
        ):
            _refuse("5c")
        presence = parameters[rule.presence_parameter_id]
        if rule.presence_semantics == "boolean_code":
            support = _numeric_support(presence)
            if support is None or not 0 <= support[0] <= support[1] <= 1:
                _refuse("5b")
        elif not _probability_support(presence):
            _refuse("5c")
        if (
            rule.instructor_status is None
            or rule.student_status is None
            or (rule.instructor_status and rule.student_status)
            or (
                rule.participation_type == ParticipationType.INSTRUCTOR
                and (not rule.instructor_status or rule.student_status)
            )
            or (
                rule.participation_type == ParticipationType.STUDENT
                and (not rule.student_status or rule.instructor_status)
            )
        ):
            _refuse("5d")
        status_sources = [
            source for source in mapping.derivations if source.operation == "assignment_status"
        ]
        if not status_sources:
            _refuse("1f")
        status_pairs = {
            (instructor, student)
            for source in status_sources
            for _, instructor, student in source.status_codes
        }
        if (rule.instructor_status, rule.student_status) not in status_pairs:
            _refuse("5e")


def _placement_checks(mapping: ExecutionMapping, parameters: dict[str, ParameterBinding]) -> None:
    rules = {rule.record_type: rule for rule in mapping.placement_rules}
    if set(rules) != set(TIME_RECORDS) or len(rules) != len(mapping.placement_rules):
        _refuse("6a")
    for rule in mapping.placement_rules:
        if rule.record_type == RecordType.MEMBER:
            complete = rule.start_parameter_id is not None and rule.end_parameter_id is not None
        else:
            complete = rule.offset_parameter_id is not None
            if rule.record_type != RecordType.EVENT:
                complete = complete and rule.duration_parameter_id is not None
            if rule.record_type in {RecordType.CAREER, RecordType.ASSIGNMENT, RecordType.TRAINING}:
                complete = complete and rule.partition_parameter_id is not None
            if rule.record_type in {RecordType.MISSION, RecordType.EVENT}:
                complete = complete and rule.mission_applicability_parameter_id is not None
            if rule.record_type in {RecordType.SESSION, RecordType.MISSION, RecordType.EVENT}:
                complete = complete and rule.count_parameter_id is not None
        if not complete:
            _refuse("6a")
        if rule.timezone != "UTC" or rule.clip or rule.resample or rule.containment != "inclusive":
            _refuse("6b")
        date_records = {
            RecordType.MEMBER,
            RecordType.CAREER,
            RecordType.ASSIGNMENT,
            RecordType.TRAINING,
        }
        if rule.unit is None:
            _refuse("3b")
        if rule.unit != ("days" if rule.record_type in date_records else "hours"):
            _refuse("6b")
        if rule.start_parameter_id is not None and rule.end_parameter_id is not None:
            start = parameters[rule.start_parameter_id].distribution
            end = parameters[rule.end_parameter_id].distribution
            if isinstance(start, FixedDistribution) and isinstance(end, FixedDistribution):
                if start.value > end.value:
                    _refuse("6b")
        if rule.duration_parameter_id is not None:
            duration = parameters[rule.duration_parameter_id].distribution
            if isinstance(duration, FixedDistribution) and duration.value < 0:
                _refuse("6b")
        if rule.shape != "binding_offsets" and rule.shape_parameter_id is None:
            _refuse("6c")
        if rule.count_parameter_id is not None:
            if rule.rounding is None:
                _refuse("3a")
            if rule.count_meaning is None or not rule.counting_interval:
                _refuse("3c")
            expected_counts = {
                RecordType.SESSION: CountMeaning.SESSIONS,
                RecordType.MISSION: CountMeaning.MISSIONS,
                RecordType.EVENT: CountMeaning.PHYSICAL_DISCHARGES,
            }
            if rule.count_meaning != expected_counts.get(rule.record_type):
                _refuse("3d")
        if rule.partition_parameter_id is not None and rule.rounding is None:
            _refuse("3a")
        if rule.mission_applicability_parameter_id is not None:
            support = _numeric_support(parameters[rule.mission_applicability_parameter_id])
            if support is None or not 0 <= support[0] <= support[1] <= 1:
                _refuse("6a")
        for parameter_id in _placement_ids(rule):
            if isinstance(parameters[parameter_id].distribution, CategoricalDistribution):
                _refuse("2b")


def _missingness_checks(
    config: SimulationConfig,
    mapping: ExecutionMapping,
    parameters: dict[str, ParameterBinding],
) -> None:
    targets = {target.target_quantity: target for target in mapping.missingness_targets}
    if len(targets) != len(mapping.missingness_targets) or len(
        {target.field_ref for target in mapping.missingness_targets}
    ) != len(mapping.missingness_targets):
        _refuse("7f")
    rules = {rule.target_quantity: rule for rule in config.missingness_configuration.rules}
    if len(rules) != len(config.missingness_configuration.rules):
        _refuse("7f")
    for target in mapping.missingness_targets:
        record, _, name = target.field_ref.partition(".")
        model = next((model for kind, model in RECORD_MODELS.items() if kind.value == record), None)
        if model is not None and (not name or name in ENGINE_FIELDS):
            _refuse("7b")
        if model is not None and name in model.model_fields:
            annotation = model.model_fields[name].annotation
            if not _contains(annotation, type(None)) or _contains(annotation, tuple):
                _refuse("7b")
        if target.field_ref not in MISSINGNESS_FIELDS:
            _refuse("7a")
        rule = rules.get(target.target_quantity)
        if rule is None:
            _refuse("7e")
        if rule.mechanism not in {
            MissingnessMechanism.MCAR,
            MissingnessMechanism.STRUCTURAL,
            MissingnessMechanism.NOT_COLLECTED,
        }:
            raise ValueError(
                f"missingness target {rule.target_quantity}: mechanism {rule.mechanism} refused"
            )
        if (rule.mechanism == MissingnessMechanism.MCAR) != (
            target.mcar_probability_parameter_id is not None
        ):
            _refuse("7e")
        if not target.latent_never_none and rule.mechanism != MissingnessMechanism.STRUCTURAL:
            _refuse("7c")
        if rule.mechanism == MissingnessMechanism.MCAR:
            probability = parameters.get(target.mcar_probability_parameter_id or "")
            if (
                probability is None
                or probability not in config.execution_bindings
                or probability.parameter_class != ParameterClass.SCENARIO_ASSUMPTION
                or not isinstance(probability.distribution, FixedDistribution)
                or not 0 <= probability.distribution.value <= 1
                or rule.scenario_assumption_id is None
                or rule.scenario_assumption_id not in probability.scenario_assumption_ids
            ):
                _refuse("7d")
        if rule.condition_quantity_ids:
            _refuse("7g")
    supported = {
        MissingnessMechanism.MCAR,
        MissingnessMechanism.STRUCTURAL,
        MissingnessMechanism.NOT_COLLECTED,
    }
    if not targets or not any(rule.mechanism in supported for rule in rules.values()):
        _refuse("7h")
    if set(rules) != set(targets):
        _refuse("7h")
    for rule in rules.values():
        if rule.mechanism not in supported:
            raise ValueError(
                f"missingness target {rule.target_quantity}: mechanism {rule.mechanism} refused"
            )


def _union(bindings: Iterable[ParameterBinding], field: str) -> set[str]:
    return {value for binding in bindings for value in getattr(binding, field)}


def _at_or_below(kind: RecordType, origin: RecordType) -> bool:
    return tuple(RecordType).index(kind) >= tuple(RecordType).index(origin)


def _lineage_checks(
    config: SimulationConfig,
    mapping: ExecutionMapping,
    parameters: dict[str, ParameterBinding],
) -> None:
    lineage = {item.record_type: item for item in mapping.record_lineage}
    if set(lineage) != set(RecordType) or len(lineage) != len(mapping.record_lineage):
        _refuse("8a")
    needed: dict[RecordType, set[str]] = {kind: set() for kind in RecordType}
    for field in mapping.field_bindings:
        needed[field.record_type].add(field.parameter_id)
    for source in mapping.derivations:
        needed[source.record_type].update(source.parameter_ids)
    for placement in mapping.placement_rules:
        needed[placement.record_type].update(_placement_ids(placement))
    for role in mapping.role_presence_rules:
        needed[RecordType.EXPOSURE].update((role.parameter_id, role.presence_parameter_id))
    for target in mapping.missingness_targets:
        kind = RecordType(target.field_ref.split(".")[0])
        if target.mcar_probability_parameter_id is not None:
            needed[kind].add(target.mcar_probability_parameter_id)
    # Descendants retain their ancestors' placement/selection lineage. Event rows
    # include optional mission choices too, since applicability is a driving input.
    ancestors: set[str] = set()
    for kind in RecordType:
        ancestors.update(needed[kind])
        record = lineage[kind]
        if (
            len(record.parameter_ids) != len(set(record.parameter_ids))
            or not ancestors <= set(record.parameter_ids)
            or record.rng_stream != RECORD_STREAMS[kind]
        ):
            _refuse("8a")
        bound = [parameters[key] for key in record.parameter_ids]
        for dimension in config.uncertainty_configuration.dimensions:
            origins = {
                UncertaintyDimension.CAREER_DURATION: RecordType.CAREER,
                UncertaintyDimension.ASSIGNMENT_DURATION: RecordType.ASSIGNMENT,
                UncertaintyDimension.TRAINING_EVENT_FREQUENCY: RecordType.TRAINING,
                UncertaintyDimension.ROUNDS_PER_EVENT: RecordType.EVENT,
                UncertaintyDimension.PARTICIPATION: RecordType.EXPOSURE,
                UncertaintyDimension.ROLE: RecordType.ASSIGNMENT,
                UncertaintyDimension.MISSING_YEARS: RecordType.MEMBER,
                UncertaintyDimension.SOURCE_SUPPORT: RecordType.MEMBER,
            }
            if not _at_or_below(kind, origins[dimension.dimension]):
                continue
            if not set(dimension.scenario_assumption_ids) <= _union(
                bound, "scenario_assumption_ids"
            ):
                _refuse("8a")
            if not set(dimension.uncertainty_types) <= _union(bound, "uncertainty_types"):
                _refuse("8a")
        for dependency in _all_dependencies(config):
            dependency_origins = {
                "training-configuration": RecordType.TRAINING,
                "weapon-platform-eligibility": RecordType.ASSIGNMENT,
                "training-context": RecordType.ASSIGNMENT,
                "training-event-frequency": RecordType.SESSION,
                "rounds-per-event": RecordType.EVENT,
                "participation": RecordType.EXPOSURE,
            }
            origin = dependency_origins.get(dependency.output_quantity)
            if origin is None:
                _refuse("8a")
            if not _at_or_below(kind, origin):
                continue
            if (
                dependency.scenario_assumption_id is not None
                and dependency.scenario_assumption_id
                not in _union(bound, "scenario_assumption_ids")
            ) or not set(dependency.uncertainty_types) <= _union(bound, "uncertainty_types"):
                _refuse("8a")
        for rule in config.missingness_configuration.rules:
            target = next(
                item
                for item in mapping.missingness_targets
                if item.target_quantity == rule.target_quantity
            )
            if not _at_or_below(kind, RecordType(target.field_ref.split(".")[0])):
                continue
            if rule.scenario_assumption_id is not None and (
                rule.scenario_assumption_id not in _union(bound, "scenario_assumption_ids")
            ):
                _refuse("8a")
    order = mapping.evaluation_order
    required = ["sample", *(kind.value for kind in RecordType), "place", "mask"]
    if len(order) != len(set(order)) or not set(required) <= set(order):
        _refuse("7i")
    positions = [order.index(operation) for operation in required]
    if positions != sorted(positions):
        _refuse("7j")


def _field_reference(reference: str) -> tuple[RecordType, str]:
    record_name, _, field_name = reference.partition(".")
    for kind, model in RECORD_MODELS.items():
        if kind.value == record_name and field_name in model.model_fields:
            return kind, field_name
    _refuse("1d")


def declared_field_sources(mapping: ExecutionMapping) -> dict[str, tuple[str, ...]]:
    """Latent writers only: masks modify a value and never supply its source."""
    writers: dict[str, list[str]] = {}

    def add(reference: str, writer: str) -> None:
        writers.setdefault(reference, []).append(writer)

    for index, field in enumerate(mapping.field_bindings):
        add(field.field_ref, f"field_binding:{index}")
    for index, placement in enumerate(mapping.placement_rules):
        for name in PLACEMENT_FIELDS.get(placement.record_type, ()):
            add(f"{placement.record_type.value}.{name}", f"placement:{index}")
    if mapping.role_presence_rules:
        # Three conditional association rules are one role/presence writer,
        # rather than three competing writers of the same association fields.
        add("ParticipantExposure.role", "role_presence")
        add("ParticipantExposure.participation_type", "role_presence")
    for index, source in enumerate(mapping.derivations):
        add(source.field_ref, f"derivation:{index}")
        if source.operation == "assignment_status":
            add("AssignmentEpisode.student_status", f"derivation:{index}")
    return {reference: tuple(values) for reference, values in writers.items()}


def _field_source_coverage(mapping: ExecutionMapping) -> None:
    writers = declared_field_sources(mapping)
    for kind, model in RECORD_MODELS.items():
        for name in model.model_fields:
            if name not in ENGINE_FIELDS and len(writers.get(f"{kind.value}.{name}", ())) != 1:
                _refuse("1f")


def _derivation_checks(
    config: SimulationConfig,
    mapping: ExecutionMapping,
    parameters: dict[str, ParameterBinding],
) -> None:
    for source in mapping.derivations:
        kind, name = _field_reference(source.field_ref)
        if name in ENGINE_FIELDS or name in TIME_FIELDS:
            _refuse("1e")
        if source.field_ref in DERIVATION_ONLY and (
            source.operation != DERIVATION_ONLY[source.field_ref]
        ):
            _refuse("1e")
        if source.selector_parameter_id is not None and (
            source.selector_parameter_id not in source.parameter_ids
        ):
            _refuse("1c")
        if source.operation in {
            "component_selection",
            "assignment_status",
            "identifier_codebook",
            "eligibility_platform",
            "assignment_weapon",
        }:
            if source.selector_parameter_id is None:
                _refuse("1f")
        if source.operation == "component_selection":
            if source.field_ref != "CareerEpisode.component":
                _refuse("2a")
            required = {
                row.population_weight.parameter_id
                for row in config.population_configuration.components
            }
            required.add(config.career_configuration.branch_component_transition.parameter_id)
            if not required <= set(source.parameter_ids) or (
                source.selector_parameter_id
                != config.career_configuration.branch_component_transition.parameter_id
            ):
                _refuse("1f")
            codes = tuple(code for code, _ in source.component_codes)
            support = _numeric_support(parameters[source.selector_parameter_id or ""])
            if support is None or len(codes) != len(set(codes)):
                _refuse("4c")
            if len({code for code in codes if support[0] <= code <= support[1]}) != (
                support[1] - support[0] + 1
            ):
                _refuse("4c")
            if not {value for _, value in source.component_codes} <= {
                row.component for row in config.population_configuration.components
            }:
                _refuse("2a")
        elif source.operation == "assignment_status":
            if source.field_ref != "AssignmentEpisode.instructor_status":
                _refuse("2a")
            codes = tuple(code for code, _, _ in source.status_codes)
            support = _numeric_support(parameters[source.selector_parameter_id or ""])
            if support is None or len(codes) != len(set(codes)):
                _refuse("4c")
            if len({code for code in codes if support[0] <= code <= support[1]}) != (
                support[1] - support[0] + 1
            ):
                _refuse("4c")
            for _, instructor, student in source.status_codes:
                if type(instructor) is not bool or type(student) is not bool:
                    _refuse("5b")
                if instructor and student:
                    _refuse("5d")
        elif source.operation == "identifier_codebook":
            if source.codebook_field_ref != source.field_ref:
                _refuse("4a")
        elif source.operation == "branch_from_component":
            if source.field_ref != "CareerEpisode.branch" or (
                source.source_field_ref != "CareerEpisode.component"
            ):
                _refuse("2a")
        elif source.operation == "eligibility_weapons":
            if (
                source.field_ref != "AssignmentEpisode.weapon_system_ids"
                or source.source_field_ref != "AssignmentEpisode.occupation_id"
            ):
                _refuse("1f")
        elif source.operation in {"eligibility_platform", "assignment_weapon"}:
            expected = {
                "eligibility_platform": (
                    "AssignmentEpisode.platform_id",
                    "AssignmentEpisode.occupation_id",
                ),
                "assignment_weapon": (
                    "FiringEvent.weapon_system_id",
                    "AssignmentEpisode.weapon_system_ids",
                ),
            }
            target, parent = expected[source.operation]
            if source.field_ref != target or source.source_field_ref != parent:
                _refuse("1f")
            if source.codebook_field_ref != target:
                _refuse("4a")
        elif source.operation == "carry_forward":
            if source.source_field_ref is None:
                _refuse("1f")
            parent_kind, parent_name = _field_reference(source.source_field_ref)
            if not _at_or_below(kind, parent_kind) or source.source_field_ref == source.field_ref:
                _refuse("1f")
            target_annotation = RECORD_MODELS[kind].model_fields[name].annotation
            parent_annotation = RECORD_MODELS[parent_kind].model_fields[parent_name].annotation
            if (
                name != parent_name
                or _contains(parent_annotation, tuple)
                or _contains(parent_annotation, list)
                or _contains(target_annotation, tuple)
                or _contains(target_annotation, list)
                or not _contains(target_annotation, str)
                or not _contains(parent_annotation, str)
            ):
                _refuse("2a")
        else:
            _refuse("1f")


def _quantity_routes(config: SimulationConfig, mapping: ExecutionMapping) -> None:
    frequency_ids = {
        row.training_event_frequency.parameter_id
        for row in config.training_configuration.component_configurations
    }
    rounds_ids = {
        row.rounds_per_event.parameter_id
        for row in config.training_configuration.component_configurations
    }
    restricted = frequency_ids | rounds_ids
    non_count_refs = {field.parameter_id for field in mapping.field_bindings}
    non_count_refs.update(key for source in mapping.derivations for key in source.parameter_ids)
    non_count_refs.update(
        key
        for rule in mapping.role_presence_rules
        for key in (rule.parameter_id, rule.presence_parameter_id)
    )
    for rule in mapping.placement_rules:
        non_count_refs.update(
            value
            for name in PLACEMENT_REFERENCES
            if name != "count_parameter_id" and isinstance(value := getattr(rule, name), str)
        )
        if rule.count_parameter_id in frequency_ids and not (
            rule.record_type == RecordType.SESSION and rule.count_meaning == CountMeaning.SESSIONS
        ):
            _refuse("3d")
        if rule.count_parameter_id in rounds_ids and not (
            rule.record_type == RecordType.EVENT
            and rule.count_meaning == CountMeaning.PHYSICAL_DISCHARGES
        ):
            _refuse("3d")
    if non_count_refs & restricted:
        _refuse("3d")


def validate_execution_mapping(
    config: SimulationConfig,
    scenario: ScenarioDefinition,
    mapping: ExecutionMapping,
) -> None:
    """Refuse the first contract violation before any RNG or hierarchy row."""
    from .fictional import validate_fictional_scenario

    try:
        validate_fictional_scenario(config, scenario)
    except ValueError as error:
        raise ValueError(MESSAGES["9b"]) from error
    if not isinstance(mapping, ExecutionMapping):
        _refuse("9b")
    if mapping.execution_generator_version != EXECUTION_GENERATOR_VERSION:
        _refuse("9b")
    if (mapping.scenario_id, mapping.scenario_version) != (
        scenario.scenario_id,
        scenario.scenario_version,
    ):
        _refuse("9a")
    configured = {
        binding.parameter_id: binding for binding in configured_parameter_bindings(config)
    }
    intersection = set(configured) & {binding.parameter_id for binding in scenario.parameters}
    referenced = {field.parameter_id for field in mapping.field_bindings}
    referenced.update(key for rule in mapping.placement_rules for key in _placement_ids(rule))
    referenced.update(
        key
        for role in mapping.role_presence_rules
        for key in (role.parameter_id, role.presence_parameter_id)
    )
    referenced.update(
        target.mcar_probability_parameter_id
        for target in mapping.missingness_targets
        if target.mcar_probability_parameter_id is not None
    )
    referenced.update(key for item in mapping.record_lineage for key in item.parameter_ids)
    referenced.update(key for source in mapping.derivations for key in source.parameter_ids)
    referenced.update(
        source.selector_parameter_id
        for source in mapping.derivations
        if source.selector_parameter_id is not None
    )
    if not referenced <= intersection:
        _refuse("1c")
    validate_configuration_references(
        config,
        scenario,
        prior_definition_ids=set(),
        prior_classifications={},
        evidence_ids=set(),
        sme_estimate_ids=set(),
    )
    # Derive consumption separately: lineage references are citations, not mappings.
    consumption = {field.parameter_id for field in mapping.field_bindings}
    consumption.update(key for rule in mapping.placement_rules for key in _placement_ids(rule))
    consumption.update(
        key
        for role in mapping.role_presence_rules
        for key in (role.parameter_id, role.presence_parameter_id)
    )
    consumption.update(
        target.mcar_probability_parameter_id
        for target in mapping.missingness_targets
        if target.mcar_probability_parameter_id is not None
    )
    consumption.update(key for source in mapping.derivations for key in source.parameter_ids)
    if not set(configured) <= consumption:
        _refuse("1a")
    for field in mapping.field_bindings:
        if field.field_name not in RECORD_MODELS[field.record_type].model_fields:
            _refuse("1d")
        if (
            field.field_name in ENGINE_FIELDS
            or field.field_name in TIME_FIELDS
            or field.field_ref in DERIVATION_ONLY
        ):
            _refuse("1e")
        _field_checks(field, configured[field.parameter_id])
    _quantity_routes(config, mapping)
    _derivation_checks(config, mapping, configured)
    if any(len(values) > 1 for values in declared_field_sources(mapping).values()):
        _refuse("1b")
    _codebook_checks(mapping, configured)
    _role_checks(config, mapping, configured)
    _placement_checks(mapping, configured)
    _missingness_checks(config, mapping, configured)
    _field_source_coverage(mapping)
    _lineage_checks(config, mapping, configured)
