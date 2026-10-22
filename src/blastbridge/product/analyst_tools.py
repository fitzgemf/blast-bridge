"""Context-bound evidence access and native training-draft initiation."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable, MutableMapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import date, timedelta
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from blastbridge.models.reference import CanonicalWeapon

from . import agent, store
from .agent import IntakeProvider, IntakeResult
from .evidence import (
    Comparison,
    EvidenceReconstructionProposal,
    SharedEventCandidate,
    compare_sources,
    participants,
    possible_shared_events,
    prepare_reconstruction,
    verification_queue,
)
from .followup import SOURCES, FollowUpState, evaluate
from .models import (
    EventStatus,
    HistoryEntry,
    IntakeSource,
    Person,
    TrainingEvent,
    TrainingEventDraft,
)
from .models import provenance_text as record_provenance
from .patterns import (
    FEATURE_LABELS,
    FEATURE_NAMES,
    PATTERN_DISCLAIMER,
    REFERENCE_LABEL,
    PatternModel,
    PatternStatus,
    assess_pattern,
    occupational_features,
)
from .readiness import ATTENTION_PRECEDENCE, ReadinessAssessment, assess_readiness
from .symptoms import (
    DangerSign,
    FunctionalImpact,
    Persistence,
    Symptom,
    SymptomReport,
    SymptomSource,
    TemporalRelationship,
)


@dataclass(frozen=True)
class AgentContext:
    analysis_as_of: date
    reference_date: date
    selected_person_id: str | None = None
    selected_calendar_date: date | None = None
    page: Literal["home", "person"] = "home"
    prior_analysis_stale: bool = False

    def render(self) -> str:
        return "Application context\n" + canonical_json(asdict(self))


@dataclass(frozen=True)
class AnalystData:
    people: Sequence[Person]
    member_history: Callable[[str], Sequence[HistoryEntry]]
    symptom_reports: Callable[[str], Sequence[SymptomReport]]
    pattern_model: PatternModel | None
    catalog: Sequence[CanonicalWeapon]
    save_draft: Callable[[TrainingEventDraft, IntakeSource], str]
    events: Callable[[], Sequence[TrainingEvent]] = field(default=lambda: ())

    @classmethod
    def from_connection(
        cls,
        conn: sqlite3.Connection,
        pattern_model: PatternModel | None,
        catalog: Sequence[CanonicalWeapon],
    ) -> AnalystData:
        return cls(
            people=store.list_people(conn),
            member_history=lambda person_id: store.member_history(conn, person_id),
            symptom_reports=lambda person_id: store.list_symptom_reports(conn, person_id),
            pattern_model=pattern_model,
            catalog=catalog,
            save_draft=lambda draft, source: store.save_draft(conn, draft, intake_source=source),
            events=lambda: [
                *store.list_events(conn, EventStatus.DRAFT, limit=-1),
                *store.list_events(conn, EventStatus.APPROVED, limit=-1),
            ],
        )


@dataclass(frozen=True)
class ConversationTurn:
    role: Literal["user", "assistant"]
    text: str
    utterance_id: str | None = None


@dataclass
class Conversation:
    conversation_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    pending_clarification: str | None = None
    current_action_key: str | None = None
    next_user_number: int = 1

    def add_user(self, text: str) -> str:
        utterance_id = f"U{self.next_user_number}"
        self.next_user_number += 1
        self.turns.append(ConversationTurn("user", text, utterance_id))
        self._bound()
        return utterance_id

    def add_assistant(self, summary: str, clarification: str | None) -> None:
        self.pending_clarification = clarification
        text = summary + ("\n" + clarification if clarification else "")
        self.turns.append(ConversationTurn("assistant", text))
        self._bound()

    def _bound(self) -> None:
        counts = {"user": 0, "assistant": 0}
        kept = []
        for turn in reversed(self.turns):
            counts[turn.role] += 1
            if counts[turn.role] <= 6:
                kept.append(turn)
        self.turns[:] = reversed(kept)


@dataclass(frozen=True)
class CreatedDraft:
    kind: Literal["review", "proposed", "needs_review"]
    action_key: str
    status: str
    review_destination: str
    event_id: str | None = None
    resolved: dict[str, Any] = field(default_factory=dict)
    unresolved: tuple[str, ...] = ()
    issues: tuple[dict[str, Any], ...] = ()
    provenance: dict[str, str] = field(default_factory=dict)
    intake_result: IntakeResult | None = None
    recovered: bool = False

    def payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "action_key": self.action_key,
            "event_id": self.event_id,
            "status": self.status,
            "resolved": self.resolved,
            "unresolved": self.unresolved,
            "issues": self.issues,
            "provenance": self.provenance,
            "review_destination": self.review_destination,
            "recovered": self.recovered,
        }


@dataclass
class ActionEntry:
    state: Literal["running", "draft_saved", "proposed", "failed"]
    outcome: CreatedDraft | None = None
    error: str | None = None
    conversation_id: str | None = None
    superseded: bool = False


@dataclass(frozen=True)
class SymptomProposal:
    person_id: str
    event_id: str | None = None
    report_date: date | None = None
    symptoms: tuple[Symptom, ...] = ()
    danger_signs: tuple[DangerSign, ...] = ()
    temporal_relationship: TemporalRelationship | None = None
    persistence: Persistence | None = None
    functional_impact: FunctionalImpact | None = None
    source: SymptomSource | None = None
    note: str | None = None
    source_utterance_ids: tuple[str, ...] = ()
    dropped: tuple[str, ...] = ()

    def missing(self) -> list[str]:
        fields = (
            ("report date", self.report_date),
            ("relationship to a recorded event", self.temporal_relationship),
            ("persistence", self.persistence),
            ("functional impact", self.functional_impact),
            ("source", self.source),
        )
        missing = [name for name, value in fields if value is None]
        if not self.symptoms and not self.danger_signs:
            missing.append("symptoms")
        return missing

    def payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = json.loads(canonical_json(asdict(self)))
        return payload


type ActionLedger = MutableMapping[str, ActionEntry]


@dataclass(frozen=True)
class ToolTrace:
    tool: str
    input: dict[str, Any]
    summary: str
    ok: bool
    scope: Literal["outer", "nested", "validation", "rendering"] = "outer"
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Evidence:
    ref: str
    person_id: str | None
    kind: str
    payload: dict[str, Any]
    recorded_date: date | None = None


class PersonInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    person_id: str = Field(min_length=1)


class EmptyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    utterance_ids: list[str] = Field(min_length=1, max_length=6)


class SymptomProposalInput(PersonInput):
    utterance_ids: list[str] = Field(min_length=1)
    event_id: str | None = None
    report_date: date | None = None
    symptoms: list[Symptom] = Field(default_factory=list)
    danger_signs: list[DangerSign] = Field(default_factory=list)
    temporal_relationship: TemporalRelationship | None = None
    persistence: Persistence | None = None
    functional_impact: FunctionalImpact | None = None
    source: SymptomSource | None = None
    note: str | None = None


class EvidenceScopeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    person_id: str | None = None


class EventPairInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    event_ids: list[str] = Field(min_length=2, max_length=2)


READ_TOOLS = (
    "get_person_record",
    "get_pattern_assessment",
    "get_symptom_history",
    "get_followup_assessment",
    "audit_record_quality",
)
_TOOL_INPUTS: list[tuple[str, str, type[BaseModel]]] = [
    (name, name.replace("_", " ") + " at application analysis date", PersonInput)
    for name in READ_TOOLS
]
_TOOL_INPUTS.extend(
    [
        ("get_attention_queue", "Existing readiness precedence; no new score", EmptyInput),
        (
            "create_training_event_draft",
            "Only when asked to log an event: reuse intake on exact stored user utterances",
            DraftInput,
        ),
        (
            "prepare_symptom_report",
            "Only when asked to log/record a symptom: structure ONLY facts the user explicitly "
            "stated into a session proposal for the existing symptom form; never persists",
            SymptomProposalInput,
        ),
        ("find_evidence_issues", "Ordered evidence verification findings", EvidenceScopeInput),
        (
            "find_possible_shared_events",
            "Conservative possible shared events, never confirmed matches",
            EvidenceScopeInput,
        ),
        ("compare_event_evidence", "Compare two recorded sources field by field", EventPairInput),
        (
            "prepare_reconstruction_proposal",
            "Session-only reconstruction of a surfaced candidate; humans resolve conflicts",
            EventPairInput,
        ),
    ]
)


def _without_max_items(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_max_items(item)
            for key, item in value.items()
            if key != "maxItems" and not (key == "minItems" and item > 1)
        }
    if isinstance(value, list):
        return [_without_max_items(item) for item in value]
    return value


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": _without_max_items(schema.model_json_schema()),
    }
    for name, description, schema in _TOOL_INPUTS
]


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def readiness_for(person_id: str, context: AgentContext, data: AnalystData) -> ReadinessAssessment:
    entries = visible_history(person_id, context, data)
    reports = visible_reports(person_id, context, data)
    pattern = assess_pattern(data.pattern_model, entries, context.analysis_as_of)
    return assess_readiness(person_id, entries, reports, pattern, context.analysis_as_of)


def visible_history(person_id: str, context: AgentContext, data: AnalystData) -> list[HistoryEntry]:
    return sorted(
        (
            entry
            for entry in data.member_history(person_id)
            if entry.event_date <= context.analysis_as_of
        ),
        key=lambda entry: (entry.event_date, entry.event_id, entry.crew_name, entry.position),
    )


def visible_reports(
    person_id: str, context: AgentContext, data: AnalystData
) -> list[SymptomReport]:
    return sorted(
        (
            report
            for report in data.symptom_reports(person_id)
            if report.draft.person_id == person_id
            and report.draft.report_date <= context.analysis_as_of
        ),
        key=lambda report: (report.draft.report_date, report.report_id),
    )


def evidence_fingerprint(person_id: str, context: AgentContext, data: AnalystData) -> str:
    assessment = readiness_for(person_id, context, data)
    content = {
        "person_id": person_id,
        "analysis_as_of": context.analysis_as_of,
        "records": [
            entry.model_dump(mode="json") for entry in visible_history(person_id, context, data)
        ],
        "reports": [
            report.model_dump(mode="json") for report in visible_reports(person_id, context, data)
        ],
        "pattern": assessment.ml_pattern.status if assessment.ml_pattern else None,
        "followup": assessment.symptom_followup_status,
    }
    return sha256(canonical_json(content).encode()).hexdigest()


def action_key(conversation_id: str, utterance_ids: Sequence[str]) -> str:
    return sha256((conversation_id + "|" + ",".join(utterance_ids)).encode()).hexdigest()[:16]


def returned_refs(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        refs = [payload["evidence_ref"]] if "evidence_ref" in payload else []
        for value in payload.values():
            refs.extend(returned_refs(value))
        return list(dict.fromkeys(refs))
    if isinstance(payload, (list, tuple)):
        return list(dict.fromkeys(ref for item in payload for ref in returned_refs(item)))
    return []


def tool_summary(name: str, payload: dict[str, Any]) -> str:
    if name == "get_person_record":
        count = len(payload["records"])
        return f"{count} {'record' if count == 1 else 'records'} reviewed"
    if name == "get_pattern_assessment":
        return PatternStatus(payload["status"]).label
    if name == "get_symptom_history":
        count = len(payload["reports"])
        return f"{count} {'report' if count == 1 else 'reports'} reviewed"
    if name == "get_followup_assessment":
        return FollowUpState(payload["state"]).label if payload["state"] else "no reports"
    if name == "audit_record_quality":
        count = len(payload["issues"])
        return (
            f"{count} {'item' if count == 1 else 'items'} worth reviewing"
            if count
            else "no material issue identified"
        )
    if name == "get_attention_queue":
        count = len(payload["people"])
        return f"{count} {'person' if count == 1 else 'people'}"
    if name == "prepare_symptom_report":
        return "session proposal prepared for human review"
    if name in ("find_evidence_issues", "find_possible_shared_events"):
        return f"{len(payload['items'])} evidence workflow items"
    if name in ("compare_event_evidence", "prepare_reconstruction_proposal"):
        return "source comparison prepared for human review"
    return str(payload["status"])


def _event_identified(event: HistoryEntry, utterances: list[str], context: AgentContext) -> bool:
    if event.event_date == context.selected_calendar_date:
        return True
    day = f"0?{event.event_date.day}"
    months = (event.event_date.strftime("%b"), event.event_date.strftime("%B"))
    dates = [rf"\b(?:{day}\s+{month}|{month}\s+{day})\b" for month in months]
    return any(
        event.event_id in text
        or event.event_date.isoformat() in text
        or any(re.search(pattern, text, re.IGNORECASE) for pattern in dates)
        for text in utterances
    )


@dataclass
class ToolSession:
    context: AgentContext
    data: AnalystData
    intake_provider: IntakeProvider
    conversation: Conversation
    ledger: ActionLedger
    evidence: dict[str, list[Evidence]] = field(default_factory=dict)
    trace: list[ToolTrace] = field(default_factory=list)
    created_draft: CreatedDraft | None = None
    symptom_proposal: SymptomProposal | None = None
    outer_calls: int = 0
    nested_model_calls: int = 0
    nested_tool_calls: int = 0
    draft_action_called: bool = False
    recovered_conversation: bool = False
    symptom_action_called: bool = False
    reconstructions: MutableMapping[str, EvidenceReconstructionProposal] = field(
        default_factory=dict
    )
    reconstruction: EvidenceReconstructionProposal | None = None
    comparisons: dict[str, Comparison] = field(default_factory=dict)
    candidates: dict[str, SharedEventCandidate] = field(default_factory=dict)

    def register(
        self,
        ref: str,
        person_id: str | None,
        kind: str,
        payload: dict[str, Any],
        recorded_date: date | None = None,
    ) -> dict[str, Any]:
        payload = {"evidence_ref": ref, **payload}
        self.evidence.setdefault(ref, []).append(
            Evidence(ref, person_id, kind, payload, recorded_date)
        )
        return payload

    def execute(self, name: str, arguments: Any) -> tuple[dict[str, Any], bool]:
        self.outer_calls += 1
        safe_input = arguments if isinstance(arguments, dict) else {}
        try:
            if name == "create_training_event_draft" and self.draft_action_called:
                raise ValueError("one draft action per request")
            if name == "prepare_symptom_report" and self.symptom_action_called:
                raise ValueError("one symptom proposal per request")
            if self.outer_calls > 8:
                raise ValueError("tool budget exhausted")
            if name in READ_TOOLS:
                parsed = PersonInput.model_validate(arguments)
                person = next(
                    (person for person in self.data.people if person.person_id == parsed.person_id),
                    None,
                )
                if person is None:
                    raise ValueError("unknown person_id")
                payload = self.read(name, person)
            elif name == "get_attention_queue":
                EmptyInput.model_validate(arguments)
                payload = self.attention()
            elif name == "create_training_event_draft":
                draft_input = DraftInput.model_validate(arguments)
                # Spent only by a well-formed call within budget; a rejected call can be retried.
                self.draft_action_called = True
                payload = self.create_draft(draft_input.utterance_ids)
            elif name == "prepare_symptom_report":
                proposal_input = SymptomProposalInput.model_validate_json(canonical_json(arguments))
                self.symptom_action_called = True
                payload = self.prepare_symptom_report(proposal_input)
            elif name in ("find_evidence_issues", "find_possible_shared_events"):
                scope = EvidenceScopeInput.model_validate(arguments)
                payload = self.evidence_findings(name, scope.person_id)
            elif name in ("compare_event_evidence", "prepare_reconstruction_proposal"):
                pair = EventPairInput.model_validate(arguments)
                payload = self.compare_evidence(name, pair.event_ids)
            else:
                raise ValueError("unknown tool")
        except (ValidationError, ValueError, store.StoreError, sqlite3.Error) as exc:
            message = "invalid tool input" if isinstance(exc, ValidationError) else str(exc)
            self.trace.append(ToolTrace(name, safe_input, message, False))
            return {"untrusted_record_data": {"error": message}}, True
        self.trace.append(
            ToolTrace(
                name,
                safe_input,
                "existing draft for this conversation"
                if name == "create_training_event_draft" and self.recovered_conversation
                else tool_summary(name, payload),
                True,
                evidence_refs=tuple(returned_refs(payload)),
            )
        )
        return {"untrusted_record_data": payload}, False

    def evidence_sources(self) -> list[TrainingEvent]:
        return [
            source
            for source in self.data.events()
            if source.status != EventStatus.REJECTED
            and source.draft.event_date <= self.context.analysis_as_of
        ]

    def evidence_findings(self, name: str, person_id: str | None) -> dict[str, Any]:
        if person_id is not None and not any(p.person_id == person_id for p in self.data.people):
            raise ValueError("unknown person_id")
        sources = self.evidence_sources()
        candidates = possible_shared_events(sources)
        if person_id is not None:
            involved = {source.event_id for source in sources if person_id in participants(source)}
            candidates = [
                candidate for candidate in candidates if involved.intersection(candidate.source_ids)
            ]
        self.candidates.update({candidate.key: candidate for candidate in candidates})
        if name == "find_possible_shared_events":
            return {
                "items": [
                    self.register(
                        f"candidate:{candidate.key}", None, "candidate", asdict(candidate)
                    )
                    for candidate in candidates
                ]
            }
        findings = verification_queue(
            sources,
            self.context.analysis_as_of,
            [person_id] if person_id is not None else [p.person_id for p in self.data.people],
        )
        if person_id is not None:
            findings = [
                finding
                for finding in findings
                if finding.person_id == person_id or involved.intersection(finding.source_ids)
            ]
        return {
            "items": [
                self.register(
                    f"finding:{finding.code}:{'+'.join(finding.source_ids) or finding.person_id}",
                    None,
                    "finding",
                    asdict(finding),
                )
                for finding in findings
            ]
        }

    def compare_evidence(self, name: str, event_ids: list[str]) -> dict[str, Any]:
        by_id = {source.event_id: source for source in self.evidence_sources()}
        if len(set(event_ids)) != 2 or any(event_id not in by_id for event_id in event_ids):
            raise ValueError("two existing non-rejected source records are required")
        comparison = compare_sources(by_id[event_ids[0]], by_id[event_ids[1]])
        candidate = next(
            (
                item
                for item in possible_shared_events(comparison.sources)
                if item.key == comparison.key
            ),
            None,
        )
        if (
            name == "prepare_reconstruction_proposal"
            and comparison.key not in self.candidates
            and comparison.key not in self.reconstructions
        ):
            raise ValueError("surface the possible shared event candidate first")
        if name == "prepare_reconstruction_proposal" and candidate is None:
            raise ValueError("source records no longer form a possible shared event candidate")
        self.comparisons[comparison.key] = comparison
        for source in comparison.sources:
            self.register(
                f"source:{source.event_id}", None, "source", source.model_dump(mode="json")
            )
        comparison_payload = {
            "source_ids": comparison.source_ids,
            "sources": [source.model_dump(mode="json") for source in comparison.sources],
            "rows": [asdict(row) for row in comparison.rows],
        }
        compared = self.register(
            f"comparison:{comparison.key}", None, "comparison", comparison_payload
        )
        if name != "prepare_reconstruction_proposal":
            return compared
        proposal = self.reconstructions.get(comparison.key)
        if proposal is None:
            proposal = prepare_reconstruction(comparison)
            self.reconstructions[comparison.key] = proposal
        self.reconstruction = proposal
        proposal_payload = {
            "key": proposal.key,
            "source_ids": proposal.source_ids,
            "fields": [asdict(item) for item in proposal.fields],
            "created_draft_id": proposal.created_draft_id,
            "comparison": comparison_payload,
        }
        return self.register(
            f"reconstruction:{proposal.key}", None, "reconstruction", proposal_payload
        )

    def prepare_symptom_report(self, values: SymptomProposalInput) -> dict[str, Any]:
        if not any(person.person_id == values.person_id for person in self.data.people):
            raise ValueError("unknown person_id")
        turns = [
            turn
            for turn in self.conversation.turns
            if turn.role == "user" and turn.utterance_id in values.utterance_ids
        ]
        ids = tuple(turn.utterance_id for turn in turns if turn.utterance_id is not None)
        if len(set(values.utterance_ids)) != len(values.utterance_ids):
            raise ValueError("duplicate utterance ids")
        if set(ids) != set(values.utterance_ids):
            raise ValueError("unknown user utterance ids")
        dropped = []
        report_date = values.report_date
        if report_date is not None and report_date > self.context.analysis_as_of:
            report_date = None
            dropped.append("Report date not kept: after the analysis date")
        event_id = values.event_id
        if event_id is not None:
            event = next(
                (
                    entry
                    for entry in self.data.member_history(values.person_id)
                    if entry.event_id == event_id
                ),
                None,
            )
            if event is None or event.event_date > (report_date or self.context.analysis_as_of):
                event_id = None
                dropped.append(
                    "Event link not kept: not an eligible recorded event for this person"
                )
            elif not _event_identified(event, [turn.text for turn in turns], self.context):
                event_id = None
                dropped.append("Event link not kept: not explicitly identified")
        relationship = values.temporal_relationship
        if (relationship == TemporalRelationship.AFTER_RECORDED_EVENT and event_id is None) or (
            relationship == TemporalRelationship.NOT_LINKED_TO_EVENT and event_id is not None
        ):
            relationship = None
            dropped.append("Event relationship not kept: inconsistent with the retained event link")
        note = values.note.strip() if values.note is not None else None
        if note is not None and (len(note) > 500 or not any(note in turn.text for turn in turns)):
            note = None
            dropped.append("Note not kept: must be verbatim user text of at most 500 characters")
        self.symptom_proposal = SymptomProposal(
            person_id=values.person_id,
            event_id=event_id,
            report_date=report_date,
            symptoms=tuple(values.symptoms),
            danger_signs=tuple(values.danger_signs),
            temporal_relationship=relationship,
            persistence=values.persistence,
            functional_impact=values.functional_impact,
            source=values.source,
            note=note,
            source_utterance_ids=ids,
            dropped=tuple(dropped),
        )
        return self.register(
            f"symptom_proposal:{values.person_id}",
            values.person_id,
            "symptom_proposal",
            self.symptom_proposal.payload(),
        )

    def read(self, name: str, person: Person) -> dict[str, Any]:
        person_id = person.person_id
        entries = visible_history(person_id, self.context, self.data)
        reports = visible_reports(person_id, self.context, self.data)
        if name == "get_person_record":
            records = [self.record(person_id, entry) for entry in entries]
            features = occupational_features(
                (entry.event_date for entry in entries), self.context.analysis_as_of
            )
            facts = self.register(
                f"facts:{person_id}",
                person_id,
                "facts",
                {
                    "scope": "all recorded occupational events",
                    "features": [
                        {"label": FEATURE_LABELS[key], "value": value}
                        for key, value in zip(FEATURE_NAMES, features, strict=True)
                    ],
                },
            )
            identity = self.register(
                f"person:{person_id}",
                person_id,
                "person",
                {
                    key: value
                    for key, value in person.model_dump(mode="json").items()
                    if key != "home_position"
                },
            )
            return {"person": identity, "records": records, "facts": facts}
        if name == "get_symptom_history":
            return {"reports": [self.report(person_id, report) for report in reports]}
        assessment = readiness_for(person_id, self.context, self.data)
        if name == "get_pattern_assessment":
            pattern = assessment.ml_pattern
            assert pattern is not None
            return self.register(
                f"pattern:{person_id}",
                person_id,
                "pattern",
                {
                    "status": pattern.status.value,
                    "reason": pattern.reason,
                    "elevated_features": [FEATURE_LABELS[key] for key in pattern.elevated_features],
                    "differing": [asdict(comparison) for comparison in pattern.differing],
                    "reference_label": REFERENCE_LABEL,
                    "scope_note": "HIMARS occupational dates only; symptoms and counts excluded",
                    "excluded_non_scope_records": pattern.excluded_non_scope_records,
                    "readiness_status": assessment.overall_readiness_status.value,
                    "readiness_label": assessment.overall_readiness_status.label,
                    "disclaimer": PATTERN_DISCLAIMER,
                },
            )
        if name == "get_followup_assessment":
            details = []
            for report in reports:
                result = evaluate(report.draft)
                details.append(
                    self.register(
                        report.report_id,
                        person_id,
                        "report_guidance",
                        {
                            "date": report.draft.report_date.isoformat(),
                            "state": result.state.value,
                            "headline": result.headline,
                            "explanation": result.explanation,
                            "source_titles": [
                                source.title
                                for source in SOURCES
                                if source.key in result.source_keys
                            ],
                        },
                        report.draft.report_date,
                    )
                )
            followup = assessment.symptom_followup_status
            return self.register(
                f"followup:{person_id}",
                person_id,
                "followup",
                {
                    "state": followup.value if followup else None,
                    "label": followup.label if followup else None,
                    "readiness_status": assessment.overall_readiness_status.value,
                    "readiness_label": assessment.overall_readiness_status.label,
                    "urgent": assessment.urgent_status,
                    "evidence_lines": assessment.evidence_lines,
                    "reports": details,
                },
            )
        return self.audit(person_id, entries, assessment)

    def record(self, person_id: str, entry: HistoryEntry) -> dict[str, Any]:
        return self.register(
            entry.event_id,
            person_id,
            "record",
            {
                "event_id": entry.event_id,
                "date": entry.event_date.isoformat(),
                "weapon_system_id": entry.weapon_system_id,
                "weapon_name": entry.weapon_name,
                "event_type": entry.event_type.value,
                "training_context": entry.training_context.value,
                "crew_name": entry.crew_name,
                "role": entry.position.label,
                "activity_count": (
                    entry.physical_event_count
                    if entry.physical_event_count is not None
                    else "Unknown"
                ),
                "location_unit": entry.location_unit,
                "provenance": record_provenance(entry.intake_source, EventStatus.APPROVED),
            },
            entry.event_date,
        )

    def report(self, person_id: str, report: SymptomReport) -> dict[str, Any]:
        draft = report.draft
        return self.register(
            report.report_id,
            person_id,
            "report",
            {
                "report_id": report.report_id,
                "date": draft.report_date.isoformat(),
                "source": draft.source.label,
                "symptoms": [symptom.label for symptom in draft.symptoms],
                "danger_signs": [sign.label for sign in draft.danger_signs],
                "temporal_relationship": draft.temporal_relationship.label,
                "persistence": draft.persistence.label,
                "functional_impact": draft.functional_impact.label,
                "note": draft.note,
            },
            draft.report_date,
        )

    def audit(
        self, person_id: str, entries: Sequence[HistoryEntry], assessment: ReadinessAssessment
    ) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        for entry in entries:
            if entry.physical_event_count is None:
                self.record(person_id, entry)
                issues.append(
                    {
                        "code": "UNKNOWN_ACTIVITY_COUNT",
                        "event_ref": entry.event_id,
                        "crew": entry.crew_name,
                        "date": entry.event_date.isoformat(),
                    }
                )
        days = {
            entry.event_date
            for entry in entries
            if entry.event_date > self.context.analysis_as_of - timedelta(days=365)
        }
        pattern = assessment.ml_pattern
        history_reason = (
            pattern is not None
            and pattern.status is PatternStatus.PATTERN_NOT_AVAILABLE
            and pattern.reason
            in (
                "recorded history shorter than the 365-day comparison window",
                "no HIMARS record in the prior 365 days",
                "outside the HIMARS prototype scope",
            )
        )
        if len(days) <= 1 or history_reason:
            issues.append({"code": "INSUFFICIENT_APPLICABLE_HISTORY"})
        return {
            "issues": [
                self.register(f"audit:{person_id}:{i}", person_id, "issue", issue)
                for i, issue in enumerate(issues, 1)
            ],
            "data_quality": self.register(
                f"quality:{person_id}",
                person_id,
                "quality",
                {
                    "notes": assessment.data_quality_notes,
                    "empty_audit_wording": (
                        "No material issue was identified in the evidence reviewed."
                        if not issues
                        else None
                    ),
                },
            ),
        }

    def attention(self) -> dict[str, Any]:
        rows = [
            (person, readiness_for(person.person_id, self.context, self.data))
            for person in self.data.people
        ]
        rows = [
            (person, assessment)
            for person, assessment in rows
            if assessment.overall_readiness_status in ATTENTION_PRECEDENCE
        ]
        rows.sort(
            key=lambda row: (
                ATTENTION_PRECEDENCE[row[1].overall_readiness_status],
                row[0].display_name,
            )
        )
        return {
            "people": [
                self.register(
                    f"attention:{person.person_id}",
                    person.person_id,
                    "attention",
                    {
                        "person_id": person.person_id,
                        "display_name": person.display_name,
                        "readiness_status": assessment.overall_readiness_status.value,
                        "status_label": assessment.overall_readiness_status.label,
                        "reason": assessment.evidence_lines,
                    },
                )
                for person, assessment in rows
            ]
        }

    def create_draft(self, utterance_ids: list[str]) -> dict[str, Any]:
        existing_key = self.conversation.current_action_key
        locked = [
            (key, entry)
            for key, entry in self.ledger.items()
            if (entry.conversation_id == self.conversation.conversation_id or key == existing_key)
            and entry.state in ("draft_saved", "running")
        ]
        if locked:
            key, locked_entry = locked[0]
            return self.recover_action(key, locked_entry)
        if len(set(utterance_ids)) != len(utterance_ids):
            raise ValueError("duplicate utterance ids")
        turns = [
            turn
            for turn in self.conversation.turns
            if turn.role == "user" and turn.utterance_id in utterance_ids
        ]
        ordered_ids = [turn.utterance_id for turn in turns if turn.utterance_id is not None]
        if set(ordered_ids) != set(utterance_ids):
            raise ValueError("unknown user utterance ids")
        key = action_key(self.conversation.conversation_id, ordered_ids)
        prior = self.ledger.get(key)
        if prior is not None and prior.state in ("draft_saved", "running"):
            return self.recover_action(key, prior)
        if prior is not None and prior.state == "proposed" and not prior.superseded:
            assert prior.outcome is not None
            self.conversation.current_action_key = key
            self.created_draft = replace(prior.outcome, recovered=True)
        else:
            if existing_key is not None and existing_key != key:
                previous = self.ledger.get(existing_key)
                if previous is not None and previous.state == "proposed":
                    previous.superseded = True
            self.conversation.current_action_key = key
            self.ledger[key] = ActionEntry(
                "running", conversation_id=self.conversation.conversation_id
            )
            try:
                result = agent.run_intake(
                    "\n".join(turn.text for turn in turns),
                    self.intake_provider,
                    self.data.catalog,
                    self.data.people,
                    today=self.context.reference_date,
                )
            except Exception:
                self.ledger[key] = ActionEntry(
                    "failed",
                    error="Intake failed before saving",
                    conversation_id=self.conversation.conversation_id,
                )
                raise ValueError("Intake failed before saving") from None
            self.nested_model_calls += result.model_calls
            self.nested_tool_calls += sum(
                block.get("type") == "tool_use" for turn in result.turns for block in turn["blocks"]
            )
            self.trace.extend(
                ToolTrace("intake", {}, step.text, step.ok, "nested") for step in result.trace
            )
            for turn in result.turns:
                for block in turn["blocks"]:
                    if block.get("type") == "tool_use":
                        self.trace.append(
                            ToolTrace(
                                str(block.get("name")),
                                block.get("input", {}),
                                "Nested intake lookup",
                                True,
                                "nested",
                            )
                        )
            if result.error:
                self.ledger[key] = ActionEntry(
                    "failed", error=result.error, conversation_id=self.conversation.conversation_id
                )
                raise ValueError("Intake failed: " + result.error)
            event_id = None
            if result.draft is not None:
                source = (
                    IntakeSource.AI_REPLAY
                    if self.intake_provider.name != "live"
                    else IntakeSource.AI_LIVE
                )
                try:
                    event_id = self.data.save_draft(result.draft, source)
                except (store.StoreError, sqlite3.Error) as exc:
                    # The save transaction rolled back, so nothing was written.
                    self.ledger[key] = ActionEntry(
                        "failed",
                        error="Draft was not saved",
                        conversation_id=self.conversation.conversation_id,
                    )
                    raise ValueError(f"Draft was not saved: {exc}") from None
                except Exception:
                    raise ValueError(
                        "Save outcome uncertain; needs review in Review queue"
                    ) from None
            outcome = CreatedDraft(
                kind="review" if event_id else "proposed",
                action_key=key,
                status="draft — awaiting human review" if event_id else "proposed — needs review",
                review_destination=f"review:{event_id}" if event_id else f"proposed:{key}",
                event_id=event_id,
                resolved=result.form_values,
                unresolved=tuple(result.proposal.unresolved) if result.proposal else (),
                issues=tuple(asdict(issue) for issue in result.issues),
                provenance=result.origins,
                intake_result=result,
            )
            self.ledger[key] = ActionEntry(
                "draft_saved" if event_id else "proposed",
                outcome,
                conversation_id=self.conversation.conversation_id,
            )
            self.created_draft = outcome
        assert self.created_draft is not None
        return self.register(f"draft:{key}", None, "draft", self.created_draft.payload())

    def recover_action(self, key: str, entry: ActionEntry) -> dict[str, Any]:
        self.conversation.current_action_key = key
        self.recovered_conversation = True
        if entry.state == "draft_saved":
            assert entry.outcome is not None
            self.created_draft = replace(entry.outcome, recovered=True)
        else:
            self.created_draft = CreatedDraft(
                "needs_review",
                key,
                "Needs review in Review queue; do not repeat the action",
                "review",
                recovered=True,
            )
        return self.register(f"draft:{key}", None, "draft", self.created_draft.payload())
