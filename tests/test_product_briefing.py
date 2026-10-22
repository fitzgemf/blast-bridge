"""Review-brief citations use captured structured evidence, never generated source labels."""

from blastbridge.product.analyst import Brief, BriefSection
from blastbridge.product.analyst_tools import Evidence
from blastbridge.product.briefing import brief_citations

PERSON = "FIC-010"


def brief(*refs):
    headings = ("WHAT CHANGED", "EVIDENCE QUALITY", "RECOMMENDED NEXT ACTIONS")
    return Brief(
        sections=[
            BriefSection(
                heading=headings[index], text="Generated brief wording", evidence_refs=items
            )
            for index, items in enumerate(refs)
        ]
    )


def evidence(ref, kind, payload, person_id=PERSON):
    return Evidence(ref, person_id, kind, payload)


def test_numbering_follows_first_appearance_and_reuses_repeated_refs():
    wording = "No material issue was identified in the evidence reviewed."
    items = [
        evidence("facts", "facts", {"scope": "recorded occupational events", "features": []}),
        evidence("quality", "quality", {"notes": [], "empty_audit_wording": wording}),
    ]
    citations, sections = brief_citations(
        brief(["quality", "facts", "quality"], ["facts"]), items, PERSON
    )
    assert [(item.number, item.ref) for item in citations] == [(1, "quality"), (2, "facts")]
    assert sections == ((1, 2), (2,))
    assert citations[0].label == "Evidence quality audit"
    assert citations[0].lines == (wording,)
    assert "complete" not in " ".join(citations[0].lines).lower()
    assert all("Generated brief wording" not in item.label for item in citations)


def test_record_has_human_label_structured_card_and_record_target():
    record = evidence(
        "EVT-DEMO-C3",
        "record",
        {
            "event_id": "EVT-DEMO-C3",
            "date": "2026-10-13",
            "weapon_name": "HIMARS",
            "crew_name": "Launcher 1",
            "training_context": "qualification_certification",
            "role": "Launcher chief",
            "activity_count": 6,
            "location_unit": "Demo Range North",
            "provenance": "Organizational record — manually entered",
        },
    )
    citations, _ = brief_citations(brief([record.ref]), [record], PERSON)
    citation = citations[0]
    assert citation.label == "13 Oct 2026 · HIMARS · Launcher 1"
    assert record.ref not in citation.label
    assert dict(citation.fields)["Physical events"] == "6"
    assert dict(citation.fields)["Location / unit"] == "Demo Range North"
    assert citation.action is not None
    assert citation.action.kind == "OPEN_REVIEW"
    assert citation.action.event_id == "EVT-DEMO-C3"
    assert citation.evidence is record
    assert record.payload["activity_count"] == 6


def test_unknown_count_issue_preserves_unknown_and_opens_its_source_record():
    issue = evidence(
        "audit:FIC-010:1",
        "issue",
        {
            "code": "UNKNOWN_ACTIVITY_COUNT",
            "event_ref": "EVT-DEMO-C1",
            "date": "2026-10-13",
            "crew": "Launcher 2",
        },
    )
    record = evidence("EVT-DEMO-C1", "record", {"activity_count": "Unknown"})
    citations, _ = brief_citations(brief([issue.ref, record.ref]), [issue, record], PERSON)
    citation = citations[0]
    assert citation.label == "13 Oct 2026 · Launcher 2 · Unknown count"
    assert dict(citation.fields)["Activity count"] == "Unknown"
    assert citation.action is not None and citation.action.event_id == "EVT-DEMO-C1"
    assert "BlastBridge preserves Unknown rather than treating it as zero." in citation.lines
    assert dict(citations[1].fields)["Physical events"] == "Unknown"


def test_pattern_card_uses_authoritative_status_and_occupational_scope_without_scores():
    pattern = evidence(
        "pattern:FIC-010",
        "pattern",
        {
            "status": "atypical_elevated_activity",
            "reason": None,
            "reference_label": "SME-informed fictional HIMARS scenario reference",
            "scope_note": "HIMARS occupational dates only; symptoms and counts excluded",
            "elevated_features": ["Occupational events in prior 30 days"],
            "differing": [{"label": "Recent cadence", "value": 999.99, "median": 123.45}],
            "score": 0.56789,
            "percentile": 99.9,
        },
    )
    citations, _ = brief_citations(brief([pattern.ref]), [pattern], PERSON)
    citation = citations[0]
    card = " ".join([citation.label, *citation.lines, *(value for _, value in citation.fields)])
    assert citation.label == "Occupational pattern assessment"
    assert dict(citation.fields)["Status"] == "Atypical elevated occupational cadence"
    assert "Differing features" not in dict(citation.fields)
    assert (
        dict(citation.fields)["Elevated activity features"]
        == "Occupational events in prior 30 days"
    )
    assert "HIMARS occupational dates only" in card
    assert not any(text in card.lower() for text in ("risk", "%", "999.99", "123.45", "0.56789"))
    assert citation.action is not None and citation.action.kind == "OPEN_PERSON"
    assert citation.action.person_id == PERSON


def test_followup_cards_relay_only_captured_deterministic_guidance():
    guidance = {
        "state": "follow_up_suggested",
        "headline": "Medical follow-up suggested",
        "explanation": "Recorded symptoms meet the deterministic follow-up rule.",
        "source_titles": ["Recorded follow-up guidance source"],
    }
    report = evidence("SYM-DEMO-02", "report", {"date": "2026-09-24", "symptoms": ["Headache"]})
    relay = evidence(report.ref, "report_guidance", guidance)
    followup = evidence(
        "followup:FIC-010",
        "followup",
        {"label": "Medical follow-up suggested", "evidence_lines": [], "reports": [guidance]},
    )
    citations, _ = brief_citations(
        brief([followup.ref, report.ref]), [followup, relay, report], PERSON
    )
    for citation in citations:
        assert guidance["headline"] in citation.lines
        assert guidance["explanation"] in citation.lines
        assert citation.action is not None and citation.action.kind == "OPEN_FOLLOWUP"
        assert (
            "Recorded symptoms are not inputs to the occupational-pattern model." in citation.lines
        )
    assert citations[1].kind == "report"
    assert citations[1].label == "24 Sep 2026 · recorded symptom report"
    assert dict(citations[1].fields)["Recorded symptoms"] == "Headache"
    standalone, _ = brief_citations(brief([relay.ref]), [relay], PERSON)
    assert standalone[0].label == "Deterministic report guidance"


def test_duplicate_registrations_prefer_person_then_report_and_collapse_identical_items():
    report = evidence("SYM-DEMO-02", "report", {"date": "2026-09-24", "source": "Self report"})
    guidance = evidence(report.ref, "report_guidance", {"headline": "Deterministic guidance"})
    other_person = evidence(report.ref, "record", {"event_id": "wrong-record"}, "FIC-002")
    items = [other_person, guidance, report, report, guidance]
    citations, sections = brief_citations(brief([report.ref], [report.ref]), items, PERSON)
    assert len(citations) == 1 and sections == ((1,), (1,))
    assert citations[0].evidence is report
    assert citations[0].kind == "report"
    assert citations[0].lines.count("Deterministic guidance") == 1
    assert citations[0].action is not None and citations[0].action.kind == "OPEN_FOLLOWUP"


def test_missing_evidence_fails_closed_without_inferring_a_navigation_target():
    citations, sections = brief_citations(brief(["EVT-DEMO-C3", "pattern:FIC-010"]), [], PERSON)
    assert sections == ((1, 2),)
    for citation in citations:
        assert citation.label == "Source unavailable in this analysis"
        assert citation.evidence is None
        assert citation.action is None
        assert citation.fields == () and citation.lines == ()
