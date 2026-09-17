"""Versioned, field-cited public reference data; no exposure or medical quantities."""

import re
import unicodedata
from datetime import date
from enum import StrEnum
from typing import Annotated, ClassVar, Literal, Self

from pydantic import AwareDatetime, Field, HttpUrl, StrictBool, StringConstraints, model_validator

from .core import ResearchModel, Text
from .enums import Branch, Tier1Status

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$")]
SemVer = Annotated[
    str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
]
SHA256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class ReferenceSourceType(StrEnum):
    OFFICIAL = "official"
    PEER_REVIEWED = "peer_reviewed"


class Authority(StrEnum):
    DOD = "dod"
    DHA = "dha"
    ARMY = "army"
    MARINE_CORPS = "marine_corps"
    NAVY = "navy"
    AIR_FORCE = "air_force"
    GAO = "gao"
    OTHER = "other"


class RetrievalMethod(StrEnum):
    DOWNLOADED = "downloaded"
    INDEXED_OFFICIAL_TEXT = "indexed_official_text"


class DatasetMetadata(ResearchModel):
    dataset_name: Identifier
    dataset_version: SemVer
    generated_at: AwareDatetime
    schema_version: Literal["0.1.0"]
    source_registry_version: SemVer


class ReferenceSource(ResearchModel):
    source_id: Identifier
    title: Text
    organization: Text
    authority: Authority
    publication_date: date | None
    url: HttpUrl
    source_type: ReferenceSourceType
    accessed_date: date
    document_version: Text | None
    retrieval_method: RetrievalMethod
    content_sha256: SHA256 | None
    tier1_list_scope: Text | None = None
    tier1_list_complete: StrictBool = False
    notes: Text

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        host = (self.url.host or "").lower()
        if self.url.username is not None or self.url.password is not None:
            raise ValueError("source URLs must not contain credentials")
        if self.url.fragment is not None:
            raise ValueError("put source locators in citations, not URL fragments")
        if self.source_type == ReferenceSourceType.OFFICIAL:
            domains = {
                Authority.DOD: ("defense.gov", "health.mil"),
                Authority.DHA: ("health.mil", "dha.mil"),
                Authority.ARMY: ("army.mil",),
                Authority.MARINE_CORPS: ("marines.mil",),
                Authority.NAVY: ("navy.mil",),
                Authority.AIR_FORCE: ("af.mil",),
                Authority.GAO: ("gao.gov",),
            }
            if not any(
                host == d or host.endswith("." + d) for d in domains.get(self.authority, ())
            ):
                raise ValueError("official source authority must match an approved official domain")
        elif self.authority != Authority.OTHER:
            raise ValueError("peer-reviewed sources use authority other, not official authority")
        if self.publication_date is not None and self.publication_date > self.accessed_date:
            raise ValueError("publication_date must not follow accessed_date")
        if self.retrieval_method == RetrievalMethod.DOWNLOADED and self.content_sha256 is None:
            raise ValueError("downloaded sources require a byte hash")
        if self.retrieval_method == RetrievalMethod.INDEXED_OFFICIAL_TEXT and (
            self.content_sha256 is not None or self.source_type != ReferenceSourceType.OFFICIAL
        ):
            raise ValueError("indexed official text cannot claim a downloaded file hash")
        if self.tier1_list_scope is not None and (
            self.source_type != ReferenceSourceType.OFFICIAL
            or self.authority not in {Authority.DOD, Authority.DHA}
        ):
            raise ValueError("Tier-1 list provenance must be official DoD or DHA")
        if self.tier1_list_complete and self.tier1_list_scope is None:
            raise ValueError("a complete Tier-1 list requires an explicit document scope")
        return self


class Citation(ResearchModel):
    source_id: Identifier
    locator: Text


class FactEvidence(ResearchModel):
    field: Text
    citations: tuple[Citation, ...] = Field(min_length=1)
    basis: Literal["direct", "curator_mapping"] = "direct"


class CitedRecord(ResearchModel):
    """List items require their own citations; identifiers are local schema keys."""

    FACT_FIELDS: ClassVar[tuple[str, ...]] = ()
    source_ids: tuple[Identifier, ...] = Field(min_length=1)
    facts: tuple[FactEvidence, ...] = Field(min_length=1)
    notes: Text | None = None

    def citations_for(self, field: str) -> tuple[Citation, ...]:
        return tuple(c for fact in self.facts if fact.field == field for c in fact.citations)

    @model_validator(mode="after")
    def validate_fact_coverage(self) -> Self:
        expected: set[str] = set()
        for field in (*self.FACT_FIELDS, "notes"):
            value = getattr(self, field)
            if value is None:
                continue
            if isinstance(value, tuple):
                expected.update(f"{field}.{i}" for i in range(len(value)))
            else:
                expected.add(field)
        fields = [fact.field for fact in self.facts]
        if len(fields) != len(set(fields)) or set(fields) != expected:
            raise ValueError(f"fact citation fields must match populated facts: {sorted(expected)}")
        used = {c.source_id for fact in self.facts for c in fact.citations}
        if len(self.source_ids) != len(set(self.source_ids)) or set(self.source_ids) != used:
            raise ValueError("source_ids must exactly match the unique cited sources")
        return self


class TaxonomyCategory(CitedRecord):
    FACT_FIELDS = ("label", "scope", "parent_category_id")
    category_id: Identifier
    label: Text
    scope: Literal["official_tier1", "research_family"]
    parent_category_id: Identifier | None = None


class CanonicalWeapon(CitedRecord):
    FACT_FIELDS = (
        "canonical_name",
        "aliases",
        "record_kind",
        "weapon_family",
        "caliber",
        "service_branches",
        "dod_tier1_status",
        "tier1_category",
        "tier1_basis",
    )
    weapon_system_id: Identifier
    canonical_name: Text
    aliases: tuple[Text, ...] = ()
    record_kind: Literal["weapon_system", "exposure_category"]
    weapon_family: Identifier
    caliber: Text | None = None
    service_branches: tuple[Branch, ...] = ()
    dod_tier1_status: Tier1Status = Tier1Status.UNKNOWN
    tier1_category: Identifier | None = None
    tier1_basis: Literal["listed", "absent_from_complete_list", "not_determined"]

    @model_validator(mode="after")
    def validate_tier1(self) -> Self:
        expected = {
            Tier1Status.YES: "listed",
            Tier1Status.NO: "absent_from_complete_list",
            Tier1Status.UNKNOWN: "not_determined",
        }
        if self.tier1_basis != expected[self.dod_tier1_status]:
            raise ValueError("Tier-1 status and evidence basis disagree")
        if (self.dod_tier1_status == Tier1Status.YES) != (self.tier1_category is not None):
            raise ValueError("only verified Tier-1 membership may have a Tier-1 category")
        if self.dod_tier1_status == Tier1Status.NO and self.notes is None:
            raise ValueError("negative Tier-1 classification requires documented reasoning")
        if self.record_kind == "exposure_category" and self.caliber is not None:
            raise ValueError("an exposure category has no single weapon caliber")
        if len(self.service_branches) != len(set(self.service_branches)):
            raise ValueError("duplicate service branches")
        if Branch.UNKNOWN in self.service_branches:
            raise ValueError("use an empty branch list for unverified applicability")
        return self


class ExposureRelevance(StrEnum):
    DIRECT_WEAPON_OPERATOR = "direct_weapon_operator"
    CREW_MEMBER = "crew_member"
    FREQUENT_PROXIMITY_POSSIBLE = "frequent_proximity_possible"
    BREACHING_OR_EXPLOSIVES = "breaching_or_explosives"
    INSTRUCTOR_EXPOSURE_POSSIBLE = "instructor_exposure_possible"
    UNKNOWN = "unknown"


class OccupationalSpecialty(CitedRecord):
    FACT_FIELDS = ("branch", "code", "title", "occupational_family", "blast_exposure_relevance")
    occupation_id: Identifier
    branch: Branch
    code: Text
    title: Text
    occupational_family: Text | None = None
    blast_exposure_relevance: tuple[ExposureRelevance, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_occupation(self) -> Self:
        if self.branch == Branch.ARMY and not re.fullmatch(r"[0-9]{2}[A-Z]", self.code):
            raise ValueError("Army MOS must have two digits and an uppercase letter")
        if self.branch == Branch.MARINE_CORPS and not re.fullmatch(r"[0-9]{4}", self.code):
            raise ValueError("Marine Corps MOS must retain four digits including leading zeros")
        relevance = self.blast_exposure_relevance
        if len(relevance) != len(set(relevance)):
            raise ValueError("duplicate exposure relevance labels")
        if ExposureRelevance.UNKNOWN in relevance and len(relevance) != 1:
            raise ValueError("unknown relevance cannot coexist with known categories")
        if self.branch == Branch.UNKNOWN:
            raise ValueError("an official occupation requires a known branch")
        return self


class RelationshipType(StrEnum):
    PRIMARY_PLATFORM = "primary_platform"
    COMMONLY_OPERATED = "commonly_operated"
    CREW_EXPOSURE = "crew_exposure"
    TRAINING_EXPOSURE = "training_exposure"
    POSSIBLE_EXPOSURE = "possible_exposure"


class OccupationWeaponRelationship(CitedRecord):
    FACT_FIELDS = (
        "occupation_id",
        "weapon_system_id",
        "relationship_type",
        "documentation_strength",
        "temporal_scope",
    )
    relationship_id: Identifier
    occupation_id: Identifier
    weapon_system_id: Identifier
    relationship_type: RelationshipType
    documentation_strength: Literal[
        "direct_duty", "direct_training_standard", "observed_training", "contextual"
    ]
    temporal_scope: Text


class ReferenceDataset[T](ResearchModel):
    NAME: ClassVar[str] = ""
    ID_FIELD: ClassVar[str] = ""
    metadata: DatasetMetadata
    records: tuple[T, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dataset(self) -> Self:
        if self.metadata.dataset_name != self.NAME:
            raise ValueError(f"expected dataset_name {self.NAME}")
        keys = [getattr(row, self.ID_FIELD) for row in self.records]
        if len(keys) != len(set(keys)):
            raise ValueError(f"{self.ID_FIELD} values must be unique")
        return self


class SourceRegistry(ReferenceDataset[ReferenceSource]):
    NAME = "sources"
    ID_FIELD = "source_id"

    @model_validator(mode="after")
    def validate_registry_version(self) -> Self:
        if self.metadata.dataset_version != self.metadata.source_registry_version:
            raise ValueError("source registry must reference its own dataset version")
        return self


def normalized_name(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKC", value).casefold() if c.isalnum())


class WeaponCatalog(ReferenceDataset[CanonicalWeapon]):
    NAME = "weapons"
    ID_FIELD = "weapon_system_id"

    @model_validator(mode="after")
    def validate_aliases(self) -> Self:
        names: dict[str, str] = {}
        for weapon in self.records:
            local: set[str] = set()
            # IDs are also lookup names: an alias cannot shadow another system's ID.
            for name in (weapon.weapon_system_id, weapon.canonical_name, *weapon.aliases):
                key = normalized_name(name)
                if not key:
                    raise ValueError("empty normalized weapon name")
                if key in names and names[key] != weapon.weapon_system_id:
                    raise ValueError("ambiguous canonical name or alias across weapon systems")
                names[key] = weapon.weapon_system_id
            for name in (weapon.canonical_name, *weapon.aliases):
                key = normalized_name(name)
                if key in local:
                    raise ValueError("duplicate canonical name/alias within weapon record")
                local.add(key)
        return self


class OccupationCatalog(ReferenceDataset[OccupationalSpecialty]):
    NAME = "occupations"
    ID_FIELD = "occupation_id"

    @model_validator(mode="after")
    def validate_codes(self) -> Self:
        codes = [(row.branch, row.code) for row in self.records]
        if len(codes) != len(set(codes)):
            raise ValueError("branch and occupation code pairs must be unique")
        return self


class RelationshipCatalog(ReferenceDataset[OccupationWeaponRelationship]):
    NAME = "occupation_weapon_relationships"
    ID_FIELD = "relationship_id"

    @model_validator(mode="after")
    def validate_relationships(self) -> Self:
        keys = [(r.occupation_id, r.weapon_system_id, r.relationship_type) for r in self.records]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate occupation/weapon/relationship-type assertion")
        return self


class Taxonomy(ReferenceDataset[TaxonomyCategory]):
    NAME = "taxonomy"
    ID_FIELD = "category_id"

    @model_validator(mode="after")
    def validate_hierarchy(self) -> Self:
        categories = {r.category_id: r for r in self.records}
        for row in self.records:
            seen: set[str] = set()
            node: TaxonomyCategory | None = row
            while node is not None:
                if node.category_id in seen:
                    raise ValueError("taxonomy hierarchy contains a cycle")
                seen.add(node.category_id)
                parent = node.parent_category_id
                if parent is not None and parent not in categories:
                    raise ValueError("taxonomy parent does not exist")
                node = categories.get(parent) if parent is not None else None
        return self


class ReferenceBundle(ResearchModel):
    sources: SourceRegistry
    weapons: WeaponCatalog
    occupations: OccupationCatalog
    relationships: RelationshipCatalog
    taxonomy: Taxonomy

    @model_validator(mode="after")
    def validate_integrity(self) -> Self:
        sources = {s.source_id: s for s in self.sources.records}
        datasets = (self.weapons, self.occupations, self.relationships, self.taxonomy)
        registry_version = self.sources.metadata.dataset_version
        records: tuple[CitedRecord, ...] = tuple(r for ds in datasets for r in ds.records)
        for dataset in datasets:
            if dataset.metadata.source_registry_version != registry_version:
                raise ValueError("source registry version mismatch")
        for record in records:
            for sid in record.source_ids:
                if sid not in sources:
                    raise ValueError(f"unknown source_id: {sid}")
            # Identity, official classification, and occupational assertions require
            # official evidence. Future peer-reviewed-only annotations need a new schema.
            for fact in record.facts:
                if not any(
                    sources[c.source_id].source_type == ReferenceSourceType.OFFICIAL
                    for c in fact.citations
                ):
                    raise ValueError("reference facts require at least one official source")

        def tier1_sources(record: CitedRecord, field: str) -> list[ReferenceSource]:
            selected = [sources[c.source_id] for c in record.citations_for(field)]
            qualifying = [s for s in selected if s.tier1_list_scope is not None]
            if not qualifying:
                raise ValueError("known Tier-1 facts require an official DoD/DHA list source")
            return qualifying

        categories = {c.category_id: c for c in self.taxonomy.records}
        for category in self.taxonomy.records:
            if category.scope == "official_tier1":
                tier1_sources(category, "scope")
                tier1_sources(category, "label")
                if category.parent_category_id is not None:
                    tier1_sources(category, "parent_category_id")
                    if categories[category.parent_category_id].scope != "official_tier1":
                        raise ValueError("official category cannot descend from a research family")
        for weapon in self.weapons.records:
            if weapon.weapon_family not in categories:
                raise ValueError("unknown weapon family")
            if weapon.tier1_category is not None:
                cat = categories.get(weapon.tier1_category)
                if cat is None or cat.scope != "official_tier1":
                    raise ValueError("unknown or unofficial Tier-1 category")
                tier1_sources(weapon, "tier1_category")
            if weapon.dod_tier1_status != Tier1Status.UNKNOWN:
                status_sources = tier1_sources(weapon, "dod_tier1_status")
                tier1_sources(weapon, "tier1_basis")
                if weapon.dod_tier1_status == Tier1Status.NO and not any(
                    s.tier1_list_complete for s in status_sources
                ):
                    raise ValueError("negative Tier-1 status requires a complete scoped list")
        weapon_ids = {w.weapon_system_id for w in self.weapons.records}
        occupation_ids = {o.occupation_id for o in self.occupations.records}
        for relationship in self.relationships.records:
            if relationship.weapon_system_id not in weapon_ids:
                raise ValueError("relationship references an unknown weapon_system_id")
            if relationship.occupation_id not in occupation_ids:
                raise ValueError("relationship references an unknown occupation_id")
        return self


ReferenceFilename = Literal[
    "sources.json",
    "weapons.json",
    "occupations.json",
    "occupation_weapon_relationships.json",
    "taxonomy.json",
]


class ReleaseFile(ResearchModel):
    filename: ReferenceFilename
    dataset_version: SemVer
    sha256: SHA256


class ReleaseManifest(ResearchModel):
    metadata: DatasetMetadata
    schema_sha256: SHA256
    files: tuple[ReleaseFile, ...] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        if self.metadata.dataset_name != "reference_release":
            raise ValueError("expected reference_release metadata")
        if len({f.filename for f in self.files}) != 5:
            raise ValueError("release manifest requires each dataset exactly once")
        return self
