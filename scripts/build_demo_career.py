"""Build one FICTIONAL DEMO career; seed curation is an explicit development step."""

import argparse
import json
from collections import Counter
from datetime import date
from itertools import pairwise
from pathlib import Path

from blastbridge.models.core import ResearchModel
from blastbridge.simulation import engine
from blastbridge.simulation.execution import RECORD_STREAMS
from blastbridge.simulation.fictional import FictionalGenerationApproval
from blastbridge.simulation.models import (
    REQUIRED_DEPENDENCY_PAIRS,
    AssignmentConfiguration,
    CareerConfiguration,
    Codebook,
    Component,
    ComponentPopulationConfiguration,
    ComponentTrainingConfiguration,
    DependencyMode,
    DependencySpecification,
    EligibilityRelation,
    ExecutionMapping,
    FieldBinding,
    FieldDerivation,
    MissingnessConfiguration,
    MissingnessRule,
    MissingnessTarget,
    ParameterBinding,
    ParticipationConfiguration,
    ParticipationType,
    PlacementRule,
    PopulationConfiguration,
    RecordLineage,
    RecordType,
    RolePresenceRule,
    ScenarioAssumption,
    ScenarioDefinition,
    ScenarioLabel,
    SimulationConfig,
    SyntheticCareerDataset,
    TrainingConfiguration,
    UncertaintyConfiguration,
    UncertaintyDimension,
    UncertaintyLineage,
    UncertaintyType,
    configured_parameter_bindings,
)
from blastbridge.simulation.outputs import SyntheticOutput
from blastbridge.simulation.persistence import save_career

# Frozen 2026-10-16 by one-time curation (first passing seed in 0..999),
# selected for demo readability.
DEMO_SEED: int | None = 0
_DEMO_DIRECTORY = Path(__file__).resolve().parents[1] / "examples" / "fictional" / "demo-career"
_ASSUMPTION = "test-demo-assumption"
_QUALITY_CONDITIONS = (
    "exactly-one-member",
    "assignment-spans",
    "training-spans",
    "missions-and-event-ownership",
    "participation-types",
    "missingness-target",
)


def _pid(name: str) -> str:
    return f"test-demo-{name}"


def _binding(name: str, distribution: dict[str, object]) -> ParameterBinding:
    return ParameterBinding.model_validate(
        {
            "parameter_id": _pid(name),
            "distribution": distribution,
            "parameter_class": "scenario_assumption",
            "prior_definition_ids": (),
            "evidence_ids": (),
            "sme_estimate_ids": (),
            "scenario_assumption_ids": (_ASSUMPTION,),
            "uncertainty_types": ("aleatory",),
        }
    )


def build_inputs(
    master_seed: int,
) -> tuple[SimulationConfig, ScenarioDefinition, FictionalGenerationApproval, ExecutionMapping]:
    """Explicit demo-only assumptions; none are estimates of real service histories."""
    fixed = {
        "population-weight": 1,
        "career-duration": 4000,
        "career-count": 1,
        "component-selector": 2,
        "assignment-duration": 600,
        "occupation-selector": 2,
        "platform-selector": 2,
        "context-selector": 2,
        "session-count": 2,
        "event-count": 4,
        "role": 2,
        "nearby": 2,
        "instructor": 2,
        "zero": 0,
        "service-end": 4700,
        "one": 1,
        "assignment-count": 2,
        "training-count": 2,
        "training-duration": 100,
        "session-duration": 6,
        "mission-duration": 4,
        "unit-selector": 2,
        "crew-selector": 2,
        "cycle-selector": 2,
        "weapon-selector": 2,
        "family-selector": 2,
        "ammunition-selector": 2,
    }
    parameters = {
        name: _binding(name, {"kind": "fixed", "value": value}) for name, value in fixed.items()
    }
    for name, lower, upper in (
        ("assignment-offset", 0, 3000),
        ("training-offset", 0, 450),
        ("session-offset", 0, 2000),
        ("event-offset", 0, 4),
        ("status-selector", 0, 2),
        ("event-applicability", 0, 1),
    ):
        parameters[name] = _binding(
            name,
            {
                "kind": "discrete_uniform",
                "lower": lower,
                "upper": upper,
            },
        )
    dependencies = tuple(
        DependencySpecification(
            dependency_id=_pid(f"dependency-{ordinal:02}"),
            input_quantities=(source,),
            output_quantity=target,
            mode=DependencyMode.INDEPENDENT_ASSUMPTION,
            rule_description="TEST FICTIONAL DEMO: sample the output binding independently.",
            scenario_assumption_id=_ASSUMPTION,
            uncertainty_types=(UncertaintyType.ALEATORY,),
        )
        for ordinal, (source, target) in enumerate(REQUIRED_DEPENDENCY_PAIRS)
    )
    required = {
        "population-weight",
        "career-duration",
        "career-count",
        "component-selector",
        "assignment-duration",
        "occupation-selector",
        "platform-selector",
        "context-selector",
        "session-count",
        "event-count",
        "role",
        "nearby",
        "instructor",
    }
    config = SimulationConfig(
        simulation_id="test-demo-simulation",
        simulation_version="0.5.0",
        scenario_id="test-demo-scenario",
        scenario_version="0.5.0",
        generator_version="0.5.0",
        rng_algorithm="python-mt19937-random-v1",
        master_seed=master_seed,
        population_size=1,
        simulation_start_date=date(2012, 1, 1),
        simulation_end_date=date(2024, 12, 31),
        reference_dataset_version="0.1.0",
        training_tempo_dataset_version="0.2.0",
        prior_design_version="0.3.0",
        population_configuration=PopulationConfiguration(
            population_scope="TEST FICTIONAL DEMO: one invented member.",
            components=(
                ComponentPopulationConfiguration(
                    component=Component.ARMY_ACTIVE,
                    population_weight=parameters["population-weight"],
                ),
            ),
        ),
        career_configuration=CareerConfiguration(
            career_duration=parameters["career-duration"],
            career_episode_count=parameters["career-count"],
            branch_component_transition=parameters["component-selector"],
            dependencies=(),
        ),
        assignment_configuration=AssignmentConfiguration(
            assignment_duration=parameters["assignment-duration"],
            occupation_selection=parameters["occupation-selector"],
            weapon_platform_eligibility=parameters["platform-selector"],
            dependencies=(),
        ),
        training_configuration=TrainingConfiguration(
            cycle_context=parameters["context-selector"],
            dependencies=dependencies,
            component_configurations=(
                ComponentTrainingConfiguration(
                    component=Component.ARMY_ACTIVE,
                    training_event_frequency=parameters["session-count"],
                    rounds_per_event=parameters["event-count"],
                    dependencies=(),
                ),
            ),
        ),
        participation_configuration=ParticipationConfiguration(
            role_participation=parameters["role"],
            nearby_participation=parameters["nearby"],
            instructor_repeated_presence=parameters["instructor"],
            dependencies=(),
        ),
        missingness_configuration=MissingnessConfiguration(
            rules=(
                MissingnessRule(
                    target_quantity="platform-id",
                    mechanism="structural_missing",
                    condition_quantity_ids=(),
                    scenario_assumption_id=None,
                    rationale="TEST FICTIONAL DEMO: platform is structurally not applicable.",
                ),
            )
        ),
        uncertainty_configuration=UncertaintyConfiguration(
            dimensions=tuple(
                UncertaintyLineage(
                    dimension=dimension,
                    uncertainty_types=(UncertaintyType.ALEATORY,),
                    prior_definition_ids=(),
                    evidence_ids=(),
                    sme_estimate_ids=(),
                    scenario_assumption_ids=(_ASSUMPTION,),
                    rationale="TEST FICTIONAL DEMO assumption labels only.",
                )
                for dimension in UncertaintyDimension
            )
        ),
        execution_bindings=tuple(
            value for name, value in parameters.items() if name not in required
        ),
    )
    scenario = ScenarioDefinition(
        scenario_id=config.scenario_id,
        scenario_version=config.scenario_version,
        label=ScenarioLabel.CUSTOM,
        purpose="TEST FICTIONAL DEMO for software demonstration only.",
        population_scope=config.population_configuration.population_scope,
        prior_definition_ids=(),
        evidence_constraint_ids=(),
        sme_estimate_ids=(),
        supporting_evidence_ids=(),
        assumptions=(
            ScenarioAssumption(
                assumption_id=_ASSUMPTION,
                statement=(
                    "TEST FICTIONAL DEMO: every value is invented "
                    "for software demonstration."
                ),
                scope="No actual member, unit, deployment or clinical record is represented.",
            ),
        ),
        parameters=tuple(parameters.values()),
        dependency_ids=tuple(d.dependency_id for d in dependencies),
    )
    declarations = (
        (RecordType.CAREER, "occupation_id", "occupation-selector", "test-demo-occupation"),
        (RecordType.ASSIGNMENT, "training_context", "context-selector", "test-demo-context"),
        (RecordType.ASSIGNMENT, "unit_type", "unit-selector", "test-demo-unit"),
        (RecordType.ASSIGNMENT, "crew_role", "crew-selector", "test-demo-crew-role"),
        (
            RecordType.ASSIGNMENT,
            "deployment_or_training_cycle_status",
            "cycle-selector",
            "test-demo-cycle",
        ),
        (
            RecordType.EVENT,
            "ammunition_configuration_id",
            "ammunition-selector",
            "test-demo-ammunition",
        ),
    )
    fields = tuple(
        FieldBinding(
            parameter_id=_pid(parameter),
            record_type=kind,
            field_name=field,
            value_type="identifier",
        )
        for kind, field, parameter, _ in declarations
    )
    books = tuple(
        Codebook(
            field_ref=f"{kind.value}.{field}",
            numeric_codes=((2, identifier),),
        )
        for kind, field, _, identifier in declarations
    ) + (
        Codebook(
            field_ref="AssignmentEpisode.platform_id", numeric_codes=((2, "test-demo-platform"),)
        ),
        Codebook(
            field_ref="FiringEvent.weapon_system_id", numeric_codes=((2, "test-demo-weapon"),)
        ),
        Codebook(field_ref="FiringEvent.weapon_family", numeric_codes=((2, "test-demo-family"),)),
    )
    derivations = (
        FieldDerivation(
            record_type=RecordType.CAREER,
            field_name="component",
            operation="component_selection",
            parameter_ids=(_pid("population-weight"), _pid("component-selector")),
            selector_parameter_id=_pid("component-selector"),
            component_codes=((2, Component.ARMY_ACTIVE),),
        ),
        FieldDerivation(
            record_type=RecordType.CAREER,
            field_name="branch",
            operation="branch_from_component",
            parameter_ids=(_pid("population-weight"), _pid("component-selector")),
            source_field_ref="CareerEpisode.component",
        ),
        FieldDerivation(
            record_type=RecordType.ASSIGNMENT,
            field_name="occupation_id",
            operation="carry_forward",
            parameter_ids=(_pid("occupation-selector"),),
            source_field_ref="CareerEpisode.occupation_id",
        ),
        FieldDerivation(
            record_type=RecordType.ASSIGNMENT,
            field_name="weapon_system_ids",
            operation="eligibility_weapons",
            parameter_ids=(_pid("occupation-selector"),),
            source_field_ref="AssignmentEpisode.occupation_id",
        ),
        FieldDerivation(
            record_type=RecordType.ASSIGNMENT,
            field_name="platform_id",
            operation="eligibility_platform",
            parameter_ids=(_pid("platform-selector"),),
            selector_parameter_id=_pid("platform-selector"),
            source_field_ref="AssignmentEpisode.occupation_id",
            codebook_field_ref="AssignmentEpisode.platform_id",
        ),
        FieldDerivation(
            record_type=RecordType.ASSIGNMENT,
            field_name="instructor_status",
            operation="assignment_status",
            parameter_ids=(_pid("status-selector"),),
            selector_parameter_id=_pid("status-selector"),
            status_codes=((0, False, False), (1, True, False), (2, False, True)),
        ),
        FieldDerivation(
            record_type=RecordType.TRAINING,
            field_name="training_context",
            operation="carry_forward",
            parameter_ids=(_pid("context-selector"),),
            source_field_ref="AssignmentEpisode.training_context",
        ),
        FieldDerivation(
            record_type=RecordType.EVENT,
            field_name="training_context",
            operation="carry_forward",
            parameter_ids=(_pid("context-selector"),),
            source_field_ref="AssignmentEpisode.training_context",
        ),
        FieldDerivation(
            record_type=RecordType.EVENT,
            field_name="weapon_system_id",
            operation="assignment_weapon",
            parameter_ids=(_pid("weapon-selector"),),
            selector_parameter_id=_pid("weapon-selector"),
            source_field_ref="AssignmentEpisode.weapon_system_ids",
            codebook_field_ref="FiringEvent.weapon_system_id",
        ),
        FieldDerivation(
            record_type=RecordType.EVENT,
            field_name="weapon_family",
            operation="identifier_codebook",
            parameter_ids=(_pid("family-selector"),),
            selector_parameter_id=_pid("family-selector"),
            codebook_field_ref="FiringEvent.weapon_family",
        ),
    )
    roles = tuple(
        RolePresenceRule(
            quantity=quantity,
            parameter_id=_pid(parameter),
            role_id=role,
            participation_type=participation_type,
            presence_parameter_id=_pid("one"),
            presence_semantics="boolean_code",
            presence_description="TEST FICTIONAL DEMO: 1 means present.",
            repetition_scope="per_event",
            instructor_status=instructor,
            student_status=student,
        )
        for quantity, parameter, role, participation_type, instructor, student in (
            (
                "role_participation",
                "role",
                "test-demo-firer",
                ParticipationType.FIRED_WEAPON,
                False,
                False,
            ),
            (
                "nearby_participation",
                "nearby",
                "test-demo-student",
                ParticipationType.STUDENT,
                False,
                True,
            ),
            (
                "instructor_repeated_presence",
                "instructor",
                "test-demo-instructor",
                ParticipationType.INSTRUCTOR,
                True,
                False,
            ),
        )
    )
    placement_specs = (
        (
            RecordType.MEMBER,
            "days",
            {"start_parameter_id": "zero", "end_parameter_id": "service-end"},
        ),
        (
            RecordType.CAREER,
            "days",
            {
                "offset_parameter_id": "zero",
                "duration_parameter_id": "career-duration",
                "partition_parameter_id": "career-count",
            },
        ),
        (
            RecordType.ASSIGNMENT,
            "days",
            {
                "offset_parameter_id": "assignment-offset",
                "duration_parameter_id": "assignment-duration",
                "partition_parameter_id": "assignment-count",
            },
        ),
        (
            RecordType.TRAINING,
            "days",
            {
                "offset_parameter_id": "training-offset",
                "duration_parameter_id": "training-duration",
                "partition_parameter_id": "training-count",
            },
        ),
        (
            RecordType.SESSION,
            "hours",
            {
                "offset_parameter_id": "session-offset",
                "duration_parameter_id": "session-duration",
                "count_parameter_id": "session-count",
            },
        ),
        (
            RecordType.MISSION,
            "hours",
            {
                "offset_parameter_id": "zero",
                "duration_parameter_id": "mission-duration",
                "count_parameter_id": "one",
                "mission_applicability_parameter_id": "one",
            },
        ),
        (
            RecordType.EVENT,
            "hours",
            {
                "offset_parameter_id": "event-offset",
                "count_parameter_id": "event-count",
                "mission_applicability_parameter_id": "event-applicability",
            },
        ),
    )
    count_specs = {
        RecordType.SESSION: ("sessions", "per_training_period"),
        RecordType.MISSION: ("missions", "per_session"),
        RecordType.EVENT: ("physical_discharges", "per_session"),
    }
    placements = []
    for kind, unit, references in placement_specs:
        data = {
            "record_type": kind,
            "unit": unit,
            "timezone": "UTC",
            "shape": "binding_offsets",
            "containment": "inclusive",
            "clip": False,
            "resample": False,
            "rounding": "reject",
            **{field: _pid(parameter) for field, parameter in references.items()},
        }
        if kind in count_specs:
            meaning, interval = count_specs[kind]
            data.update(count_meaning=meaning, counting_interval=interval)
        placements.append(PlacementRule.model_validate(data))
    ids = tuple(sorted(p.parameter_id for p in configured_parameter_bindings(config)))
    mapping = ExecutionMapping(
        mapping_id="test-demo-mapping",
        mapping_version="0.5.0",
        execution_generator_version="0.5.0",
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.scenario_version,
        field_bindings=fields,
        codebooks=books,
        derivations=derivations,
        eligibility=(
            EligibilityRelation(
                occupation_id="test-demo-occupation",
                eligible_weapon_ids=("test-demo-weapon",),
                eligible_platform_ids=("test-demo-platform",),
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
                record_type=kind,
                parameter_ids=ids,
                rng_stream=RECORD_STREAMS[kind],
            )
            for kind in RecordType
        ),
        evaluation_order=("sample", *(kind.value for kind in RecordType), "place", "mask"),
    )
    approval = FictionalGenerationApproval(
        scenario_id=scenario.scenario_id,
        approved_scenario_version=scenario.scenario_version,
        population_scope=scenario.population_scope,
        simulation_purpose=scenario.purpose,
        fictional_acknowledgement=True,
    )
    return config, scenario, approval, mapping


def _overlap(spans: list[tuple[date, date]]) -> bool:
    ordered = sorted(spans)
    return any(right[0] <= left[1] for left, right in pairwise(ordered))


def demo_quality(dataset: SyntheticCareerDataset) -> list[str]:
    """Return failed readability conditions; this is not population validation."""
    failed = []
    if len(dataset.members) != 1:
        failed.append("exactly-one-member")
    if len(dataset.assignments) < 2 or _overlap(
        [(row.start_date, row.end_date) for row in dataset.assignments]
    ):
        failed.append("assignment-spans")
    if len(dataset.training_periods) < 4 or any(
        _overlap(
            [
                (p.start_date, p.end_date)
                for p in dataset.training_periods
                if p.assignment_id == assignment.assignment_id
            ]
        )
        for assignment in dataset.assignments
    ):
        failed.append("training-spans")
    if (
        not dataset.firing_missions
        or not any(event.mission_id is None for event in dataset.firing_events)
        or not any(event.mission_id is not None for event in dataset.firing_events)
    ):
        failed.append("missions-and-event-ownership")
    if len({row.participation_type for row in dataset.participant_exposures}) < 2:
        failed.append("participation-types")
    if not any(row.platform_id is None for row in dataset.assignments):
        failed.append("missingness-target")
    return failed


def curate_demo_seed(max_seed: int = 999) -> int:
    """Development only: return the first readable seed without changing any engine rule."""
    failures: Counter[str] = Counter(dict.fromkeys(_QUALITY_CONDITIONS, 0))
    aborts: Counter[str] = Counter()
    for seed in range(max_seed + 1):
        try:
            dataset = engine.generate(*build_inputs(seed))
        except ValueError as error:
            reason = str(error)
            if reason.startswith("record path "):
                reason = reason.partition(": ")[2]
            aborts[f"ValueError: {reason.partition(':')[0]}"] += 1
            continue
        failed = demo_quality(dataset)
        if not failed:
            return seed
        failures.update(failed)
    raise SystemExit(
        "No demo seed passed curation. "
        + json.dumps(
            {
                "seeds_inspected": max(0, max_seed + 1),
                "failed_conditions": dict(failures),
                "aborted_seeds": sum(aborts.values()),
                "abort_reason_prefixes": dict(aborts),
            },
            sort_keys=True,
        )
    )


def _write_model(model: ResearchModel, path: Path) -> None:
    text = (
        json.dumps(
            json.loads(model.model_dump_json()),
            sort_keys=True,
            indent=2,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curate-seed", action="store_true", help="one-time development curation")
    args = parser.parse_args()
    if args.curate_seed:
        seed = curate_demo_seed()
        print(f"Selected seed {seed}. Freeze DEMO_SEED = {seed}, then regenerate normally.")
        return
    if DEMO_SEED is None:
        raise SystemExit(
            "DEMO_SEED is not frozen. Run python scripts/build_demo_career.py --curate-seed "
            "first, then freeze its selected seed in DEMO_SEED."
        )
    config, scenario, approval, mapping = build_inputs(DEMO_SEED)
    dataset = engine.generate(config, scenario, approval, mapping)
    failed = demo_quality(dataset)
    if failed:
        raise SystemExit(f"Frozen demo failed readability conditions: {', '.join(failed)}")
    _DEMO_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for name, model in (
        ("config", config),
        ("scenario", scenario),
        ("approval", approval),
        ("mapping", mapping),
    ):
        _write_model(model, _DEMO_DIRECTORY / f"{name}.json")
    save_career(
        SyntheticOutput(config=config, scenario=scenario, records=dataset),
        mapping,
        _DEMO_DIRECTORY / "career.json",
    )
    (_DEMO_DIRECTORY / "README.md").write_text(
        "# FICTIONAL DEMO career\n\n"
        "Every record is fictional. Exposure is not injury. This is a software demonstration.\n\n"
        "The seed was selected for demo readability. It is not statistically representative "
        "and carries no empirical or medical interpretation.\n\n"
        f"Frozen seed: `{DEMO_SEED}`. Generator: `0.5.0`; output schema: `0.4.0`.\n\n"
        "Regenerate with `python scripts/build_demo_career.py`. The normal path uses the "
        "frozen seed directly and performs no search.\n\n"
        "Curation is a one-time dev step: `python scripts/build_demo_career.py --curate-seed`. "
        "The selected seed is then frozen in the script.\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
