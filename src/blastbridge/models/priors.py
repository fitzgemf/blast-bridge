"""V0.3 design contracts. No distribution fitting, sampling or medical inference."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .core import ResearchModel, Text
from .reference import SHA256, Identifier, ReferenceBundle
from .training_tempo import (
    Claim,
    CountingUnit,
    ParticipationRole,
    Representativeness,
    TempoComponent,
    TimeWindow,
    TrainingContext,
    TrainingTempoBundle,
)


class PriorType(StrEnum):
    EMPIRICAL = "empirical_prior"
    CONSTRAINT = "evidence_constraint"
    SME = "sme_estimate"
    SCENARIO = "scenario_assumption"


class DistributionFamily(StrEnum):
    FIXED = "fixed"
    DISCRETE_UNIFORM = "discrete_uniform"
    TRIANGULAR = "triangular"
    BETA = "beta"
    NORMAL = "normal"
    LOGNORMAL = "lognormal"
    POISSON = "poisson"
    NEGATIVE_BINOMIAL = "negative_binomial"
    CATEGORICAL = "categorical"
    EMPIRICAL = "empirical"
    NONE = "none"


class SupportLevel(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    REQUIREMENT_ONLY = "R"


class UncertaintyType(StrEnum):
    ALEATORY = "aleatory"
    EPISTEMIC = "epistemic"
    UNKNOWN = "unknown_unclassified"


class UncertaintyDimension(StrEnum):
    ANNUAL_EVENTS = "annual_event_count"
    ROUNDS = "rounds_per_event"
    PARTICIPATION = "crew_participation"
    ROLE = "role"
    NEARBY = "nearby_exposure"
    DURATION = "assignment_duration"
    MISSING_YEARS = "missing_years"
    RELIABILITY = "source_reliability"


class UncertaintyDefinition(ResearchModel):
    uncertainty_id: Identifier
    dimension: UncertaintyDimension
    uncertainty_type: UncertaintyType
    rationale: Text
    future_aleatory_component: Text | None
    future_epistemic_component: Text | None
    propagation_plan: Text
    numerical_weight: None = None


class PriorDefinition(ResearchModel):
    prior_id: Identifier
    population_scope: Text
    branch: Literal["army", "marine_corps"]
    component: TempoComponent
    occupation_ids: tuple[Identifier, ...]
    weapon_system_ids: tuple[Identifier, ...]
    unit_type: Text | None
    role_scope: tuple[ParticipationRole, ...] = Field(min_length=1)
    training_context: tuple[TrainingContext, ...] = Field(min_length=1)
    quantity_being_modeled: Literal[
        "requirement_structure", "reported_activity", "recalled_tempo", "annual_event_count"
    ]
    counting_unit: CountingUnit
    time_window: TimeWindow
    prior_type: PriorType
    # Vocabulary is reserved for a later authorized parameter schema. V0.3 is non-executable.
    distribution_family: DistributionFamily
    parameters: None
    lower_bound: None
    upper_bound: None
    anchor_evidence_id: Identifier | None
    evidence_ids: tuple[Identifier, ...]
    source_ids: tuple[Identifier, ...]
    evidence_payload: Claim | None
    scope_binding: Literal["source_only", "hypothetical_scenario"]
    confidence_class: Literal["unassessed"]
    support_level: SupportLevel
    representativeness: Representativeness | Literal["not_applicable"]
    uncertainty_ids: tuple[Identifier, ...] = Field(min_length=1)
    scenario: Literal["conservative", "central", "high-tempo"] | None
    rationale: Text
    limitations: tuple[Text, ...] = Field(min_length=1)
    version: Literal["0.3.0"]
    status: Literal["source_bound", "design_only"]
    individual_exposure_inference: Literal["not_established"]

    @model_validator(mode="after")
    def check_design_boundary(self) -> Self:
        if self.prior_type == PriorType.EMPIRICAL:
            raise ValueError(
                "empirical_prior unavailable: V0.3 has no qualifying representative empirical data"
            )
        if self.distribution_family != DistributionFamily.NONE:
            raise ValueError("V0.3 cannot select or parameterize numerical distributions")
        if self.support_level in {SupportLevel.A, SupportLevel.B}:
            raise ValueError(
                "A/B require empirical qualification or reviewed independence evidence"
            )
        for values in (
            self.occupation_ids,
            self.weapon_system_ids,
            self.role_scope,
            self.training_context,
            self.evidence_ids,
            self.source_ids,
            self.uncertainty_ids,
        ):
            unique(values)
        for values in (self.role_scope, self.training_context):
            if "unknown" in values and len(values) != 1:
                raise ValueError("unknown role/context cannot coexist with known values")
        allowed = {
            "army": {"active", "army_national_guard", "army_reserve", "unknown"},
            "marine_corps": {"active", "marine_corps_reserve", "unknown"},
        }
        if self.component not in allowed[self.branch]:
            raise ValueError("branch/component mismatch")
        if self.prior_type == PriorType.SCENARIO:
            if (
                self.support_level != SupportLevel.F
                or self.status != "design_only"
                or self.scope_binding != "hypothetical_scenario"
                or self.scenario is None
                or self.anchor_evidence_id is not None
                or self.evidence_payload is not None
                or self.representativeness != "not_applicable"
                or self.quantity_being_modeled != "annual_event_count"
            ):
                raise ValueError("scenario assumptions must remain unparameterized design-only F")
        else:
            if (
                self.anchor_evidence_id is None
                or self.anchor_evidence_id not in self.evidence_ids
                or self.evidence_payload is None
                or self.status != "source_bound"
                or self.scope_binding != "source_only"
                or self.scenario is not None
                or self.representativeness == "not_applicable"
            ):
                raise ValueError("source-bound definitions require an anchor and preserved claim")
            kind = self.evidence_payload.kind
            if self.prior_type == PriorType.SME:
                if (
                    kind != "estimate"
                    or self.support_level != SupportLevel.E
                    or self.quantity_being_modeled != "recalled_tempo"
                ):
                    raise ValueError("SME provenance must remain an E estimate")
            elif not (
                (
                    kind == "requirement"
                    and self.support_level in {SupportLevel.REQUIREMENT_ONLY, SupportLevel.C}
                    and self.quantity_being_modeled == "requirement_structure"
                )
                or (
                    kind == "observation"
                    and self.support_level == SupportLevel.D
                    and self.quantity_being_modeled == "reported_activity"
                )
            ):
                raise ValueError(
                    "constraints preserve requirements or scoped observations, not plans"
                )
        return self


def unique(values: tuple[object, ...] | list[str]) -> None:
    if len(values) != len(set(values)):
        raise ValueError("duplicate identifiers or vocabulary entries")


class DesignMetadata(ResearchModel):
    version: Literal["0.3.0"]
    baseline_reference_version: Literal["0.1.0"]
    training_tempo_version: Literal["0.2.0"]
    purpose: Literal["modeling_assumption_and_prior_design"]


class PriorRegistry(ResearchModel):
    metadata: DesignMetadata
    empirical_priors: None
    numerical_scenarios_authorized: Literal[False]
    records: tuple[PriorDefinition, ...] = Field(min_length=1)
    uncertainties: tuple[UncertaintyDefinition, ...] = Field(min_length=8, max_length=8)


class ResearchGap(ResearchModel):
    gap_id: Identifier
    population: Text
    quantity_needed: Text
    why_needed: Text
    current_evidence: tuple[Identifier, ...]
    preferred_future_source: Text
    impact_on_modeling: Text
    status: Literal["open"]


class ResearchGaps(ResearchModel):
    metadata: DesignMetadata
    records: tuple[ResearchGap, ...] = Field(min_length=1)


class PriorDesignBundle(ResearchModel):
    priors: PriorRegistry
    gaps: ResearchGaps

    @model_validator(mode="after")
    def check_internal_links(self) -> Self:
        unique([p.prior_id for p in self.priors.records])
        unique([g.gap_id for g in self.gaps.records])
        unique([u.uncertainty_id for u in self.priors.uncertainties])
        dimensions = [u.dimension for u in self.priors.uncertainties]
        if len(set(dimensions)) != len(dimensions) or set(dimensions) != set(UncertaintyDimension):
            raise ValueError("uncertainty register must cover each dimension exactly once")
        uncertainties = {u.uncertainty_id: u for u in self.priors.uncertainties}
        for prior in self.priors.records:
            if not set(prior.uncertainty_ids) <= uncertainties.keys():
                raise ValueError("unknown uncertainty ID")
            if prior.prior_type == PriorType.SCENARIO and {
                uncertainties[i].dimension for i in prior.uncertainty_ids
            } != set(UncertaintyDimension):
                raise ValueError(
                    "scenario design must explicitly retain all uncertainty dimensions"
                )
        for gap in self.gaps.records:
            unique(gap.current_evidence)
        return self

    def validate_evidence(self, tempo: TrainingTempoBundle, reference: ReferenceBundle) -> None:
        evidence = {e.tempo_evidence_id: e for e in tempo.evidence.records}
        occupations = {o.occupation_id: o for o in reference.occupations.records}
        weapons = {w.weapon_system_id for w in reference.weapons.records}
        for gap in self.gaps.records:
            if not set(gap.current_evidence) <= evidence.keys():
                raise ValueError("gap references unknown evidence")
        for prior in self.priors.records:
            if not set(prior.evidence_ids) <= evidence.keys():
                raise ValueError("unknown evidence ID")
            cited = [evidence[eid] for eid in prior.evidence_ids]
            expected_sources = {c.source_id for row in cited for c in row.citations}
            if set(prior.source_ids) != expected_sources:
                raise ValueError("source IDs must exactly equal cited evidence provenance")
            if not set(prior.occupation_ids) <= occupations.keys():
                raise ValueError("unknown occupation ID")
            if any(occupations[oid].branch != prior.branch for oid in prior.occupation_ids):
                raise ValueError("occupation branch mismatch")
            if not set(prior.weapon_system_ids) <= weapons:
                raise ValueError("unknown weapon ID")
            if prior.prior_type == PriorType.SCENARIO:
                # Supporting material is contextual; it cannot supply a hidden numeric payload.
                if any(
                    row.branch != prior.branch
                    or (row.component != "unknown" and row.component != prior.component)
                    or (
                        row.occupation_ids
                        and not set(row.occupation_ids) & set(prior.occupation_ids)
                    )
                    or (
                        row.weapon_system_ids
                        and not set(row.weapon_system_ids) & set(prior.weapon_system_ids)
                    )
                    for row in cited
                ):
                    raise ValueError("scenario context requires a compatible population mapping")
                continue
            assert prior.anchor_evidence_id is not None
            anchor = evidence[prior.anchor_evidence_id]
            for prior_field, evidence_field in (
                ("population_scope", "population_scope"),
                ("branch", "branch"),
                ("component", "component"),
                ("occupation_ids", "occupation_ids"),
                ("weapon_system_ids", "weapon_system_ids"),
                ("unit_type", "unit_type"),
                ("role_scope", "participation_roles"),
                ("training_context", "training_context"),
                ("counting_unit", "normalized_activity_type"),
                ("time_window", "time_window"),
                ("representativeness", "representativeness"),
                ("evidence_payload", "claim"),
            ):
                if getattr(prior, prior_field) != getattr(anchor, evidence_field):
                    raise ValueError(f"source-bound {prior_field} differs from V0.2 anchor")
            if not set(anchor.limitations) <= set(prior.limitations):
                raise ValueError("source limitations must be retained")
            if prior.prior_type == PriorType.SME:
                if anchor.evidence_type != "subject_matter_expert":
                    raise ValueError("SME needs SME provenance")
            elif anchor.evidence_type == "subject_matter_expert":
                raise ValueError("SME cannot become an official constraint")
            if prior.support_level == SupportLevel.C:
                observations = [row for row in cited if row.claim.kind == "observation"]
                if (
                    not observations
                    or any(
                        row.branch != anchor.branch
                        or row.component != anchor.component
                        or not set(row.occupation_ids) & set(anchor.occupation_ids)
                        or not set(row.weapon_system_ids) & set(anchor.weapon_system_ids)
                        for row in observations
                    )
                    or any(
                        row.claim.kind != "observation"
                        for row in cited
                        if row.tempo_evidence_id != prior.anchor_evidence_id
                    )
                ):
                    raise ValueError("C needs a requirement plus compatible official observations")
            elif prior.evidence_ids != (prior.anchor_evidence_id,):
                raise ValueError("R/D/E are single-source-bound records; do not pool evidence")


PriorFilename = Literal["prior_definitions.json", "research_gaps.json"]


class PriorFileHash(ResearchModel):
    filename: PriorFilename
    sha256: SHA256


class PriorManifest(ResearchModel):
    version: Literal["0.3.0"]
    files: tuple[PriorFileHash, ...] = Field(min_length=2, max_length=2)
    schema_sha256: SHA256
    baseline_tag: Literal["v0.2.0"]
    baseline_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    baseline_manifest_sha256: SHA256

    @model_validator(mode="after")
    def check_files(self) -> Self:
        if {entry.filename for entry in self.files} != {
            "prior_definitions.json",
            "research_gaps.json",
        }:
            raise ValueError("manifest must include every design dataset exactly once")
        return self
