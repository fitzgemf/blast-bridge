import json
from pathlib import Path

import pytest

from blastbridge.data.catalog import load_weapon_catalog
from blastbridge.models.reference import WeaponCatalog

CATALOG = Path(__file__).resolve().parents[1] / "data" / "reference" / "weapons.json"


def test_canonical_catalog_without_blast_values():
    weapons = load_weapon_catalog(CATALOG)
    assert len(weapons) == 18
    assert {w.weapon_system_id for w in weapons} == {
        "m142-himars",
        "m270-mlrs",
        "m109-paladin",
        "m777",
        "m119",
        "m224",
        "m252",
        "m120",
        "m121",
        "m3-maaws",
        "m136-at4",
        "m72-law",
        "m107",
        "mk15",
        "m2a1",
        "gau-21",
        "m1-abrams-120mm",
        "explosive-breaching",
    }
    for weapon in weapons:
        assert "blastbridge-scope-v1" not in weapon.source_ids
        assert "peak_pressure" not in weapon.model_dump()
        assert "impulse" not in weapon.model_dump()


def test_duplicate_catalog_ids_rejected():
    raw = json.loads(CATALOG.read_text(encoding="utf-8"))
    raw["records"].append(raw["records"][0])
    with pytest.raises(ValueError, match="unique"):
        WeaponCatalog.model_validate(raw)
