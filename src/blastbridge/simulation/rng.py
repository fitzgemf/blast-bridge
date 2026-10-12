"""Explicit deterministic random streams; never uses Python's global RNG."""

import json
import random
from hashlib import sha256

from blastbridge.models.reference import SemVer

from .models import RngStream, ScenarioDefinition, SimulationConfig


def derive_seed(
    master_seed: int,
    generator_version: str,
    scenario_version: SemVer,
    configuration_fingerprint: str,
    stream: RngStream,
    entity_key: str,
) -> int:
    """Derive a stable 256-bit child seed without randomized ``hash()``."""
    payload = "\0".join(
        (
            str(master_seed),
            generator_version,
            scenario_version,
            configuration_fingerprint,
            stream.value,
            entity_key,
        )
    ).encode("utf-8")
    return int.from_bytes(sha256(payload).digest(), "big")


def child_rng(
    config: SimulationConfig,
    scenario: ScenarioDefinition,
    stream: RngStream,
    entity_key: str,
) -> random.Random:
    """Create an isolated stream keyed by run version, domain stream and entity."""
    if not entity_key:
        raise ValueError("entity_key must be explicit and non-empty")
    if (scenario.scenario_id, scenario.scenario_version) != (
        config.scenario_id,
        config.scenario_version,
    ):
        raise ValueError("RNG scenario must match the simulation configuration")
    seed = derive_seed(
        config.master_seed,
        config.generator_version,
        config.scenario_version,
        _fingerprint(config, scenario),
        stream,
        entity_key,
    )
    rng = random.Random()
    rng.seed(seed, version=2)
    return rng


def stream_seeds(
    config: SimulationConfig,
    scenario: ScenarioDefinition,
    entity_key: str,
) -> dict[RngStream, int]:
    """Return deterministic seeds for every isolated generation concern."""
    if (scenario.scenario_id, scenario.scenario_version) != (
        config.scenario_id,
        config.scenario_version,
    ):
        raise ValueError("RNG scenario must match the simulation configuration")
    return {
        stream: derive_seed(
            config.master_seed,
            config.generator_version,
            config.scenario_version,
            _fingerprint(config, scenario),
            stream,
            entity_key,
        )
        for stream in RngStream
    }


def _fingerprint(config: SimulationConfig, scenario: ScenarioDefinition) -> str:
    payload = json.dumps(
        {"config": config.model_dump(mode="json"), "scenario": scenario.model_dump(mode="json")},
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()
