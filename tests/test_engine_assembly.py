"""Deterministic fictional assembly contracts; execution is owned by the orchestrator."""

import random
from collections import Counter
from hashlib import sha256

import pytest
from execution_mapping_fixtures import (
    assembly_fixture,
    assembly_missingness_fixture,
    execution_fixture,
    replace_parameter,
)

from blastbridge.simulation import distributions, engine
from blastbridge.simulation.execution import RECORD_STREAMS
from blastbridge.simulation.fictional import authorize_fictional_execution
from blastbridge.simulation.models import (
    Component,
    ComponentPopulationConfiguration,
    ExecutionRounding,
    MissingnessMechanism,
    ParameterClass,
    RecordType,
    RngStream,
    SyntheticCareerDataset,
    SyntheticEntityType,
    configured_parameter_bindings,
    stable_synthetic_id,
)
from blastbridge.simulation.outputs import SyntheticOutput
from blastbridge.simulation.rng import _fingerprint, child_rng, derive_seed, stream_seeds


def key(path, operation, parameter):
    return "|".join(f"{len(s)}:{s}" for s in (*map(str, path), operation, parameter))


def placements(mapping, kind, **updates):
    return mapping.model_copy(
        update={
            "placement_rules": tuple(
                rule.model_copy(update=updates) if rule.record_type == kind else rule
                for rule in mapping.placement_rules
            )
        }
    )


def roles(mapping, quantity, **updates):
    return mapping.model_copy(
        update={
            "role_presence_rules": tuple(
                rule.model_copy(update=updates) if rule.quantity == quantity else rule
                for rule in mapping.role_presence_rules
            )
        }
    )


def status(mapping, parameter="test-placement-zero"):
    return mapping.model_copy(
        update={
            "derivations": tuple(
                source.model_copy(
                    update={
                        "selector_parameter_id": parameter,
                        "parameter_ids": (parameter,),
                    }
                )
                if source.operation == "assignment_status"
                else source
                for source in mapping.derivations
            )
        }
    )


def fixed(config, scenario, parameter, value):
    return replace_parameter(config, scenario, parameter, {"kind": "fixed", "value": value})


def all_tables(dataset):
    return (
        (RecordType.MEMBER, dataset.members),
        (RecordType.CAREER, dataset.career_episodes),
        (RecordType.ASSIGNMENT, dataset.assignments),
        (RecordType.TRAINING, dataset.training_periods),
        (RecordType.SESSION, dataset.live_fire_sessions),
        (RecordType.MISSION, dataset.firing_missions),
        (RecordType.EVENT, dataset.firing_events),
        (RecordType.EXPOSURE, dataset.participant_exposures),
    )


@pytest.mark.parametrize("size", [1, 10])
def test_complete_validated_graph(size):
    config, scenario, approval, mapping = assembly_fixture(size)
    dataset = engine.generate(config, scenario, approval, mapping)
    assert SyntheticCareerDataset.model_validate(dataset.model_dump()) == dataset
    assert SyntheticOutput(config=config, scenario=scenario, records=dataset).records == dataset
    assert len(dataset.members) == size
    assert all(rows for _, rows in all_tables(dataset))
    assert any(event.mission_id is None for event in dataset.firing_events)
    assert any(event.mission_id is not None for event in dataset.firing_events)
    assert len({row.event_id for row in dataset.firing_events}) == len(dataset.firing_events)
    assert {row.event_id for row in dataset.participant_exposures} <= {
        row.event_id for row in dataset.firing_events
    }


@pytest.mark.slow
def test_ten_thousand_members():
    config, scenario, approval, mapping = assembly_fixture(10_000, event_count=2)
    dataset = engine.generate(config, scenario, approval, mapping)
    assert len(dataset.members) == 10_000
    assert len(dataset.firing_events) == 20_000
    assert SyntheticOutput(config=config, scenario=scenario, records=dataset).records == dataset


def test_repeat_seed_and_mapping_determinism():
    config, scenario, approval, mapping = assembly_fixture()
    original = engine.generate(config, scenario, approval, mapping).model_dump(mode="json")
    assert engine.generate(config, scenario, approval, mapping).model_dump(mode="json") == original
    seeded = config.model_copy(update={"master_seed": config.master_seed + 1})
    assert engine.generate(seeded, scenario, approval, mapping).model_dump(mode="json") != original
    revised = mapping.model_copy(update={"mapping_version": "0.5.1"})
    assert revised.fingerprint() != mapping.fingerprint()
    assert engine.generate(config, scenario, approval, revised).model_dump(mode="json") != original


def test_legacy_seed_bytes_and_rng_are_unchanged():
    args = (17, "0.4.0", "0.4.0", "test-fingerprint", RngStream.TRAINING, "test-entity")
    expected = 111879601812787733936075660678641710946513449952058856382809007711372056655621
    assert derive_seed(*args) == expected
    assert derive_seed(*args, execution_fingerprint=None) == expected
    fingerprint = "test-execution-fingerprint"
    payload = "\0".join(
        (
            "17",
            "0.4.0",
            "0.4.0",
            "test-fingerprint",
            "training",
            "test-entity",
            fingerprint,
        )
    )
    assert derive_seed(*args, execution_fingerprint=fingerprint) == int.from_bytes(
        sha256(payload.encode()).digest(), "big"
    )
    config, scenario, _, mapping = assembly_fixture()
    for stream, seed in stream_seeds(config, scenario, "test-entity").items():
        old_payload = "\0".join(
            (
                str(config.master_seed),
                config.generator_version,
                config.scenario_version,
                _fingerprint(config, scenario),
                stream.value,
                "test-entity",
            )
        )
        assert seed == int.from_bytes(sha256(old_payload.encode()).digest(), "big")
        old_rng = random.Random()
        old_rng.seed(seed, version=2)
        new_rng = child_rng(config, scenario, stream, "test-entity")
        assert [new_rng.random() for _ in range(4)] == [old_rng.random() for _ in range(4)]
        assert (
            stream_seeds(
                config, scenario, "test-entity", execution_fingerprint=mapping.fingerprint()
            )[stream]
            != seed
        )


@pytest.mark.parametrize(
    "mechanism", [MissingnessMechanism.STRUCTURAL, MissingnessMechanism.NOT_COLLECTED]
)
def test_deterministic_masks(mechanism, monkeypatch):
    original = engine.child_rng

    def observed(config, scenario, stream, entity_key, **kwargs):
        assert stream != RngStream.MISSINGNESS
        return original(config, scenario, stream, entity_key, **kwargs)

    monkeypatch.setattr(engine, "child_rng", observed)
    dataset = engine.generate(*assembly_missingness_fixture(mechanism))
    assert dataset.assignments
    assert all(row.platform_id is None for row in dataset.assignments)


@pytest.mark.parametrize("p", [0, 1])
def test_mcar_exactly_one_draw_per_occurrence_including_endpoints(p, monkeypatch):
    config, scenario, approval, mapping = assembly_missingness_fixture(MissingnessMechanism.MCAR, p)
    config = config.model_copy(update={"population_size": 2})
    inputs = config, scenario, approval, mapping
    original = engine.child_rng
    draws = Counter()
    creations = Counter()

    class Counting:
        def __init__(self, rng, entity_key):
            self.rng, self.entity_key = rng, entity_key

        def random(self):
            draws[self.entity_key] += 1
            return self.rng.random()

    def observed(config, scenario, stream, entity_key, **kwargs):
        assert kwargs["execution_fingerprint"] == inputs[3].fingerprint()
        rng = original(config, scenario, stream, entity_key, **kwargs)
        if stream == RngStream.MISSINGNESS:
            creations[entity_key] += 1
            return Counting(rng, entity_key)
        return rng

    monkeypatch.setattr(engine, "child_rng", observed)
    dataset = engine.generate(*inputs)
    assert len(draws) == len(creations) == len(dataset.assignments) == 2
    assert set(draws.values()) == set(creations.values()) == {1}
    assert all((row.platform_id is None) == bool(p) for row in dataset.assignments)
    expected_keys = [
        key((1, 1, 1), "mask", "platform-id"),
        key((2, 1, 1), "mask", "platform-id"),
    ]
    assert list(draws) == list(creations) == expected_keys
    assert [row.assignment_id for row in dataset.assignments] == [
        "SYN-ASSIGNMENT-000001",
        "SYN-ASSIGNMENT-000002",
    ]


def test_independent_bindings_use_own_distributions_and_reproducible_keys(monkeypatch):
    config, scenario, approval, mapping = assembly_fixture(event_count=3)
    for parameter in ("test-army-active-event-frequency", "test-army-active-rounds-per-event"):
        config, scenario = replace_parameter(
            config, scenario, parameter, {"kind": "discrete_uniform", "lower": 2, "upper": 4}
        )
    bound = {p.parameter_id: p for p in configured_parameter_bindings(config)}
    original_rng, original_sample = engine.child_rng, distributions.sample
    operations, samples = {}, Counter()

    def observed_rng(config, scenario, stream, entity_key, **kwargs):
        assert entity_key not in operations  # Every operation owns one RNG, never recreated.
        rng = original_rng(config, scenario, stream, entity_key, **kwargs)
        operations[entity_key] = (rng, stream)
        rng.test_entity_key = entity_key
        return rng

    def observed_sample(spec, rng):
        entity_key = rng.test_entity_key
        if "count:LiveFireSession" in entity_key:
            assert spec == bound["test-army-active-event-frequency"].distribution
            samples["sessions"] += 1
        if "count:FiringEvent" in entity_key:
            assert spec == bound["test-army-active-rounds-per-event"].distribution
            samples["events"] += 1
        return original_sample(spec, rng)

    monkeypatch.setattr(engine, "child_rng", observed_rng)
    monkeypatch.setattr(distributions, "sample", observed_sample)
    dataset = engine.generate(config, scenario, approval, mapping)
    session_parameter = "test-army-active-event-frequency"
    session_key = key((1, 1, 1, 1), "count:LiveFireSession", session_parameter)
    rng = original_rng(
        config,
        scenario,
        RngStream.TRAINING,
        session_key,
        execution_fingerprint=mapping.fingerprint(),
    )
    assert len(dataset.live_fire_sessions) == original_sample(
        bound[session_parameter].distribution, rng
    )
    event_parameter = "test-army-active-rounds-per-event"
    for ordinal, session in enumerate(dataset.live_fire_sessions, 1):
        event_key = key((1, 1, 1, 1, ordinal), "count:FiringEvent", event_parameter)
        rng = original_rng(
            config,
            scenario,
            RngStream.FIRING,
            event_key,
            execution_fingerprint=mapping.fingerprint(),
        )
        events = [
            event for event in dataset.firing_events if event.session_id == session.session_id
        ]
        assert len(events) == original_sample(bound[event_parameter].distribution, rng)
    assert samples == {"sessions": 1, "events": len(dataset.live_fire_sessions)}


@pytest.mark.parametrize("value,reason", [(-1, "negative value"), (1.25, "fractional value")])
def test_invalid_child_count_aborts(value, reason):
    config, scenario, approval, mapping = assembly_fixture()
    config, scenario = fixed(config, scenario, "test-career-episode-count", value)
    with pytest.raises(ValueError, match=rf"record path.*test-career-episode-count.*{reason}"):
        engine.generate(config, scenario, approval, mapping)


@pytest.mark.parametrize(
    "kind,reason",
    [
        (RecordType.CAREER, "CareerEpisode outside parent containment"),
        (RecordType.SESSION, "LiveFireSession outside parent containment"),
        (RecordType.EVENT, "event outside mission containment"),
    ],
)
def test_out_of_bounds_aborts(kind, reason):
    config, scenario, approval, mapping = assembly_fixture()
    if kind == RecordType.CAREER:
        config, scenario = fixed(config, scenario, "test-career-duration", 31)
    elif kind == RecordType.SESSION:
        mapping = placements(mapping, kind, duration_parameter_id="test-placement-end")
        config, scenario = fixed(config, scenario, "test-placement-end", 100)
    else:
        mapping = placements(
            mapping, RecordType.MISSION, duration_parameter_id="test-placement-zero"
        )
        mapping = placements(mapping, RecordType.EVENT, offset_parameter_id="test-placement-one")
        config, scenario = fixed(config, scenario, "test-assembly-event-applicability", 1)
    with pytest.raises(ValueError, match=rf"record path.*parameter.*{reason}"):
        engine.generate(config, scenario, approval, mapping)


@pytest.mark.parametrize("shape", ["uniform", "evenly_spaced", "midnight"])
def test_unsupported_shape_before_execution(shape, monkeypatch):
    config, scenario, approval, mapping = assembly_fixture()
    mapping = placements(
        mapping, RecordType.SESSION, shape=shape, shape_parameter_id="test-placement-one"
    )
    forbid_operations(monkeypatch)
    with pytest.raises(
        ValueError,
        match=f"placement shape {shape} for LiveFireSession: no executable algorithm in V5-2",
    ):
        engine.generate(config, scenario, approval, mapping)


def forbid_operations(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("preflight refusal reached execution")

    for name in (
        "child_rng",
        "SyntheticMember",
        "CareerEpisode",
        "AssignmentEpisode",
        "TrainingPeriod",
        "LiveFireSession",
        "FiringMission",
        "FiringEvent",
        "ParticipantExposure",
    ):
        monkeypatch.setattr(engine, name, unexpected)
    assert all(operation is unexpected for operation in engine._execution_operations())


def test_multiple_components_before_execution(monkeypatch):
    """S10 is an unreachable backstop: rule 1a requires every component binding
    to be consumed, but 3d restricts distinct frequency/rounds bindings to the
    single SESSION/EVENT count slots permitted by rule 6a (and MCAR rule 7d
    requires execution bindings, whose IDs cannot duplicate component bindings).
    """
    config, scenario, approval, mapping = assembly_fixture()
    population = config.population_configuration.components[0]
    training = config.training_configuration.component_configurations[0]
    config = config.model_copy(
        update={
            "population_configuration": config.population_configuration.model_copy(
                update={
                    "components": (
                        population,
                        ComponentPopulationConfiguration(
                            component=Component.ARMY_RESERVE,
                            population_weight=population.population_weight,
                        ),
                    ),
                }
            ),
            "training_configuration": config.training_configuration.model_copy(
                update={
                    "component_configurations": (
                        training,
                        training.model_copy(update={"component": Component.ARMY_RESERVE}),
                    ),
                }
            ),
        }
    )
    forbid_operations(monkeypatch)
    # Isolate this engine preflight addition: the mapping validator independently
    # rejects duplicate parameter IDs in this deliberately expanded configuration.
    with pytest.raises(
        ValueError,
        match="multiple population components: per-component placement selection undefined in V5-2",
    ):
        engine._preflight(config, mapping)


def test_multiple_missions_aborts():
    config, scenario, approval, mapping = assembly_fixture()
    mapping = placements(mapping, RecordType.MISSION, count_parameter_id="test-career-duration")
    with pytest.raises(
        ValueError,
        match="multiple missions per session: event-to-mission assignment undefined in V5-2",
    ):
        engine.generate(config, scenario, approval, mapping)


def test_event_applicability_without_mission_aborts():
    config, scenario, approval, mapping = assembly_fixture()
    mapping = placements(
        mapping, RecordType.MISSION, mission_applicability_parameter_id="test-placement-zero"
    )
    config, scenario = fixed(config, scenario, "test-assembly-event-applicability", 1)
    with pytest.raises(
        ValueError, match="record path.*parameter.*applicability requires a mission"
    ):
        engine.generate(config, scenario, approval, mapping)


def test_latent_none_guarantee_is_checked_before_mask(monkeypatch):
    inputs = assembly_missingness_fixture(MissingnessMechanism.MCAR)
    original = engine._Assembler.fields

    def latent_none(self, kind, path, row, ancestors):
        original(self, kind, path, row, ancestors)
        if kind == RecordType.ASSIGNMENT:
            row["platform_id"] = None

    monkeypatch.setattr(engine._Assembler, "fields", latent_none)
    with pytest.raises(
        ValueError, match="record path.*platform-id.*latent None in latent_never_none"
    ):
        engine.generate(*inputs)


@pytest.mark.parametrize(
    "semantics,value,reason",
    [
        ("boolean_code", 2, "boolean_code value.*outside"),
        ("probability", 1.5, "probability.*outside"),
    ],
)
def test_bad_presence_draw_aborts(semantics, value, reason, monkeypatch):
    config, scenario, approval, mapping = assembly_fixture()
    mapping = roles(mapping, "nearby_participation", presence_semantics=semantics)
    sample = distributions.sample

    def invalid(spec, rng):
        if getattr(rng, "test_presence", False):
            return value
        return sample(spec, rng)

    original = engine.child_rng

    def marked(config, scenario, stream, entity_key, **kwargs):
        rng = original(config, scenario, stream, entity_key, **kwargs)
        rng.test_presence = "presence:nearby_participation" in entity_key
        return rng

    monkeypatch.setattr(engine, "child_rng", marked)
    monkeypatch.setattr(distributions, "sample", invalid)
    with pytest.raises(ValueError, match=rf"record path.*test-placement-one.*{reason}"):
        engine.generate(config, scenario, approval, mapping)


@pytest.mark.parametrize("scope", ["per_event", "per_session"])
def test_copresent_rules_abort_and_name_all_conflicts(scope):
    config, scenario, approval, mapping = execution_fixture()
    mapping = status(mapping)
    config, scenario = fixed(config, scenario, "test-placement-probability", 1)
    mapping = roles(mapping, "role_participation", repetition_scope=scope)
    with pytest.raises(ValueError) as caught:
        engine.generate(config, scenario, approval, mapping)
    message = str(caught.value)
    assert (
        "multiple applicable role/presence rules present for member (1,) event (1, 1, 1, 1, 1, 1)"
    ) in message
    assert "role_participation/test-role-alpha/fired_weapon" in message
    assert "nearby_participation/test-role-alpha/nearby_crew" in message


def test_status_mismatch_never_draws_or_emits(monkeypatch):
    config, scenario, approval, mapping = assembly_fixture()
    original = engine.child_rng
    seen = []

    def observed(config, scenario, stream, entity_key, **kwargs):
        seen.append(entity_key)
        return original(config, scenario, stream, entity_key, **kwargs)

    monkeypatch.setattr(engine, "child_rng", observed)
    dataset = engine.generate(config, scenario, approval, mapping)
    assert not any("presence:instructor_repeated_presence" in operation for operation in seen)
    assert all(row.participation_type != "instructor" for row in dataset.participant_exposures)


def test_per_session_presence_reuses_one_decision(monkeypatch):
    config, scenario, approval, mapping = assembly_fixture()
    mapping = roles(mapping, "nearby_participation", repetition_scope="per_session")
    original = engine.child_rng
    seen = []

    def observed(config, scenario, stream, entity_key, **kwargs):
        if "presence:nearby_participation" in entity_key:
            seen.append(entity_key)
        return original(config, scenario, stream, entity_key, **kwargs)

    monkeypatch.setattr(engine, "child_rng", observed)
    dataset = engine.generate(config, scenario, approval, mapping)
    assert len(dataset.participant_exposures) == len(dataset.firing_events) == 12
    assert seen == [key((1, 1, 1, 1, 1), "presence:nearby_participation", "test-placement-one")]


def test_probability_uses_same_rng_and_events_can_have_different_roles(monkeypatch):
    config, scenario, approval, mapping = assembly_fixture()
    config, scenario = fixed(config, scenario, "test-placement-probability", 0.5)
    mapping = roles(
        mapping,
        "role_participation",
        presence_semantics="probability",
        presence_parameter_id="test-placement-probability",
    )
    mapping = roles(
        mapping,
        "nearby_participation",
        presence_semantics="probability",
        presence_parameter_id="test-placement-probability",
        role_id="test-role-nearby",
    )
    original = engine.child_rng
    sample = distributions.sample
    decisions = Counter()
    samples = Counter()

    class Decision:
        def __init__(self, event, quantity):
            self.event, self.quantity = event, quantity

        def random(self):
            decisions[(self.event, self.quantity)] += 1
            present = (self.event % 2 == 0) == (self.quantity == "role_participation")
            return 0.25 if present else 0.75

    def scripted(config, scenario, stream, entity_key, **kwargs):
        for quantity in ("role_participation", "nearby_participation"):
            if f"presence:{quantity}" in entity_key:
                event = int(entity_key.split("|")[5].split(":")[1])
                return Decision(event, quantity)
        return original(config, scenario, stream, entity_key, **kwargs)

    def observed_sample(spec, rng):
        if isinstance(rng, Decision):
            probability = next(
                p
                for p in config.execution_bindings
                if p.parameter_id == "test-placement-probability"
            )
            assert spec == probability.distribution
            samples[(rng.event, rng.quantity)] += 1
        return sample(spec, rng)

    monkeypatch.setattr(engine, "child_rng", scripted)
    monkeypatch.setattr(distributions, "sample", observed_sample)
    dataset = engine.generate(config, scenario, approval, mapping)
    assert len(dataset.firing_events) == len(dataset.participant_exposures) == 12
    assert [row.participation_type.value for row in dataset.participant_exposures] == [
        "nearby_crew" if n % 2 else "fired_weapon" for n in range(1, 13)
    ]
    assert set(decisions.values()) == {1}
    assert len(decisions) == 24
    assert samples == decisions
    assert {row.role for row in dataset.participant_exposures} == {
        "test-role-alpha",
        "test-role-nearby",
    }
    assert [row.event_id for row in dataset.participant_exposures] == [
        row.event_id for row in dataset.firing_events
    ]


def test_integer_tuple_preorder_with_twelve_siblings(monkeypatch):
    config, scenario, approval, mapping = assembly_fixture(event_count=12)
    original = engine.child_rng
    event_paths = []

    def observed(config, scenario, stream, entity_key, **kwargs):
        if "applicability:event" in entity_key:
            event_paths.append(tuple(int(s.split(":")[1]) for s in entity_key.split("|")[:6]))
        return original(config, scenario, stream, entity_key, **kwargs)

    monkeypatch.setattr(engine, "child_rng", observed)
    dataset = engine.generate(config, scenario, approval, mapping)
    assert event_paths == [(1, 1, 1, 1, 1, n) for n in range(1, 13)]
    assert event_paths[1] < event_paths[9]
    assert [row.round_or_launch_index for row in dataset.firing_events] == list(range(1, 13))
    assert [row.event_id for row in dataset.firing_events] == [
        stable_synthetic_id(SyntheticEntityType.EVENT, n) for n in range(1, 13)
    ]


def test_lineage_union_and_no_feature_computation(monkeypatch):
    from blastbridge.features import synthetic

    class NoFeatures:
        def __iter__(self):
            pytest.fail("generation computed feature contracts")

    monkeypatch.setattr(synthetic, "FEATURE_CONTRACTS", NoFeatures())
    config, scenario, approval, mapping = assembly_fixture()
    dataset = engine.generate(config, scenario, approval, mapping)
    parameters = {p.parameter_id: p for p in configured_parameter_bindings(config)}
    assert all(p.parameter_class == ParameterClass.SCENARIO_ASSUMPTION for p in parameters.values())
    lineage = {item.record_type: item for item in mapping.record_lineage}
    for kind, rows in all_tables(dataset):
        ids = tuple(dict.fromkeys(lineage[kind].parameter_ids))
        bound = [parameters[p] for p in ids]
        for row in rows:
            provenance = row.provenance
            assert provenance.parameter_ids == ids
            assert provenance.rng_stream == RECORD_STREAMS[kind]
            assert provenance.scenario_assumption_ids == tuple(
                dict.fromkeys(v for p in bound for v in p.scenario_assumption_ids)
            )
            assert provenance.uncertainty_types == tuple(
                dict.fromkeys(v for p in bound for v in p.uncertainty_types)
            )
            assert (
                provenance.prior_definition_ids
                == provenance.evidence_ids
                == provenance.sme_estimate_ids
                == ()
            )
            assert provenance.generation_method == "distribution_sample"
            assert not any(
                fragment in name.lower()
                for name in type(row).model_fields
                for fragment in ("tbi", "injury", "diagnos", "symptom", "medical")
            )


@pytest.mark.parametrize(
    "rounding,expected", [(ExecutionRounding.FLOOR, 1), (ExecutionRounding.CEIL, 2)]
)
def test_fractional_count_uses_declared_rounding(rounding, expected):
    config, scenario, approval, mapping = assembly_fixture()
    config, scenario = fixed(config, scenario, "test-career-episode-count", 1.25)
    mapping = placements(mapping, RecordType.CAREER, rounding=rounding)
    dataset = engine.generate(config, scenario, approval, mapping)
    assert len(dataset.career_episodes) == expected


def test_zero_children_and_zero_mission_count_are_supported():
    config, scenario, approval, mapping = assembly_fixture()
    config, scenario = fixed(config, scenario, "test-career-episode-count", 0)
    dataset = engine.generate(config, scenario, approval, mapping)
    assert len(dataset.members) == 1
    assert not any(rows for kind, rows in all_tables(dataset) if kind != RecordType.MEMBER)
    config, scenario, approval, mapping = assembly_fixture()
    mapping = placements(mapping, RecordType.MISSION, count_parameter_id="test-placement-zero")
    config, scenario = fixed(config, scenario, "test-assembly-event-applicability", 0)
    dataset = engine.generate(config, scenario, approval, mapping)
    assert not dataset.firing_missions
    assert dataset.firing_events
    assert all(event.mission_id is None for event in dataset.firing_events)


@pytest.mark.parametrize("mechanism", [MissingnessMechanism.STRUCTURAL, MissingnessMechanism.MCAR])
def test_conditional_masks_refused_before_execution(mechanism, monkeypatch):
    config, scenario, approval, mapping = assembly_missingness_fixture(mechanism)
    rule = config.missingness_configuration.rules[0].model_copy(
        update={"condition_quantity_ids": ("role",)}
    )
    config = config.model_copy(
        update={
            "missingness_configuration": config.missingness_configuration.model_copy(
                update={"rules": (rule,)}
            ),
        }
    )
    forbid_operations(monkeypatch)
    with pytest.raises(ValueError, match="7g: supported missingness cannot specify conditioning"):
        engine.generate(config, scenario, approval, mapping)


@pytest.mark.parametrize(
    "semantics,value,rule", [("boolean_code", 2, "5b"), ("probability", 1.5, "5c")]
)
def test_bad_presence_support_refused_before_execution(semantics, value, rule, monkeypatch):
    config, scenario, approval, mapping = assembly_fixture()
    config, scenario = fixed(config, scenario, "test-placement-probability", value)
    mapping = roles(
        mapping,
        "role_participation",
        presence_semantics=semantics,
        presence_parameter_id="test-placement-probability",
    )
    forbid_operations(monkeypatch)
    with pytest.raises(ValueError, match=rule):
        engine.generate(config, scenario, approval, mapping)


def test_mission_count_draw_occurs_even_when_not_applicable(monkeypatch):
    config, scenario, approval, mapping = assembly_fixture()
    mapping = placements(
        mapping, RecordType.MISSION, mission_applicability_parameter_id="test-placement-zero"
    )
    config, scenario = fixed(config, scenario, "test-assembly-event-applicability", 0)
    original = engine.child_rng
    seen = []

    def observed(config, scenario, stream, entity_key, **kwargs):
        if "count:FiringMission" in entity_key:
            seen.append(entity_key)
        return original(config, scenario, stream, entity_key, **kwargs)

    monkeypatch.setattr(engine, "child_rng", observed)
    dataset = engine.generate(config, scenario, approval, mapping)
    assert not dataset.firing_missions
    assert seen == [key((1, 1, 1, 1, 1), "count:FiringMission", "test-placement-one")]


def test_unknown_evaluation_operation_refused_before_execution(monkeypatch):
    config, scenario, approval, mapping = assembly_fixture()
    mapping = mapping.model_copy(
        update={
            "evaluation_order": (*mapping.evaluation_order, "test-undefined-operation"),
        }
    )
    forbid_operations(monkeypatch)
    with pytest.raises(
        ValueError,
        match="evaluation operation test-undefined-operation: no executable algorithm",
    ):
        engine.generate(config, scenario, approval, mapping)


@pytest.mark.parametrize(
    "kind,reference",
    [
        (kind, reference)
        for kinds, references in (
            (
                (RecordType.MEMBER,),
                (
                    "shape_parameter_id",
                    "offset_parameter_id",
                    "duration_parameter_id",
                    "partition_parameter_id",
                    "count_parameter_id",
                    "mission_applicability_parameter_id",
                ),
            ),
            (
                (RecordType.CAREER, RecordType.ASSIGNMENT, RecordType.TRAINING),
                (
                    "shape_parameter_id",
                    "start_parameter_id",
                    "end_parameter_id",
                    "count_parameter_id",
                    "mission_applicability_parameter_id",
                ),
            ),
            (
                (RecordType.SESSION,),
                (
                    "shape_parameter_id",
                    "start_parameter_id",
                    "end_parameter_id",
                    "partition_parameter_id",
                    "mission_applicability_parameter_id",
                ),
            ),
            (
                (RecordType.MISSION,),
                (
                    "shape_parameter_id",
                    "start_parameter_id",
                    "end_parameter_id",
                    "partition_parameter_id",
                ),
            ),
            (
                (RecordType.EVENT,),
                (
                    "shape_parameter_id",
                    "start_parameter_id",
                    "end_parameter_id",
                    "duration_parameter_id",
                    "partition_parameter_id",
                ),
            ),
        )
        for kind in kinds
        for reference in references
    ],
)
def test_unused_placement_references_refused_before_execution(kind, reference, monkeypatch):
    config, scenario, approval, mapping = assembly_fixture()
    mapping = placements(mapping, kind, **{reference: "test-placement-one"})
    forbid_operations(monkeypatch)
    expected = f"^placement {kind}: unused reference {reference} refused in V5-2$"
    # Exercise every engine backstop, including invalid count/record pairings
    # which authorization already refuses before the engine preflight runs.
    with pytest.raises(ValueError, match=expected):
        engine._preflight(config, mapping)
    if reference == "count_parameter_id":
        with pytest.raises(ValueError, match="^3c: count binding requires count meaning"):
            engine.generate(config, scenario, approval, mapping)
    else:
        authorize_fictional_execution(config, scenario, approval, mapping)
        with pytest.raises(ValueError, match=expected):
            engine.generate(config, scenario, approval, mapping)


@pytest.mark.parametrize(
    "kind,reference,unused_reference",
    [
        (RecordType.CAREER, "partition_parameter_id", "count_parameter_id"),
        (RecordType.ASSIGNMENT, "partition_parameter_id", "count_parameter_id"),
        (RecordType.TRAINING, "partition_parameter_id", "count_parameter_id"),
        (RecordType.SESSION, "count_parameter_id", "partition_parameter_id"),
        (RecordType.MISSION, "count_parameter_id", "partition_parameter_id"),
        (RecordType.EVENT, "count_parameter_id", "partition_parameter_id"),
    ],
)
def test_child_count_selects_reference_by_record_type(
    kind, reference, unused_reference, monkeypatch
):
    config, scenario, _, mapping = assembly_fixture()
    mapping = placements(mapping, kind, **{unused_reference: "test-placement-end"})
    assembler = engine._Assembler(config, scenario, mapping)
    rule = next(rule for rule in mapping.placement_rules if rule.record_type == kind)
    sampled = []

    def observed(record, path, operation, parameter):
        sampled.append((record, path, operation, parameter))
        return 1

    # Isolate selection from preflight: an unused reference can never override
    # the parameter chosen by S4, even when count() is inspected on its own.
    monkeypatch.setattr(assembler, "draw", observed)
    assert assembler.count(kind, (1,)) == 1
    assert sampled == [(kind, (1,), f"count:{kind.value}", getattr(rule, reference))]
