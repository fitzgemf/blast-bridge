"""Offline loading and byte-integrity checks for a complete reference release."""

import hashlib
import json
from pathlib import Path
from typing import Any

from blastbridge.models.reference import (
    ReferenceBundle,
    ReleaseManifest,
    SourceRegistry,
)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_object)


def load_source_registry(path: str | Path) -> SourceRegistry:
    """Validate source records and registry metadata independently."""
    return SourceRegistry.model_validate(read_json(path))


def load_reference_bundle(
    directory: str | Path, *, verify_manifest: bool = True
) -> ReferenceBundle:
    """Validate citations, joins, taxonomy and (by default) release hashes offline.

    verify_manifest=False is for editing a candidate release, never for experiments.
    It still performs all schema, citation and referential-integrity checks.
    """
    root = Path(directory)
    paths = {
        "sources": "sources.json",
        "weapons": "weapons.json",
        "occupations": "occupations.json",
        "relationships": "occupation_weapon_relationships.json",
        "taxonomy": "taxonomy.json",
    }
    payload = {name: read_json(root / filename) for name, filename in paths.items()}
    bundle = ReferenceBundle.model_validate(payload)
    if verify_manifest:
        manifest = ReleaseManifest.model_validate(read_json(root / "release_manifest.json"))
        schema_hash = hashlib.sha256((root / "reference.schema.json").read_bytes()).hexdigest()
        if schema_hash != manifest.schema_sha256:
            raise ValueError("release schema hash mismatch")
        if manifest.metadata.source_registry_version != bundle.sources.metadata.dataset_version:
            raise ValueError("release manifest source registry version mismatch")
        datasets = {filename: payload[name] for name, filename in paths.items()}
        for entry in manifest.files:
            if entry.dataset_version != datasets[entry.filename]["metadata"]["dataset_version"]:
                raise ValueError(f"release manifest dataset version mismatch: {entry.filename}")
            actual = hashlib.sha256((root / entry.filename).read_bytes()).hexdigest()
            if actual != entry.sha256:
                raise ValueError(f"release hash mismatch: {entry.filename}")
    return bundle
