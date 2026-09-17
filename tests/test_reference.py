import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from blastbridge.data.reference import load_reference_bundle, load_source_registry, read_json
from blastbridge.models.reference import (
    DatasetMetadata,
    ReferenceBundle,
    ReferenceSource,
    ReleaseManifest,
)

ROOT = Path(__file__).resolve().parents[1] / "data" / "reference"
FILES = {
    "sources": "sources.json",
    "weapons": "weapons.json",
    "occupations": "occupations.json",
    "relationships": "occupation_weapon_relationships.json",
    "taxonomy": "taxonomy.json",
}


@pytest.fixture
def payload():
    return {key: read_json(ROOT / filename) for key, filename in FILES.items()}


@pytest.fixture
def release_copy(tmp_path):
    for filename in [*FILES.values(), "reference.schema.json", "release_manifest.json"]:
        (tmp_path / filename).write_bytes((ROOT / filename).read_bytes())
    return tmp_path


def rec(payload, collection, rid):
    field = {
        "weapons": "weapon_system_id",
        "occupations": "occupation_id",
        "taxonomy": "category_id",
        "relationships": "relationship_id",
        "sources": "source_id",
    }[collection]
    return next(row for row in payload[collection]["records"] if row[field] == rid)


def cite(row, field, sid):
    fact = next(f for f in row["facts"] if f["field"] == field)
    fact["citations"] = [{"source_id": sid, "locator": "Unit-test locator"}]
    row["source_ids"] = sorted({c["source_id"] for f in row["facts"] for c in f["citations"]})


def test_release_roundtrip_schema_and_counts():
    bundle = load_reference_bundle(ROOT)
    assert ReferenceBundle.model_validate_json(bundle.model_dump_json()) == bundle
    assert len(bundle.sources.records) == 11
    assert len(bundle.occupations.records) == 8
    assert len(bundle.relationships.records) == 12
    assert len(bundle.taxonomy.records) == 10
    assert load_source_registry(ROOT / "sources.json") == bundle.sources
    assert read_json(ROOT / "reference.schema.json") == ReferenceBundle.model_json_schema()
    assert sum(w.dod_tier1_status == "yes" for w in bundle.weapons.records) == 15


@pytest.mark.parametrize("collection", list(FILES))
def test_duplicate_ids(payload, collection):
    payload[collection]["records"].append(deepcopy(payload[collection]["records"][0]))
    with pytest.raises(ValidationError, match="unique"):
        ReferenceBundle.model_validate(payload)


@pytest.mark.parametrize("collection", ["weapons", "occupations", "relationships", "taxonomy"])
def test_missing_sources(payload, collection):
    row = payload[collection]["records"][0]
    cite(row, row["facts"][0]["field"], "missing-source")
    with pytest.raises(ValidationError, match="unknown source_id"):
        ReferenceBundle.model_validate(payload)


@pytest.mark.parametrize("collection", ["weapons", "occupations", "relationships", "taxonomy"])
def test_missing_fact_coverage(payload, collection):
    payload[collection]["records"][0]["facts"].pop()
    with pytest.raises(ValidationError, match="fact citation fields"):
        ReferenceBundle.model_validate(payload)


def test_new_alias_requires_citation(payload):
    payload["weapons"]["records"][0]["aliases"].append("Uncited alias")
    with pytest.raises(ValidationError, match="fact citation fields"):
        ReferenceBundle.model_validate(payload)


@pytest.mark.parametrize("alias", ["M777 howitzer", " m777-HOWITZER ", "Ｍ７７７ howitzer", "m777"])
def test_alias_collision_normalization(payload, alias):
    row = rec(payload, "weapons", "m119")
    row["aliases"] = [alias]
    row["facts"].append({**deepcopy(row["facts"][0]), "field": "aliases.0"})
    with pytest.raises(ValidationError, match="ambiguous"):
        ReferenceBundle.model_validate(payload)


def test_canonical_name_collision(payload):
    rec(payload, "weapons", "m119")["canonical_name"] = "M777 howitzer"
    with pytest.raises(ValidationError, match="ambiguous"):
        ReferenceBundle.model_validate(payload)


def test_duplicate_local_alias(payload):
    row = rec(payload, "weapons", "m136-at4")
    row["aliases"].append("at-4")
    row["facts"].append(
        {
            **deepcopy(next(f for f in row["facts"] if f["field"] == "aliases.0")),
            "field": "aliases.1",
        }
    )
    with pytest.raises(ValidationError, match="duplicate canonical"):
        ReferenceBundle.model_validate(payload)


@pytest.mark.parametrize("field", ["occupation_id", "weapon_system_id"])
def test_dangling_relationship(payload, field):
    payload["relationships"]["records"][0][field] = "missing-record"
    with pytest.raises(ValidationError, match="relationship references an unknown"):
        ReferenceBundle.model_validate(payload)


def test_duplicate_occupation_code(payload):
    row = deepcopy(payload["occupations"]["records"][0])
    row["occupation_id"] = "another-occupation"
    payload["occupations"]["records"].append(row)
    with pytest.raises(ValidationError, match="branch and occupation code"):
        ReferenceBundle.model_validate(payload)


def test_duplicate_relationship_assertion(payload):
    row = deepcopy(payload["relationships"]["records"][0])
    row["relationship_id"] = "another-relationship"
    payload["relationships"]["records"].append(row)
    with pytest.raises(ValidationError, match="duplicate occupation/weapon"):
        ReferenceBundle.model_validate(payload)


@pytest.mark.parametrize(
    ("oid", "code"),
    [
        ("usmc-0341", 341),
        ("usmc-0341", "341"),
        ("usmc-0341", "034A"),
        ("army-13m", "13m"),
        ("army-13m", "13"),
        ("army-13m", "013M"),
    ],
)
def test_occupation_codes(payload, oid, code):
    rec(payload, "occupations", oid)["code"] = code
    with pytest.raises(ValidationError):
        ReferenceBundle.model_validate(payload)


@pytest.mark.parametrize("field", ["dod_tier1_status", "tier1_basis", "tier1_category"])
def test_tier1_requires_dod_dha_list(payload, field):
    cite(rec(payload, "weapons", "m119"), field, "army-redleg-2024")
    with pytest.raises(ValidationError, match="official DoD/DHA list"):
        ReferenceBundle.model_validate(payload)


def test_official_category_requires_list(payload):
    cite(rec(payload, "taxonomy", "howitzer"), "scope", "army-redleg-2024")
    with pytest.raises(ValidationError, match="official DoD/DHA list"):
        ReferenceBundle.model_validate(payload)


def test_unknown_tier1_has_no_category(payload):
    rec(payload, "weapons", "m119").update(dod_tier1_status="unknown", tier1_basis="not_determined")
    with pytest.raises(ValidationError, match="only verified Tier-1"):
        ReferenceBundle.model_validate(payload)


def test_negative_tier1_needs_complete_list(payload):
    row = rec(payload, "weapons", "m119")
    row.update(dod_tier1_status="no", tier1_basis="absent_from_complete_list", tier1_category=None)
    row["facts"] = [f for f in row["facts"] if f["field"] != "tier1_category"]
    rec(payload, "sources", "dod-report-2021")["tier1_list_complete"] = False
    with pytest.raises(ValidationError, match="complete scoped list"):
        ReferenceBundle.model_validate(payload)


@pytest.mark.parametrize("bad", ["assumption", "synthetic", "sensor", "blog", "reddit"])
def test_unsupported_registry_sources(payload, bad):
    with pytest.raises(ValidationError):
        ReferenceSource.model_validate({**payload["sources"]["records"][0], "source_type": bad})


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "file:///tmp/source.pdf",
        "ftp://health.mil/source.pdf",
        "https://health.mil.evil.example/source",
        "https://example.com/source",
        "https://user:password@health.mil/source",
        "https://health.mil/source#page=4",
    ],
)
def test_invalid_official_url(payload, url):
    with pytest.raises(ValidationError):
        ReferenceSource.model_validate({**payload["sources"]["records"][0], "url": url})


def test_peer_reviewed_supported_but_not_sufficient_for_official_facts(payload):
    row = rec(payload, "sources", "army-redleg-2024")
    row.update(
        source_type="peer_reviewed", authority="other", url="https://pubmed.ncbi.nlm.nih.gov/1/"
    )
    assert ReferenceSource.model_validate(row).source_type == "peer_reviewed"
    with pytest.raises(ValidationError, match="at least one official source"):
        ReferenceBundle.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("content_sha256", None),
        ("content_sha256", "abc"),
        ("retrieval_method", "indexed_official_text"),
        ("publication_date", "2099-01-01"),
    ],
)
def test_source_metadata_constraints(payload, field, value):
    with pytest.raises(ValidationError):
        ReferenceSource.model_validate({**payload["sources"]["records"][0], field: value})


@pytest.mark.parametrize("version", ["0.1", "v0.1.0", "01.1.0", "0.1.-1", "1.0.0.0", 1])
def test_semver_constraints(payload, version):
    with pytest.raises(ValidationError):
        DatasetMetadata.model_validate(
            {**payload["weapons"]["metadata"], "dataset_version": version}
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "0.2.0"),
        ("generated_at", "2026-09-17T01:00:00"),
        ("dataset_name", "../weapons"),
    ],
)
def test_metadata_constraints(payload, field, value):
    with pytest.raises(ValidationError):
        DatasetMetadata.model_validate({**payload["weapons"]["metadata"], field: value})


@pytest.mark.parametrize("collection", ["weapons", "occupations", "relationships", "taxonomy"])
def test_registry_version_mismatch(payload, collection):
    payload[collection]["metadata"]["source_registry_version"] = "0.2.0"
    with pytest.raises(ValidationError, match="registry version mismatch"):
        ReferenceBundle.model_validate(payload)


def test_dataset_name_cannot_be_swapped(payload):
    payload["weapons"]["metadata"]["dataset_name"] = "occupations"
    with pytest.raises(ValidationError, match="expected dataset_name"):
        ReferenceBundle.model_validate(payload)


def test_unknown_family(payload):
    rec(payload, "weapons", "m119")["weapon_family"] = "missing-family"
    with pytest.raises(ValidationError, match="unknown weapon family"):
        ReferenceBundle.model_validate(payload)


@pytest.mark.parametrize(
    ("parent", "message"), [("howitzer", "cycle"), ("missing-family", "parent does not exist")]
)
def test_invalid_taxonomy(payload, parent, message):
    rec(payload, "taxonomy", "howitzer")["parent_category_id"] = parent
    with pytest.raises(ValidationError, match=message):
        ReferenceBundle.model_validate(payload)


@pytest.mark.parametrize(
    "field", ["peak_pressure", "impulse", "safe_distance", "risk_score", "rounds_per_year"]
)
def test_no_exposure_risk_or_frequency_values(payload, field):
    payload["weapons"]["records"][0][field] = 1.0
    with pytest.raises(ValidationError, match="Extra inputs"):
        ReferenceBundle.model_validate(payload)


def test_duplicate_json_keys(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"records": [], "records": [1]}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        read_json(path)


@pytest.mark.parametrize("filename", ["weapons.json", "reference.schema.json"])
def test_changed_bytes_fail_hash(release_copy, filename):
    path = release_copy / filename
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_reference_bundle(release_copy)
    assert load_reference_bundle(release_copy, verify_manifest=False)


def test_manifest_no_traversal():
    manifest = read_json(ROOT / "release_manifest.json")
    manifest["files"][0]["filename"] = "../sources.json"
    with pytest.raises(ValidationError):
        ReleaseManifest.model_validate(manifest)


def test_manifest_requires_unique_datasets():
    manifest = read_json(ROOT / "release_manifest.json")
    manifest["files"][1] = deepcopy(manifest["files"][0])
    with pytest.raises(ValidationError, match="each dataset exactly once"):
        ReleaseManifest.model_validate(manifest)


def test_manifest_version_mismatch(release_copy):
    manifest = read_json(release_copy / "release_manifest.json")
    manifest["files"][0]["dataset_version"] = "0.2.0"
    (release_copy / "release_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest dataset version mismatch"):
        load_reference_bundle(release_copy)


def test_schema_hash_exact():
    manifest = read_json(ROOT / "release_manifest.json")
    assert (
        hashlib.sha256((ROOT / "reference.schema.json").read_bytes()).hexdigest()
        == manifest["schema_sha256"]
    )


def test_unknowns_and_identity_boundaries():
    bundle = load_reference_bundle(ROOT)
    weapons = {w.weapon_system_id: w for w in bundle.weapons.records}
    for wid in ["m142-himars", "m270-mlrs", "m1-abrams-120mm"]:
        assert weapons[wid].dod_tier1_status == "unknown"
        assert weapons[wid].tier1_category is None
    assert weapons["m136-at4"].caliber is None
    assert "M135 AT4" not in weapons["m136-at4"].aliases
    assert "M3A1" not in weapons["m3-maaws"].aliases
    assert weapons["m120"].weapon_system_id != weapons["m121"].weapon_system_id
    assert not any(r.occupation_id == "army-89d" for r in bundle.relationships.records)
    assert not any(r.weapon_system_id == "m121" for r in bundle.relationships.records)
