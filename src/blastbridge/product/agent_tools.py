"""Two local, deterministic lookups for fictional training-record intake."""

import re
from collections.abc import Sequence
from typing import Any

from blastbridge.models.reference import CanonicalWeapon

from .models import Person


def normalize(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text.lower()).strip()


def search_weapon_catalog(
    query: str, catalog: Sequence[CanonicalWeapon]
) -> list[dict[str, object]]:
    tokens = set(normalize(query).split())
    if not tokens:
        return []
    matches = [
        weapon
        for weapon in catalog
        if tokens
        <= set(
            normalize(
                " ".join(
                    (
                        weapon.weapon_system_id,
                        weapon.canonical_name,
                        *weapon.aliases,
                    )
                )
            ).split()
        )
    ]
    return [
        {
            "weapon_system_id": weapon.weapon_system_id,
            "canonical_name": weapon.canonical_name,
            "aliases": list(weapon.aliases),
            "weapon_family": weapon.weapon_family,
        }
        for weapon in sorted(matches, key=lambda weapon: weapon.canonical_name)[:5]
    ]


def search_roster(query: str, people: Sequence[Person]) -> list[dict[str, object]]:
    text = normalize(query)
    tokens = set(text.split())
    if not tokens:
        return []
    matches = [
        person
        for person in people
        if (
            tokens <= set(normalize(person.display_name).split())
            or text == normalize(person.callsign)
        )
    ]
    return [
        {
            "person_id": person.person_id,
            "display_name": person.display_name,
            "section": person.section,
        }
        for person in sorted(matches, key=lambda person: person.display_name)[:5]
    ]


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "search_weapon_catalog",
        "description": (
            "Look up a weapon system in the BlastBridge reference catalog. Use for every weapon "
            "or system mentioned. Returns canonical ids; use only ids returned here."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_roster",
        "description": (
            "Look up fictional BlastBridge personnel by name or callsign. Use once per person "
            "mentioned. Returns person ids; use only ids returned here."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
]
