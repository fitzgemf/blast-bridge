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
from blastbridge.product.models import (
    Crew,
    CrewMember,
    CrewPosition,
    EventStatus,
    Person,
    TrainingEvent,
    TrainingEventDraft,
)
from blastbridge.product.seed import DEMO_EVENTS, DEMO_PEOPLE

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
            store.reset_demo(CONN, DEMO_PEOPLE, DEMO_EVENTS)
            for key in list(st.session_state):
                if key.startswith(("review", "editing", "f_")) or key in (
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
        links.metric("Participant-event associations", str(known_links))
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
            f"associations are unknown, never zero. The known crews' total is {known_links} "
            f"associations across {d.known_physical_event_count} physical launches."
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


def history() -> None:
    header("Personnel exposure history", "Approved training activity for one fictional person.")
    chosen = st.session_state.pop("history_person_id", None)
    if chosen:
        st.session_state["h_person"] = chosen
    person_id = st.selectbox("Person", list(PEOPLE), format_func=person_text, key="h_person")
    p = PEOPLE[person_id]
    entries = store.member_history(CONN, person_id)

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
    a, b, c = st.columns(3)
    a.metric("Approved training events", len(entries))
    b.metric(
        "Known physical events",
        "Unknown" if entries and not known else sum(known),
    )
    c.metric("Records with unknown count", len(entries) - len(known))
    st.caption(
        "Totals use known counts only. Events with an unknown count are listed and are never "
        "counted as zero."
    )

    if not entries:
        st.info("No approved training events for this person yet.")
        return
    months = Counter(e.event_date.strftime("%Y-%m") for e in entries)
    month = min(e.event_date for e in entries).replace(day=1)
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
    st.dataframe(
        [
            {
                "Date": e.event_date,
                "Weapon": e.weapon_name,
                "Position": e.position.label,
                "Physical events": count_text(e.physical_event_count),
                "Crew": e.crew_name,
                "Training context": label(e.training_context),
                "Activity": label(e.event_type),
                "Location / unit": e.location_unit or "",
                "Event ID": e.event_id,
            }
            for e in entries
        ],
        column_config={"Date": st.column_config.DateColumn("Date", format="DD MMM YYYY")},
        hide_index=True,
        width="stretch",
    )


PAGES = {
    "dashboard": st.Page(dashboard, title="Dashboard", icon=":material/dashboard:", default=True),
    "new": st.Page(new_event, title="New Training Event", icon=":material/add_circle:"),
    "review": st.Page(review, title="Review / Approve", icon=":material/fact_check:"),
    "history": st.Page(history, title="Personnel History", icon=":material/person_search:"),
}

try:
    st.navigation(list(PAGES.values())).run()
finally:
    CONN.close()
