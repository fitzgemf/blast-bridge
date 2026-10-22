"""Deterministic comparisons of recorded training events; proposals remain session-only."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from itertools import combinations
from typing import Any, Literal

from .models import EventStatus, TrainingEvent, TrainingEventDraft

type ComparisonState = Literal["AGREES", "CONFLICTS", "COMPLEMENTARY", "UNKNOWN", "UNSUPPORTED"]
type ResolutionState = Literal["AGREED", "COMPLEMENTARY", "UNKNOWN", "UNRESOLVED", "HUMAN_RESOLVED"]


@dataclass(frozen=True)
class Signal:
    name: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class SharedEventCandidate:
    source_ids: tuple[str, str]
    signals: tuple[Signal, ...]
    blockers_checked: tuple[str, ...] = (
        "different known locations",
        "distinct crews under same name",
    )

    @property
    def key(self) -> str:
        return "+".join(self.source_ids)


def participants(source: TrainingEvent) -> set[str]:
    return {member.person_id for crew in source.draft.crews for member in crew.members}


def _location(source: TrainingEvent) -> str | None:
    value = source.draft.location_unit
    return value.strip().casefold() if value and value.strip() else None


def _reconstruction_pairs(sources: Sequence[TrainingEvent]) -> set[frozenset[str]]:
    excluded: set[frozenset[str]] = set()
    for event in sources:
        if event.reconstructed_from:
            excluded.update(
                frozenset((event.event_id, source_id)) for source_id in event.reconstructed_from
            )
            excluded.update(frozenset(pair) for pair in combinations(event.reconstructed_from, 2))
    return excluded


def possible_shared_events(sources: Sequence[TrainingEvent]) -> list[SharedEventCandidate]:
    candidates = []
    excluded = _reconstruction_pairs(sources)
    eligible = sorted(
        (source for source in sources if source.status != EventStatus.REJECTED),
        key=lambda source: source.event_id,
    )
    for a, b in combinations(eligible, 2):
        if frozenset((a.event_id, b.event_id)) in excluded:
            continue
        if a.event_id == b.event_id or (
            a.draft.event_date != b.draft.event_date
            or a.draft.weapon_system_id != b.draft.weapon_system_id
        ):
            continue
        location_a, location_b = _location(a), _location(b)
        if location_a and location_b and location_a != location_b:
            continue
        crews_b = {crew.crew_name: crew for crew in b.draft.crews}
        if any(
            crew.physical_event_count is not None
            and other.physical_event_count is not None
            and crew.physical_event_count != other.physical_event_count
            and not {m.person_id for m in crew.members} & {m.person_id for m in other.members}
            for crew in a.draft.crews
            if (other := crews_b.get(crew.crew_name)) is not None
        ):
            continue
        signals = []
        if location_a and location_a == location_b:
            signals.append(Signal("same_location", (a.draft.location_unit or "",)))
        if (a.draft.event_type, a.draft.training_context) == (
            b.draft.event_type,
            b.draft.training_context,
        ):
            signals.append(
                Signal("same_context", (a.draft.event_type.value, a.draft.training_context.value))
            )
        overlap = participants(a) & participants(b)
        if len(overlap) >= 2:
            signals.append(Signal("participant_overlap", tuple(sorted(overlap))))
        if len(signals) >= 2:
            candidates.append(SharedEventCandidate((a.event_id, b.event_id), tuple(signals)))
    return candidates


@dataclass(frozen=True)
class ComparisonRow:
    field: str
    label: str
    value_a: Any
    value_b: Any
    state: ComparisonState
    finding_code: str | None = None


@dataclass(frozen=True)
class Comparison:
    sources: tuple[TrainingEvent, TrainingEvent]
    rows: tuple[ComparisonRow, ...]

    @property
    def source_ids(self) -> tuple[str, str]:
        return self.sources[0].event_id, self.sources[1].event_id

    @property
    def key(self) -> str:
        return "+".join(self.source_ids)


def _state(a: Any, b: Any) -> ComparisonState:
    if a is None and b is None:
        return "UNKNOWN"
    if a is None or b is None:
        return "COMPLEMENTARY"
    return "AGREES" if a == b else "CONFLICTS"


def compare_sources(a: TrainingEvent, b: TrainingEvent) -> Comparison:
    if a.event_id == b.event_id or EventStatus.REJECTED in (a.status, b.status):
        raise ValueError("two distinct non-rejected source records are required")
    a, b = sorted((a, b), key=lambda source: source.event_id)
    rows = []
    for field, label in (
        ("event_date", "Event date"),
        ("weapon_system_id", "Weapon"),
        ("event_type", "Event type"),
        ("training_context", "Training context"),
    ):
        va, vb = getattr(a.draft, field), getattr(b.draft, field)
        rows.append(ComparisonRow(field, label, va, vb, _state(va, vb)))
    rows.append(
        ComparisonRow(
            "location_unit",
            "Location",
            a.draft.location_unit,
            b.draft.location_unit,
            _state(_location(a), _location(b)),
        )
    )
    crews_a = {crew.crew_name: crew for crew in a.draft.crews}
    crews_b = {crew.crew_name: crew for crew in b.draft.crews}
    for name in sorted(crews_a.keys() | crews_b.keys()):
        ca, cb = crews_a.get(name), crews_b.get(name)
        rows.append(
            ComparisonRow(
                f"crew:{name}",
                name,
                True if ca else None,
                True if cb else None,
                "AGREES" if ca and cb else "COMPLEMENTARY",
            )
        )
        va = ca.physical_event_count if ca else None
        vb = cb.physical_event_count if cb else None
        state = _state(va, vb)
        rows.append(
            ComparisonRow(
                f"count:{name}",
                f"{name} activity count",
                va,
                vb,
                state,
                "CONFLICTING_ACTIVITY_COUNT" if state == "CONFLICTS" else None,
            )
        )
    members_a = {
        member.person_id: (crew.crew_name, member.position.value)
        for crew in a.draft.crews
        for member in crew.members
    }
    members_b = {
        member.person_id: (crew.crew_name, member.position.value)
        for crew in b.draft.crews
        for member in crew.members
    }
    for person_id in sorted(members_a.keys() | members_b.keys()):
        va, vb = members_a.get(person_id), members_b.get(person_id)
        state = _state(va, vb)
        rows.append(
            ComparisonRow(
                f"member:{person_id}",
                f"{person_id} crew / position",
                va,
                vb,
                state,
                "CONFLICTING_PARTICIPANT_ROLE" if state == "CONFLICTS" else None,
            )
        )
    rows.append(
        ComparisonRow(
            "source_relationship",
            "Source relationship",
            "not recorded in BlastBridge",
            "not recorded in BlastBridge",
            "UNSUPPORTED",
        )
    )
    return Comparison((a, b), tuple(rows))


@dataclass(frozen=True)
class ResolutionOption:
    key: str
    value: Any
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class FieldResolution:
    field: str
    label: str
    value: Any
    state: ResolutionState
    contributing_source_ids: tuple[str, ...]
    conflicting_source_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    options: tuple[ResolutionOption, ...] = ()


@dataclass(frozen=True)
class EvidenceReconstructionProposal:
    key: str
    source_ids: tuple[str, str]
    fields: tuple[FieldResolution, ...]
    comparison: Comparison
    created_draft_id: str | None = None


def prepare_reconstruction(comparison: Comparison) -> EvidenceReconstructionProposal:
    if not possible_shared_events(comparison.sources):
        raise ValueError("a possible shared event candidate is required")
    fields = []
    ids = comparison.source_ids
    for row in comparison.rows:
        if row.state == "UNSUPPORTED":
            continue
        refs = tuple(f"source:{source_id}" for source_id in ids)
        if row.state == "CONFLICTS":
            options = tuple(
                ResolutionOption(source_id, value, (source_id,))
                for source_id, value in zip(ids, (row.value_a, row.value_b), strict=True)
            )
            if row.field.startswith("count:") or row.field == "location_unit":
                options += (ResolutionOption("unknown", None, ()),)
            fields.append(
                FieldResolution(
                    row.field,
                    row.label,
                    None,
                    "UNRESOLVED",
                    (),
                    ids,
                    refs,
                    options,
                )
            )
        else:
            contributors = tuple(
                source_id
                for source_id, value in zip(ids, (row.value_a, row.value_b), strict=True)
                if value is not None
            )
            state: ResolutionState = (
                "AGREED"
                if row.state == "AGREES"
                else "UNKNOWN"
                if row.state == "UNKNOWN"
                else "COMPLEMENTARY"
            )
            fields.append(
                FieldResolution(
                    row.field,
                    row.label,
                    row.value_a if row.value_a is not None else row.value_b,
                    state,
                    contributors,
                    (),
                    refs,
                )
            )
    return EvidenceReconstructionProposal(comparison.key, ids, tuple(fields), comparison)


def resolve(
    proposal: EvidenceReconstructionProposal, field: str, choice: str
) -> EvidenceReconstructionProposal:
    if proposal.created_draft_id is not None:
        raise ValueError("a draft has already been created from this proposal")
    current = next((item for item in proposal.fields if item.field == field), None)
    if current is None or not current.options:
        raise ValueError("field has no human resolution options")
    option = next((item for item in current.options if item.key == choice), None)
    if option is None:
        raise ValueError("choice must be one of the field's options")
    updated = replace(
        current,
        value=option.value,
        state="HUMAN_RESOLVED",
        contributing_source_ids=option.source_ids,
    )
    return replace(
        proposal,
        fields=tuple(updated if item.field == field else item for item in proposal.fields),
    )


def to_draft(proposal: EvidenceReconstructionProposal) -> TrainingEventDraft:
    if any(item.state == "UNRESOLVED" for item in proposal.fields):
        raise ValueError("human resolution is required for conflicting fields")
    values = {item.field: item.value for item in proposal.fields}
    members: dict[str, list[dict[str, str]]] = {}
    for field, value in values.items():
        if field.startswith("member:") and value is not None:
            name, position = value
            members.setdefault(name, []).append(
                {"person_id": field.removeprefix("member:"), "position": position}
            )
    source = next(
        item
        for item in proposal.comparison.sources
        if item.draft.weapon_system_id == values["weapon_system_id"]
    )
    return TrainingEventDraft.model_validate(
        {
            **{
                key: values[key]
                for key in (
                    "event_date",
                    "event_type",
                    "training_context",
                    "weapon_system_id",
                    "location_unit",
                )
            },
            "weapon_name": source.draft.weapon_name,
            "crews": [
                {
                    "crew_name": name,
                    "members": crew_members,
                    "physical_event_count": values[f"count:{name}"],
                }
                for name, crew_members in sorted(members.items())
            ],
        }
    )


def creation_block_reason(
    proposal: EvidenceReconstructionProposal, sources: Sequence[TrainingEvent]
) -> str | None:
    if any(source.reconstructed_from for source in sources):
        return "A reconstruction cannot be a source"
    if any(item.state == "UNRESOLVED" for item in proposal.fields):
        return "Resolve conflicting fields before creating a training draft."
    by_id = {source.event_id: source for source in sources}
    if any(source_id not in by_id for source_id in proposal.source_ids):
        return "A source record is no longer available."
    if any(by_id[source_id].status == EventStatus.APPROVED for source_id in proposal.source_ids):
        return "An approved source is already recorded; this proposal remains session-only."
    if any(by_id[source_id].status != EventStatus.DRAFT for source_id in proposal.source_ids):
        return "Every source must still be a draft."
    if any(by_id[source.event_id] != source for source in proposal.comparison.sources):
        return "Source records changed; review a fresh comparison."
    return None


def can_create_draft(
    proposal: EvidenceReconstructionProposal, sources: Sequence[TrainingEvent]
) -> bool:
    return creation_block_reason(proposal, sources) is None


@dataclass(frozen=True)
class EvidenceFinding:
    code: str
    source_ids: tuple[str, ...]
    on_date: date
    message: str
    person_id: str | None = None


def verification_queue(
    sources: Sequence[TrainingEvent], analysis_as_of: date, person_ids: Sequence[str] = ()
) -> list[EvidenceFinding]:
    sources = [
        source
        for source in sources
        if source.status != EventStatus.REJECTED and source.draft.event_date <= analysis_as_of
    ]
    findings = []
    for candidate in possible_shared_events(sources):
        pair = [source for source in sources if source.event_id in candidate.source_ids]
        comparison = compare_sources(*pair)
        for row in comparison.rows:
            if row.finding_code:
                findings.append(
                    EvidenceFinding(
                        row.finding_code, candidate.source_ids, pair[0].draft.event_date, row.label
                    )
                )
        findings.append(
            EvidenceFinding(
                "POSSIBLE_SHARED_EVENT",
                candidate.source_ids,
                pair[0].draft.event_date,
                "Possible shared event — not confirmed",
            )
        )
    approved = [source for source in sources if source.status == EventStatus.APPROVED]
    for source in approved:
        if source.draft.event_date > analysis_as_of - timedelta(days=365):
            for crew in source.draft.crews:
                if crew.physical_event_count is None:
                    findings.append(
                        EvidenceFinding(
                            "UNKNOWN_ACTIVITY_COUNT",
                            (source.event_id,),
                            source.draft.event_date,
                            f"{crew.crew_name}: activity count Unknown",
                        )
                    )
    people = set(person_ids) or {person for source in approved for person in participants(source)}
    for person_id in sorted(people):
        history = [
            source
            for source in approved
            if person_id in participants(source) and source.draft.weapon_system_id == "m142-himars"
        ]
        days = {source.draft.event_date for source in history}
        recent = {day for day in days if day > analysis_as_of - timedelta(days=365)}
        if len(recent) <= 1 or not days or min(days) > analysis_as_of - timedelta(days=365):
            findings.append(
                EvidenceFinding(
                    "INSUFFICIENT_APPLICABLE_HISTORY",
                    tuple(sorted(s.event_id for s in history)),
                    max(days) if days else analysis_as_of,
                    "Insufficient applicable recorded history for the comparison.",
                    person_id,
                )
            )
    priority = {
        "CONFLICTING_ACTIVITY_COUNT": 0,
        "CONFLICTING_PARTICIPANT_ROLE": 0,
        "UNKNOWN_ACTIVITY_COUNT": 1,
        "POSSIBLE_SHARED_EVENT": 2,
        "INSUFFICIENT_APPLICABLE_HISTORY": 3,
    }
    return sorted(
        findings,
        key=lambda item: (
            priority[item.code],
            -item.on_date.toordinal(),
            item.source_ids,
            item.person_id or "",
            item.message,
        ),
    )
