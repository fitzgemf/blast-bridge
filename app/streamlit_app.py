"""BlastBridge recorder demo. FICTIONAL data only. Run: streamlit run app/streamlit_app.py"""

import os
import sqlite3
from dataclasses import replace
from datetime import date, datetime
from enum import StrEnum
from html import escape
from pathlib import Path
from uuid import uuid4

import streamlit as st
import ui
from pydantic import ValidationError

from blastbridge.data.catalog import load_weapon_catalog
from blastbridge.models.enums import EventType
from blastbridge.models.training_tempo import TrainingContext
from blastbridge.product import store
from blastbridge.product.agent import (
    GOLDEN_NARRATIVE,
    IntakeProvider,
    IntakeResult,
    load_replay,
    run_intake,
)
from blastbridge.product.analyst import (
    ANALYST_DISCLAIMER,
    AgentContext,
    AnalystData,
    AnalystRun,
    Conversation,
    EvidenceSection,
    UIAction,
    activity_lines,
    ask,
    comparison_action,
    evidence_count,
    evidence_fingerprint,
    is_stale,
    load_analyst_replay,
    navigation_action,
    recommendation_action,
    replay_providers,
)
from blastbridge.product.analyst_tools import SymptomProposal
from blastbridge.product.anthropic_provider import AnthropicProvider, live_available
from blastbridge.product.briefing import brief_citations, uncovered_summaries
from blastbridge.product.calendar_view import (
    DEMO_STORY_DATE,
    DayMarks,
    calendar_form_values,
    can_record_on,
    month_weeks,
    organization_marks,
    person_marks,
)
from blastbridge.product.calendar_view import (
    next_action as calendar_next_action,
)
from blastbridge.product.evidence import (
    Comparison,
    can_create_draft,
    compare_sources,
    creation_block_reason,
    resolve,
    to_draft,
)
from blastbridge.product.evidence_graph import evidence_map
from blastbridge.product.followup import (
    ABSENCE_NOTE,
    BOUNDARY_NOTE,
    DANGER_SIGN_LABEL,
    EMPTY_FOLLOWUP,
    GOVERNANCE_NOTE,
    NOTE_RULE_CAPTION,
    PRIVACY_NOTE,
    SOURCES,
    SYMPTOM_LIST_LABEL,
    FollowUp,
    FollowUpState,
    evaluate,
)
from blastbridge.product.image_intake import (
    image_sha256,
    load_image_replay,
    run_image_intake,
    validate_upload,
)
from blastbridge.product.models import (
    Crew,
    CrewMember,
    CrewPosition,
    EventStatus,
    IntakeSource,
    Person,
    TrainingEvent,
    TrainingEventDraft,
    provenance_text,
)
from blastbridge.product.patterns import (
    CONTEXT_NOTE,
    DIFFERING_HEADING,
    ELEVATION_RULE_TEXT,
    FEATURE_LABELS,
    OBSERVATION_NOTE,
    PATTERN_DISCLAIMER,
    REDUCED_TEXT,
    REFERENCE_LABEL,
    PatternModel,
    PatternStatus,
    assess_pattern,
    fit_pattern_model,
    load_reference,
)
from blastbridge.product.readiness import (
    ATTENTION_PRECEDENCE,
    ReadinessAssessment,
    ReadinessStatus,
    assess_readiness,
)
from blastbridge.product.review_flow import (
    APPROVED_STATUS,
    DRAFT_STATUS,
    PROPOSAL_STATUS,
    REJECTED_STATUS,
    save_reviewed_event,
)
from blastbridge.product.seed import DEMO_EVENTS, DEMO_PEOPLE, DEMO_SOURCE_DRAFTS, DEMO_SYMPTOMS
from blastbridge.product.symptoms import (
    DangerSign,
    FunctionalImpact,
    Persistence,
    Symptom,
    SymptomReportDraft,
    SymptomSource,
    TemporalRelationship,
)

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(
    os.environ.get("BLASTBRIDGE_DB", ROOT / "data" / "synthetic" / "product-demo.sqlite")
)
POSITIONS = (CrewPosition.CHIEF, CrewPosition.GUNNER, CrewPosition.DRIVER)
DEMO_ARRANGEMENT_NOTE = (
    "Fictional demo history is arranged: EVT-DEMO-B1–B3 (Oct 2025–Mar 2026) were added so "
    "most of the roster has the 365-day history the comparison requires, and EVT-DEMO-C1–C3 "
    "(Oct 2026) were constructed so Reese Calder demonstrates an elevated-cadence comparison. "
    "The model, threshold, reference and rules were not changed for the demo."
)

st.set_page_config(page_title="BlastBridge", layout="wide", initial_sidebar_state="collapsed")
ui.install()


@st.cache_resource
def _initialized(path: str) -> str:
    conn = store.connect(path)
    store.init_db(conn)
    store.seed_people(conn, DEMO_PEOPLE)
    store.seed_demo_events(conn, DEMO_EVENTS)
    store.seed_demo_symptoms(conn, DEMO_SYMPTOMS)
    store.seed_demo_drafts(conn, DEMO_SOURCE_DRAFTS)
    conn.close()
    return path


@st.cache_data
def weapons() -> dict[str, str]:
    catalog = load_weapon_catalog(ROOT / "data" / "reference" / "weapons.json")
    return dict(
        sorted(((w.weapon_system_id, w.canonical_name) for w in catalog), key=lambda x: x[1])
    )


DB_PATH.parent.mkdir(parents=True, exist_ok=True)
_initialized(str(DB_PATH))
CONN = store.connect(DB_PATH)
PEOPLE: dict[str, Person] = {p.person_id: p for p in store.list_people(CONN)}

if st.session_state.pop("reset_demo_view", False):
    st.session_state["analysis_as_of"] = DEMO_STORY_DATE
    for calendar_key in ("org", "person"):
        st.session_state[f"{calendar_key}_month"] = DEMO_STORY_DATE.replace(day=1)
        st.session_state[f"{calendar_key}_day"] = DEMO_STORY_DATE
    for session_key in list(st.session_state):
        if session_key.startswith(
            ("ask_conversation_", "ask_run_", "ask_replay_", "ask_notice_", "ask_demo_date_")
        ):
            del st.session_state[session_key]
    st.session_state.pop("ask_ledger", None)
# Keep the analysis date when its Home-only widget is absent on another page.
st.session_state["analysis_as_of"] = st.session_state.get("analysis_as_of", date.today())
ANALYSIS_AS_OF = st.session_state["analysis_as_of"]


@st.cache_resource
def pattern_model() -> PatternModel | None:
    try:
        rows, metadata = load_reference()
    except FileNotFoundError:
        return None
    return fit_pattern_model(rows, metadata)


def readiness_for(person_id: str, as_of: date) -> ReadinessAssessment:
    entries = store.member_history(CONN, person_id)
    reports = store.list_symptom_reports(CONN, person_id)
    model = pattern_model()
    pattern = assess_pattern(model, entries, as_of)
    return assess_readiness(person_id, entries, reports, pattern, as_of)


def all_readiness(as_of: date) -> dict[str, ReadinessAssessment]:
    return {person_id: readiness_for(person_id, as_of) for person_id in PEOPLE}


def readiness_pill(status: ReadinessStatus) -> None:
    style = {
        ReadinessStatus.ROUTINE_MONITORING: "routine",
        ReadinessStatus.REVIEW_PRIORITY: "review",
        ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED: "medical",
        ReadinessStatus.URGENT_EVALUATION: "urgent",
    }[status]
    st.markdown(f'<span class="bb-pill {style}">{status.label}</span>', unsafe_allow_html=True)


def readiness_tone(status: ReadinessStatus) -> str:
    return {
        ReadinessStatus.ROUTINE_MONITORING: "gray",
        ReadinessStatus.REVIEW_PRIORITY: "violet",
        ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED: "orange",
        ReadinessStatus.URGENT_EVALUATION: "red",
    }[status]


def readiness_reason(status: ReadinessStatus) -> str:
    return {
        ReadinessStatus.ROUTINE_MONITORING: "Continue tracking recorded activity and symptoms.",
        ReadinessStatus.REVIEW_PRIORITY: "Exposure pattern changed",
        ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED: (
            "Persistent symptoms affecting daily function"
        ),
        ReadinessStatus.URGENT_EVALUATION: "An urgent danger sign was reported.",
    }[status]


def render_calendar(key: str, marks: dict[date, DayMarks], person: bool) -> date | None:
    today = date.today()
    s = st.session_state
    s.setdefault(f"{key}_month", today.replace(day=1))
    s.setdefault(f"{key}_day", today)
    month = s[f"{key}_month"]
    with st.container(key=f"cal-{key}"):
        with st.container(key=f"month-nav-{key}"):
            title, previous, following = st.columns([6, 1, 1])
            if previous.button("‹", key=f"{key}-previous", width="stretch"):
                s[f"{key}_month"] = date(
                    month.year - (month.month == 1), (month.month - 2) % 12 + 1, 1
                )
                st.rerun()
            title.markdown(f'<div class="bb-month">{month:%B %Y}</div>', unsafe_allow_html=True)
            if following.button("›", key=f"{key}-next", width="stretch"):
                s[f"{key}_month"] = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
                st.rerun()
        for column, weekday in zip(
            st.columns(7),
            ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"),
            strict=True,
        ):
            column.markdown(f'<div class="bb-weekday">{weekday[0]}</div>', unsafe_allow_html=True)
        for week in month_weeks(month.year, month.month):
            for column, day in zip(st.columns(7), week, strict=True):
                if day is None:
                    column.write("")
                    continue
                enabled = can_record_on(day, today)
                mark = marks.get(day, DayMarks()) if enabled else DayMarks()
                dots = []
                if mark.training:
                    dots.append(":violet[●]")
                if person and mark.symptom:
                    dots.append(":primary[●]")
                if mark.urgent:
                    dots.append(":red[●]")
                text = str(day.day) + "\n" + (" ".join(dots) if dots else "\u00a0")
                today_suffix = "-today" if day == today and day != s[f"{key}_day"] else ""
                with column.container(key=f"day-{key}-{day.isoformat()}{today_suffix}"):
                    if st.button(
                        text,
                        key=f"{key}-{day.isoformat()}",
                        disabled=not enabled,
                        width="stretch",
                        type="primary" if day == s[f"{key}_day"] else "secondary",
                    ):
                        s[f"{key}_day"] = day
                        st.rerun()
        st.caption(
            ":violet[●] occupational record · "
            + (":primary[●] symptom report · " if person else "")
            + ":red[●] urgent danger sign recorded"
        )
        with st.expander("About these dates"):
            st.caption(
                "Records after the analysis date are shown but are not part of the "
                "current assessment."
            )
    return s.get(f"{key}_day")


def label(value: StrEnum) -> str:
    if value is TrainingContext.QUALIFICATION:
        return "Qualification"
    return value.value.replace("_", " ").capitalize()


def next_action(status: ReadinessStatus) -> str:
    if status is ReadinessStatus.REVIEW_PRIORITY:
        return (
            "Recent HIMARS training cadence is elevated relative to the fictional scenario "
            "reference. Review the record."
        )
    return calendar_next_action(status)


def count_text(n: int | None) -> str:
    return "Unknown" if n is None else str(n)


def comparison_number(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def person_text(person_id: str) -> str:
    p = PEOPLE[person_id]
    return f"{p.display_name} “{p.callsign}” · {p.section}"


def header(title: str, subtitle: str) -> None:
    ui.brand(title)
    st.markdown(f'<div class="bb-sub">{escape(subtitle)}</div>', unsafe_allow_html=True)
    demo_banner()


def demo_banner() -> None:
    with st.expander("About this demo"):
        st.caption(
            "FICTIONAL DEMO — All people and events are invented. "
            "BlastBridge records occupational exposure; exposure does not imply injury."
        )


def field(name: str, value: str) -> None:
    ui.field(name, value)


def crew_names(event: TrainingEvent) -> str:
    return ", ".join(PEOPLE[m.person_id].display_name for c in event.draft.crews for m in c.members)


# ---- navigation helpers -------------------------------------------------------------------------


def form_values(
    d: TrainingEventDraft | None = None, on_date: date | None = None
) -> dict[str, object]:
    values = {
        "f_date": d.event_date if d else date.today(),
        "f_type": d.event_type if d else EventType.WEAPON_FIRING,
        "f_context": d.training_context if d else TrainingContext.HOME_STATION,
        "f_weapon": d.weapon_system_id if d else "m142-himars",
        "f_location": (d.location_unit or "") if d else "",
        "f_crews": list(range(len(d.crews))) if d else [0],
        "f_next_crew": len(d.crews) if d else 1,
    }
    if on_date is not None:
        values.update(calendar_form_values(on_date))
    for i in values["f_crews"]:
        crew = d.crews[i] if d else None
        members = {m.position: m.person_id for m in crew.members} if crew else {}
        values.update(
            {
                f"f_c{i}_name": crew.crew_name if crew else f"Launcher {i + 1}",
                f"f_c{i}_known": ("Unknown" if crew.physical_event_count is None else "Known")
                if crew
                else None,
                f"f_c{i}_count": crew.physical_event_count if crew else None,
                **{f"f_c{i}_{pos}": members.get(pos) for pos in POSITIONS},
            }
        )
    return values


def change_crews(remove: int | None = None) -> None:
    s = st.session_state
    # Copy widget values before rerunning: Streamlit cleans up widgets omitted from a run.
    values = {
        key: value
        for key, value in s.items()
        if key.startswith("f_") and not key.endswith("_remove")
    }
    if remove is not None:
        values["f_crews"] = [i for i in s["f_crews"] if i != remove]
    else:
        i = s["f_next_crew"]
        values["f_crews"] = [*s["f_crews"], i]
        values["f_next_crew"] = i + 1
        values.update(
            {
                f"f_c{i}_name": f"Launcher {i + 1}",
                f"f_c{i}_known": None,
                f"f_c{i}_count": None,
                **{f"f_c{i}_{pos}": None for pos in POSITIONS},
            }
        )
    s["form_init"] = values
    st.rerun()


def open_form(
    event: TrainingEvent | None = None,
    on_date: date | None = None,
    mode: str | None = None,
) -> None:
    st.session_state.pop("event_decision", None)
    st.session_state.pop("event_proposal", None)
    st.session_state.pop("event_proposal_metadata", None)
    if event is None:
        clear_ai_state()
    st.session_state["form_init"] = form_values(event.draft if event else None, on_date)
    st.session_state["form_init"]["f_mode"] = mode or (
        "Enter manually" if event else "Describe / paste training record"
    )
    st.session_state.pop("calendar_date", None)
    if on_date is not None:
        st.session_state["form_init"]["f_date"] = on_date
        st.session_state["calendar_date"] = on_date
    st.session_state.pop("ai_pending", None)
    st.session_state["editing_event_id"] = event.event_id if event else None
    st.session_state["editing_revision"] = event.revision if event else None
    st.switch_page(PAGES["new"])


def open_review(event_id: str) -> None:
    st.session_state["review_event_id"] = event_id
    st.session_state["last_decided"] = None
    st.session_state["review_shown"] = None
    st.switch_page(PAGES["review"])


def open_history(person_id: str) -> None:
    st.session_state["history_person_id"] = person_id
    st.session_state["people_person"] = person_id
    st.session_state["person_day"] = ANALYSIS_AS_OF
    st.session_state["person_month"] = ANALYSIS_AS_OF.replace(day=1)
    st.switch_page(PAGES["person"])


# ---- pages --------------------------------------------------------------------------------------


def fictional_pill() -> None:
    st.markdown('<span class="bb-pill fictional">FICTIONAL DEMO</span>', unsafe_allow_html=True)


def short_provenance(source: IntakeSource, status: EventStatus) -> str:
    origin = {
        IntakeSource.MANUAL: "Manually entered",
        IntakeSource.AI_LIVE: "AI-assisted",
        IntakeSource.AI_REPLAY: "Validated demo replay",
    }[source]
    if status is EventStatus.REJECTED:
        return "Rejected · not part of personnel history"
    suffix = "human approved" if status is EventStatus.APPROVED else "awaiting human approval"
    return f"{origin} · {suffix}"


def priority_people(assessments: dict[str, ReadinessAssessment]) -> list[ReadinessAssessment]:
    order = ATTENTION_PRECEDENCE
    return sorted(
        (item for item in assessments.values() if item.overall_readiness_status in order),
        key=lambda item: (
            order[item.overall_readiness_status],
            PEOPLE[item.person_id].display_name,
        ),
    )


def analyst_context(person_id: str | None, *, stale: bool = False) -> AgentContext:
    return AgentContext(
        analysis_as_of=ANALYSIS_AS_OF,
        reference_date=ANALYSIS_AS_OF,
        selected_person_id=person_id,
        selected_calendar_date=st.session_state.get("person_day" if person_id else "org_day"),
        page="person" if person_id else "home",
        prior_analysis_stale=stale,
    )


def analyst_data(*, include_catalog: bool) -> AnalystData:
    return AnalystData(
        people=tuple(PEOPLE.values()),
        member_history=lambda person_id: store.member_history(CONN, person_id),
        symptom_reports=lambda person_id: store.list_symptom_reports(CONN, person_id),
        events=lambda: [
            *store.list_events(CONN, EventStatus.DRAFT, limit=-1),
            *store.list_events(CONN, EventStatus.APPROVED, limit=-1),
        ],
        pattern_model=pattern_model(),
        catalog=(
            load_weapon_catalog(ROOT / "data/reference/weapons.json") if include_catalog else ()
        ),
        save_draft=lambda draft, source: store.save_draft(CONN, draft, intake_source=source),
    )


def analyst_suggestions(person_id: str | None) -> list[tuple[str, str]]:
    if person_id is None:
        return [
            ("Log a training event", "log_event"),
            ("Who needs attention?", "attention"),
            ("Find possible duplicate records", "shared_event"),
        ]
    if person_id == "FIC-010":
        return [
            ("Summarize Reese for review", "reese_brief"),
            ("What information is missing for Reese?", "reese_missing"),
        ]
    if person_id == "FIC-002":
        return [("Create a brief for Jordan", "jordan_brief")]
    return []


def submit_analyst(
    scope: str,
    person_id: str | None,
    question: str | None,
    *,
    replay_name: str | None = None,
    replay_index: int = 0,
    stale: bool = False,
) -> None:
    s = st.session_state
    conversation_key = f"ask_conversation_{scope}"
    replay_key = f"ask_replay_{scope}"
    notice_key = f"ask_notice_{scope}"
    s.pop(notice_key, None)
    s.pop(f"ask_demo_date_{scope}", None)
    conversation = s.setdefault(conversation_key, Conversation(uuid4().hex))
    try:
        if live_available():
            provider, intake_provider = AnthropicProvider(), AnthropicProvider()
        else:
            if question is None:
                replay_name, replay_index = s.get(replay_key, (None, 0))
            if replay_name is None and question is not None:
                names = [name for _, name in analyst_suggestions(person_id)]
                for name in names:
                    fixture = load_analyst_replay(name)
                    for index, step in enumerate(fixture.steps):
                        if question == step.utterance:
                            replay_name, replay_index = name, index
                            break
                    if replay_name is not None:
                        break
            if replay_name is None:
                raise ValueError(
                    "Demo replay covers the suggested requests. "
                    "Live AI isn't available in this demo."
                )
            fixture = load_analyst_replay(replay_name)
            if fixture.analysis_as_of != ANALYSIS_AS_OF:
                s[f"ask_demo_date_{scope}"] = fixture.analysis_as_of == DEMO_STORY_DATE
                fixture = load_analyst_replay(replay_name, analysis_as_of=ANALYSIS_AS_OF)
            step = fixture.steps[replay_index]
            if replay_index and question is not None:
                previous = s.get(f"ask_run_{scope}")
                if (
                    s.get(replay_key) != (replay_name, replay_index - 1)
                    or previous is None
                    or previous.response is None
                    or not previous.response.clarification
                ):
                    raise ValueError("Start with the suggested training-event request.")
            if question is not None:
                question = step.utterance
            s[replay_key] = (replay_name, replay_index)
            source_ids = None
            if replay_name == "log_event" and replay_index == 1:
                first_id = next(
                    turn.utterance_id
                    for turn in reversed(conversation.turns)
                    if turn.role == "user" and turn.text == fixture.steps[0].utterance
                )
                last_id = (
                    next(
                        turn.utterance_id
                        for turn in reversed(conversation.turns)
                        if turn.role == "user"
                    )
                    if question is None
                    else f"U{conversation.next_user_number}"
                )
                if first_id is None or last_id is None:
                    raise ValueError("Start with the suggested training-event request.")
                source_ids = [first_id, last_id]
            provider, intake_provider = replay_providers(step, utterance_ids=source_ids)
        ledger = s.setdefault("ask_ledger", {})
        with st.spinner("Reviewing BlastBridge evidence…"):
            s[f"ask_run_{scope}"] = ask(
                question,
                context=analyst_context(person_id, stale=stale),
                data=analyst_data(include_catalog=True),
                provider=provider,
                intake_provider=intake_provider,
                conversation=conversation,
                ledger=ledger,
                reconstructions=s.setdefault("reconstructions", {}),
            )
    except (OSError, ValueError, IndexError, StopIteration) as exc:
        s[notice_key] = str(exc)
    st.rerun()


def analyst_section(title: str, section: EvidenceSection, run: AnalystRun) -> None:
    refs = set(section.evidence_refs)
    records = {item.ref for item in run.evidence if item.kind == "record" and item.ref in refs}
    ui.analyst_section(title, section.text, len(records), len(refs))


def open_proposed_draft(result: IntakeResult) -> None:
    clear_ai_state()
    st.session_state["ai_result"] = result
    st.session_state["ai_narrative"] = result.narrative
    st.session_state["form_init"] = {"f_mode": "Describe / paste training record"}
    st.session_state["editing_event_id"] = None
    st.session_state["editing_revision"] = None
    st.session_state.pop("calendar_date", None)
    st.switch_page(PAGES["new"])


def perform_ui_action(action: UIAction, proposal: SymptomProposal | None) -> None:
    s = st.session_state
    if action.kind in (
        "OPEN_EVIDENCE_COMPARISON",
        "OPEN_SOURCE_RECORD",
        "RESOLVE_RECONSTRUCTION",
        "CREATE_RECONSTRUCTED_DRAFT",
    ):
        perform_evidence_action(action)
        return
    if action.kind == "OPEN_REVIEW":
        if action.event_id:
            open_review(action.event_id)
        else:
            st.switch_page(PAGES["inbox"])
    elif action.kind == "OPEN_PROPOSED_DRAFT":
        result = s.get("ask_proposed_result")
        if result is not None:
            open_proposed_draft(result)
    elif action.kind == "OPEN_FOLLOWUP":
        st.switch_page(PAGES["followup"])
    elif action.person_id in PEOPLE:
        person_id = action.person_id
        if action.kind == "OPEN_PERSON":
            open_history(person_id)
        elif action.kind in ("OPEN_RECORD", "OPEN_SYMPTOM_FORM"):
            if action.kind == "OPEN_SYMPTOM_FORM":
                clear_symptom_state()
                s["sym_person"] = person_id
                s["sym_open"] = True
                s["sym_ai_proposal"] = True
                restore = {}
                if proposal is not None and proposal.person_id == person_id:
                    if proposal.report_date is None:
                        s["sym_ai_needs_date"] = True
                    for key, value in (
                        ("sym_w_event", proposal.event_id),
                        ("sym_w_relationship", proposal.temporal_relationship),
                        ("sym_w_date", proposal.report_date),
                        ("sym_w_persistence", proposal.persistence),
                        ("sym_w_impact", proposal.functional_impact),
                        ("sym_w_source", proposal.source),
                        ("sym_w_note", proposal.note),
                    ):
                        if value is not None:
                            restore[key] = value
                    restore.update({f"sym_w_s_{item.value}": True for item in proposal.symptoms})
                    restore.update(
                        {f"sym_w_d_{item.value}": True for item in proposal.danger_signs}
                    )
                s["sym_restore"] = restore
            on_date = action.on_date or ANALYSIS_AS_OF
            s["history_person_id"] = person_id
            s["people_person"] = person_id
            s["person_day"] = on_date
            s["person_month"] = on_date.replace(day=1)
            st.switch_page(PAGES["person"])


def perform_evidence_action(action: UIAction) -> None:
    s = st.session_state
    key = action.evidence_key
    comparisons = s.setdefault("evidence_comparisons", {})
    comparison = comparisons.get(key)
    if action.kind == "OPEN_EVIDENCE_COMPARISON":
        candidate = s.get("evidence_candidates", {}).get(key)
        if comparison is None and candidate is not None:
            try:
                comparison = compare_sources(
                    *(store.get_event(CONN, event_id) for event_id in candidate.source_ids)
                )
            except (store.StoreError, ValueError):
                return
            comparisons[key] = comparison
        if comparison is not None:
            s["evidence_open"] = key
            st.rerun()
        return
    if comparison is None:
        return
    if action.kind == "OPEN_SOURCE_RECORD":
        if action.event_id is not None and action.event_id in comparison.source_ids:
            open_review(action.event_id)
        return
    proposals = s.setdefault("reconstructions", {})
    proposal = proposals.get(key)
    if proposal is None:
        return
    try:
        if action.kind == "RESOLVE_RECONSTRUCTION":
            proposals[key] = resolve(proposal, action.field or "", action.choice or "")
            st.rerun()
        elif action.kind == "CREATE_RECONSTRUCTED_DRAFT":
            existing = store.find_reconstruction(CONN, proposal.source_ids)
            if existing is not None:
                proposals[key] = replace(proposal, created_draft_id=existing.event_id)
                open_review(existing.event_id)
                return
            sources = [store.get_event(CONN, event_id) for event_id in proposal.source_ids]
            for source in sources:
                existing = store.live_reconstruction_for_source(CONN, source.event_id)
                if existing is not None:
                    proposals[key] = replace(proposal, created_draft_id=existing.event_id)
                    open_review(existing.event_id)
                    return
            if not can_create_draft(proposal, sources):
                st.warning(creation_block_reason(proposal, sources))
                return
            event_id = store.save_draft(
                CONN,
                to_draft(proposal),
                intake_source=IntakeSource.MANUAL,
                reconstructed_from=proposal.source_ids,
            )
            proposals[key] = replace(proposal, created_draft_id=event_id)
            s["review_notice"] = (
                f"Source drafts {', '.join(proposal.source_ids)} are unchanged in Review — "
                "reject the ones this reconstruction replaces."
            )
            open_review(event_id)
    except (ValueError, store.StoreError, sqlite3.Error) as exc:
        st.warning(str(exc))


def evidence_value(value: object) -> str:
    if value is None:
        return "Unknown"
    if value is True:
        return "Activity recorded"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, tuple):
        return " · ".join(str(item) for item in value)
    return str(value)


def evidence_field_label(field: str, label_text: str) -> str:
    person_id = field.removeprefix("member:")
    if field.startswith("member:") and person_id in PEOPLE:
        return f"{PEOPLE[person_id].display_name} crew / position"
    return label_text


def analyst_evidence_panels(run: AnalystRun, scope: str) -> None:
    s = st.session_state
    comparisons = s.setdefault("evidence_comparisons", {})
    comparisons.update({comparison.key: comparison for comparison in run.comparisons})
    candidates = s.setdefault("evidence_candidates", {})
    candidates.update({candidate.key: candidate for candidate in run.candidates})
    keys = list(
        dict.fromkeys(
            [
                *(comparison.key for comparison in run.comparisons),
                *(
                    candidate.key
                    for candidate in run.candidates
                    if candidate.key == s.get("evidence_open")
                ),
            ]
        )
    )
    for key in keys:
        comparison: Comparison = comparisons[key]
        candidate = candidates.get(key)
        with st.container(border=True):
            st.write(
                "**Possible shared event — not confirmed**"
                if candidate is not None
                else "**Source evidence comparison**"
            )
            if candidate is not None:
                for signal in candidate.signals:
                    st.caption(f"{signal.name.replace('_', ' ')}: {'; '.join(signal.evidence)}")
                st.caption("Blockers checked: " + "; ".join(candidate.blockers_checked))
            for source in comparison.sources:
                st.write(f"**{source.event_id}** · {source.draft.event_date:%d %b %Y}")
                st.caption(provenance_text(source.intake_source, source.status))
                if st.button("View source", key=f"evidence-source-{scope}-{key}-{source.event_id}"):
                    perform_ui_action(
                        UIAction("OPEN_SOURCE_RECORD", event_id=source.event_id, evidence_key=key),
                        None,
                    )
            st.subheader("Evidence map")
            st.mermaid_chart(
                evidence_map(
                    comparison,
                    s.get("reconstructions", {}).get(key),
                    candidate,
                    {person_id: person.display_name for person_id, person in PEOPLE.items()},
                ),
                alt="Source records, shared participants and evidence leading to human review.",
            )
            st.dataframe(
                [
                    {
                        "Field": evidence_field_label(row.field, row.label),
                        comparison.source_ids[0]: evidence_value(row.value_a),
                        comparison.source_ids[1]: evidence_value(row.value_b),
                        "State": row.state,
                    }
                    for row in comparison.rows
                ],
                hide_index=True,
                width="stretch",
            )
            proposal = s.get("reconstructions", {}).get(key)
            if proposal is None:
                continue
            st.write("**Session reconstruction proposal**")
            for item in proposal.fields:
                label_text = evidence_field_label(item.field, item.label)
                st.write(f"{label_text}: {evidence_value(item.value)} · {item.state}")
                if item.state == "UNKNOWN" and item.field.startswith("count:"):
                    st.caption("Activity recorded — no source contains a count")
                else:
                    st.caption(
                        "Supported by: "
                        + "; ".join(f"✓ {source_id}" for source_id in item.contributing_source_ids)
                    )
                if item.conflicting_source_ids:
                    st.caption("Conflicting sources: " + ", ".join(item.conflicting_source_ids))
                if item.state == "HUMAN_RESOLVED":
                    st.caption("Human-resolved: " + evidence_value(item.value))
                if item.state == "UNRESOLVED":
                    st.write("BlastBridge cannot resolve this from the recorded evidence.")
                    for option in item.options:
                        label_text = (
                            "Keep Unknown"
                            if option.key == "unknown"
                            else f"Use {evidence_value(option.value)} ({option.key})"
                        )
                        if st.button(
                            label_text, key=f"resolve-{scope}-{key}-{item.field}-{option.key}"
                        ):
                            perform_ui_action(
                                UIAction(
                                    "RESOLVE_RECONSTRUCTION",
                                    evidence_key=key,
                                    field=item.field,
                                    choice=option.key,
                                ),
                                None,
                            )
            existing = store.find_reconstruction(CONN, proposal.source_ids)
            if existing is not None:
                st.caption(
                    f"Source drafts {', '.join(proposal.source_ids)} are unchanged in Review — "
                    "reject the ones this reconstruction replaces."
                )
                open_label = (
                    "Open in Review" if existing.status is EventStatus.DRAFT else "Open record"
                )
                if st.button(open_label, key=f"reconstructed-open-{scope}-{key}"):
                    perform_ui_action(
                        UIAction("CREATE_RECONSTRUCTED_DRAFT", evidence_key=key), None
                    )
            else:
                try:
                    sources = [
                        store.get_event(CONN, source_id) for source_id in proposal.source_ids
                    ]
                except store.StoreError:
                    st.caption("A source record is no longer available.")
                    continue
                reason = creation_block_reason(proposal, sources)
                if reason:
                    st.caption(reason)
                elif st.button("Create training draft", key=f"reconstruct-{scope}-{key}"):
                    perform_ui_action(
                        UIAction("CREATE_RECONSTRUCTED_DRAFT", evidence_key=key), None
                    )


def analyst_symptom_proposal(proposal: SymptomProposal, action: UIAction, scope: str) -> None:
    with st.container(border=True):
        st.write("**Symptom report proposal**")
        st.write(PEOPLE[proposal.person_id].display_name)
        st.write("Symptoms: " + ("; ".join(item.label for item in proposal.symptoms) or "Not set"))
        if proposal.danger_signs:
            st.write("Danger signs: " + "; ".join(item.label for item in proposal.danger_signs))
        if proposal.report_date is not None:
            st.write(f"Report date: {proposal.report_date:%d %b %Y}")
        if proposal.event_id is not None:
            st.write("Linked event: " + linked_event_text(proposal.event_id))
        for label_text, value in (
            ("Relationship", proposal.temporal_relationship),
            ("Persistence", proposal.persistence),
            ("Functional impact", proposal.functional_impact),
            ("Source", proposal.source),
        ):
            if value is not None:
                st.write(f"{label_text}: {value.label}")
        if proposal.note is not None:
            st.write("Note: " + proposal.note)
        if proposal.missing():
            st.write("Still needs: " + "; ".join(proposal.missing()))
        for reason in proposal.dropped:
            st.caption(reason)
        if st.button("Review symptom report", key=f"ask-symptom-{scope}", type="primary"):
            perform_ui_action(action, proposal)


def analyst_draft(run: AnalystRun, scope: str) -> None:
    draft = run.created_draft
    if draft is None:
        return
    with st.container(key=f"ask-draft-{scope}"):
        if draft.kind == "needs_review":
            st.write(draft.status)
            st.caption("Start over to log another event")
            st.page_link(PAGES["inbox"], label="Open Review queue")
            return
        st.write(f"**{DRAFT_STATUS if draft.event_id else 'AI-assisted proposal'}**")
        st.caption("Not in personnel history" if draft.event_id else PROPOSAL_STATUS)
        for issue in draft.issues:
            ui.compact_line(str(issue["message"]), muted=True)
        for unresolved in draft.unresolved:
            ui.compact_line(unresolved, muted=True)
        if draft.recovered:
            st.caption("Recovered the existing draft; no second draft was created.")
        if draft.event_id:
            st.caption("Start over to log another event")
            if st.button("Open in Review", key=f"ask-open-review-{scope}", type="primary"):
                open_review(draft.event_id)
        elif draft.intake_result is not None:
            if st.button("Open proposed draft", key=f"ask-open-proposed-{scope}"):
                open_proposed_draft(draft.intake_result)


ACTION_LABELS = {
    "OPEN_REVIEW": "Open in Review",
    "OPEN_PROPOSED_DRAFT": "Open proposed draft",
    "OPEN_RECORD": "Open record",
    "OPEN_PERSON": "Open person",
    "OPEN_FOLLOWUP": "Open Follow-up",
    "OPEN_EVIDENCE_COMPARISON": "Compare sources",
}


def review_brief(run: AnalystRun, scope: str) -> None:
    response = run.response
    if response is None or response.brief is None:
        return
    citations, section_numbers = brief_citations(response.brief, run.evidence, response.person_id)
    run_key = f"brief-{scope}-{id(run)}"
    selection_key = f"{run_key}-source"
    person = PEOPLE.get(response.person_id or "")
    with st.container(border=True):
        st.subheader("REVIEW BRIEF")
        st.write(person.display_name if person else "Selected person")
        st.caption(f"Analysis as of {run.analysis_as_of:%d %b %Y} · FICTIONAL DEMO")
        st.caption(f"Grounded in {len(citations)} cited evidence items")
        for index, (section, numbers) in enumerate(
            zip(response.brief.sections, section_numbers, strict=True)
        ):
            analyst_section(section.heading.capitalize(), section, run)
            if numbers:
                st.caption("Sources:")
                with st.container(
                    key=f"brief-citations-{run_key}-{index}", horizontal=True, gap="small"
                ):
                    for number in numbers:
                        citation = citations[number - 1]
                        if st.button(
                            f"[{number}] {citation.label}",
                            key=f"{run_key}-{index}-{number}",
                            type="tertiary",
                        ):
                            st.session_state[selection_key] = citation.ref
        selected = next(
            (item for item in citations if item.ref == st.session_state.get(selection_key)), None
        )
        if selected is not None:
            with st.container(border=True):
                st.caption("SOURCE EVIDENCE")
                st.write(f"**[{selected.number}] {selected.label}**")
                for heading, value in selected.fields:
                    if heading in ("Training context", "Activity"):
                        try:
                            value = label(
                                TrainingContext(value)
                                if heading == "Training context"
                                else EventType(value)
                            )
                        except ValueError:
                            value = "Unknown"
                    ui.field(heading, value)
                for line in selected.lines:
                    st.write(line)
                action = selected.action
                if (
                    selected.kind in ("candidate", "comparison", "reconstruction", "finding")
                    and selected.evidence is not None
                ):
                    action = comparison_action(selected.evidence, run) or action
                action_label = (
                    ({**ACTION_LABELS, "OPEN_REVIEW": "Open record"}).get(action.kind)
                    if action
                    else None
                )
                if action is not None and action_label is not None:
                    if st.button(action_label, key=f"{run_key}-open-{selected.number}"):
                        perform_ui_action(action, None)


def analyst_result(run: AnalystRun, scope: str, person_id: str | None) -> None:
    label = "Demo replay" if run.mode == "replay" else f"Live AI · {run.model or 'unavailable'}"
    st.caption(f"{label} · Analysis as of {run.analysis_as_of:%d %b %Y}")
    st.caption(ANALYST_DISCLAIMER)
    ui.analyst_activity(activity_lines(run))
    checks = evidence_count(run)
    if checks or run.tool_trace:
        details_label = (
            f"{checks} evidence {'check' if checks == 1 else 'checks'} · View evidence & actions"
            if checks
            else "View evidence & actions"
        )
        with st.expander(details_label):
            if run.mode == "replay":
                st.caption(
                    "Scripted model turns authored for the fictional demo — not a live recording. "
                    "Tools, intake and validation run for real."
                )
            for step in run.tool_trace:
                st.write(f"**{step.tool}** · {step.scope} · {'ok' if step.ok else 'error'}")
                st.json({"input": step.input, "refs": step.evidence_refs, "summary": step.summary})
            st.json(
                {
                    "mode": run.mode,
                    "model": run.model,
                    "outer_model_turns": run.counts.outer_model_turns,
                    "outer_tool_calls": run.counts.outer_tool_calls,
                    "nested_intake_model_calls": run.counts.nested_intake_model_calls,
                    "nested_intake_tool_calls": run.counts.nested_intake_tool_calls,
                    "grounded": run.grounded,
                    "validation": [
                        {"code": item.code, "path": item.path} for item in run.validation
                    ],
                }
            )
    if not run.grounded or run.response is None:
        st.write("BlastBridge couldn't produce a grounded answer.")
        if run.error:
            st.caption(run.error)
        if st.button("Retry", key=f"ask-retry-{scope}"):
            submit_analyst(scope, person_id, None)
        analyst_draft(run, scope)
        return
    response = run.response
    st.session_state.setdefault("evidence_candidates", {}).update(
        {candidate.key: candidate for candidate in run.candidates}
    )
    st.session_state.setdefault("evidence_comparisons", {}).update(
        {comparison.key: comparison for comparison in run.comparisons}
    )
    st.write(response.answer_summary)
    if run.fallback:
        st.caption("Generated wording was withheld; showing grounded facts from BlastBridge tools.")
    if response.clarification:
        st.info(response.clarification)
    brief_view = bool(
        response.intent == "GENERATE_BRIEF" and response.brief and response.brief.sections
    )
    if brief_view:
        review_brief(run, scope)
    for title, section in uncovered_summaries(response, brief_view):
        analyst_section(title, section, run)
    if not brief_view:
        if response.brief:
            with st.expander("Readiness brief"):
                for section in response.brief.sections:
                    analyst_section(section.heading.capitalize(), section, run)
    if response.recommendations:
        st.write("**Recommended next actions**")
        for i, recommendation in enumerate(response.recommendations):
            action = recommendation_action(recommendation, run)
            if run.created_draft is not None:
                st.session_state["ask_proposed_result"] = run.created_draft.intake_result
            if (
                ui.analyst_recommendation(
                    recommendation.title,
                    recommendation.rationale,
                    medical=recommendation.authority == "DETERMINISTIC_GUIDANCE_RELAY",
                    key=f"{scope}-{i}",
                    action_label=ACTION_LABELS.get(action.kind) if action else None,
                )
                and action is not None
            ):
                perform_ui_action(action, run.symptom_proposal)
    action = navigation_action(run)
    if action is not None:
        if run.symptom_proposal is not None:
            analyst_symptom_proposal(run.symptom_proposal, action, scope)
        else:
            label_text = {
                "OPEN_REVIEW": "Open Review",
                "OPEN_FOLLOWUP": "Open Follow-up",
                "OPEN_SYMPTOM_FORM": "Log symptom report",
                "OPEN_PERSON": (
                    f"Open {PEOPLE[action.person_id].display_name.split()[0]}"
                    if action.person_id in PEOPLE
                    else "Open person"
                ),
            }[action.kind]
            if st.button(label_text, key=f"ask-navigation-{scope}", type="primary"):
                perform_ui_action(action, None)
    for limitation in response.limitations:
        st.caption(limitation)
    analyst_evidence_panels(run, scope)
    analyst_draft(run, scope)


def use_demo_date() -> None:
    st.session_state["reset_demo_view"] = True


def ask_workspace(person_id: str | None = None) -> None:
    scope = person_id or "home"
    s = st.session_state
    with st.container(key=f"ask-workspace-{scope}"):
        title = (
            f"Ask about {PEOPLE[person_id].display_name.split()[0]}"
            if person_id
            else "Ask BlastBridge"
        )
        st.subheader(title)
        with st.form(f"ask-form-{scope}", clear_on_submit=True):
            question = st.text_input(
                "Ask BlastBridge",
                placeholder="What would you like to do?",
                key=f"ask-question-{scope}",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Ask", type="primary")
        if submitted and question.strip():
            submit_analyst(scope, person_id, question)
        with st.container(horizontal=True, gap="small"):
            for label, name in analyst_suggestions(person_id):
                if st.button(label, key=f"ask-suggest-{scope}-{name}", type="tertiary"):
                    submit_analyst(scope, person_id, label, replay_name=name)
        run = s.get(f"ask_run_{scope}")
        if s.get(f"ask_notice_{scope}"):
            st.caption(s[f"ask_notice_{scope}"])
            if s.get(f"ask_demo_date_{scope}") and not live_available():
                st.button(
                    "Use demo date (19 Oct 2026)",
                    key=f"ask-demo-date-{scope}",
                    on_click=use_demo_date,
                )
        if run is not None:
            if person_id and run.fingerprint is not None:
                fingerprint = evidence_fingerprint(
                    person_id, analyst_context(person_id), analyst_data(include_catalog=False)
                )
                if is_stale(run, fingerprint):
                    st.info("Evidence changed since this analysis.")
                    if st.button("Run updated analysis", key=f"ask-update-{scope}"):
                        submit_analyst(scope, person_id, None, stale=True)
            analyst_result(run, scope, person_id)
            if (
                run.grounded
                and run.response
                and run.response.clarification
                and s.get(f"ask_replay_{scope}") == ("log_event", 0)
                and not live_available()
            ):
                reply = "Launcher 1. Launcher 2 fired too but I don't know how many."
                if st.button(reply, key=f"ask-clarify-{scope}", type="tertiary"):
                    submit_analyst(scope, person_id, reply, replay_name="log_event", replay_index=1)
            if st.button("Start over", key=f"ask-start-over-{scope}", type="tertiary"):
                for prefix in ("ask_conversation", "ask_run", "ask_replay", "ask_notice"):
                    s.pop(f"{prefix}_{scope}", None)
                st.rerun()


def dashboard() -> None:
    ui.brand()
    st.markdown(
        f'<div class="bb-home-date">{ANALYSIS_AS_OF:%A, %B} {ANALYSIS_AS_OF.day}</div>',
        unsafe_allow_html=True,
    )
    st.caption("Occupational brain-health readiness")
    approved = store.list_events(CONN, EventStatus.APPROVED, limit=-1)
    reports = store.list_symptom_reports(CONN)
    assessments = all_readiness(ANALYSIS_AS_OF)
    marks = organization_marks(approved, reports, ANALYSIS_AS_OF)
    with ui.surface("org"):
        selected = render_calendar("org", marks, person=False)
        day_column, log_column = st.columns([4, 1], vertical_alignment="center")
        with log_column:
            if selected and can_record_on(selected, date.today()):
                with st.container(key="log-action"):
                    with st.popover("+ Log", type="primary"):
                        if st.button("Training event · describe with AI"):
                            open_form(on_date=selected, mode="Describe / paste training record")
                        if st.button("Training event · enter manually"):
                            open_form(on_date=selected, mode="Enter manually")
        with day_column:
            if selected:
                with st.container(key="selected-day"):
                    st.subheader(f"{selected:%B} {selected.day}")
                    day_events = [event for event in approved if event.draft.event_date == selected]
                    urgent_day = marks.get(selected, DayMarks()).urgent
                    if not day_events and not urgent_day:
                        st.caption("No records on this date.")
                    for event in day_events:
                        d = event.draft
                        st.write(f"**{d.weapon_name}**")
                        st.write(label(d.training_context))
                        st.caption(
                            f"{len(d.crews)} {'crew' if len(d.crews) == 1 else 'crews'} · "
                            f"{d.participant_count} personnel"
                        )
                        st.caption(short_provenance(event.intake_source, event.status))
                        if st.button("Open record ›", key=f"day-record-{event.event_id}"):
                            open_review(event.event_id)
                        st.divider()
                    if urgent_day:
                        st.write("An urgent danger sign was recorded on this date")
                        st.page_link(PAGES["inbox"], label="Review urgent guidance")

    with st.container(key="attention-heading", horizontal=True, vertical_alignment="center"):
        st.subheader("Needs attention")
        st.page_link(PAGES["inbox"], label="Open Review")
    priority = priority_people(assessments)
    if not priority:
        st.caption("No personnel currently surfaced from the recorded information.")
    for item in priority[:5]:
        status = item.overall_readiness_status
        if ui.row(
            PEOPLE[item.person_id].display_name,
            readiness_reason(status),
            state=status.label,
            tone=ui.attention_tone(status),
            key=f"home-person-{item.person_id}",
            avatar=True,
        ):
            open_history(item.person_id)
    ask_workspace()
    ui.demo_details(DEMO_ARRANGEMENT_NOTE)
    with st.expander("Demo / Advanced"):
        st.date_input("Analysis as of", key="analysis_as_of", max_value=date.today())
        st.caption("Readiness and the occupational-pattern result are computed as of this date.")
        st.subheader("Recorded training events")
        st.dataframe(
            [
                {
                    "Date": event.draft.event_date,
                    "Weapon": event.draft.weapon_name,
                    "Context": label(event.draft.training_context),
                    "Physical events": count_text(event.draft.physical_event_count),
                    "Personnel": event.draft.participant_count,
                    "Crews": len(event.draft.crews),
                }
                for event in approved
            ],
            hide_index=True,
            width="stretch",
        )
        confirmed = st.checkbox("I understand this deletes all recorded events")
        if st.button("Reset to demo state", disabled=not confirmed):
            try:
                store.reset_demo(CONN, DEMO_PEOPLE, DEMO_EVENTS, DEMO_SYMPTOMS, DEMO_SOURCE_DRAFTS)
            except (store.StoreError, sqlite3.Error) as exc:
                st.warning(f"Could not reset demo data: {exc}")
                return
            for key in list(st.session_state):
                if key.startswith(("review", "editing", "f_", "sym_", "ai_")) or key in (
                    "last_decided",
                    "form_init",
                    "calendar_date",
                    "people_person",
                    "history_person_id",
                    "reconstructions",
                    "evidence_comparisons",
                    "evidence_candidates",
                    "evidence_open",
                ):
                    del st.session_state[key]
            st.session_state["reset_demo_view"] = True
            st.rerun()
        st.caption(
            "Reset restores the fictional demo state and the demo analysis date (19 Oct 2026)."
        )


def clear_ai_state() -> None:
    st.session_state.pop("event_decision", None)
    st.session_state.pop("event_proposal", None)
    st.session_state.pop("event_proposal_metadata", None)
    for key in list(st.session_state):
        if key.startswith("ai_") and key != "ai_drafts":
            del st.session_state[key]


def run_demo_replay() -> None:
    try:
        narrative, provider, metadata = load_replay()
        reference_date = date.fromisoformat(metadata["reference_date"])
    except (OSError, ValueError, KeyError, TypeError):
        st.session_state["ai_replay_notice"] = (
            "The demo replay is not available yet. Enter manually or use live AI when configured."
        )
        return
    st.session_state["ai_narrative"] = narrative
    st.session_state.pop("calendar_date", None)
    st.session_state["ai_metadata"] = metadata
    st.session_state["ai_result"] = run_intake(
        narrative,
        provider,
        load_weapon_catalog(ROOT / "data/reference/weapons.json"),
        list(PEOPLE.values()),
        reference_date,
    )


def ai_metadata(result: IntakeResult) -> dict[str, object]:
    stored = st.session_state.get("ai_metadata", {})
    metadata = stored if result.mode == "replay" or stored.get("source_type") else {}
    return {
        **metadata,
        "mode": result.mode,
        "model": result.model,
        "recorded_at": metadata.get("recorded_at"),
        "origins": result.origins,
    }


def show_ai_metadata(metadata: dict[str, object]) -> None:
    if metadata.get("source_type"):
        st.caption(f"Source: {metadata['source_type']} · {metadata.get('filename', '')}")
        st.caption(f"SHA-256: {metadata.get('sha256')}")
        st.caption("Observed on source")
        st.text(str(metadata.get("observed_text", "")))
    if metadata["mode"] == "replay":
        recorded = str(metadata.get("recorded_at") or "Not recorded")
        try:
            recorded = datetime.fromisoformat(recorded).strftime("%d %b %Y")
        except ValueError:
            pass
        st.caption(
            "Demo replay — previously validated AI response "
            f"(recorded {recorded}, {metadata.get('model')})"
        )
    else:
        st.caption(f"Model: {metadata.get('model')}")


def load_example_narrative() -> None:
    st.session_state["ai_narrative"] = GOLDEN_NARRATIVE
    st.session_state.pop("calendar_date", None)


def image_intake() -> None:
    st.caption(
        "FICTIONAL DEMO — do not upload real personnel, medical, PHI/PII, "
        "controlled or operational military records."
    )
    st.caption("Uploaded image bytes remain session-only and are not persisted by BlastBridge.")
    upload = st.file_uploader("Upload record", type=["jpg", "jpeg", "png", "webp"])
    if upload is None:
        return
    data = upload.getvalue()
    try:
        validate_upload(data, upload.type)
    except ValueError as exc:
        st.warning(str(exc))
        return
    digest = image_sha256(data)
    if st.session_state.get("ai_image_digest") != digest:
        clear_ai_state()
        st.session_state["ai_image_digest"] = digest
    st.session_state["ai_image_bytes"] = data
    st.markdown("**SOURCE IMAGE**")
    st.image(data, width="stretch")
    if st.button("Create proposal", type="primary"):
        try:
            metadata: dict[str, object] = {}
            intake_provider: IntakeProvider
            provider = AnthropicProvider() if live_available() else None
            reference_date = date.today()
            if provider is None:
                replay_provider, replay_metadata = load_image_replay(data)
                metadata.update(replay_metadata)
                reference_date = date.fromisoformat(replay_metadata["reference_date"])
                intake_provider = replay_provider
            else:
                intake_provider = provider
            with st.spinner("Reading the training record…"):
                result = run_image_intake(
                    data,
                    upload.type,
                    intake_provider,
                    load_weapon_catalog(ROOT / "data/reference/weapons.json"),
                    list(PEOPLE.values()),
                    reference_date,
                )
            st.session_state["ai_result"] = result
            st.session_state["ai_metadata"] = {
                **metadata,
                "source_type": "uploaded image",
                "filename": upload.name,
                "sha256": digest,
                "observed_text": result.narrative,
            }
        except (OSError, ValueError, KeyError, TypeError) as exc:
            st.warning(str(exc))
            st.caption("Use manual entry to record the training event.")
    result = st.session_state.get("ai_result")
    if result is not None:
        st.markdown("**WHAT BLASTBRIDGE READ**")
        with st.expander("Observed on source", expanded=True):
            st.text(result.narrative)
        if result.error:
            st.warning(result.error)
            st.caption("Use a clearer image or select Enter manually.")
            return
        ai_intake(image_mode=True)


def ai_intake(*, image_mode: bool = False) -> None:
    if not image_mode and st.session_state.get("ai_result") is None:
        text_intake_controls()
    result = st.session_state.get("ai_result")
    if result is None:
        return
    if result.error:
        st.warning(result.error)
        if result.mode == "live":
            st.caption("Demo replay uses the golden fictional narrative instead of your text.")
            st.button("Use demo replay instead", on_click=run_demo_replay)
        st.button("Start Over", on_click=clear_ai_state)
        return
    render_intake_proposal(result)


def text_intake_controls() -> None:
    workspace = st.container(key="ai-workspace")
    with workspace:
        st.text_area(
            "Describe / paste training record",
            key="ai_narrative",
            height=180,
            placeholder="Paste or type the training record here.",
        )
        st.button("Load example narrative", on_click=load_example_narrative, type="tertiary")
    available = live_available()
    with workspace:
        if not available:
            st.caption("Live AI isn't available in this demo. Use the demo replay.")
        live = replay = ui.actions()
    if live.button(
        "Create proposal",
        disabled=not available,
        type="secondary" if st.session_state.get("ai_result") else "primary",
    ):
        narrative = st.session_state["ai_narrative"]
        if len("".join(narrative.split())) < 20:
            st.warning("Paste or type a training record first.")
        else:
            st.session_state.pop("ai_pending", None)
            st.session_state["ai_metadata"] = {}
            with st.spinner("Building a proposed training record…"):
                st.session_state["ai_result"] = run_intake(
                    narrative,
                    AnthropicProvider(),
                    load_weapon_catalog(ROOT / "data/reference/weapons.json"),
                    list(PEOPLE.values()),
                    date.today(),
                )
    replay.button("Use demo replay", on_click=run_demo_replay)
    notice = st.session_state.pop("ai_replay_notice", None)
    if notice:
        st.info(notice)


def render_intake_proposal(
    result: IntakeResult, *, metadata: dict[str, object] | None = None
) -> None:
    metadata = ai_metadata(result) if metadata is None else metadata
    with st.container(key="proposed-draft"):
        st.subheader("Review event")
        st.write(
            "Proposal"
            if result.mode == "manual"
            else "AI-assisted proposal from uploaded record"
            if metadata.get("source_type")
            else "AI-assisted proposal"
        )
        st.caption(PROPOSAL_STATUS)
        st.caption("Nothing has been recorded yet. Check the details before approving.")
        values = result.form_values
        calendar_date = st.session_state.get("calendar_date")
        narrative_date = values.get("f_date")
        if calendar_date and narrative_date and narrative_date != calendar_date:
            narrative_date_label = (
                f"{narrative_date.day} {narrative_date:%b %Y}"
                if isinstance(narrative_date, date)
                else str(narrative_date)
            )
            calendar_date_label = (
                f"{calendar_date.day} {calendar_date:%b %Y}"
                if isinstance(calendar_date, date)
                else str(calendar_date)
            )
            st.info("Date differs from calendar context")
            st.caption(
                f"Source: {narrative_date_label} · Calendar selection: {calendar_date_label}"
            )
            st.caption("BlastBridge kept the date stated in the source.")
        for title, key in (
            ("Date", "f_date"),
            ("Activity", "f_type"),
            ("Training context", "f_context"),
            ("Weapon", "f_weapon"),
            ("Location / unit", "f_location"),
        ):
            value = values.get(key)
            if key == "f_weapon" and value:
                value = weapons().get(value, value)
            elif key == "f_type" and value:
                value = label(EventType(value))
            elif key == "f_context" and value:
                value = label(TrainingContext(value))
            elif isinstance(value, StrEnum):
                value = label(value)
            elif isinstance(value, date):
                value = value.strftime("%d %B %Y")
            ui.field(title, str(value) if value is not None else "Needs review")
        rows = []
        for i in values.get("f_crews", []):
            prefix = f"f_c{i}_"
            name = values[prefix + "name"]
            for position in POSITIONS:
                person = PEOPLE.get(values.get(prefix + position))
                as_written = (
                    ", ".join(
                        member.name_text
                        for member in result.proposal.crews[i].members
                        if member.position == position
                    )
                    if result.proposal
                    else ""
                )
                known = values.get(prefix + "known")
                count = (
                    values.get(prefix + "count")
                    if known == "Known"
                    else ("Unknown" if known == "Unknown" else "Needs review")
                )
                rows.append(
                    {
                        "Crew": name,
                        "Position": position.label,
                        "As written": as_written,
                        "Person": person.display_name if person else "Needs review",
                        "Origin": result.origins.get(f"{name} · {position.label}", "unresolved"),
                        "Physical events": str(count),
                    }
                )
        with st.container(key="draft-crews"):
            previous_crew = None
            for row in rows:
                if row["Crew"] != previous_crew:
                    ui.crew_heading(f"{row['Crew']} · {row['Physical events']} physical events")
                    previous_crew = row["Crew"]
                ui.compact_line(f"{row['Position']} · {row['Person']}")
                if row["As written"] and row["As written"] != row["Person"]:
                    ui.compact_line(f"As written: {row['As written']}", muted=True)
        if result.issues:
            with st.container(key="draft-issues"):
                st.markdown(":orange[Needs review]")
                for issue in sorted(result.issues, key=lambda item: not item.blocking):
                    st.write(f"{'Required · ' if issue.blocking else ''}{issue.message}")
        with st.expander("Source / provenance"):
            if result.mode == "manual":
                st.caption("Manually entered proposal")
            else:
                show_ai_metadata(metadata)
            for field_name, origin in result.origins.items():
                st.caption(f"{field_name}: {origin}")
            for step in result.trace:
                st.write(f"{'✓' if step.ok else '!'} {step.text}")
        approve_col = edit_col = save_col = discard_col = ui.actions()
        approve = approve_col.button("Approve event", disabled=result.draft is None, type="primary")
        edit = edit_col.button("Edit", type="tertiary")
        save = save_col.button("Save for later", disabled=result.draft is None)
        if (approve or save) and result.draft is not None:
            source = {
                "replay": IntakeSource.AI_REPLAY,
                "manual": IntakeSource.MANUAL,
            }.get(result.mode, IntakeSource.AI_LIVE)
            decision = save_reviewed_event(CONN, result.draft, source, approve=approve)
            if decision.event_id is None:
                st.warning(decision.error)
            else:
                if result.mode != "manual":
                    st.session_state.setdefault("ai_drafts", {})[decision.event_id] = metadata
                clear_ai_state()
                st.session_state.pop("f_ai_pending", None)
                st.session_state["event_decision"] = decision
                st.rerun()
        if edit:
            st.session_state["form_init"] = {**values, "f_mode": "Enter manually"}
            if values.get("f_date") is None and calendar_date:
                st.session_state["form_init"]["f_date"] = calendar_date
                metadata = {
                    **metadata,
                    "origins": {**result.origins, "Date": "selected on calendar"},
                }
            st.session_state["editing_event_id"] = None
            st.session_state["editing_revision"] = None
            clear_ai_state()
            st.session_state["ai_pending"] = metadata
            st.rerun()
        with discard_col.container(key="discard-proposal"):
            if st.button("Discard", type="tertiary", key="discard-new-event"):
                clear_ai_state()
                st.session_state.pop("f_ai_pending", None)
                st.switch_page(PAGES["dashboard"])


def new_event() -> None:
    init = st.session_state.pop("form_init", None)
    if init is None:
        st.session_state.pop("ai_pending", None)
        if "f_date" not in st.session_state:
            st.session_state.pop("f_ai_pending", None)
    else:
        # Keep provenance with the handed-off form across its own widget reruns.
        st.session_state["f_ai_pending"] = st.session_state.get("ai_pending")
    if init is None and "f_date" not in st.session_state:
        init = form_values()
        st.session_state["editing_event_id"] = None
    for key, value in (init or {}).items():
        st.session_state[key] = value
    editing = st.session_state.get("editing_event_id")

    header("Log training event", "Record what the crew physically did.")
    decision = st.session_state.get("event_decision")
    if decision is not None:
        if decision.error:
            st.warning(decision.error)
        elif decision.approved:
            st.success(APPROVED_STATUS)
        else:
            st.success("Saved to Review")
            st.caption(f"{DRAFT_STATUS} · Not in personnel history")
        if st.button("Open record" if decision.approved else "Open Review", type="primary"):
            open_review(decision.event_id)
        if st.button("Log another event"):
            open_form()
        return
    proposal = st.session_state.get("event_proposal")
    if proposal is not None:
        render_intake_proposal(
            proposal, metadata=st.session_state.get("event_proposal_metadata", {})
        )
        return
    mode = st.radio(
        "Entry mode",
        ["Describe / paste training record", "Upload / photograph record", "Enter manually"],
        key="f_mode",
        horizontal=True,
    )
    if mode == "Describe / paste training record":
        ai_intake()
        return
    if mode == "Upload / photograph record":
        image_intake()
        return
    if editing:
        st.info(f"Editing draft {editing}. Changes are saved when you review again.")

    with st.container(key="training-event-fields"):
        st.subheader("Event")
        a, b = st.columns(2)
        a.date_input("Date", value=None, max_value=date.today(), key="f_date")
        b.selectbox(
            "Activity type",
            list(EventType),
            index=None,
            format_func=label,
            key="f_type",
            placeholder="Select activity",
        )
        a.selectbox(
            "Training context",
            list(TrainingContext),
            index=None,
            format_func=label,
            key="f_context",
            placeholder="Select context",
        )
        b.selectbox(
            "Weapon system",
            list(weapons()),
            index=None,
            format_func=weapons().get,
            key="f_weapon",
            placeholder="Select weapon",
        )
        st.text_input("Location / unit (optional)", key="f_location")

    for i in st.session_state["f_crews"]:
        prefix = f"f_c{i}_"
        with st.container(key=f"crew-fields-{i}"):
            st.subheader(st.session_state[prefix + "name"])
            if len(st.session_state["f_crews"]) > 1:
                if st.button("Remove crew", key=prefix + "remove"):
                    change_crews(i)
            st.text_input("Crew name", key=prefix + "name")
            for col, pos in zip(st.columns(3), POSITIONS, strict=True):
                col.selectbox(
                    pos.label,
                    list(PEOPLE),
                    index=None,
                    format_func=person_text,
                    placeholder="Select a person",
                    key=prefix + pos,
                )
            st.caption("Count each launch once per crew. Do not multiply by people present.")
            st.radio(
                "Launch / firing-event count",
                ["Known", "Unknown"],
                index=None,
                horizontal=True,
                key=prefix + "known",
            )
            if st.session_state[prefix + "known"] == "Known":
                st.session_state.setdefault(prefix + "count", None)
                st.number_input(
                    "Number of physical launches",
                    min_value=1,
                    max_value=999,
                    value=None,
                    step=1,
                    key=prefix + "count",
                )
            else:
                st.session_state[prefix + "count"] = None
                if st.session_state[prefix + "known"] == "Unknown":
                    st.caption("Recorded as **Unknown**. Unknown is never zero.")
    if st.button("+ Add Crew"):
        change_crews()

    left, right, _ = st.columns([1, 1, 4])
    if right.button("Cancel"):
        st.session_state["editing_event_id"] = None
        st.session_state.pop("ai_pending", None)
        st.session_state.pop("f_ai_pending", None)
        st.switch_page(PAGES["dashboard"])
    if not left.button("Review event", type="primary"):
        return

    s = st.session_state
    if any(s.get(key) is None for key in ("f_date", "f_type", "f_context", "f_weapon")):
        st.warning(
            "Choose a date, activity type, training context and weapon system before review."
        )
        return
    if s["f_date"] > date.today():
        st.warning("Event date cannot be in the future.")
        return
    missing = [
        f"{s[f'f_c{i}_name']} · {pos.label}"
        for i in s["f_crews"]
        for pos in POSITIONS
        if not s.get(f"f_c{i}_{pos}")
    ]
    if missing:
        st.warning(f"Select a person for: {', '.join(missing)}.")
        return
    if any(s[f"f_c{i}_known"] is None for i in s["f_crews"]):
        st.warning("Choose whether the launch count is Known or Unknown.")
        return
    if any(s[f"f_c{i}_known"] == "Known" and s.get(f"f_c{i}_count") is None for i in s["f_crews"]):
        st.warning("Enter the number of physical launches, or choose Unknown.")
        return
    assignments = {}
    for i in s["f_crews"]:
        for pos in POSITIONS:
            assignments.setdefault(s[f"f_c{i}_{pos}"], []).append(
                f"{s[f'f_c{i}_name']} · {pos.label}"
            )
    duplicates = []
    for person_id, places in assignments.items():
        if len(places) > 1:
            times = "twice" if len(places) == 2 else f"{len(places)} times"
            duplicates.append(
                f"{PEOPLE[person_id].display_name} is assigned {times}: " + " and ".join(places)
            )
    if duplicates:
        st.warning("; ".join(duplicates))
        return
    try:
        draft = TrainingEventDraft(
            event_date=s["f_date"],
            event_type=s["f_type"],
            training_context=s["f_context"],
            weapon_system_id=s["f_weapon"],
            weapon_name=weapons()[s["f_weapon"]],
            location_unit=(s["f_location"] or "").strip() or None,
            crews=tuple(
                Crew(
                    crew_name=s[f"f_c{i}_name"].strip() or f"Launcher {i + 1}",
                    members=tuple(
                        CrewMember(person_id=s[f"f_c{i}_{pos}"], position=pos) for pos in POSITIONS
                    ),
                    physical_event_count=int(s[f"f_c{i}_count"])
                    if s[f"f_c{i}_known"] == "Known"
                    else None,
                )
                for i in s["f_crews"]
            ),
        )
    except ValidationError as exc:
        st.warning(" ".join(e["msg"].removeprefix("Value error, ") for e in exc.errors()))
        return
    if not editing:
        pending = s.get("ai_pending") or s.get("f_ai_pending") or {}
        s["event_proposal"] = IntakeResult(
            narrative=str(pending.get("observed_text", "")),
            mode=pending.get("mode", "manual"),
            model=pending.get("model"),
            draft=draft,
            form_values=form_values(draft),
            origins=pending.get("origins", {}),
        )
        s["event_proposal_metadata"] = pending
        st.rerun()
    try:
        store.update_draft(CONN, editing, draft, s["editing_revision"])
        event_id = editing
    except (store.StoreError, sqlite3.Error) as exc:
        # The draft changed or was decided elsewhere: show its current state instead of retrying.
        st.session_state["editing_event_id"] = None
        st.session_state["review_notice"] = f"Your edits were not saved: {exc}"
        open_review(editing)
    st.session_state["editing_event_id"] = None
    pending = st.session_state.pop("ai_pending", None)
    form_pending = st.session_state.pop("f_ai_pending", None)
    pending = pending or form_pending
    if pending:
        st.session_state.setdefault("ai_drafts", {})[event_id] = pending
    open_review(event_id)


def reconstruction_provenance(event: TrainingEvent) -> str | None:
    if event.reconstructed_from:
        return "Reconstructed from " + ", ".join(event.reconstructed_from)
    replacement = store.live_reconstruction_for_source(CONN, event.event_id)
    if replacement is not None:
        status = DRAFT_STATUS if replacement.status is EventStatus.DRAFT else APPROVED_STATUS
        return f"Replaced by reconstruction {replacement.event_id} ({status})"
    return None


def status_pill(event: TrainingEvent) -> str:
    return {
        EventStatus.DRAFT: f'<span class="bb-pill draft">{DRAFT_STATUS}</span>',
        EventStatus.APPROVED: f'<span class="bb-pill approved">{APPROVED_STATUS}</span>',
        EventStatus.REJECTED: f'<span class="bb-pill">{REJECTED_STATUS}</span>',
    }[event.status]


def decide(action: str, event: TrainingEvent) -> None:
    try:
        if action == "approve":
            store.approve_event(CONN, event.event_id, event.revision)
        else:
            store.reject_event(CONN, event.event_id, event.revision)
    except (store.StoreError, sqlite3.Error) as exc:
        st.session_state["review_notice"] = f"Decision was not saved: {exc}"
    else:
        st.session_state["last_decided"] = event.event_id
    st.session_state["review_event_id"] = None
    st.rerun()


def training_crew_rows(draft: TrainingEventDraft) -> None:
    for crew in draft.crews:
        st.write(f"**{crew.crew_name}**")
        for member in crew.members:
            st.write(f"{member.position.label} · {PEOPLE[member.person_id].display_name}")
        associations = (
            crew.physical_event_count * len(crew.members)
            if crew.physical_event_count is not None
            else None
        )
        st.caption(
            f"Physical events: {count_text(crew.physical_event_count)} · "
            f"{len(crew.members)} participants · Associations: {count_text(associations)}"
        )


def show_decision(event_id: str) -> None:
    try:
        event = store.get_event(CONN, event_id)
    except store.StoreError:
        st.session_state["last_decided"] = None
        return
    d = event.draft
    provenance = reconstruction_provenance(event) or provenance_text(
        event.intake_source, event.status
    )
    with st.container(key="decision-summary"):
        st.markdown(
            f"{status_pill(event)} &nbsp; **{escape(d.weapon_name)}** · "
            f"{d.event_date:%d %b %Y} · <small>{escape(event.event_id)}</small>",
            unsafe_allow_html=True,
        )
        if event.status is not EventStatus.APPROVED:
            st.caption(provenance)
            st.caption("This event was not added to anyone's history.")
            return
        st.caption(provenance)
        st.info("Approved. Each participant's history now includes this event.")
        st.write(f"{label(d.training_context)} · {d.location_unit or 'Location not recorded'}")
        training_crew_rows(d)
        members = [m for crew in d.crews for m in crew.members]
        for start in range(0, len(members), 4):
            row = members[start : start + 4]
            for col, m in zip(st.columns(len(row)), row, strict=True):
                if col.button(f"View {PEOPLE[m.person_id].display_name}", key=f"h-{m.person_id}"):
                    open_history(m.person_id)


def review() -> None:
    header("Training record", "Nothing enters personnel history until you approve it.")
    notice = st.session_state.pop("review_notice", None)
    if notice:
        st.warning(notice)
    decided = st.session_state.get("last_decided")
    if decided:
        show_decision(decided)
        st.page_link(PAGES["inbox"], label="Back to Review")
        return

    drafts = store.list_events(CONN, EventStatus.DRAFT, limit=50)
    event_id = st.session_state.get("review_event_id")
    if event_id is None:
        if not drafts:
            if not decided:
                st.info("Nothing waiting for review")
                st.caption(
                    "Drafts you save for later and reconstructed records awaiting approval "
                    "will appear here."
                )
            if st.button("+ Record Training Event", type="primary"):
                open_form()
            return
        event_id = st.selectbox(
            "Draft to review",
            [e.event_id for e in drafts],
            format_func=lambda i: next(
                f"{e.draft.weapon_name} · {e.draft.event_date:%d %b %Y} · {i}"
                for e in drafts
                if e.event_id == i
            ),
        )
    try:
        event = store.get_event(CONN, event_id)
    except store.StoreError:
        st.session_state["review_event_id"] = None
        st.session_state["review_notice"] = f"Event {event_id} no longer exists."
        st.rerun()
    if event.status is not EventStatus.DRAFT:
        # Decided elsewhere (another session or tab): show the outcome, not a stale draft.
        st.session_state["review_event_id"] = None
        st.session_state["last_decided"] = event.event_id
        st.rerun()
    d = event.draft
    shown = st.session_state.get("review_shown")
    if shown and shown[0] == event.event_id and shown[1] != event.revision:
        st.warning("This draft changed since you opened it. Check the updated details below.")
    st.session_state["review_shown"] = (event.event_id, event.revision)

    st.markdown(
        f"{status_pill(event)} &nbsp; <small>{escape(event.event_id)}</small>",
        unsafe_allow_html=True,
    )
    st.caption(
        reconstruction_provenance(event) or provenance_text(event.intake_source, event.status)
    )
    st.write("")

    metadata = st.session_state.get("ai_drafts", {}).get(event.event_id)
    if event.intake_source is not IntakeSource.MANUAL and event.status is EventStatus.DRAFT:
        st.info(f"{DRAFT_STATUS}. Not in personnel history.")
    if metadata:
        show_ai_metadata(metadata)
        with st.expander("Field origins"):
            st.dataframe(
                [{"Field": key, "Origin": value} for key, value in metadata["origins"].items()],
                hide_index=True,
            )

    known_links = sum(
        c.physical_event_count * len(c.members)
        for c in d.crews
        if c.physical_event_count is not None
    )
    unknown_people = sum(len(c.members) for c in d.crews if c.physical_event_count is None)
    with st.container(key="approval-summary"):
        st.subheader("What approval will record")
        a, b, c, links = st.columns(4)
        a.metric("Crews", len(d.crews))
        b.metric("Unique participants", d.participant_count)
        c.metric("Physical events (launches)", count_text(d.physical_event_count))
        links.metric(
            "Participant-event associations",
            str(known_links) if d.unknown_crew_count < len(d.crews) else "Unknown",
        )
        if unknown_people:
            links.caption(f"+ {unknown_people} people with unknown count")
        training_crew_rows(d)
        st.caption(
            "Launches are counted once per crew; associations link people to those launches "
            "and are not additional launches. When a crew's count is unknown, that crew's "
            "associations are unknown, never zero."
            + (
                f" The known crews' total is {known_links} associations across "
                f"{d.known_physical_event_count} physical launches."
                if d.unknown_crew_count < len(d.crews)
                else ""
            )
        )

    with st.container(key="review-event-fields"):
        st.subheader("Event")
        a, b, c = st.columns(3)
        with a:
            field("Date", f"{d.event_date:%d %b %Y}")
            field("Activity", label(d.event_type))
        with b:
            field("Weapon system", d.weapon_name)
            field("Training context", label(d.training_context))
        with c:
            field("Location / unit", d.location_unit or "Not recorded")

    # Keys carry the revision on screen: a click made on an older revision does not fire here.
    key = f"{event.event_id}-r{event.revision}"
    a, b, c, _ = st.columns([1.3, 1, 1, 3])
    if a.button("Approve", type="primary", key=f"approve-{key}"):
        decide("approve", event)
    if b.button("Edit", key=f"edit-{key}"):
        open_form(event)
    with c.container(key=f"reject-action-{key}"):
        if st.button("Reject draft", key=f"reject-{key}"):
            decide("reject", event)


def followup_card(result: FollowUp) -> None:
    if result.state is FollowUpState.URGENT_EVALUATION_RECOMMENDED:
        st.error(result.headline)
    elif result.state is FollowUpState.FOLLOW_UP_SUGGESTED:
        with st.container(border=True):
            st.markdown(
                f'<span class="bb-pill medical">{escape(result.headline)}</span>',
                unsafe_allow_html=True,
            )
    else:
        st.caption(result.headline)
    for sentence in result.missing:
        st.caption(sentence)
    st.write(result.explanation)


def official_resources() -> None:
    for source in SOURCES:
        st.markdown(f"[{source.title}]({source.url})")
        st.caption(f"{source.publisher} · {source.version}")
        st.write(source.use)
        st.caption(source.verification)
    st.caption(GOVERNANCE_NOTE)


def linked_event_text(event_id: str | None) -> str:
    if event_id is None:
        return "No linked event"
    try:
        event = store.get_event(CONN, event_id)
    except store.StoreError:
        return event_id
    return f"{event.draft.event_date:%d %b %Y} · {event.draft.weapon_name} · {event_id}"


def report_fields(report: SymptomReportDraft) -> None:
    st.write(f"{PEOPLE[report.person_id].display_name} · FICTIONAL · {report.person_id}")
    st.write(f"Report date: {report.report_date:%d %b %Y}")
    st.write(f"Linked event: {linked_event_text(report.event_id)}")
    st.write(report.temporal_relationship.label)
    st.write("Symptoms: " + (", ".join(item.label for item in report.symptoms) or "None recorded"))
    if report.danger_signs:
        st.write("Danger signs: " + "; ".join(item.label for item in report.danger_signs))
    else:
        st.caption("Danger signs: None recorded")
    st.write(f"Persistence: {report.persistence.label}")
    st.write(f"Functional impact: {report.functional_impact.label}")
    st.write(f"Source: {report.source.label}")
    st.write(f"Note: {report.note or 'Not recorded'}")


def clear_symptom_state() -> None:
    for key in list(st.session_state):
        if key.startswith("sym_"):
            del st.session_state[key]


def symptom_form(person_id: str) -> None:
    s = st.session_state
    if s.get("sym_person") != person_id:
        clear_symptom_state()
    notice = s.pop("sym_notice", None)
    if notice:
        st.info(notice)
    if not s.get("sym_open"):
        return
    if s.get("sym_ai_proposal"):
        st.info("AI-assisted proposal — review before confirming")
    st.caption(BOUNDARY_NOTE)
    pending = s.get("sym_review")
    if pending is not None:
        with st.container(border=True):
            st.subheader("Review report")
            report_fields(pending)
            if pending.note:
                st.caption(NOTE_RULE_CAPTION)
            followup_card(evaluate(pending))
            confirm, edit, discard = st.columns(3)
            if confirm.button("Confirm", key="sym_confirm"):
                try:
                    store.confirm_symptom_report(CONN, pending)
                except (store.StoreError, sqlite3.Error) as exc:
                    st.warning(f"Could not confirm report: {exc}")
                else:
                    clear_symptom_state()
                    s["sym_person"] = person_id
                    s["sym_notice"] = "Report confirmed."
                    st.rerun()
            if edit.button("Edit", key="sym_edit"):
                s["sym_restore"] = s["sym_values"]
                del s["sym_review"]
                st.rerun()
            if discard.button("Discard", key="sym_discard"):
                clear_symptom_state()
                st.rerun()
        return

    for key, value in s.pop("sym_restore", {}).items():
        s[key] = value
    entries = store.member_history(CONN, person_id)
    by_id = {entry.event_id: entry for entry in entries}
    with st.container(border=True):
        st.subheader("Log Symptom Report")
        event_id = st.selectbox(
            "Linked event (optional)",
            [None, *by_id],
            key="sym_w_event",
            format_func=lambda value: (
                "No linked event"
                if value is None
                else (
                    f"{by_id[value].event_date:%d %b %Y} · {by_id[value].weapon_name} · "
                    f"{by_id[value].position.label}"
                )
            ),
        )
        relationships = [
            TemporalRelationship.AFTER_RECORDED_EVENT
            if event_id
            else TemporalRelationship.NOT_LINKED_TO_EVENT,
            TemporalRelationship.RELATIONSHIP_UNKNOWN,
        ]
        if s.get("sym_w_relationship") not in relationships:
            s["sym_w_relationship"] = None
        relationship = st.radio(
            "Temporal relationship",
            relationships,
            index=None,
            format_func=lambda value: value.label,
            key="sym_w_relationship",
        )
        if s.get("sym_ai_needs_date"):
            report_date = st.date_input(
                "Report date", value=None, max_value=date.today(), key="sym_w_date"
            )
            if report_date is None:
                st.caption("Report date was not stated — choose the date before reviewing.")
        else:
            report_date = st.date_input("Report date", max_value=date.today(), key="sym_w_date")
        st.write(SYMPTOM_LIST_LABEL)
        symptoms = tuple(
            item for item in Symptom if st.checkbox(item.label, key=f"sym_w_s_{item.value}")
        )
        with st.container(border=True):
            st.write(DANGER_SIGN_LABEL)
            danger_signs = tuple(
                item for item in DangerSign if st.checkbox(item.label, key=f"sym_w_d_{item.value}")
            )
        persistence = st.radio(
            "Persistence",
            list(Persistence),
            index=None,
            format_func=lambda value: value.label,
            key="sym_w_persistence",
        )
        impact = st.radio(
            "Functional impact",
            list(FunctionalImpact),
            index=None,
            format_func=lambda value: value.label,
            key="sym_w_impact",
        )
        source = st.radio(
            "Source",
            list(SymptomSource),
            index=None,
            format_func=lambda value: value.label,
            key="sym_w_source",
        )
        note = st.text_area("Note (optional)", max_chars=500, key="sym_w_note")
        st.caption(NOTE_RULE_CAPTION)
        if st.button("Discard", key="sym_form_discard"):
            clear_symptom_state()
            st.rerun()
        if not st.button("Review report", key="sym_form_review"):
            return
        if report_date is None:
            st.warning("Choose the report date.")
            return
        if any(value is None for value in (relationship, persistence, impact, source)):
            st.warning(
                "Choose temporal relationship, persistence, functional impact and "
                "source explicitly."
            )
            return
        if report_date > date.today():
            st.warning("Report date cannot be in the future.")
            return
        if (
            relationship is TemporalRelationship.AFTER_RECORDED_EVENT
            and event_id
            and report_date < by_id[event_id].event_date
        ):
            st.warning("A report after a recorded event cannot predate that event.")
            return
        try:
            pending = SymptomReportDraft(
                person_id=person_id,
                event_id=event_id,
                report_date=report_date,
                source=source,
                symptoms=symptoms,
                danger_signs=danger_signs,
                note=note,
                temporal_relationship=relationship,
                persistence=persistence,
                functional_impact=impact,
            )
        except ValidationError as exc:
            st.warning(" ".join(e["msg"].removeprefix("Value error, ") for e in exc.errors()))
            return
        s["sym_values"] = {key: value for key, value in s.items() if key.startswith("sym_w_")}
        s["sym_review"] = pending
        st.rerun()


def followup_list(key: str) -> None:
    reports = [
        report
        for report in store.list_symptom_reports(CONN)
        if report.draft.report_date <= ANALYSIS_AS_OF
        and evaluate(report.draft).state is not FollowUpState.NO_FOLLOWUP_RULE_TRIGGERED
    ]
    reports.sort(
        key=lambda report: (
            evaluate(report.draft).state is FollowUpState.URGENT_EVALUATION_RECOMMENDED,
            report.draft.report_date,
            report.confirmed_at,
        ),
        reverse=True,
    )
    if not reports:
        st.write(EMPTY_FOLLOWUP)
        st.caption(ABSENCE_NOTE)
    for report in reports:
        result = evaluate(report.draft)
        urgent = result.state is FollowUpState.URGENT_EVALUATION_RECOMMENDED
        if ui.row(
            PEOPLE[report.draft.person_id].display_name,
            f"{report.draft.report_date.day} {report.draft.report_date:%B}",
            state=(
                "Urgent medical evaluation recommended"
                if urgent
                else "Medical follow-up recommended"
            ),
            tone="red" if urgent else "orange",
            key=f"{key}-{report.report_id}",
            avatar=True,
        ):
            open_history(report.draft.person_id)
        with st.expander("Report details"):
            report_fields(report.draft)
            followup_card(result)


def guidance_resources() -> None:
    official_resources()
    st.caption(BOUNDARY_NOTE)
    st.caption(PRIVACY_NOTE)


def followup() -> None:
    header("Follow-up", "Confirmed reports for fictional personnel.")
    st.caption(f"Analysis as of {ANALYSIS_AS_OF:%d %b %Y}")
    followup_list("followup")
    with st.expander("Official resources"):
        guidance_resources()


def inbox() -> None:
    ui.brand("Review")
    st.caption("Saved items awaiting a decision")
    training, guidance = st.tabs(["Training drafts", "Follow-up"])
    with training:
        drafts = store.list_events(CONN, EventStatus.DRAFT, limit=-1)
        if not drafts:
            ui.empty_state()
        for event in drafts:
            d = event.draft
            crew_text = f"{len(d.crews)} {'crew' if len(d.crews) == 1 else 'crews'}"
            if ui.row(
                f"{d.event_date.day} {d.event_date:%b} · {d.weapon_name} · {crew_text}",
                reconstruction_provenance(event)
                or short_provenance(event.intake_source, event.status),
                state="Awaiting approval",
                tone="violet",
                key=f"inbox-{event.event_id}",
            ):
                open_review(event.event_id)
    with guidance:
        followup_list("inbox-followup")
        with st.expander("Official resources"):
            guidance_resources()


def people_list() -> None:
    st.session_state.pop("history_person_id", None)
    st.session_state.pop("people_person", None)
    history()


def history() -> None:
    chosen = st.session_state.pop("history_person_id", None)
    if chosen:
        st.session_state["people_person"] = chosen
    person_id = st.session_state.get("people_person")
    if person_id not in PEOPLE:
        ui.brand("People")
        query = (
            st.text_input(
                "Search people",
                key="people_search",
                placeholder="Search people",
                label_visibility="collapsed",
            )
            .strip()
            .casefold()
        )
        assessments = all_readiness(ANALYSIS_AS_OF)
        matches = [
            p
            for p in PEOPLE.values()
            if query in f"{p.display_name} {p.callsign} {p.section}".casefold()
        ]
        if not matches:
            st.caption("No fictional personnel match your search.")
        for p in matches:
            status = assessments[p.person_id].overall_readiness_status
            if ui.row(
                p.display_name,
                p.section,
                state="" if status is ReadinessStatus.ROUTINE_MONITORING else status.label,
                tone=ui.attention_tone(status),
                key=f"people-{p.person_id}",
                avatar=True,
            ):
                open_history(p.person_id)
        ui.demo_details(DEMO_ARRANGEMENT_NOTE)
        return

    if ui.action("← People", "back-people"):
        st.session_state.pop("people_person", None)
        clear_symptom_state()
        st.switch_page(PAGES["history"])
    p = PEOPLE[person_id]
    entries = store.member_history(CONN, person_id)
    reports = store.list_symptom_reports(CONN, person_id)
    visible_reports = [report for report in reports if report.draft.report_date <= ANALYSIS_AS_OF]
    assessment = readiness_for(person_id, ANALYSIS_AS_OF)
    pattern = assessment.ml_pattern
    with st.container(key="person-header"):
        ui.profile(p.display_name)
        ui.brand(p.display_name)
        st.caption(f"{p.section} · {p.unit}")
        st.caption(f"Analysis as of {ANALYSIS_AS_OF:%d %b %Y}")
    status = assessment.overall_readiness_status
    if status is ReadinessStatus.ROUTINE_MONITORING:
        st.caption(status.label)
    else:
        with st.container(key=f"attention-band-{ui.attention_tone(status)}"):
            st.write(f"**{status.label.upper()}**")
            st.write(readiness_reason(status))
            if assessment.symptom_followup_status in (
                FollowUpState.FOLLOW_UP_SUGGESTED,
                FollowUpState.URGENT_EVALUATION_RECOMMENDED,
            ):
                st.caption("This guidance comes from BlastBridge's deterministic follow-up rules.")
                with st.container(key="followup-action-person"):
                    if st.button("View Follow-up"):
                        st.switch_page(PAGES["followup"])
    with ui.surface("person"):
        selected = render_calendar(
            "person", person_marks(entries, reports, ANALYSIS_AS_OF), person=True
        )
    if selected:
        with st.container(key="person-selected-day"):
            st.subheader(f"{selected:%B} {selected.day}")
            day_entries = [entry for entry in entries if entry.event_date == selected]
            day_reports = [report for report in reports if report.draft.report_date == selected]
            if not day_entries and not day_reports:
                st.caption("No records on this date.")
            for entry in day_entries:
                st.write(f"**{entry.weapon_name}** · {entry.position.label}")
                st.caption(f"Physical events: {count_text(entry.physical_event_count)}")
                st.caption(short_provenance(entry.intake_source, EventStatus.APPROVED))
            for report in day_reports:
                st.write("**Symptom report**")
                st.write(
                    ", ".join(item.label for item in report.draft.symptoms)
                    or "No symptoms recorded"
                )
                st.caption(report.draft.temporal_relationship.label)
                st.caption(
                    f"{report.draft.persistence.label} · {report.draft.functional_impact.label}"
                )
                followup_card(evaluate(report.draft))
            if can_record_on(selected, date.today()):
                if ui.action("+ Log symptom", "symptom-log", primary=True):
                    clear_symptom_state()
                    st.session_state["sym_person"] = person_id
                    st.session_state["sym_open"] = True
                    st.session_state["sym_restore"] = {"sym_w_date": selected}
    symptom_form(person_id)

    st.subheader("Insights")
    with st.container(key="insight-exposure"):
        if pattern is None or pattern.status is PatternStatus.PATTERN_NOT_AVAILABLE:
            summary = PatternStatus.PATTERN_NOT_AVAILABLE.label
        elif pattern.status is PatternStatus.ATYPICAL_ELEVATED_ACTIVITY:
            summary = "Atypical elevated occupational cadence"
        elif pattern.status is PatternStatus.ATYPICAL_REDUCED_ACTIVITY:
            summary = "No elevated-cadence signal"
        else:
            summary = "Recorded HIMARS cadence within the scenario reference"
        with ui.insight("Exposure pattern", summary, "violet"):
            if pattern is None or pattern.status is PatternStatus.PATTERN_NOT_AVAILABLE:
                st.caption(pattern.reason if pattern else "pattern reference unavailable")
            elif pattern.status is PatternStatus.ATYPICAL_REDUCED_ACTIVITY:
                st.caption(
                    "An unusual lower-activity pattern is noted under 'Why was this surfaced?' "
                    "(informational)."
                )
            elif pattern.status is not PatternStatus.ATYPICAL_ELEVATED_ACTIVITY:
                st.write("Recorded HIMARS training cadence within the fictional scenario reference")
            st.caption("See Why was this surfaced? for evidence and comparison details.")
    with st.container(key="insight-symptoms"):
        if visible_reports:
            latest = visible_reports[0].draft
            summary = ", ".join(item.label for item in latest.symptoms) or "No structured symptoms"
        else:
            summary = "No confirmed symptom reports"
        with ui.insight("Symptoms", summary, "primary"):
            if visible_reports:
                st.caption(f"{latest.persistence.label} · reported {latest.report_date:%d %b %Y}")
            else:
                st.write(summary)
    with st.container(key="insight-followup"):
        if assessment.symptom_followup_status is FollowUpState.URGENT_EVALUATION_RECOMMENDED:
            summary, tone = "Urgent medical evaluation recommended", "red"
        elif assessment.symptom_followup_status is FollowUpState.FOLLOW_UP_SUGGESTED:
            summary, tone = "Medical follow-up recommended", "orange"
        else:
            summary, tone = "No rule-based follow-up signal", "gray"
        with ui.insight("Follow-up", summary, tone):
            st.caption("See Follow-up guidance & sources for confirmed reports and guidance.")

    ask_workspace(person_id)
    with st.expander("Why was this surfaced?"):
        for evidence in assessment.evidence_lines:
            st.write(evidence)
        st.caption(PATTERN_DISCLAIMER)
        st.caption(ELEVATION_RULE_TEXT)
        if pattern and pattern.status is PatternStatus.ATYPICAL_REDUCED_ACTIVITY:
            st.write(REDUCED_TEXT)
            st.caption(OBSERVATION_NOTE)
        elif pattern and pattern.status is PatternStatus.ATYPICAL_ELEVATED_ACTIVITY:
            st.write("Elevated features")
            for name in pattern.elevated_features:
                st.write(FEATURE_LABELS[name])
        if pattern and pattern.comparisons:
            st.dataframe(
                [
                    {
                        "Feature": item.label,
                        "Recorded": item.value,
                        "Reference median": comparison_number(item.median),
                        "IQR q25–q75": (
                            f"{comparison_number(item.q25)}–{comparison_number(item.q75)}"
                        ),
                    }
                    for item in pattern.comparisons
                ],
                hide_index=True,
                width="stretch",
            )
            st.write(DIFFERING_HEADING)
            for item in pattern.differing:
                st.write(
                    f"{item.label}: {item.value:g} "
                    "(fictional HIMARS scenario reference median "
                    f"{comparison_number(item.median)})"
                )
            if not pattern.differing:
                st.caption(
                    "No features outside the fictional HIMARS scenario reference's "
                    "percentile ranges."
                )
        elif pattern:
            st.caption(pattern.reason)
        st.caption(CONTEXT_NOTE)
        for note in assessment.data_quality_notes:
            st.caption(note)
        st.caption(
            "IsolationForest · 100 trees · prototype analytic threshold: "
            "5th percentile of reference scores"
        )
    with st.expander("Research details"):
        st.caption(DEMO_ARRANGEMENT_NOTE)
        st.write(REFERENCE_LABEL)
        model = pattern_model()
        if model is None:
            st.caption("Occupational-pattern model unavailable (reference not built)")
        else:
            metadata = model.metadata
            st.write(f"Evidence: {metadata.get('evidence_id', 'Not documented')}")
            for limitation in metadata.get("source_limitations", []):
                st.write(limitation)
            st.write("Scenario assumptions")
            for name, assumption in metadata.get("scenario_assumptions", {}).items():
                st.caption(f"{name}: {assumption['value']} · {assumption['basis']}")
            st.write(
                f"{metadata.get('independent_fictional_careers')} independent fictional careers · "
                f"{metadata.get('repeated_analysis_windows')} repeated analysis windows"
            )
            st.caption(metadata.get("observation_note", ""))
            st.write("Fingerprint")
            st.json(metadata.get("fingerprint", {}))
            st.caption(f"scikit-learn {metadata.get('sklearn_version_pinned')}")
    with st.expander("Follow-up guidance & sources"):
        st.page_link(PAGES["followup"], label="Open Follow-up")
        st.caption(
            "Deterministic guidance from TBICoE/CDC sources; "
            "independent of the occupational-pattern model."
        )
        if not visible_reports:
            st.caption("No confirmed symptom reports.")
        for report in visible_reports:
            st.write(f"Report: {report.draft.report_date:%d %b %Y}")
            report_fields(report.draft)
            followup_card(evaluate(report.draft))
        guidance_resources()

    with st.expander("Chronological detail"):
        training_by_id = {entry.event_id: entry for entry in entries}
        reports_by_id = {report.report_id: report for report in reports}
        timeline = [(entry.event_date, "", "training", entry.event_id) for entry in entries]
        timeline.extend(
            (report.draft.report_date, report.confirmed_at, "report", report.report_id)
            for report in reports
        )
        for _, _, kind, record_id in sorted(timeline, reverse=True):
            with st.container(key=f"row-timeline-{kind}-{record_id}"):
                if kind == "training":
                    entry = training_by_id[record_id]
                    st.write(f"**{entry.event_date:%d %b %Y} · {entry.weapon_name}**")
                    st.write(f"{label(entry.training_context)} · {entry.position.label}")
                    st.write(
                        f"Physical events: {count_text(entry.physical_event_count)} · "
                        f"{entry.crew_name}"
                    )
                    st.caption(provenance_text(entry.intake_source, EventStatus.APPROVED))
                else:
                    report = reports_by_id[record_id]
                    st.write(f"**{report.draft.report_date:%d %b %Y} · Symptom report**")
                    report_fields(report.draft)
                    followup_card(evaluate(report.draft))


PAGES = {
    "dashboard": st.Page(dashboard, title="Home", icon=":material/calendar_month:", default=True),
    "history": st.Page(people_list, title="People", icon=":material/groups:", url_path="history"),
    "person": st.Page(history, title="Person", url_path="person", visibility="hidden"),
    "inbox": st.Page(inbox, title="Review", icon=":material/inbox:"),
    "new": st.Page(
        new_event, title="Log training event", icon=":material/add_circle:", visibility="hidden"
    ),
    "review": st.Page(
        review, title="Training record", icon=":material/fact_check:", visibility="hidden"
    ),
    "followup": st.Page(
        followup, title="Follow-up", icon=":material/assignment_ind:", visibility="hidden"
    ),
}

try:
    page = st.navigation(list(PAGES.values()), position="hidden")
    current_page = next(key for key, target in PAGES.items() if target.url_path == page.url_path)
    pending_count = len(store.list_events(CONN, EventStatus.DRAFT, limit=-1))
    ui.navigation(PAGES, current_page, pending_count)
    page.run()
finally:
    CONN.close()
