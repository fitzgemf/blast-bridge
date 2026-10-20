"""BlastBridge recorder demo. FICTIONAL data only. Run: streamlit run app/streamlit_app.py"""

import os
import sqlite3
from collections import Counter
from datetime import date
from enum import StrEnum
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from blastbridge.data.catalog import load_weapon_catalog
from blastbridge.models.enums import EventType
from blastbridge.models.training_tempo import TrainingContext
from blastbridge.product import store
from blastbridge.product.agent import (
    GOLDEN_NARRATIVE,
    IntakeResult,
    load_replay,
    run_intake,
)
from blastbridge.product.anthropic_provider import AnthropicProvider, live_available
from blastbridge.product.calendar_view import (
    DEMO_STORY_DATE,
    DayMarks,
    can_record_on,
    month_weeks,
    organization_marks,
    person_marks,
)
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
    PATTERN_DISCLAIMER,
    PatternModel,
    PatternStatus,
    assess_pattern,
    fit_pattern_model,
    load_baseline,
    occupational_features,
)
from blastbridge.product.readiness import ReadinessAssessment, ReadinessStatus, assess_readiness
from blastbridge.product.seed import DEMO_EVENTS, DEMO_PEOPLE, DEMO_SYMPTOMS
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

st.set_page_config(page_title="BlastBridge", page_icon="◆", layout="wide")
st.markdown(
    """
<style>
.block-container {max-width: 1100px; padding-top: 2.2rem;}
.bb-sub {opacity: .72; margin: -.6rem 0 1rem 0;}
.bb-banner {background: rgba(128,128,128,.10); border: 1px solid rgba(128,128,128,.35);
  padding: .55rem .9rem; border-radius: 8px; font-size: .9rem; margin-bottom: 1.2rem;}
.bb-banner b {letter-spacing: .06em;}
.bb-pill {display: inline-block; padding: .12rem .65rem; border-radius: 999px;
  font-size: .8rem; font-weight: 600; border: 1px solid rgba(128,128,128,.35);}
.bb-pill.approved, .bb-pill.draft {background: rgba(128,128,128,.12);}
[data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.25);
  border-radius: 12px; padding: .8rem;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius: 12px;
  border-color: rgba(128,128,128,.25);}
.st-key-cal-org button, .st-key-cal-person button {min-height: 2.6rem; padding: .2rem;}
.bb-pill.routine {background: rgba(128,128,128,.10);}
.bb-pill.review {background: rgba(194,137,31,.10); border-color: rgba(194,137,31,.30);}
.bb-pill.medical {background: rgba(194,137,31,.18); border-color: rgba(194,137,31,.65);}
.bb-pill.urgent {background: rgba(180,45,45,.13); border-color: rgba(180,45,45,.65);}
.bb-label {font-size: .78rem; opacity: .65; text-transform: uppercase; letter-spacing: .05em;}
.bb-value {font-size: 1.02rem; margin-bottom: .55rem;}
.bb-name {font-size: 1.45rem; font-weight: 600; margin-bottom: .1rem;}
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_resource
def _initialized(path: str) -> str:
    conn = store.connect(path)
    store.init_db(conn)
    store.seed_people(conn, DEMO_PEOPLE)
    store.seed_demo_events(conn, DEMO_EVENTS)
    store.seed_demo_symptoms(conn, DEMO_SYMPTOMS)
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
st.session_state.setdefault("analysis_as_of", date.today())
ANALYSIS_AS_OF = st.sidebar.date_input(
    "Analysis as of", key="analysis_as_of", max_value=date.today()
)
st.sidebar.caption("Readiness and the occupational-pattern result are computed as of this date.")


@st.cache_resource
def pattern_model() -> PatternModel | None:
    try:
        rows, metadata = load_baseline()
    except FileNotFoundError:
        return None
    return fit_pattern_model(rows, metadata)


def readiness_for(person_id: str, as_of: date) -> ReadinessAssessment:
    entries = store.member_history(CONN, person_id)
    reports = store.list_symptom_reports(CONN, person_id)
    model = pattern_model()
    pattern = (
        assess_pattern(model, (entry.event_date for entry in entries), as_of) if model else None
    )
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


def render_calendar(key: str, marks: dict[date, DayMarks], person: bool) -> date | None:
    today = date.today()
    s = st.session_state
    s.setdefault(f"{key}_month", today.replace(day=1))
    s.setdefault(f"{key}_day", today)
    month = s[f"{key}_month"]
    with st.container(key=f"cal-{key}"):
        previous, title, following = st.columns([1, 5, 1])
        if previous.button("‹", key=f"{key}-previous"):
            s[f"{key}_month"] = date(month.year - (month.month == 1), (month.month - 2) % 12 + 1, 1)
            st.rerun()
        title.markdown(f"**{month:%B %Y}**")
        if following.button("›", key=f"{key}-next"):
            s[f"{key}_month"] = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
            st.rerun()
        for column, weekday in zip(
            st.columns(7),
            ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"),
            strict=True,
        ):
            column.caption(weekday)
        for week in month_weeks(month.year, month.month):
            for column, day in zip(st.columns(7), week, strict=True):
                if day is None:
                    column.write("")
                    continue
                enabled = can_record_on(day, today)
                mark = marks.get(day, DayMarks()) if enabled else DayMarks()
                text = str(day.day)
                if mark.training:
                    text += " :gray[●]"
                if person and mark.symptom:
                    text += " :blue[◆]"
                if mark.attention:
                    text += " :orange[●]"
                if mark.urgent:
                    text += " :red[●]"
                if column.button(
                    text,
                    key=f"{key}-{day.isoformat()}",
                    disabled=not enabled,
                    type="primary" if day == s[f"{key}_day"] else "secondary",
                ):
                    s[f"{key}_day"] = day
                    st.rerun()
        st.caption(
            "● occupational record · "
            + ("◆ symptom report · " if person else "")
            + "● (amber) personnel needing review/follow-up · ● (red) urgent danger sign only"
        )
    return s.get(f"{key}_day")


def label(value: StrEnum) -> str:
    return value.value.replace("_", " ").capitalize()


def count_text(n: int | None) -> str:
    return "Unknown" if n is None else str(n)


def person_text(person_id: str) -> str:
    p = PEOPLE[person_id]
    return f"{p.display_name} “{p.callsign}” · {p.section}"


def header(title: str, subtitle: str) -> None:
    st.title(title)
    st.markdown(f'<div class="bb-sub">{subtitle}</div>', unsafe_allow_html=True)
    demo_banner()


def demo_banner() -> None:
    st.markdown(
        '<div class="bb-banner">FICTIONAL DEMO — All people and events are invented. '
        "BlastBridge records occupational exposure; exposure does not imply injury.</div>",
        unsafe_allow_html=True,
    )


def field(name: str, value: str) -> None:
    st.markdown(
        f'<div class="bb-label">{name}</div><div class="bb-value">{value}</div>',
        unsafe_allow_html=True,
    )


def crew_names(event: TrainingEvent) -> str:
    return ", ".join(PEOPLE[m.person_id].display_name for c in event.draft.crews for m in c.members)


# ---- navigation helpers -------------------------------------------------------------------------


def form_values(d: TrainingEventDraft | None = None) -> dict[str, object]:
    values = {
        "f_date": d.event_date if d else date.today(),
        "f_type": d.event_type if d else EventType.WEAPON_FIRING,
        "f_context": d.training_context if d else TrainingContext.HOME_STATION,
        "f_weapon": d.weapon_system_id if d else "m142-himars",
        "f_location": (d.location_unit or "") if d else "",
        "f_crews": list(range(len(d.crews))) if d else [0],
        "f_next_crew": len(d.crews) if d else 1,
    }
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


def open_form(event: TrainingEvent | None = None, on_date: date | None = None) -> None:
    if event is None:
        clear_ai_state()
    st.session_state["form_init"] = form_values(event.draft if event else None)
    st.session_state["form_init"]["f_mode"] = (
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
    st.switch_page(PAGES["history"])


# ---- pages --------------------------------------------------------------------------------------


def dashboard() -> None:
    title, action = st.columns([3, 1], vertical_alignment="center")
    with title:
        st.title("BlastBridge")
        st.write("Brain-health readiness from longitudinal occupational exposure records")
    if action.button("+ Record Training Event", type="primary"):
        open_form()
    demo_banner()
    st.caption(f"Analysis as of {ANALYSIS_AS_OF:%d %b %Y}")
    st.write(
        "An AI-assisted occupational brain-health readiness system that reconstructs longitudinal "
        "blast-exposure history and surfaces service members whose recorded exposure patterns "
        "or symptoms deserve attention."
    )
    st.caption(
        "Four separate signals: AI-assisted record intake · longitudinal occupational history · "
        "ML occupational-pattern result · deterministic symptom/follow-up guidance. "
        "No combined score."
    )
    approved = store.list_events(CONN, EventStatus.APPROVED, limit=-1)
    drafts = store.list_events(CONN, EventStatus.DRAFT, limit=-1)
    assessments = all_readiness(ANALYSIS_AS_OF)
    statuses = Counter(item.overall_readiness_status for item in assessments.values())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Personnel monitored", len(PEOPLE))
    c2.metric("Review priority", statuses[ReadinessStatus.REVIEW_PRIORITY])
    c3.metric("Medical follow-up", statuses[ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED])
    c4.metric("Urgent", statuses[ReadinessStatus.URGENT_EVALUATION])
    if pattern_model() is None:
        st.info("Occupational-pattern model unavailable (baseline not built)")
    marks = organization_marks(approved, assessments)
    calendar, detail = st.columns([2, 1])
    with calendar:
        st.subheader("Organization calendar")
        selected = render_calendar("org", marks, person=False)
        st.caption(
            "Recorded dates only; attention markers reflect readiness as of the analysis date."
        )
    with detail:
        st.subheader("Selected day")
        if selected:
            st.write(f"**{selected:%d %b %Y}**")
            day_events = [event for event in approved if event.draft.event_date == selected]
            if not day_events:
                st.write("No approved occupational records on this date.")
            for event in day_events:
                with st.container(border=True):
                    st.write(
                        f"**{event.draft.weapon_name}** · {label(event.draft.training_context)}"
                    )
                    st.write(f"{event.draft.participant_count} participants")
                    for crew in event.draft.crews:
                        st.write(
                            f"{crew.crew_name}: {count_text(crew.physical_event_count)} "
                            "physical events"
                        )
                        for member in crew.members:
                            st.caption(
                                f"{PEOPLE[member.person_id].display_name} · {member.position.label}"
                            )
                    st.caption(provenance_text(event.intake_source, event.status))
            people = marks.get(selected, DayMarks()).people
            needing_attention = [
                person_id
                for person_id in sorted(people)
                if assessments[person_id].overall_readiness_status
                is not ReadinessStatus.ROUTINE_MONITORING
            ]
            if needing_attention:
                st.write(
                    f"{len(needing_attention)} people associated with this day currently "
                    "need review or follow-up"
                )
                for person_id in needing_attention:
                    st.write(PEOPLE[person_id].display_name)
                    readiness_pill(assessments[person_id].overall_readiness_status)
                    if st.button("Open history", key=f"day-history-{person_id}"):
                        open_history(person_id)
            if can_record_on(selected, date.today()):
                if st.button("Record training event for this date"):
                    open_form(on_date=selected)
    st.subheader("Priority review")
    order = {
        ReadinessStatus.URGENT_EVALUATION: 0,
        ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED: 1,
        ReadinessStatus.REVIEW_PRIORITY: 2,
    }
    priority = sorted(
        (item for item in assessments.values() if item.overall_readiness_status in order),
        key=lambda item: (
            order[item.overall_readiness_status],
            PEOPLE[item.person_id].display_name,
        ),
    )
    if not priority:
        st.write("No personnel currently surfaced from the recorded information.")
    for assessment in priority:
        with st.container(border=True):
            st.write(f"**{PEOPLE[assessment.person_id].display_name}** · FICTIONAL")
            readiness_pill(assessment.overall_readiness_status)
            for evidence in assessment.evidence_lines:
                st.write(evidence)
            st.caption(
                "ML: "
                + (
                    assessment.ml_pattern.status.label
                    if assessment.ml_pattern
                    else "unavailable (baseline not built)"
                )
            )
            if st.button("Review history", key=f"priority-{assessment.person_id}"):
                open_history(assessment.person_id)

    if drafts:
        st.subheader("Awaiting review")
        for event in drafts:
            with st.container(border=True):
                left, right = st.columns([5, 1], vertical_alignment="center")
                d = event.draft
                left.markdown(
                    f"**{d.weapon_name}** · {d.event_date:%d %b %Y} · "
                    f"{label(d.training_context)}  \n"
                    f"{crew_names(event)}"
                )
                if right.button("Review", key=f"review-{event.event_id}"):
                    open_review(event.event_id)

    with st.expander("Recorded training events"):
        if not approved:
            st.info("No approved events yet. Record a training event to begin.")
        st.dataframe(
            [
                {
                    "Date": event.draft.event_date,
                    "Weapon": event.draft.weapon_name,
                    "Context": label(event.draft.training_context),
                    "Physical events": count_text(event.draft.physical_event_count),
                    "Participants": event.draft.participant_count,
                    "Crews": len(event.draft.crews),
                }
                for event in approved[:15]
            ],
            hide_index=True,
            width="stretch",
        )
    with st.expander("Demo data"):
        confirmed = st.checkbox("I understand this deletes all recorded events")
        if st.button("Reset to demo state", disabled=not confirmed):
            try:
                store.reset_demo(CONN, DEMO_PEOPLE, DEMO_EVENTS, DEMO_SYMPTOMS)
            except (store.StoreError, sqlite3.Error) as exc:
                st.warning(f"Could not reset demo data: {exc}")
                return
            for key in list(st.session_state):
                if key.startswith(("review", "editing", "f_", "sym_", "ai_")) or key in (
                    "last_decided",
                    "form_init",
                    "calendar_date",
                ):
                    del st.session_state[key]
            st.session_state["reset_demo_view"] = True
            st.rerun()
        st.caption(
            "Reset restores the fictional demo state and the demo analysis date (19 Oct 2026)."
        )


def clear_ai_state() -> None:
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
    st.session_state["ai_metadata"] = metadata
    st.session_state["ai_result"] = run_intake(
        narrative,
        provider,
        load_weapon_catalog(ROOT / "data/reference/weapons.json"),
        list(PEOPLE.values()),
        reference_date,
    )


def ai_metadata(result: IntakeResult) -> dict[str, object]:
    metadata = st.session_state.get("ai_metadata", {}) if result.mode == "replay" else {}
    return {
        "mode": result.mode,
        "model": result.model,
        "recorded_at": metadata.get("recorded_at"),
        "origins": result.origins,
    }


def show_ai_metadata(metadata: dict[str, object]) -> None:
    if metadata["mode"] == "replay":
        st.caption(
            "Demo replay — previously validated AI response "
            f"(recorded {metadata.get('recorded_at')}, {metadata.get('model')})"
        )
    else:
        st.caption(f"Model: {metadata.get('model')}")


def load_example_narrative() -> None:
    st.session_state["ai_narrative"] = GOLDEN_NARRATIVE


def ai_intake() -> None:
    st.text_area(
        "Describe / paste training record",
        key="ai_narrative",
        height=180,
        placeholder="Paste or type the training record here.",
    )
    st.button("Load example narrative", on_click=load_example_narrative)
    available = live_available()
    if not available:
        st.caption("Live AI unavailable: ANTHROPIC_API_KEY is not configured. Use the demo replay.")
    live, replay = st.columns(2)
    if live.button("Draft with AI", disabled=not available):
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
    metadata = ai_metadata(result)
    with st.container(border=True):
        st.markdown(
            '<span class="bb-pill">AI-generated draft — not yet recorded</span>',
            unsafe_allow_html=True,
        )
        show_ai_metadata(metadata)
        values = result.form_values
        calendar_date = st.session_state.get("calendar_date")
        narrative_date = values.get("f_date")
        if calendar_date and narrative_date and narrative_date != calendar_date:
            st.info(
                f"The narrative date ({narrative_date}) differs from the date selected on the "
                f"calendar ({calendar_date}). Review the date."
            )
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
            st.write(f"{title}: {value if value is not None else 'Needs review'}")
            st.caption(f"Origin: {result.origins.get(title, 'unresolved')}")
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
        st.dataframe(rows, hide_index=True, width="stretch")
        if result.issues:
            st.write("NEEDS REVIEW")
            for issue in sorted(result.issues, key=lambda item: not item.blocking):
                st.write(f"{'Required · ' if issue.blocking else ''}{issue.message}")
        with st.expander("How BlastBridge built this draft"):
            for step in result.trace:
                st.write(f"{'✓' if step.ok else '!'} {step.text}")
        continue_col, edit_col, start_col = st.columns(3)
        if continue_col.button("Continue to Review", disabled=result.draft is None):
            try:
                source = IntakeSource.AI_REPLAY if result.mode == "replay" else IntakeSource.AI_LIVE
                event_id = store.save_draft(CONN, result.draft, intake_source=source)
            except (store.StoreError, sqlite3.Error) as exc:
                st.warning(f"Could not save this draft: {exc}")
            else:
                st.session_state.setdefault("ai_drafts", {})[event_id] = metadata
                clear_ai_state()
                open_review(event_id)
        if edit_col.button("Edit Draft"):
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
        start_col.button("Start Over", on_click=clear_ai_state)


def new_event() -> None:
    init = st.session_state.pop("form_init", None)
    if init is None and "f_date" not in st.session_state:
        init = form_values()
        st.session_state["editing_event_id"] = None
    for key, value in (init or {}).items():
        st.session_state[key] = value
    editing = st.session_state.get("editing_event_id")

    header("New training event", "Record what the crew physically did. You will review it next.")
    mode = st.radio(
        "Entry mode",
        ["Describe / paste training record", "Enter manually"],
        key="f_mode",
        horizontal=True,
    )
    if mode == "Describe / paste training record":
        ai_intake()
        return
    if editing:
        st.info(f"Editing draft {editing}. Changes are saved when you review again.")

    with st.container(border=True):
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
        with st.container(border=True):
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
        st.switch_page(PAGES["dashboard"])
    if not left.button("Review Event", type="primary"):
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
    try:
        if editing:
            store.update_draft(CONN, editing, draft, s["editing_revision"])
            event_id = editing
        else:
            pending_mode = (s.get("ai_pending") or {}).get("mode")
            source = {
                "live": IntakeSource.AI_LIVE,
                "replay": IntakeSource.AI_REPLAY,
            }.get(pending_mode, IntakeSource.MANUAL)
            event_id = store.save_draft(CONN, draft, intake_source=source)
    except (store.StoreError, sqlite3.Error) as exc:
        if not editing:
            st.warning(f"Could not save this draft: {exc}")
            return
        # The draft changed or was decided elsewhere: show its current state instead of retrying.
        st.session_state["editing_event_id"] = None
        st.session_state["review_notice"] = f"Your edits were not saved: {exc}"
        open_review(editing)
    st.session_state["editing_event_id"] = None
    pending = st.session_state.pop("ai_pending", None)
    if pending:
        st.session_state.setdefault("ai_drafts", {})[event_id] = pending
    open_review(event_id)


def status_pill(event: TrainingEvent) -> str:
    return {
        EventStatus.DRAFT: '<span class="bb-pill draft">Draft · awaiting approval</span>',
        EventStatus.APPROVED: (
            '<span class="bb-pill approved">Approved · in personnel history</span>'
        ),
        EventStatus.REJECTED: '<span class="bb-pill">Rejected · not in history</span>',
    }[event.status]


def decide(action: str, event: TrainingEvent) -> None:
    try:
        if action == "approve":
            store.approve_event(CONN, event.event_id, event.revision)
        else:
            store.reject_event(CONN, event.event_id, event.revision)
    except (store.StoreError, sqlite3.Error) as exc:
        st.session_state["review_notice"] = f"Not recorded: {exc}"
    else:
        st.session_state["last_decided"] = event.event_id
    st.session_state["review_event_id"] = None
    st.rerun()


def show_decision(event_id: str) -> None:
    try:
        event = store.get_event(CONN, event_id)
    except store.StoreError:
        st.session_state["last_decided"] = None
        return
    d = event.draft
    with st.container(border=True):
        st.markdown(
            f"{status_pill(event)} &nbsp; **{d.weapon_name}** · {d.event_date:%d %b %Y} · "
            f"<small>{event.event_id}</small>",
            unsafe_allow_html=True,
        )
        if event.status is not EventStatus.APPROVED:
            st.caption(provenance_text(event.intake_source, event.status))
            st.caption("This event was not added to anyone's history.")
            return
        st.caption(provenance_text(event.intake_source, event.status))
        st.info("Approved. Each participant's history now includes this event.")
        members = [m for crew in d.crews for m in crew.members]
        for start in range(0, len(members), 4):
            row = members[start : start + 4]
            for col, m in zip(st.columns(len(row)), row, strict=True):
                if col.button(f"View {PEOPLE[m.person_id].display_name}", key=f"h-{m.person_id}"):
                    open_history(m.person_id)


def review() -> None:
    header("Review training event", "Nothing enters personnel history until you approve it.")
    notice = st.session_state.pop("review_notice", None)
    if notice:
        st.warning(notice)
    decided = st.session_state.get("last_decided")
    if decided:
        show_decision(decided)

    drafts = store.list_events(CONN, EventStatus.DRAFT, limit=50)
    event_id = st.session_state.get("review_event_id")
    if event_id is None:
        if not drafts:
            if not decided:
                st.info("No drafts are awaiting review.")
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
        f"{status_pill(event)} &nbsp; <small>{event.event_id}</small>", unsafe_allow_html=True
    )
    st.caption(provenance_text(event.intake_source, event.status))
    st.write("")

    metadata = st.session_state.get("ai_drafts", {}).get(event.event_id)
    if event.intake_source is not IntakeSource.MANUAL and event.status is EventStatus.DRAFT:
        st.info(
            "AI-generated draft — not yet recorded. "
            "Nothing is added to personnel history until you approve."
        )
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
    with st.container(border=True):
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
        st.dataframe(
            [
                {
                    "Crew": crew.crew_name,
                    **{
                        pos.label: next(
                            (
                                PEOPLE[m.person_id].display_name
                                for m in crew.members
                                if m.position == pos
                            ),
                            "Not recorded",
                        )
                        for pos in POSITIONS
                    },
                    "Physical events": count_text(crew.physical_event_count),
                    "Participants": len(crew.members),
                    "Associations": count_text(
                        crew.physical_event_count * len(crew.members)
                        if crew.physical_event_count is not None
                        else None
                    ),
                }
                for crew in d.crews
            ],
            hide_index=True,
            width="stretch",
        )
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

    with st.container(border=True):
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
    if a.button("Approve Event", type="primary", key=f"approve-{key}"):
        decide("approve", event)
    if b.button("Edit", key=f"edit-{key}"):
        open_form(event)
    if c.button("Reject", key=f"reject-{key}"):
        decide("reject", event)


def followup_card(result: FollowUp) -> None:
    if result.state is FollowUpState.URGENT_EVALUATION_RECOMMENDED:
        st.error(result.headline)
    elif result.state is FollowUpState.FOLLOW_UP_SUGGESTED:
        with st.container(border=True):
            st.markdown(
                f'<span class="bb-pill medical">{result.headline}</span>',
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
    if st.button("Log Symptom Report"):
        clear_symptom_state()
        s["sym_person"] = person_id
        s["sym_open"] = True
    if not s.get("sym_open"):
        return
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


def followup() -> None:
    header("Follow-up", "Confirmed reports for fictional personnel.")
    st.caption(f"Analysis as of {ANALYSIS_AS_OF:%d %b %Y}")
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
        with st.container(border=True):
            report_fields(report.draft)
            followup_card(evaluate(report.draft))
            if st.button("Open history", key=f"followup-{report.report_id}"):
                open_history(report.draft.person_id)
    st.subheader("Official resources")
    official_resources()
    st.caption(BOUNDARY_NOTE)
    st.caption(PRIVACY_NOTE)


def history() -> None:
    header("Personnel history", "Occupational records, symptoms and guidance shown separately.")
    chosen = st.session_state.pop("history_person_id", None)
    if chosen:
        st.session_state["h_person"] = chosen
    person_id = st.selectbox("Person", list(PEOPLE), format_func=person_text, key="h_person")
    p = PEOPLE[person_id]
    entries = store.member_history(CONN, person_id)
    reports = store.list_symptom_reports(CONN, person_id)
    assessment = readiness_for(person_id, ANALYSIS_AS_OF)
    visible_entries = [entry for entry in entries if entry.event_date <= ANALYSIS_AS_OF]
    visible_reports = [report for report in reports if report.draft.report_date <= ANALYSIS_AS_OF]

    with st.container(border=True):
        a, b, c = st.columns([2, 1, 1])
        with a:
            st.markdown(f'<div class="bb-name">{p.display_name}</div>', unsafe_allow_html=True)
            st.markdown(
                f'<span class="bb-pill">FICTIONAL</span> &nbsp; “{p.callsign}” · {p.person_id}',
                unsafe_allow_html=True,
            )
        with b:
            field("Unit", p.unit)
            field("Section", p.section)
        with c:
            field("Usual position", p.home_position.label)
            roles = Counter(e.position for e in visible_entries)
            field(
                "Roles held",
                " · ".join(f"{pos.label} ×{roles[pos]}" for pos in POSITIONS if roles[pos])
                or "No approved records",
            )
        readiness_pill(assessment.overall_readiness_status)
        st.caption(f"Analysis as of {ANALYSIS_AS_OF:%d %b %Y}")
        st.write(" · ".join(assessment.evidence_lines) or "No current rule-based or pattern signal")

    calendar, detail = st.columns([2, 1])
    with calendar:
        st.subheader("Calendar")
        selected = render_calendar("person", person_marks(entries, reports), person=True)
        st.caption("Calendars show recorded dates; readiness uses the selected analysis date.")
    with detail:
        st.subheader("Selected day")
        if selected:
            st.write(f"**{selected:%d %b %Y}**")
            day_entries = [entry for entry in entries if entry.event_date == selected]
            day_reports = [report for report in reports if report.draft.report_date == selected]
            if not day_entries and not day_reports:
                st.caption("No records on this date.")
            for entry in day_entries:
                st.write(f"{entry.position.label} · {entry.weapon_name}")
                st.write(f"Physical events: {count_text(entry.physical_event_count)}")
                st.caption(provenance_text(entry.intake_source, EventStatus.APPROVED))
            for report in day_reports:
                st.write("Symptom report")
                report_fields(report.draft)
                followup_card(evaluate(report.draft))
            if can_record_on(selected, date.today()):
                if st.button("Log symptom report for this date"):
                    clear_symptom_state()
                    st.session_state["sym_person"] = person_id
                    st.session_state["sym_open"] = True
                    st.session_state["sym_restore"] = {"sym_w_date": selected}
    symptom_form(person_id)

    with st.container(border=True):
        st.subheader("Occupational exposure")
        st.metric("Career record count", len(visible_entries))
        features = occupational_features((entry.event_date for entry in entries), ANALYSIS_AS_OF)
        for column, name, value in zip(
            st.columns(4),
            (
                "Events · 30 days",
                "Events · 90 days",
                "Events · 365 days",
                "Days since previous event",
            ),
            features[:4],
            strict=True,
        ):
            column.metric(name, int(value))
        st.caption(
            "Occupational events are distinct recorded event days. Elapsed days are capped at 730; "
            "730 also represents no prior recorded event."
        )
        for note in assessment.data_quality_notes:
            st.caption(note)
        pattern = assessment.ml_pattern
        if pattern is None:
            st.info("Occupational-pattern model unavailable (baseline not built)")
        else:
            style = (
                "review"
                if pattern.status is PatternStatus.ATYPICAL_OCCUPATIONAL_PATTERN
                else "routine"
            )
            st.markdown(
                f'<span class="bb-pill {style}">{pattern.status.label}</span>',
                unsafe_allow_html=True,
            )
            st.dataframe(
                [
                    {
                        "Feature": item.label,
                        "Recorded": item.value,
                        "Fictional baseline median": item.median,
                        "IQR q25–q75": f"{item.q25:g}–{item.q75:g}",
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
                    f"(fictional simulation baseline median {item.median:g})"
                )
            if not pattern.differing:
                st.caption(
                    "No features outside the fictional simulation baseline's percentile ranges."
                )
            model = pattern_model()
            st.caption(
                f"Model: IsolationForest on {model.baseline_rows} fictional simulation baseline "
                "windows · prototype analytic threshold: 5th percentile"
            )
        st.caption(PATTERN_DISCLAIMER)
        st.caption(CONTEXT_NOTE)

    with st.container(border=True):
        st.subheader("Symptoms")
        st.caption(f"Confirmed reports as of {ANALYSIS_AS_OF:%d %b %Y}")
        if not visible_reports:
            st.write("No confirmed symptom reports.")
        for report in visible_reports:
            with st.container(border=True):
                report_fields(report.draft)
    with st.container(border=True):
        st.subheader("Follow-up")
        st.caption(
            "Deterministic guidance from TBICoE/CDC sources; "
            "independent of the occupational-pattern model."
        )
        for report in visible_reports:
            st.write(f"Report: {report.draft.report_date:%d %b %Y}")
            followup_card(evaluate(report.draft))
        if reports:
            with st.expander("Official resources"):
                official_resources()
    st.caption(BOUNDARY_NOTE)
    st.caption(PRIVACY_NOTE)

    with st.expander("Chronological detail"):
        training_by_id = {entry.event_id: entry for entry in entries}
        reports_by_id = {report.report_id: report for report in reports}
        timeline = [(entry.event_date, "", "training", entry.event_id) for entry in entries]
        timeline.extend(
            (report.draft.report_date, report.confirmed_at, "report", report.report_id)
            for report in reports
        )
        for _, _, kind, record_id in sorted(timeline, reverse=True):
            with st.container(border=True):
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
    "dashboard": st.Page(dashboard, title="Dashboard", icon=":material/dashboard:", default=True),
    "new": st.Page(new_event, title="New Training Event", icon=":material/add_circle:"),
    "review": st.Page(review, title="Review / Approve", icon=":material/fact_check:"),
    "history": st.Page(history, title="Personnel History", icon=":material/person_search:"),
    "followup": st.Page(followup, title="Follow-up", icon=":material/assignment_ind:"),
}

try:
    st.navigation(list(PAGES.values())).run()
finally:
    CONN.close()
