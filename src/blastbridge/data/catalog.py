"""Canonical weapon loading through a fully validated reference release."""

from pathlib import Path

from blastbridge.models.reference import CanonicalWeapon

from .reference import load_reference_bundle


def load_weapon_catalog(path: str | Path) -> tuple[CanonicalWeapon, ...]:
    """Load weapons.json together with its registry, relationships and manifest."""
    catalog = Path(path)
    if catalog.name != "weapons.json":
        raise ValueError("canonical catalog must be named weapons.json within a reference release")
    return load_reference_bundle(catalog.parent).weapons.records
