"""Execution refusal remains atomic; assembly is pending V5-2."""

import pytest
from execution_mapping_fixtures import execution_fixture

from blastbridge.simulation import engine
from blastbridge.simulation.models import (
    DependencyMode,
    MissingnessMechanism,
    MissingnessRule,
    MissingnessTarget,
)


@pytest.fixture
def forbid_execution(monkeypatch):
    """Patch the globals the engine binds, never their source modules."""

    def unexpected(*args, **kwargs):
        pytest.fail("refused input reached RNG/record construction")

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
        assert engine.generate.__globals__[name] is unexpected
    assert all(operation is unexpected for operation in engine._execution_operations())


@pytest.mark.parametrize(
    "mode", [DependencyMode.CONDITIONAL, DependencyMode.JOINT, DependencyMode.UNKNOWN]
)
def test_unsupported_dependency_refused_before_execution(mode, forbid_execution):
    config, scenario, approval, mapping = execution_fixture()
    training = config.training_configuration
    dependency = training.dependencies[0].model_copy(update={"mode": mode})
    training = training.model_copy(
        update={"dependencies": (dependency, *training.dependencies[1:])}
    )
    config = config.model_copy(update={"training_configuration": training})
    with pytest.raises(ValueError, match=f"dependency test-dependency-00: mode {mode} refused"):
        engine.generate(config, scenario, approval, mapping)


@pytest.mark.parametrize(
    "mechanism",
    [
        MissingnessMechanism.MCAR,
        MissingnessMechanism.MAR,
        MissingnessMechanism.MNAR,
        MissingnessMechanism.UNKNOWN_REASON,
    ],
)
def test_unsupported_missingness_refused_before_execution(mechanism, forbid_execution):
    config, scenario, approval, mapping = execution_fixture()
    rule = MissingnessRule(
        target_quantity="crew-role",
        mechanism=mechanism,
        condition_quantity_ids=("role",)
        if mechanism in {MissingnessMechanism.MAR, MissingnessMechanism.MNAR}
        else (),
        scenario_assumption_id="test-assumption-alpha",
        rationale="TEST unsupported declaration",
    )
    missingness = config.missingness_configuration.model_copy(
        update={"rules": (*config.missingness_configuration.rules, rule)}
    )
    config = config.model_copy(update={"missingness_configuration": missingness})
    target = MissingnessTarget(
        target_quantity="crew-role",
        field_ref="AssignmentEpisode.crew_role",
        latent_never_none=True,
        mcar_probability_parameter_id="test-placement-probability"
        if mechanism == MissingnessMechanism.MCAR
        else None,
    )
    mapping = mapping.model_copy(
        update={"missingness_targets": (*mapping.missingness_targets, target)}
    )
    if mechanism == MissingnessMechanism.MCAR:
        expected = "mcar refused"
    else:
        expected = f"missingness target crew-role: mechanism {mechanism} refused"
    with pytest.raises(ValueError, match=expected):
        engine.generate(config, scenario, approval, mapping)


@pytest.mark.parametrize("population_size", [1, 10])
def test_valid_mapping_still_defers_assembly(population_size, forbid_execution):
    config, scenario, approval, mapping = execution_fixture()
    config = config.model_copy(update={"population_size": population_size})
    with pytest.raises(ValueError, match="^assembler pending V5-2$"):
        engine.generate(config, scenario, approval, mapping)


def test_execution_mapping_is_mandatory(forbid_execution):
    config, scenario, approval, _ = execution_fixture()
    with pytest.raises(TypeError, match="mapping"):
        engine.generate(config, scenario, approval)


def test_authorization_is_the_first_operation(monkeypatch):
    config, scenario, approval, mapping = execution_fixture()

    def rejected(*args):
        raise ValueError("TEST authorization refused")

    def premature(*args):
        pytest.fail("semantics preflight preceded fictional authorization")

    monkeypatch.setattr(engine, "authorize_fictional_execution", rejected)
    monkeypatch.setattr(engine, "_preflight", premature)
    with pytest.raises(ValueError, match="TEST authorization refused"):
        engine.generate(config, scenario, approval, mapping)
