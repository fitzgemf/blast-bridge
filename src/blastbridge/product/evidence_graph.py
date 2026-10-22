"""Read-only provenance maps of existing deterministic evidence and human resolutions."""

import re
from collections.abc import Mapping, Sequence

from .evidence import (
    Comparison,
    ComparisonRow,
    EvidenceReconstructionProposal,
    FieldResolution,
    SharedEventCandidate,
)
from .models import EventStatus


def _escape(text: str) -> str:
    text = " ".join(text.split())
    escaped = "".join(
        "#quot;" if char == '"' else f"#{ord(char)};" if char in "'[]{}()|<>&#;`%\\-" else char
        for char in text
    )
    return re.sub(
        r"classdef|style|click",
        lambda match: f"#{ord(match[0][0])};{match[0][1:]}",
        escaped,
        flags=re.IGNORECASE,
    )


def _count_fact(
    row: ComparisonRow,
    resolution: FieldResolution | None,
    comparison: Comparison,
) -> tuple[list[str], tuple[str, ...], str]:
    name = row.field.removeprefix("count:")
    ids = comparison.source_ids
    if resolution is not None and resolution.state in ("UNRESOLVED", "HUMAN_RESOLVED"):
        supporting_ids = resolution.contributing_source_ids + resolution.conflicting_source_ids
        supporters = tuple(source_id for source_id in ids if source_id in supporting_ids)
        if resolution.state == "HUMAN_RESOLVED":
            value = "Count Unknown" if resolution.value is None else str(resolution.value)
            return [name, value, "Human resolved"], supporters, "fact"
        values = list(
            dict.fromkeys(
                "Unknown" if option.value is None else str(option.value)
                for option in resolution.options
                if option.source_ids
            )
        )
        return [name, " vs ".join(values), "Human decision required"], supporters, "conflict"
    if row.state == "CONFLICTS":
        return (
            [name, f"{row.value_a} vs {row.value_b}", "Human decision required"],
            ids,
            "conflict",
        )
    count_value = resolution.value if resolution is not None else row.value_a
    if resolution is None and count_value is None:
        count_value = row.value_b
    if count_value is None:
        activity = next((item for item in comparison.rows if item.field == f"crew:{name}"), None)
        supporters = (
            tuple(
                source_id
                for source_id, present in zip(
                    ids, (activity.value_a, activity.value_b), strict=True
                )
                if present is True
            )
            if activity is not None
            else ()
        )
        lines = (
            [name, "Activity recorded", "Count Unknown"] if supporters else [name, "Count Unknown"]
        )
        return lines, supporters, "unknown"
    supporters = (
        resolution.contributing_source_ids
        if resolution is not None
        else tuple(
            source_id
            for source_id, count in zip(ids, (row.value_a, row.value_b), strict=True)
            if count is not None
        )
    )
    return [name, f"{count_value} physical events"], supporters, "fact"


def evidence_map(
    comparison: Comparison,
    proposal: EvidenceReconstructionProposal | None,
    candidate: SharedEventCandidate | None,
    display_names: Mapping[str, str],
) -> str:
    lines = ["flowchart TB"]
    nodes = 0

    def node(label: Sequence[str], kind: str) -> str:
        nonlocal nodes
        node_id = f"n{nodes}"
        nodes += 1
        text = "<br/>".join(_escape(part) for part in label)
        lines.append(f'    {node_id}["{text}"]:::{kind}')
        return node_id

    def edge(start: str, end: str, label: str) -> None:
        lines.append(f"    {start} -->|{label}| {end}")

    sources: dict[str, str] = {}
    statuses = {
        EventStatus.DRAFT: "Draft · awaiting approval",
        EventStatus.APPROVED: "Approved record",
        EventStatus.REJECTED: "Rejected record",
    }
    for letter, record in zip(("A", "B"), comparison.sources, strict=True):
        sources[record.event_id] = node(
            [
                f"Range record {letter}",
                f"{record.draft.event_date:%d %b %Y} · {record.draft.weapon_name}",
                statuses[record.status],
            ],
            "source",
        )
    shared = None
    if candidate is not None:
        overlap = next(
            (
                signal.evidence
                for signal in candidate.signals
                if signal.name == "participant_overlap"
            ),
            (),
        )
        if overlap:
            names = [
                display_names.get(person_id, "Shared participant") for person_id in overlap[:3]
            ]
            if len(overlap) > 3:
                names.append(f"+{len(overlap) - 3} more")
            people = node(names, "participant")
            for source in sources.values():
                edge(people, source, "participated in")
        signal_names = {
            "same_location": "Same location",
            "same_context": "Same context",
            "participant_overlap": f"{len(overlap)} shared participants",
        }
        signals = [
            signal_names.get(signal.name, signal.name.replace("_", " "))
            for signal in candidate.signals
        ]
        shared = node(["Possible shared event", "Not confirmed", ", ".join(signals)], "shared")
        for source in sources.values():
            edge(source, shared, "contributes to")

    fields = {item.field: item for item in proposal.fields} if proposal is not None else {}
    counts = [row for row in comparison.rows if row.field.startswith("count:")]
    priority = {"UNRESOLVED": 0, "HUMAN_RESOLVED": 1, "UNKNOWN": 2}

    def count_priority(row: ComparisonRow) -> tuple[int, str]:
        if row.field in fields:
            rank = priority.get(fields[row.field].state, 3)
        else:
            rank = {"CONFLICTS": 0, "UNKNOWN": 2}.get(row.state, 3)
        return rank, row.field

    counts.sort(key=count_priority)
    facts: list[str] = []
    for row in counts[:3]:
        label, supporters, kind = _count_fact(row, fields.get(row.field), comparison)
        fact = node(label, kind)
        facts.append(fact)
        for source_id in supporters:
            if source_id in sources:
                edge(sources[source_id], fact, "supports")

    if proposal is not None:
        summary = ["Reconstruction proposal"]
        if any(item.state == "UNRESOLVED" for item in proposal.fields):
            summary += ["Conflict remains", "Human decision required"]
        else:
            for row in sorted(counts, key=lambda item: item.field)[:2]:
                item = fields.get(row.field)
                if item is not None:
                    value = "Unknown" if item.value is None else str(item.value)
                    suffix = " · Human resolved" if item.state == "HUMAN_RESOLVED" else ""
                    summary.append(f"{row.field.removeprefix('count:')}: {value}{suffix}")
        reconstruction = node(summary, "proposal")
        if shared is not None:
            edge(shared, reconstruction, "proposes")
        else:
            for source in sources.values():
                edge(source, reconstruction, "contributes to")
        for fact in facts:
            edge(fact, reconstruction, "contributes to")
        review = node(["Human Review", "Required before recording"], "review")
        edge(reconstruction, review, "requires review")
    lines += [
        "    classDef source fill:#f4f1ed,stroke:#9b9692,color:#302b30",
        "    classDef participant fill:#faf8f5,stroke:#b6aaa8,color:#40333e",
        "    classDef fact fill:#faf8f5,stroke:#b6aaa8,color:#40333e",
        "    classDef shared fill:#f5e8ee,stroke:#a45b7c,color:#592d47",
        "    classDef proposal fill:#eee8f5,stroke:#8a6b9b,color:#493254",
        "    classDef unknown fill:#f0efed,stroke:#aaa5a1,color:#615b60",
        "    classDef conflict fill:#f6eee1,stroke:#b59a6c,color:#665136",
        "    classDef review fill:#eadce9,stroke:#794a76,stroke-width:2px,color:#472641",
    ]
    return "\n".join(lines)
