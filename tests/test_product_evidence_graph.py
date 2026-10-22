"""The evidence map visualizes existing provenance without changing evidence decisions."""

import re

from blastbridge.product.evidence import (
    compare_sources,
    possible_shared_events,
    prepare_reconstruction,
    resolve,
)
from blastbridge.product.evidence_graph import evidence_map
from blastbridge.product.models import EventStatus, TrainingEvent, TrainingEventDraft
from blastbridge.product.seed import DEMO_PEOPLE, DEMO_SOURCE_DRAFTS

NAMES = {person.person_id: person.display_name for person in DEMO_PEOPLE}


def sources():
    return tuple(
        TrainingEvent(
            event_id=event_id,
            status=EventStatus.DRAFT,
            intake_source=intake_source,
            revision=1,
            draft=draft,
        )
        for event_id, draft, intake_source in DEMO_SOURCE_DRAFTS
    )


def node_id(graph, label):
    return next(
        match[1]
        for match in re.finditer(r'    (n\d+)\["([^"\n]*)"\]:::\w+', graph)
        if label in match[2]
    )


def test_demo_map_explains_shared_sources_and_reconstruction():
    pair = sources()
    comparison = compare_sources(*pair)
    candidate = possible_shared_events(pair)[0]
    proposal = prepare_reconstruction(comparison)
    graph = evidence_map(comparison, proposal, candidate, NAMES)
    assert graph == evidence_map(comparison, proposal, candidate, NAMES)
    assert graph.startswith("flowchart TB\n")
    assert len(re.findall(r'    n\d+\["', graph)) == 8
    a, b = node_id(graph, "Range record A"), node_id(graph, "Range record B")
    people = node_id(graph, "Avery Kestrel")
    assert "Jordan Pike" in graph
    assert f"{people} -->|participated in| {a}" in graph
    assert f"{people} -->|participated in| {b}" in graph
    exact = node_id(graph, "6 physical events")
    assert f"{a} -->|supports| {exact}" in graph
    assert f"{b} -->|supports| {exact}" not in graph
    assert "Possible shared event<br/>Not confirmed" in graph
    assert "Same location, Same context, 2 shared participants" in graph
    assert "Same date" not in graph
    reconstruction = node_id(graph, "Reconstruction proposal")
    review = node_id(graph, "Human Review")
    assert f"{reconstruction} -->|requires review| {review}" in graph
    assert "Required before recording" in graph
    assert "EVT-DEMO" not in graph and "FIC-" not in graph
    partial = evidence_map(comparison, None, None, NAMES)
    assert "Range record A" in partial and "6 physical events" in partial
    assert "Reconstruction proposal" not in partial
    assert "Possible shared event" not in partial
    assert "Human Review" in evidence_map(comparison, proposal, None, NAMES)


def test_unknown_conflict_and_human_resolution_keep_their_provenance():
    a, b = sources()
    comparison = compare_sources(a, b)
    candidate = possible_shared_events((a, b))[0]
    graph = evidence_map(comparison, prepare_reconstruction(comparison), candidate, NAMES)
    unknown = node_id(graph, "Activity recorded<br/>Count Unknown")
    assert f'{unknown}["Launcher 2<br/>Activity recorded<br/>Count Unknown"]:::unknown' in graph
    assert f"{node_id(graph, 'Range record B')} -->|supports| {unknown}" in graph
    assert f"{node_id(graph, 'Range record A')} -->|supports| {unknown}" not in graph
    assert "0 physical events" not in graph

    payload = b.draft.model_dump()
    payload["crews"][0]["physical_event_count"] = 8
    b = b.model_copy(update={"draft": TrainingEventDraft.model_validate(payload)})
    comparison = compare_sources(a, b)
    proposal = prepare_reconstruction(comparison)
    graph = evidence_map(comparison, proposal, candidate, NAMES)
    conflict = node_id(graph, "6 vs 8<br/>Human decision required")
    assert "Conflict remains<br/>Human decision required" in graph
    for label in ("Range record A", "Range record B"):
        assert f"{node_id(graph, label)} -->|supports| {conflict}" in graph

    resolved = resolve(proposal, "count:Launcher 1", a.event_id)
    graph = evidence_map(comparison, resolved, candidate, NAMES)
    chosen = node_id(graph, "Launcher 1<br/>6<br/>Human resolved")
    assert "6 vs 8" not in graph and "Conflict remains" not in graph
    for label in ("Range record A", "Range record B"):
        assert f"{node_id(graph, label)} -->|supports| {chosen}" in graph
    assert "Human Review<br/>Required before recording" in graph


def test_record_labels_cannot_inject_mermaid_or_html():
    unsafe = '"[]{}()|<script>&#;`\\\n%% --- --> classDef style click n99["injected"]'
    pair = []
    for source in sources():
        payload = source.draft.model_dump()
        payload["weapon_name"] = unsafe
        payload["crews"][0]["crew_name"] = unsafe
        pair.append(source.model_copy(update={"draft": TrainingEventDraft.model_validate(payload)}))
    comparison = compare_sources(*pair)
    candidate = possible_shared_events(pair)[0]
    graph = evidence_map(
        comparison,
        prepare_reconstruction(comparison),
        candidate,
        {**NAMES, "FIC-001": unsafe},
    )
    declarations = re.findall(r'    (n\d+)\["([^"\n]*)"\]:::\w+', graph)
    assert len(declarations) == 8
    assert all(re.fullmatch(r"n\d+", node) for node, _ in declarations)
    for _, label in declarations:
        text = label.replace("<br/>", "")
        assert not any(char in text for char in '"[]{}()|<>&`%\\')
        assert "---" not in text and "-->" not in text
        assert not re.search(r"classdef|style|click", text, re.IGNORECASE)
    assert len(re.findall(r"^    classDef ", graph, re.MULTILINE)) == 8
    assert not re.search(r"^\s*(click|style|%%)\b", graph, re.MULTILINE)
    assert "n99[" not in graph
    assert "#quot;" in graph and "#60;" in graph and "#37;" in graph
