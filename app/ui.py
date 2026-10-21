"""Quiet, date-first presentation helpers for the Streamlit application."""

from html import escape

import streamlit as st

CSS = """
<style>
:root {--bb-ink:#29242A; --bb-muted:#827A82; --bb-line:#EEE9EB; --bb-pink:#E45F7B;}
html, body, [data-testid="stApp"] {background:#FCFAF9; color:var(--bb-ink);}
html, body, [data-testid="stApp"], button, input, textarea, select {
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important;}
.block-container {max-width:800px; padding:1.5rem 2rem 5rem;}
[data-testid="stHeader"] {background:transparent;}
[data-testid="stToolbar"], [data-testid="stDecoration"], footer {display:none;}
h1 {font-size:2.1rem!important; font-weight:700!important; letter-spacing:-.055rem;}
h2 {font-size:1.65rem!important; letter-spacing:-.025rem;}
h3 {font-size:1.2rem!important; font-weight:600!important;}
p {font-size:1rem; line-height:1.55;}
[data-testid="stCaptionContainer"] {color:var(--bb-muted); font-size:.84rem;}
[data-testid="stVerticalBlock"] {gap:.8rem;}
.bb-sub {color:var(--bb-muted); margin:-.5rem 0 1rem;}
.bb-brand {display:flex; align-items:center; justify-content:space-between; gap:1rem;}
.bb-brand h1 {margin:0; padding:0 0 1rem;}
.bb-demo {font-size:.69rem; letter-spacing:.12em; color:var(--bb-muted); white-space:nowrap;}
.bb-pill {display:inline-block; color:var(--bb-muted); font-size:.84rem; line-height:1.6;}
.bb-pill.review {color:#7C6FA8;}
.bb-pill.medical {color:#986520;}
.bb-pill.urgent {color:#C74343; font-weight:600;}
.bb-pill.fictional {font-size:.69rem; letter-spacing:.12em;}
.bb-label {font-size:.8rem; color:var(--bb-muted); margin-bottom:.25rem;}
.bb-value {font-size:1rem; margin-bottom:.8rem;}
[data-testid="stButton"] button, [data-testid="stPopover"]>button {
  border-radius:16px; border:1px solid var(--bb-line); background:white;
  color:var(--bb-ink); box-shadow:none; min-height:42px;}
[data-testid="stButton"] button:hover, [data-testid="stPopover"]>button:hover {
  border-color:#E45F7B; color:#A63250; background:#FBE9EE;}
[data-testid="stButton"] button[kind="primary"], .st-key-log-action button {
  background:#E45F7B; color:white; border-color:transparent; font-weight:600;}
[data-testid="stButton"] button[kind="primary"]:hover, .st-key-log-action button:hover {
  background:#C54764; color:white;}
.st-key-log-action {margin:.5rem 0 1rem;}
.st-key-log-action [data-testid="stPopover"], .st-key-symptom-log [data-testid="stButton"] {
  display:flex; justify-content:center;}
.st-key-log-action [data-testid="stPopover"]>button, .st-key-symptom-log button {
  border-radius:999px!important; height:44px; min-width:120px; padding:.5rem 1.5rem;}
.st-key-log-action [data-testid="stPopover"]>button svg {display:none;}
.st-key-log-action [data-testid="stPopover"]>button [data-testid="stIconMaterial"] {
  display:none;}
[data-testid="stPopoverBody"] [data-testid="stButton"] button {
  width:100%; border:0; background:transparent; color:var(--bb-ink);
  border-radius:0; justify-content:flex-start; text-align:left;}
.st-key-app-nav {background:white; border-radius:24px; padding:.35rem 1rem;
  border:1px solid var(--bb-line); margin-bottom:1.25rem;}
.st-key-app-nav [data-testid="stPageLink"] a {
  justify-content:center; border-radius:16px; padding:.55rem;}
.st-key-app-nav [data-testid="stPageLink"] a:hover {background:#FBE9EE;}
.st-key-cal-org, .st-key-cal-person {padding:1rem 0 .5rem;}
:is(.st-key-cal-org,.st-key-cal-person) [data-testid="stHorizontalBlock"] {gap:.25rem;}
:is(.st-key-cal-org,.st-key-cal-person) [data-testid="stColumn"] {
  min-width:0!important; flex:1 1 0!important; text-align:center;}
:is(.st-key-cal-org,.st-key-cal-person) [data-testid="stButton"] {
  display:flex; justify-content:center;}
:is(.st-key-cal-org,.st-key-cal-person) button {
  width:42px!important; height:42px; min-height:42px; padding:0; border:0;
  border-radius:50%; background:transparent; overflow:visible;}
:is(.st-key-cal-org,.st-key-cal-person) button p {
  font-size:.94rem; line-height:1.1; white-space:pre-line; height:30px; padding-top:2px;}
:is(.st-key-cal-org,.st-key-cal-person) button p span {font-size:.5rem;}
:is(.st-key-cal-org,.st-key-cal-person) button[kind="primary"] p span {color:white!important;}
:is(.st-key-cal-org,.st-key-cal-person) [class*="st-key-day-"] button p::after {
  content:""; display:block; height:6px;}
[class*="st-key-month-nav-"] {max-width:320px; margin:0 auto; width:100%;}
[class*="st-key-month-nav-"] [data-testid="stColumn"]:nth-child(2) {flex:3 1 0!important;}
:is(.st-key-cal-org,.st-key-cal-person) [class*="st-key-month-nav-"] button {
  width:36px!important; height:36px; min-height:36px; color:var(--bb-muted);}
:is(.st-key-cal-org,.st-key-cal-person) [class*="st-key-month-nav-"] button p {
  font-size:1.6rem; line-height:1; height:auto; padding:0;}
:is(.st-key-cal-org,.st-key-cal-person) button:hover {background:#FBE9EE;}
:is(.st-key-cal-org,.st-key-cal-person) button[kind="primary"] {
  background:#E45F7B; color:white; box-shadow:0 3px 8px #E45F7B22;}
:is(.st-key-cal-org,.st-key-cal-person) button:disabled {opacity:.3; background:transparent;}
:is(.st-key-cal-org,.st-key-cal-person)
  [class*="st-key-day-"][class*="-today"] button {
  outline:1px solid #E45F7B; outline-offset:2px;}
.bb-month {font-size:1.25rem; font-weight:600; text-align:center; padding:.4rem 0;}
.bb-weekday {font-size:.75rem; color:var(--bb-muted); text-align:center;}
[class*="st-key-row-"] {padding:.8rem 0; border-bottom:1px solid var(--bb-line);}
[class*="st-key-row-"] [data-testid="stButton"] button {
  border:0; background:transparent; font-size:1.25rem;}
[class*="st-key-insight-"] {padding:1rem 0; border-bottom:1px solid var(--bb-line);}
.st-key-proposed-draft, .st-key-decision-summary, .st-key-approval-summary {
  background:white; padding:1.25rem; border-radius:20px;
  box-shadow:0 3px 16px #29242A06;}
.st-key-training-event-fields, .st-key-review-event-fields, [class*="st-key-crew-fields-"] {
  padding:1rem 0; border-bottom:1px solid var(--bb-line);}
[data-testid="stExpander"], [data-testid="stExpander"] details {
  border:0!important; border-radius:0!important;
  border-bottom:1px solid var(--bb-line)!important; background:transparent;}
[data-testid="stExpander"] {border-bottom:0!important;}
[data-testid="stExpander"] summary {padding:.85rem .2rem; color:var(--bb-muted);}
[data-testid="stExpander"] summary p {font-size:14px;}
[data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stTextArea"] [data-baseweb="textarea"] {
  background:white!important; border:1px solid var(--bb-line)!important; border-radius:14px;}
input, textarea {background:white!important;}
[class*="st-key-listrow-"] {border-bottom:1px solid var(--bb-line);}
[class*="st-key-listrow-"] [data-testid="stButton"] button {
  width:100%; border:0; border-radius:0; background:transparent; padding:12px 32px 12px 0;
  text-align:left; justify-content:flex-start; position:relative; height:auto;}
[class*="st-key-listrow-"] button p {
  white-space:pre-line; font-size:13.5px; line-height:1.5; color:var(--bb-muted); margin:0;}
[class*="st-key-listrow-"] button p strong {font-size:16px; font-weight:600; color:var(--bb-ink);}
[class*="st-key-listrow-"] button::after {
  content:"›"; position:absolute; right:4px; top:50%; transform:translateY(-50%);
  font-size:24px; color:var(--bb-muted);}
.bb-compact {font-size:14px; line-height:1.5; margin:0;}
.bb-compact.muted {font-size:13px; color:var(--bb-muted);}
[class*="st-key-insight-"] {padding:0;}
[class*="st-key-insight-"] summary p {
  font-size:13.5px; line-height:1.5; white-space:pre-line; color:var(--bb-muted);}
[class*="st-key-insight-"] summary p strong {
  font-size:16px; font-weight:600; color:var(--bb-ink);}
[class*="st-key-insight-"] summary p span {font-size:10px;}
.st-key-back-people button {
  border:0; background:transparent; color:var(--bb-muted); padding-left:0;}
.st-key-proposed-draft [data-testid="stVerticalBlock"] {gap:4px;}
[data-testid="stTabs"] [role="tablist"] {border-bottom:1px solid var(--bb-line); gap:1.5rem;}
[data-testid="stTabs"] [role="tab"] {padding:.75rem .2rem;}
[data-testid="stMetric"] {padding:.5rem 0;}
[data-testid="stMetricValue"] {font-size:1.65rem;}
[data-testid="stVerticalBlockBorderWrapper"] {box-shadow:none;}
[data-testid="stAlert"] {border-radius:20px;}
@media (max-width:850px) {
  .block-container {padding:1rem 1.25rem 4rem;}
  h1 {font-size:1.9rem!important;}
  .st-key-app-nav {padding:.25rem .5rem;}
}
</style>
"""


def install() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def brand(title: str = "BlastBridge") -> None:
    st.markdown(
        f'<div class="bb-brand"><h1>{escape(title)}</h1>'
        '<span class="bb-demo">FICTIONAL DEMO</span></div>',
        unsafe_allow_html=True,
    )


def navigation(pages: dict) -> None:
    with st.container(key="app-nav"):
        for column, key, title in zip(
            st.columns(3),
            ("dashboard", "history", "inbox"),
            ("Home", "People", "Review"),
            strict=True,
        ):
            column.page_link(pages[key], label=title)


def demo_details(note: str) -> None:
    st.caption("Demo histories are intentionally arranged to demonstrate prototype states.")
    with st.expander("About this demo"):
        st.caption(
            "FICTIONAL DEMO — All people and events are invented. "
            "BlastBridge records occupational exposure; exposure does not imply injury."
        )
        st.caption(note)


def field(name: str, value: str) -> None:
    st.markdown(
        f'<div class="bb-label">{escape(name)}</div><div class="bb-value">{escape(value)}</div>',
        unsafe_allow_html=True,
    )


def row(title: str, subtitle: str, *, key: str, state: str = "", tone: str = "gray") -> bool:
    """A single real button is the complete list-row hit target."""
    title = markdown_text(title)
    subtitle = markdown_text(subtitle)
    text = f"**{title}**\n{subtitle}"
    if state:
        text += f"\n:{tone}[{markdown_text(state)}]"
    with st.container(key=f"listrow-{key}"):
        return st.button(text, key=key, width="stretch")


def markdown_text(value: str) -> str:
    for character in ("\\", "*", "_", "[", "]", "`", "<", ">"):
        value = value.replace(character, "\\" + character)
    return value


def compact_line(text: str, *, muted: bool = False) -> None:
    style = "bb-compact muted" if muted else "bb-compact"
    st.markdown(f'<div class="{style}">{escape(text)}</div>', unsafe_allow_html=True)


def action(label: str, container_key: str, *, primary: bool = False) -> bool:
    with st.container(key=container_key):
        return st.button(label, type="primary" if primary else "tertiary")


def insight(title: str, summary: str, tone: str):
    text = f":{tone}[●] **{markdown_text(title)}**\n{markdown_text(summary)}"
    return st.expander(text)


def actions():
    return st.container(horizontal=True, horizontal_alignment="left", gap="small")
