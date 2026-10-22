"""Code-owned citations and source cards from an analysis's captured evidence only."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from .analyst import (
    MEDICAL_HEADINGS,
    AgentResponse,
    Brief,
    EvidenceSection,
    UIAction,
    display_value,
)
from .analyst_tools import Evidence
from .patterns import PatternStatus

# Top-level response sections and the brief headings that already carry the same content.
SUMMARY_SECTIONS: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("What changed", "what_changed", frozenset({"WHAT CHANGED"})),
    ("Why surfaced", "why_surfaced", frozenset({"WHY THIS PERSON WAS SURFACED"})),
    ("Occupational summary", "occupational_summary", frozenset()),
    ("Symptoms & follow-up", "symptom_followup_summary", frozenset(MEDICAL_HEADINGS)),
    ("Evidence quality", "data_quality_summary", frozenset({"EVIDENCE QUALITY"})),
)


def uncovered_summaries(
    response: AgentResponse, brief_view: bool
) -> list[tuple[str, EvidenceSection]]:
    """Top-level sections to show; in the brief view, only those no brief heading carries."""
    headings = (
        {section.heading for section in response.brief.sections}
        if brief_view and response.brief
        else set()
    )
    summaries = []
    for title, attribute, covered_by in SUMMARY_SECTIONS:
        section = getattr(response, attribute)
        if section and not headings & covered_by:
            summaries.append((title, section))
    return summaries


@dataclass(frozen=True)
class Citation:
    number: int
    ref: str
    label: str
    kind: str
    evidence: Evidence | None
    fields: tuple[tuple[str, str], ...] = ()
    lines: tuple[str, ...] = ()
    action: UIAction | None = None


def _text(value: Any) -> str:
    if value is None or value == "":
        return "Unknown"
    if isinstance(value, (str, int, float)):
        return display_value(value)
    return "Unknown"


def _strings(value: Any) -> list[str]:
    return (
        [item for item in value if isinstance(item, str)]
        if isinstance(value, (list, tuple))
        else []
    )


def _day(item: Evidence, key: str = "date") -> str:
    value = item.payload.get(key)
    try:
        return date.fromisoformat(str(value)).strftime("%d %b %Y")
    except ValueError:
        return item.recorded_date.strftime("%d %b %Y") if item.recorded_date else "Date unknown"


def _fields(payload: dict[str, Any], names: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(label, _text(payload.get(key))) for key, label in names]


def _descriptor(
    number: int, ref: str, items: Sequence[Evidence], person_id: str | None
) -> Citation:
    if not items:
        return Citation(number, ref, "Source unavailable in this analysis", "unavailable", None)
    preference = {
        "record": 0,
        "report": 1,
        "facts": 2,
        "pattern": 3,
        "issue": 4,
        "quality": 5,
        "followup": 6,
        "report_guidance": 7,
    }
    item = min(
        items,
        key=lambda entry: (entry.person_id != person_id, preference.get(entry.kind, 8)),
    )
    payload = item.payload
    kind = item.kind
    fields: list[tuple[str, str]] = []
    lines: list[str] = []
    action = None
    scoped_person = item.person_id
    if kind == "record":
        label = f"{_day(item)} · {_text(payload.get('weapon_name'))} · " + _text(
            payload.get("crew_name")
        )
        fields = _fields(
            payload,
            (
                ("date", "Date"),
                ("weapon_name", "Weapon"),
                ("event_type", "Activity"),
                ("training_context", "Training context"),
                ("crew_name", "Crew"),
                ("role", "Role"),
                ("activity_count", "Physical events"),
                ("location_unit", "Location / unit"),
                ("provenance", "Provenance"),
            ),
        )
        event_id = payload.get("event_id")
        if isinstance(event_id, str) and event_id:
            action = UIAction("OPEN_REVIEW", event_id=event_id)
    elif kind == "issue":
        label = "Evidence quality issue"
        if payload.get("code") == "UNKNOWN_ACTIVITY_COUNT":
            label = f"{_day(item)} · {_text(payload.get('crew'))} · Unknown count"
            fields = _fields(payload, (("date", "Date"), ("crew", "Crew")))
            fields.append(("Activity count", "Unknown"))
            lines.append("BlastBridge preserves Unknown rather than treating it as zero.")
        elif payload.get("code") == "INSUFFICIENT_APPLICABLE_HISTORY":
            lines.append("Insufficient applicable recorded history for the comparison.")
        event_ref = payload.get("event_ref")
        if isinstance(event_ref, str) and event_ref:
            action = UIAction("OPEN_REVIEW", event_id=event_ref)
    elif kind == "facts":
        label = "Recorded-history summary"
        fields = _fields(payload, (("scope", "Scope"),))
        for feature in payload.get("features", []):
            if isinstance(feature, dict) and isinstance(feature.get("label"), str):
                fields.append((feature["label"], _text(feature.get("value"))))
        if scoped_person is not None:
            action = UIAction("OPEN_PERSON", person_id=scoped_person)
    elif kind == "pattern":
        label = "Occupational pattern assessment"
        status_value = payload.get("status")
        try:
            status = (
                PatternStatus(status_value).label
                if isinstance(status_value, str)
                else "Assessment unavailable"
            )
        except (TypeError, ValueError):
            status = "Assessment unavailable"
        fields = [("Status", status)]
        for key, heading in (
            ("reason", "Reason"),
            ("reference_label", "Reference"),
            ("scope_note", "Scope"),
        ):
            if payload.get(key):
                fields.append((heading, _text(payload[key])))
        elevated = _strings(payload.get("elevated_features"))
        if elevated:
            fields.append(("Elevated activity features", "; ".join(elevated)))
        lines.append("Recorded symptoms are not inputs to the occupational-pattern model.")
        if scoped_person is not None:
            action = UIAction("OPEN_PERSON", person_id=scoped_person)
    elif kind == "quality":
        label = "Evidence quality audit"
        lines.extend(_strings(payload.get("notes")))
        if payload.get("empty_audit_wording"):
            lines.append(_text(payload["empty_audit_wording"]))
    elif kind in ("followup", "report_guidance", "report"):
        label = {
            "followup": "Deterministic follow-up guidance",
            "report_guidance": "Deterministic report guidance",
            "report": f"{_day(item)} · recorded symptom report",
        }[kind]
        if kind == "report":
            fields = _fields(
                payload,
                (
                    ("date", "Date"),
                    ("source", "Recorded source"),
                    ("temporal_relationship", "Temporal relationship"),
                    ("persistence", "Persistence"),
                    ("functional_impact", "Functional impact"),
                ),
            )
            for key, heading in (
                ("symptoms", "Recorded symptoms"),
                ("danger_signs", "Danger signs"),
            ):
                values = _strings(payload.get(key))
                if values:
                    fields.append((heading, "; ".join(values)))
            if payload.get("note"):
                fields.append(("Recorded note", _text(payload["note"])))
        elif kind == "followup":
            fields = _fields(payload, (("label", "Follow-up state"),))
            lines.extend(_strings(payload.get("evidence_lines")))
        guidance = [
            entry.payload
            for entry in items
            if entry.kind == "report_guidance" and entry.person_id == item.person_id
        ]
        if kind == "followup":
            guidance += [entry for entry in payload.get("reports", []) if isinstance(entry, dict)]
        for detail in guidance:
            for key in ("headline", "explanation"):
                if isinstance(detail.get(key), str):
                    lines.append(detail[key])
            lines.extend(_strings(detail.get("source_titles")))
        lines.append("Recorded symptoms are not inputs to the occupational-pattern model.")
        action = UIAction("OPEN_FOLLOWUP", person_id=scoped_person)
    elif kind == "attention":
        label = "Attention queue result"
        fields = _fields(payload, (("display_name", "Person"), ("status_label", "Status")))
        lines.extend(_strings(payload.get("reason")))
        if scoped_person is not None:
            action = UIAction("OPEN_PERSON", person_id=scoped_person)
    elif kind in ("candidate", "comparison", "reconstruction"):
        label = {
            "candidate": "Possible shared event · not confirmed",
            "comparison": "Recorded source comparison",
            "reconstruction": "Reconstruction proposal · human review required",
        }[kind]
        lines.append("Human review is required before recording a reconstructed draft.")
    elif kind == "person":
        label = "Person record"
        fields = _fields(
            payload,
            (
                ("display_name", "Person"),
                ("callsign", "Callsign"),
                ("unit", "Unit"),
                ("section", "Section"),
            ),
        )
        if scoped_person is not None:
            action = UIAction("OPEN_PERSON", person_id=scoped_person)
    elif kind == "finding":
        label = f"{_day(item, 'on_date')} · evidence verification finding"
        if isinstance(payload.get("message"), str):
            lines.append(payload["message"])
        source_ids = _strings(payload.get("source_ids"))
        if len(source_ids) == 1:
            action = UIAction("OPEN_REVIEW", event_id=source_ids[0])
    elif kind == "source":
        draft = payload.get("draft")
        if not isinstance(draft, dict):
            draft = {}
        label = "Recorded source"
        fields = _fields(draft, (("event_date", "Date"), ("weapon_name", "Weapon")))
        fields += _fields(draft, (("event_type", "Activity"),))
        fields += _fields(payload, (("status", "Status"),))
        event_id = payload.get("event_id")
        if isinstance(event_id, str) and event_id:
            action = UIAction("OPEN_REVIEW", event_id=event_id)
    elif kind == "draft":
        label = "Training draft · awaiting human review"
        if isinstance(payload.get("status"), str):
            lines.append(payload["status"])
        lines.extend(_strings(payload.get("unresolved")))
        event_id = payload.get("event_id")
        if isinstance(event_id, str) and event_id:
            action = UIAction("OPEN_REVIEW", event_id=event_id)
    elif kind == "symptom_proposal":
        label = "Proposed symptom report · not yet recorded"
        fields = _fields(payload, (("report_date", "Date"), ("source", "Recorded source")))
        symptoms = _strings(payload.get("symptoms"))
        if symptoms:
            fields.append(("Proposed symptoms", "; ".join(symptoms)))
        lines.append("Human review is required before recording a symptom report.")
    else:
        label = "Captured analysis evidence"
    return Citation(
        number=number,
        ref=ref,
        label=label,
        kind=kind,
        evidence=item,
        fields=tuple(fields),
        lines=tuple(dict.fromkeys(lines)),
        action=action,
    )


def brief_citations(
    brief: Brief, evidence: Sequence[Evidence], person_id: str | None
) -> tuple[tuple[Citation, ...], tuple[tuple[int, ...], ...]]:
    by_ref: dict[str, list[Evidence]] = {}
    for item in evidence:
        matches = by_ref.setdefault(item.ref, [])
        if item not in matches:
            matches.append(item)
    citations: list[Citation] = []
    numbers: dict[str, int] = {}
    sections = []
    for section in brief.sections:
        section_numbers = []
        for ref in section.evidence_refs:
            if ref not in numbers:
                number = len(citations) + 1
                numbers[ref] = number
                citations.append(_descriptor(number, ref, by_ref.get(ref, []), person_id))
            if numbers[ref] not in section_numbers:
                section_numbers.append(numbers[ref])
        sections.append(tuple(section_numbers))
    return tuple(citations), tuple(sections)
