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
from blastbridge.product.followup import (
    ABSENCE_NOTE,
    BOUNDARY_NOTE,
    DANGER_SIGN_LABEL,
    EMPTY_FOLLOWUP,
    GOVERNANCE_NOTE,
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
    Person,
    TrainingEvent,
    TrainingEventDraft,
)
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
  border-radius: 8px; padding: .8rem;}
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


def open_form(event: TrainingEvent | None = None) -> None:
    st.session_state["form_init"] = form_values(event.draft if event else None)
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
        header("BlastBridge", "Recorder dashboard for fictional training activity")
    if action.button("+ Record Training Event", type="primary"):
        open_form()
    approved = store.list_events(CONN, EventStatus.APPROVED, limit=-1)
    drafts = store.list_events(CONN, EventStatus.DRAFT, limit=-1)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fictional personnel", len(PEOPLE))
    c2.metric("Approved training events", len(approved))
    c3.metric("Drafts awaiting review", len(drafts))
    c4.metric(
        "Known physical events recorded", sum(e.draft.known_physical_event_count for e in approved)
    )
    st.metric(
        "Reports matching a follow-up rule",
        sum(
            evaluate(report.draft).state is not FollowUpState.NO_FOLLOWUP_RULE_TRIGGERED
            for report in store.list_symptom_reports(CONN)
        ),
    )

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

    st.subheader("Recent approved training events")
    if not approved:
        st.info("No approved events yet. Record a training event to begin.")
    st.dataframe(
        [
            {
                "Date": e.draft.event_date,
                "Weapon": e.draft.weapon_name,
                "Context": label(e.draft.training_context),
                "Physical events": count_text(e.draft.physical_event_count),
                "Participants": e.draft.participant_count,
                "Crews": len(e.draft.crews),
            }
            for e in approved[:15]
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
                st.error(f"Could not reset demo data: {exc}")
                return
            for key in list(st.session_state):
                if key.startswith(("review", "editing", "f_", "sym_")) or key in (
                    "last_decided",
                    "form_init",
                ):
                    del st.session_state[key]
            st.rerun()


def new_event() -> None:
    init = st.session_state.pop("form_init", None)
    if init is None and "f_date" not in st.session_state:
        init = form_values()
        st.session_state["editing_event_id"] = None
    for key, value in (init or {}).items():
        st.session_state[key] = value
    editing = st.session_state.get("editing_event_id")

    header("New training event", "Record what the crew physically did. You will review it next.")
    if editing:
        st.info(f"Editing draft {editing}. Changes are saved when you review again.")

    with st.container(border=True):
        st.subheader("Event")
        a, b = st.columns(2)
        a.date_input("Date", max_value=date.today(), key="f_date")
        b.selectbox("Activity type", list(EventType), format_func=label, key="f_type")
        a.selectbox("Training context", list(TrainingContext), format_func=label, key="f_context")
        b.selectbox("Weapon system", list(weapons()), format_func=weapons().get, key="f_weapon")
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
        st.switch_page(PAGES["dashboard"])
    if not left.button("Review Event", type="primary"):
        return

    s = st.session_state
    if s["f_date"] > date.today():
        st.error("Event date cannot be in the future.")
        return
    missing = [
        f"{s[f'f_c{i}_name']} · {pos.label}"
        for i in s["f_crews"]
        for pos in POSITIONS
        if not s.get(f"f_c{i}_{pos}")
    ]
    if missing:
        st.error(f"Select a person for: {', '.join(missing)}.")
        return
    if any(s[f"f_c{i}_known"] is None for i in s["f_crews"]):
        st.error("Choose whether the launch count is Known or Unknown.")
        return
    if any(s[f"f_c{i}_known"] == "Known" and s.get(f"f_c{i}_count") is None for i in s["f_crews"]):
        st.error("Enter the number of physical launches, or choose Unknown.")
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
        st.error("; ".join(duplicates))
        return
    try:
        draft = TrainingEventDraft(
            event_date=s["f_date"],
            event_type=s["f_type"],
            training_context=s["f_context"],
            weapon_system_id=s["f_weapon"],
            weapon_name=weapons()[s["f_weapon"]],
            location_unit=s["f_location"].strip() or None,
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
        st.error(" ".join(e["msg"].removeprefix("Value error, ") for e in exc.errors()))
        return
    try:
        if editing:
            store.update_draft(CONN, editing, draft, s["editing_revision"])
            event_id = editing
        else:
            event_id = store.save_draft(CONN, draft)
    except (store.StoreError, sqlite3.Error) as exc:
        if not editing:
            st.error(f"Could not save this draft: {exc}")
            return
        # The draft changed or was decided elsewhere: show its current state instead of retrying.
        st.session_state["editing_event_id"] = None
        st.session_state["review_notice"] = f"Your edits were not saved: {exc}"
        open_review(editing)
    st.session_state["editing_event_id"] = None
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
            st.caption("This event was not added to anyone's history.")
            return
        st.success("Approved. Each participant's history now includes this event.")
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
        st.error(notice)
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
    st.write("")

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
            st.markdown(f'<span class="bb-pill">{result.headline}</span>', unsafe_allow_html=True)
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
        st.success(notice)
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
            followup_card(evaluate(pending))
            confirm, edit, discard = st.columns(3)
            if confirm.button("Confirm", key="sym_confirm"):
                try:
                    store.confirm_symptom_report(CONN, pending)
                except (store.StoreError, sqlite3.Error) as exc:
                    st.error(f"Could not confirm report: {exc}")
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
        if st.button("Discard", key="sym_form_discard"):
            clear_symptom_state()
            st.rerun()
        if not st.button("Review report", key="sym_form_review"):
            return
        if any(value is None for value in (relationship, persistence, impact, source)):
            st.error(
                "Choose temporal relationship, persistence, functional impact and "
                "source explicitly."
            )
            return
        if report_date > date.today():
            st.error("Report date cannot be in the future.")
            return
        if (
            relationship is TemporalRelationship.AFTER_RECORDED_EVENT
            and event_id
            and report_date < by_id[event_id].event_date
        ):
            st.error("A report after a recorded event cannot predate that event.")
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
            st.error(" ".join(e["msg"].removeprefix("Value error, ") for e in exc.errors()))
            return
        s["sym_values"] = {key: value for key, value in s.items() if key.startswith("sym_w_")}
        s["sym_review"] = pending
        st.rerun()


def followup() -> None:
    header("Follow-up", "Confirmed reports for fictional personnel.")
    reports = [
        report
        for report in store.list_symptom_reports(CONN)
        if evaluate(report.draft).state is not FollowUpState.NO_FOLLOWUP_RULE_TRIGGERED
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
    header("Personnel exposure history", "Approved training activity for one fictional person.")
    chosen = st.session_state.pop("history_person_id", None)
    if chosen:
        st.session_state["h_person"] = chosen
    person_id = st.selectbox("Person", list(PEOPLE), format_func=person_text, key="h_person")
    p = PEOPLE[person_id]
    entries = store.member_history(CONN, person_id)
    reports = store.list_symptom_reports(CONN, person_id)

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
            roles = Counter(e.position for e in entries)
            field(
                "Roles held",
                " · ".join(f"{pos.label} ×{roles[pos]}" for pos in POSITIONS if roles[pos])
                or "No approved records",
            )

    known = [e.physical_event_count for e in entries if e.physical_event_count is not None]
    a, b, c, report_metric = st.columns(4)
    a.metric("Approved training events", len(entries))
    b.metric(
        "Known physical events",
        "Unknown" if entries and not known else sum(known),
    )
    c.metric("Records with unknown count", len(entries) - len(known))
    report_metric.metric("Symptom reports", len(reports))
    st.caption(
        "Totals use known counts only. Events with an unknown count are listed and are never "
        "counted as zero."
    )

    if not entries:
        st.info("No approved training events for this person yet.")
    months = Counter(e.event_date.strftime("%Y-%m") for e in entries)
    month = min((e.event_date for e in entries), default=date.today()).replace(day=1)
    today = date.today().replace(day=1)
    chart = {}
    while month <= today:
        key = month.strftime("%Y-%m")
        chart[key] = months[key]
        month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    st.subheader("Training events per month")
    st.bar_chart(
        {"Month": list(chart), "Training events": list(chart.values())},
        x="Month",
        y="Training events",
    )
    st.caption(
        "Counts approved training events, not launches. "
        "Events with unknown launch counts are included."
    )
    symptom_form(person_id)
    st.subheader("History timeline")
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
                    f"Physical events: {count_text(entry.physical_event_count)} · {entry.crew_name}"
                )
                st.caption("Source: organizational training record")
            else:
                report = reports_by_id[record_id]
                st.write(f"**{report.draft.report_date:%d %b %Y} · Symptom report**")
                report_fields(report.draft)
                followup_card(evaluate(report.draft))
    if reports:
        with st.expander("Official resources"):
            official_resources()
        st.caption(BOUNDARY_NOTE)
        st.caption(PRIVACY_NOTE)


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
