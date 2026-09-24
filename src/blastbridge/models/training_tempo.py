"""Raw training evidence with explicit population, counting and epistemic boundaries."""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, HttpUrl, StrictBool, model_validator

from .core import Confidence, Count, ResearchModel, Text
from .reference import SHA256, Citation, Identifier, ReferenceBundle


class TempoComponent(StrEnum):
    ACTIVE = "active"
    ARMY_NATIONAL_GUARD = "army_national_guard"
    ARMY_RESERVE = "army_reserve"
    MARINE_CORPS_RESERVE = "marine_corps_reserve"
    UNKNOWN = "unknown"


class CountingUnit(StrEnum):
    FIRING_EVENT = "firing_event"
    EXPOSURE_EVENT = "exposure_event"
    FIRING_MISSION = "firing_mission"
    LIVE_FIRE_SESSION = "live_fire_session"
    TRAINING_EVENT = "training_event"
    QUALIFICATION_CYCLE = "qualification_cycle"
    DUTY_DAY = "duty_day"
    ANNUAL_TRAINING_PERIOD = "annual_training_period"


class EvidenceType(StrEnum):
    DOCTRINAL_REQUIREMENT = "doctrinal_requirement"
    QUALIFICATION_REQUIREMENT = "qualification_requirement"
    OFFICIAL_UNIT_TRAINING_REPORT = "official_unit_training_report"
    OFFICIAL_AFTER_ACTION_OR_SUMMARY = "official_after_action_or_summary"
    TRAINING_CALENDAR_OR_SCHEDULE = "training_calendar_or_schedule"
    SCHOOL_REQUIREMENT = "school_requirement"
    RANGE_OR_AMMUNITION_RECORD = "range_or_ammunition_record"
    PEER_REVIEWED_OBSERVATION = "peer_reviewed_observation"
    GOVERNMENT_REPORT = "government_report"
    SUBJECT_MATTER_EXPERT = "subject_matter_expert"
    ASSUMPTION = "assumption"


class Representativeness(StrEnum):
    SINGLE_UNIT = "single_unit_example"
    SINGLE_EXERCISE = "single_exercise_example"
    MULTIPLE_UNITS = "multiple_unit_evidence"
    SERVICE_REQUIREMENT = "service_wide_requirement"
    COMPONENT_REQUIREMENT = "component_wide_requirement"
    SCHOOL = "school_environment"
    UNKNOWN = "unknown"


class ParticipationRole(StrEnum):
    WEAPON_OPERATOR = "weapon_operator"
    CREW_MEMBER = "crew_member"
    NEARBY_CREW = "nearby_crew"
    SECTION_CHIEF = "section_chief"
    SAFETY_PERSONNEL = "safety_personnel"
    INSTRUCTOR = "instructor"
    STUDENT = "student"
    OBSERVER = "observer"
    UNKNOWN = "unknown"


class TrainingContext(StrEnum):
    DEPLOYMENT_PREPARATION = "deployment_preparation"
    CTC_LARGE_SCALE_EXERCISE = "ctc_large_scale_exercise"
    HOME_STATION = "routine_home_station"
    ANNUAL_TRAINING = "annual_training"
    QUALIFICATION = "qualification_certification"
    SCHOOL = "school_instructor_environment"
    UNKNOWN = "unknown"


class TempoMetadata(ResearchModel):
    dataset_name: Identifier
    dataset_version: Literal["0.2.0"]
    schema_version: Literal["0.2.0"]
    source_registry_version: Literal["0.2.0"]
    generated_at: AwareDatetime
    baseline_reference_version: Literal["0.1.0"]


class TempoSource(ResearchModel):
    source_id: Identifier
    title: Text
    organization: Text
    source_type: Literal[
        "official", "peer_reviewed", "subject_matter_expert", "assumption", "research_definition"
    ]
    document_kind: Literal[
        "doctrine",
        "training_manual",
        "unit_report",
        "government_report",
        "school_page",
        "schedule",
        "range_record",
        "peer_reviewed",
        "user_note",
        "research_definition",
        "assumption",
    ]
    url: HttpUrl | None
    publication_date: date | None
    document_version: Text | None
    accessed_date: date
    retrieval_method: Literal[
        "downloaded", "indexed_official_text", "provided_by_user", "local_note"
    ]
    content_sha256: SHA256 | None
    local_filename: Annotated[str, Field(pattern=r"^[a-z0-9_-]+\.(pdf|html|txt)$")] | None
    retrieval_limitation: Text | None
    temporal_status: Literal["historical_scope", "current_status_unverified", "not_applicable"]
    notes: Text

    @model_validator(mode="after")
    def check_source(self) -> Self:
        private = {"subject_matter_expert", "assumption", "research_definition"}
        if self.source_type in private:
            expected = {
                "subject_matter_expert": "user_note",
                "assumption": "assumption",
                "research_definition": "research_definition",
            }
            if self.document_kind != expected[self.source_type] or self.url is not None:
                raise ValueError("local/SME provenance cannot impersonate an official document")
            if self.retrieval_method not in {"provided_by_user", "local_note"}:
                raise ValueError("local provenance requires a local retrieval method")
            if self.content_sha256 is not None or self.local_filename is not None:
                raise ValueError(
                    "local notes are preserved in the release, not claimed as downloads"
                )
        else:
            if self.url is None or self.document_kind in set(private) | {"user_note"}:
                raise ValueError("published evidence requires a publication URL and document kind")
            if self.url.username is not None or self.url.password is not None or self.url.fragment:
                raise ValueError("source URLs cannot contain credentials or citation fragments")
            if self.source_type == "official":
                host = (self.url.host or "").lower()
                domains = (
                    "army.mil",
                    "marines.mil",
                    "nationalguard.mil",
                    "defense.gov",
                    "health.mil",
                    "gao.gov",
                    "govinfo.gov",
                    "dvidshub.net",
                )
                if not any(host == d or host.endswith("." + d) for d in domains):
                    raise ValueError("official source requires an approved official domain")
                if self.document_kind == "peer_reviewed":
                    raise ValueError("peer-reviewed evidence has a distinct source type")
            elif self.document_kind != "peer_reviewed":
                raise ValueError("peer-reviewed source requires peer-reviewed document kind")
            if self.retrieval_method == "downloaded":
                if self.content_sha256 is None or self.local_filename is None:
                    raise ValueError("downloaded originals require filename and byte hash")
            elif self.retrieval_method == "indexed_official_text":
                if self.source_type != "official" or self.content_sha256 or self.local_filename:
                    raise ValueError("indexed official text cannot claim original-byte hashes")
                if self.retrieval_limitation is None:
                    raise ValueError("blocked direct retrieval must be documented")
            else:
                raise ValueError("published source requires an appropriate retrieval method")
        if self.publication_date is not None and self.publication_date > self.accessed_date:
            raise ValueError("publication cannot follow access date")
        return self


class CountValue(ResearchModel):
    """Raw count qualification; bounds/central recollections are not prior parameters."""

    precision: Literal["exact", "approximate", "greater_than", "less_than", "range"]
    value: Count | None = None
    lower: Count | None = None
    upper: Count | None = None
    recalled_central: Count | None = None

    @model_validator(mode="after")
    def check_shape(self) -> Self:
        if self.precision == "range":
            if self.value is not None or self.lower is None or self.upper is None:
                raise ValueError("a range requires lower/upper and no exact value")
            if self.lower > self.upper:
                raise ValueError("range bounds must be ordered")
            if (
                self.recalled_central is not None
                and not self.lower <= self.recalled_central <= self.upper
            ):
                raise ValueError("recalled central value must lie within the reported range")
        elif self.value is None or any(
            v is not None for v in (self.lower, self.upper, self.recalled_central)
        ):
            raise ValueError("non-range counts require only a value and explicit precision")
        return self


class Interval(ResearchModel):
    value: Annotated[int, Field(gt=0, strict=True)]
    unit: Literal["day", "week", "month", "year"]


class Frequency(ResearchModel):
    count: CountValue
    counting_unit: CountingUnit
    per: Interval
    population_denominator: Literal["unit", "crew", "launcher", "person", "unspecified"]
    interpretation: Text


class ScopedCount(ResearchModel):
    count: CountValue
    population_denominator: Literal["unit_total", "crew", "launcher", "person", "unspecified"]
    scope: Text


class Requirement(ResearchModel):
    kind: Literal["requirement"]
    minimum_required_frequency: Frequency | None = None
    qualification_validity: Interval | None = None
    task_sustainment_interval: Interval | None = None
    live_fire_required: StrictBool | None
    conditions: Text

    @model_validator(mode="after")
    def no_recalled_requirement(self) -> Self:
        frequency = self.minimum_required_frequency
        if frequency is not None and frequency.count.recalled_central is not None:
            raise ValueError("recalled central estimates cannot become requirements")
        return self


class Observation(ResearchModel):
    kind: Literal["observation"]
    observed_frequency: Frequency | None = None
    observed_round_count: ScopedCount | None = None
    observed_firing_event_count: ScopedCount | None = None
    observed_training_event_count: ScopedCount | None = None
    reported_crew_count: CountValue | None = None
    reported_launcher_count: CountValue | None = None
    denominator_linkage: Text
    live_fire_confirmed: StrictBool | None

    @model_validator(mode="after")
    def no_estimate_parameters(self) -> Self:
        counts = (
            self.observed_round_count,
            self.observed_firing_event_count,
            self.observed_training_event_count,
        )
        values = [c.count for c in counts if c is not None]
        values += [
            c for c in (self.reported_crew_count, self.reported_launcher_count) if c is not None
        ]
        if self.observed_frequency is not None:
            values.append(self.observed_frequency.count)
        if any(v.recalled_central is not None for v in values):
            raise ValueError("recalled central estimates cannot masquerade as observations")
        if self.live_fire_confirmed is not True and (
            self.observed_round_count is not None or self.observed_firing_event_count is not None
        ):
            raise ValueError("observed firing counts require confirmation of firing")
        return self


class Estimate(ResearchModel):
    kind: Literal["estimate"]
    estimated_frequency: Frequency | None = None
    estimated_rounds_per_event: ScopedCount | None = None
    event_unit: CountingUnit | None = None
    recollection: Text
    uncertainty: Text

    @model_validator(mode="after")
    def check_event_unit(self) -> Self:
        if self.estimated_rounds_per_event is not None and self.event_unit is None:
            raise ValueError("per-event estimate requires a separately mapped event unit")
        return self


class Assumption(ResearchModel):
    kind: Literal["assumption"]
    assumption: Text
    justification: Text
    usable_as_evidence: Literal[False]


class Schedule(ResearchModel):
    kind: Literal["schedule"]
    planned_frequency: Frequency | None = None
    planned_activity: Text
    completion_verified: Literal[False]


Claim = Annotated[
    Requirement | Observation | Estimate | Assumption | Schedule, Field(discriminator="kind")
]


class TimeWindow(ResearchModel):
    description: Text
    start_date: date | None = None
    end_date: date | None = None
    year: Annotated[int, Field(ge=1900, le=2100, strict=True)] | None = None

    @model_validator(mode="after")
    def check_dates(self) -> Self:
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("time-window dates must be ordered")
        if self.year is not None and any(
            d.year != self.year for d in (self.start_date, self.end_date) if d
        ):
            raise ValueError("year must agree with dated observations")
        return self


class TempoEvidence(ResearchModel):
    tempo_evidence_id: Identifier
    branch: Literal["army", "marine_corps"]
    component: TempoComponent
    occupation_ids: tuple[Identifier, ...]
    occupation_link_basis: Literal["direct", "curator_relevance", "unknown"]
    weapon_system_ids: tuple[Identifier, ...]
    weapon_link_basis: Literal["direct", "family_mapping", "unknown"]
    source_platform_wording: Text | None
    unit_type: Text | None
    crew_role: Text | None
    participation_roles: tuple[ParticipationRole, ...] = Field(min_length=1)
    training_context: tuple[TrainingContext, ...] = Field(min_length=1)
    source_id: Identifier
    citations: tuple[Citation, ...] = Field(min_length=1)
    source_wording: Text
    normalized_activity_type: CountingUnit
    mapping_note: Text
    context_basis: Text
    time_window: TimeWindow
    population_scope: Text
    unit_scope: Text
    evidence_type: EvidenceType
    representativeness: Representativeness
    representativeness_basis: Text
    confidence: Confidence | None = None
    confidence_rationale: Text | None = None
    limitations: tuple[Text, ...] = Field(min_length=1)
    notes: Text
    individual_exposure_inference: Literal["not_established"]
    claim: Claim

    @model_validator(mode="after")
    def check_evidence(self) -> Self:
        allowed_components = {
            "army": {"active", "army_national_guard", "army_reserve", "unknown"},
            "marine_corps": {"active", "marine_corps_reserve", "unknown"},
        }
        if self.component not in allowed_components[self.branch]:
            raise ValueError("component is incompatible with branch")
        for values in (
            self.occupation_ids,
            self.weapon_system_ids,
            self.participation_roles,
            self.training_context,
        ):
            if len(values) != len(set(values)):
                raise ValueError("duplicate population/platform/context identifiers")
        for values in (self.participation_roles, self.training_context):
            if "unknown" in values and len(values) > 1:
                raise ValueError("unknown cannot coexist with known roles/contexts")
        if bool(self.occupation_ids) == (self.occupation_link_basis == "unknown"):
            raise ValueError("occupation mapping basis must agree with populated IDs")
        if bool(self.weapon_system_ids) == (self.weapon_link_basis == "unknown"):
            raise ValueError("weapon mapping basis must agree with populated IDs")
        if self.source_id not in {c.source_id for c in self.citations}:
            raise ValueError("primary source requires an exact citation locator")
        if len({(c.source_id, c.locator) for c in self.citations}) != len(self.citations):
            raise ValueError("duplicate source citations")
        if (self.confidence is None) != (self.confidence_rationale is None):
            raise ValueError(
                "numeric confidence requires an explicit rationale; no automatic score"
            )
        kinds = {
            EvidenceType.DOCTRINAL_REQUIREMENT: {"requirement"},
            EvidenceType.QUALIFICATION_REQUIREMENT: {"requirement"},
            EvidenceType.SCHOOL_REQUIREMENT: {"requirement"},
            EvidenceType.OFFICIAL_UNIT_TRAINING_REPORT: {"observation"},
            EvidenceType.OFFICIAL_AFTER_ACTION_OR_SUMMARY: {"observation"},
            EvidenceType.TRAINING_CALENDAR_OR_SCHEDULE: {"schedule"},
            EvidenceType.RANGE_OR_AMMUNITION_RECORD: {"observation"},
            EvidenceType.PEER_REVIEWED_OBSERVATION: {"observation"},
            EvidenceType.GOVERNMENT_REPORT: {"requirement", "observation"},
            EvidenceType.SUBJECT_MATTER_EXPERT: {"estimate"},
            EvidenceType.ASSUMPTION: {"assumption"},
        }
        if self.claim.kind not in kinds[self.evidence_type]:
            raise ValueError("evidence type and claim kind disagree")
        broad = {Representativeness.SERVICE_REQUIREMENT, Representativeness.COMPONENT_REQUIREMENT}
        if self.representativeness in broad and self.claim.kind != "requirement":
            raise ValueError("unit observations/estimates cannot be population-wide requirements")
        if (
            self.representativeness == Representativeness.COMPONENT_REQUIREMENT
            and self.component == "unknown"
        ):
            raise ValueError("component-wide requirement needs a known component")
        if self.evidence_type in {EvidenceType.SUBJECT_MATTER_EXPERT, EvidenceType.ASSUMPTION}:
            if self.representativeness != Representativeness.UNKNOWN:
                raise ValueError("SME/assumption representativeness remains unknown")
        if self.normalized_activity_type == CountingUnit.EXPOSURE_EVENT:
            raise ValueError(
                "V0.2 contains activity evidence, not individual exposure observations"
            )
        frequencies = []
        if isinstance(self.claim, Requirement):
            frequencies.append(self.claim.minimum_required_frequency)
        elif isinstance(self.claim, Observation):
            frequencies.append(self.claim.observed_frequency)
        elif isinstance(self.claim, Estimate):
            frequencies.append(self.claim.estimated_frequency)
        elif isinstance(self.claim, Schedule):
            frequencies.append(self.claim.planned_frequency)
        if any(f.counting_unit != self.normalized_activity_type for f in frequencies if f):
            raise ValueError("frequency unit must agree with the explicit activity mapping")
        return self


class CountingDefinition(ResearchModel):
    counting_unit: CountingUnit
    definition: Text
    boundary: Text
    source_id: Identifier
    locator: Text
    provenance_kind: Literal["research_definition"]


class TermMapping(ResearchModel):
    source_term: Text
    evidence_id: Identifier
    mapping: CountingUnit | None
    ambiguity: Text


class TempoSources(ResearchModel):
    metadata: TempoMetadata
    records: tuple[TempoSource, ...] = Field(min_length=1)


class TempoEvidenceDataset(ResearchModel):
    metadata: TempoMetadata
    records: tuple[TempoEvidence, ...] = Field(min_length=1)


class TempoTaxonomy(ResearchModel):
    metadata: TempoMetadata
    records: tuple[CountingDefinition, ...] = Field(min_length=8, max_length=8)
    source_term_mappings: tuple[TermMapping, ...] = Field(min_length=1)
    evidence_types: tuple[EvidenceType, ...]
    representativeness_values: tuple[Representativeness, ...]
    participation_roles: tuple[ParticipationRole, ...]
    components: tuple[TempoComponent, ...]


class TrainingTempoBundle(ResearchModel):
    sources: TempoSources
    evidence: TempoEvidenceDataset
    taxonomy: TempoTaxonomy

    @model_validator(mode="after")
    def check_integrity(self) -> Self:
        for dataset, name, keys in (
            (self.sources, "training_tempo_sources", [s.source_id for s in self.sources.records]),
            (
                self.evidence,
                "training_tempo_evidence",
                [e.tempo_evidence_id for e in self.evidence.records],
            ),
            (
                self.taxonomy,
                "training_tempo_taxonomy",
                [t.counting_unit for t in self.taxonomy.records],
            ),
        ):
            if dataset.metadata.dataset_name != name:
                raise ValueError(f"expected dataset_name {name}")
            if len(keys) != len(set(keys)):
                raise ValueError("dataset IDs must be unique")
        for values, enumeration in (
            ([r.counting_unit for r in self.taxonomy.records], CountingUnit),
            (self.taxonomy.evidence_types, EvidenceType),
            (self.taxonomy.representativeness_values, Representativeness),
            (self.taxonomy.participation_roles, ParticipationRole),
            (self.taxonomy.components, TempoComponent),
        ):
            if len(values) != len(set(values)) or set(values) != set(enumeration):
                raise ValueError("taxonomy must exactly describe the supported vocabulary")
        sources = {s.source_id: s for s in self.sources.records}
        for row in self.evidence.records:
            if row.source_id not in sources or any(
                c.source_id not in sources for c in row.citations
            ):
                raise ValueError("unknown training source ID")
            source = sources[row.source_id]
            expected_type = {
                EvidenceType.SUBJECT_MATTER_EXPERT: "subject_matter_expert",
                EvidenceType.ASSUMPTION: "assumption",
                EvidenceType.PEER_REVIEWED_OBSERVATION: "peer_reviewed",
            }.get(row.evidence_type, "official")
            if source.source_type != expected_type:
                raise ValueError("source type cannot masquerade as another evidence type")
            if any(sources[c.source_id].source_type != expected_type for c in row.citations):
                raise ValueError(
                    "mixed official/SME/assumption provenance must be separate records"
                )
            if row.claim.kind == "requirement" and source.document_kind not in {
                "doctrine",
                "training_manual",
                "government_report",
                "school_page",
            }:
                raise ValueError("a unit news report cannot establish a normative requirement")
        for definition in self.taxonomy.records:
            if (
                definition.source_id not in sources
                or sources[definition.source_id].source_type != "research_definition"
            ):
                raise ValueError("counting definitions require explicit research provenance")
        evidence = {e.tempo_evidence_id: e for e in self.evidence.records}
        for mapping in self.taxonomy.source_term_mappings:
            if mapping.evidence_id not in evidence:
                raise ValueError("source-term mapping references unknown evidence")
        return self

    def validate_reference_links(self, reference: ReferenceBundle) -> None:
        occupations = {o.occupation_id: o for o in reference.occupations.records}
        weapons = {w.weapon_system_id for w in reference.weapons.records}
        if {s.source_id for s in self.sources.records} & {
            s.source_id for s in reference.sources.records
        }:
            raise ValueError("tempo and baseline source IDs must not collide")
        for row in self.evidence.records:
            for oid in row.occupation_ids:
                if oid not in occupations:
                    raise ValueError("unknown occupation ID")
                if occupations[oid].branch != row.branch:
                    raise ValueError("occupation branch does not match evidence branch")
            if any(wid not in weapons for wid in row.weapon_system_ids):
                raise ValueError("unknown weapon-system ID")


TempoFilename = Literal[
    "training_tempo_sources.json", "training_tempo_evidence.json", "training_tempo_taxonomy.json"
]


class TempoReleaseFile(ResearchModel):
    filename: TempoFilename
    dataset_version: Literal["0.2.0"]
    sha256: SHA256


class TempoManifest(ResearchModel):
    metadata: TempoMetadata
    files: tuple[TempoReleaseFile, ...] = Field(min_length=3, max_length=3)
    schema_sha256: SHA256
    baseline_manifest_sha256: SHA256
    baseline_git_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    baseline_git_tag: Literal["v0.1.0"]

    @model_validator(mode="after")
    def check_files(self) -> Self:
        if self.metadata.dataset_name != "training_tempo_release":
            raise ValueError("expected training_tempo_release metadata")
        if len({entry.filename for entry in self.files}) != 3:
            raise ValueError("manifest requires each tempo dataset exactly once")
        return self
