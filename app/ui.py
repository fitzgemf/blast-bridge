"""Quiet, date-first presentation helpers for the Streamlit application."""

from html import escape

import streamlit as st

CSS = """
<style>
:root {--bb-ink:#29242A; --bb-muted:#827A82; --bb-line:#EEE9EB; --bb-pink:#E45F7B;}
html, body, [data-testid="stApp"] {
  background:#FCFAF9; color:var(--bb-ink); font-variant-numeric:lining-nums;}
html, body, [data-testid="stApp"], button, input, textarea, select {
  font-family:Candara,"Trebuchet MS","Segoe UI",sans-serif!important;}
.block-container {max-width:800px; padding:.75rem 2rem 4rem;}
[data-testid="stHeader"] {background:transparent;}
[data-testid="stToolbar"], [data-testid="stDecoration"], footer {display:none;}
h1 {font-size:34px!important; font-weight:700!important; letter-spacing:-.025em; padding:0;}
h2 {font-size:24px!important; font-weight:600!important; letter-spacing:-.025em;}
h3 {font-size:20px!important; font-weight:600!important; padding:.25rem 0;}
p {font-size:1rem; line-height:1.45;}
[data-testid="stCaptionContainer"] {color:var(--bb-muted); font-size:.84rem;}
[data-testid="stVerticalBlock"] {gap:.5rem;}
[data-testid="stCaptionContainer"] p {font-size:13.5px; margin-bottom:.5rem;}
.bb-sub {color:var(--bb-muted); margin:0 0 .5rem;}
.bb-brand {display:flex; align-items:center; justify-content:space-between; gap:1rem;}
.bb-brand h1 {margin:0; padding:0 0 .5rem;}
.bb-demo {font-size:.69rem; letter-spacing:.12em; color:var(--bb-muted); white-space:nowrap;}
.bb-pill {display:inline-block; color:var(--bb-muted); font-size:.84rem; line-height:1.6;}
.bb-pill.review {color:#7C6FA8;}
.bb-pill.medical {color:#A15F0E;}
.bb-pill.urgent {color:#B42318; font-weight:600;}
.bb-pill.fictional {font-size:.69rem; letter-spacing:.12em;}
.bb-label {font-size:.8rem; color:var(--bb-muted); margin-bottom:.25rem;}
.bb-value {font-size:1rem; margin-bottom:.8rem;}
[data-testid="stButton"] button, [data-testid="stPopover"] button {
  border-radius:16px; border:1px solid var(--bb-line); background:white;
  color:var(--bb-ink); box-shadow:none; min-height:42px;}
[data-testid="stButton"] button:hover, [data-testid="stPopover"] button:hover {
  border-color:#E45F7B; color:#A63250; background:#FBE9EE;}
[data-testid="stButton"] button[kind="primary"], .st-key-log-action button {
  background:#E45F7B; color:white; border-color:transparent; font-weight:600;}
[data-testid="stButton"] button[kind="primary"]:hover, .st-key-log-action button:hover {
  background:#C54764; color:white;}
.st-key-log-action, .st-key-symptom-log {margin:.5rem 0 .5rem;}
.st-key-log-action [data-testid="stPopover"], .st-key-symptom-log [data-testid="stButton"] {
  display:flex; justify-content:center;}
.st-key-log-action [data-testid="stPopover"] button, .st-key-symptom-log button {
  border-radius:999px!important; height:44px; min-width:120px; padding:.5rem 1.5rem;}
.st-key-log-action [data-testid="stPopover"] button svg {display:none;}
.st-key-log-action [data-testid="stPopover"] button [data-testid="stIconMaterial"] {
  display:none;}
[data-testid="stPopoverBody"] [data-testid="stButton"] button {
  width:100%; border:0; background:transparent; color:var(--bb-ink);
  border-radius:0; justify-content:flex-start; text-align:left;}
.st-key-app-nav {background:white; border-radius:24px; padding:.25rem .5rem;
  border:1px solid var(--bb-line); width:100%; max-width:480px; margin:0 auto .5rem;}
.st-key-app-nav [data-testid="stPageLink"] {display:flex; justify-content:center;}
.st-key-app-nav [data-testid="stPageLink"] a {
  justify-content:center; border-radius:16px; padding:.5rem 1rem;}
.st-key-app-nav [data-testid="stPageLink"] a[aria-current="page"] {background:#F6E9EC;}
.st-key-app-nav [data-testid="stPageLink"] a:hover {background:#FBE9EE;}
.st-key-cal-org, .st-key-cal-person {padding:.25rem 0 0;}
:is(.st-key-cal-org,.st-key-cal-person) [data-testid="stVerticalBlock"] {gap:.25rem;}
:is(.st-key-cal-org,.st-key-cal-person) [data-testid="stHorizontalBlock"] {gap:.25rem;}
:is(.st-key-cal-org,.st-key-cal-person) [data-testid="stColumn"] {
  min-width:0!important; flex:1 1 0!important; text-align:center;}
:is(.st-key-cal-org,.st-key-cal-person) [data-testid="stButton"] {
  display:flex; justify-content:center;}
:is(.st-key-cal-org,.st-key-cal-person) button {
  width:42px!important; height:42px; min-height:42px; padding:0; border:0;
  font-variant-numeric:lining-nums tabular-nums;
  border-radius:50%; background:transparent; overflow:visible;}
:is(.st-key-cal-org,.st-key-cal-person) button p {
  font-size:.94rem; line-height:1.1; white-space:pre-line; height:30px; padding-top:2px;}
:is(.st-key-cal-org,.st-key-cal-person) button p span {font-size:.6rem;}
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
  background:#E45F7B; color:white; box-shadow:none;}
:is(.st-key-cal-org,.st-key-cal-person) button:disabled {opacity:.3; background:transparent;}
:is(.st-key-cal-org,.st-key-cal-person)
  [class*="st-key-day-"][class*="-today"] button:not([kind="primary"]) {
  outline:1px solid #D9D0D3; outline-offset:2px;}
.bb-month {font-size:24px; font-weight:600; text-align:center; padding:.25rem 0;}
.bb-month {font-variant-numeric:lining-nums tabular-nums;}
.bb-weekday {font-size:.75rem; color:var(--bb-muted); text-align:center;}
[class*="st-key-row-"] {padding:.8rem 0; border-bottom:1px solid var(--bb-line);}
[class*="st-key-row-"] [data-testid="stButton"] button {
  border:0; background:transparent; font-size:1.25rem;}
[class*="st-key-insight-"] {padding:1rem 0; border-bottom:1px solid var(--bb-line);}
.st-key-proposed-draft, .st-key-decision-summary, .st-key-approval-summary {
  background:white; padding:1.25rem; border-radius:16px;
  box-shadow:0 3px 16px #29242A06;}
.st-key-training-event-fields, .st-key-review-event-fields, [class*="st-key-crew-fields-"] {
  padding:1rem 0; border-bottom:1px solid var(--bb-line);}
[data-testid="stExpander"], [data-testid="stExpander"] details {
  border:0!important; border-radius:0!important;
  border-bottom:1px solid var(--bb-line)!important; background:transparent;}
[data-testid="stExpander"] {border-bottom:0!important;}
[data-testid="stExpander"] summary {padding:1rem 0; color:var(--bb-muted);}
[data-testid="stExpander"] summary > span {flex-direction:row-reverse; width:100%; gap:.5rem;}
[data-testid="stExpander"] summary > span > div {flex:1; min-width:0;}
[data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
  font-size:20px; font-weight:400; color:var(--bb-muted); margin-right:0;}
[data-testid="stExpander"] summary:hover {background:transparent;}
[data-testid="stExpander"] summary p {font-size:14px;}
[data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stTextArea"] [data-baseweb="textarea"] {
  background:white!important; border:1px solid var(--bb-line)!important; border-radius:14px;}
input, textarea {background:white!important;}
[data-testid="stTextArea"] label {margin-bottom:.25rem;}
.st-key-f_mode [role="radiogroup"] {
  background:white; border:1px solid var(--bb-line); border-radius:24px; padding:4px; gap:4px;
  flex-direction:row; align-items:center;}
.st-key-f_mode label[data-testid="stRadioOption"] {
  min-height:42px; padding:.5rem 1rem; border-radius:20px; margin:0;
  display:flex; align-items:center;}
.st-key-f_mode label[data-testid="stRadioOption"]:has(input:checked) {background:#F6E9EC;}
.st-key-f_mode label[data-testid="stRadioOption"] > div > div:first-child {display:none;}
.st-key-f_mode label[data-testid="stRadioOption"] p {margin:0;}
[class*="st-key-listrow-"] {border-bottom:1px solid var(--bb-line);}
[class*="st-key-listrow-"] [data-testid="stButton"] button {
  width:100%; border:0; border-radius:0; background:transparent; padding:12px 32px 12px 0;
  text-align:left; justify-content:flex-start; position:relative; height:auto;}
[class*="st-key-listrow-"] button > div, [class*="st-key-listrow-"] button > div > span {
  justify-content:flex-start; width:100%;}
[class*="st-key-listrow-"] button p {
  white-space:pre-line; font-size:13.5px; line-height:1.5; color:var(--bb-muted); margin:0;}
[class*="st-key-listrow-"] button p strong {font-size:16px; font-weight:600; color:var(--bb-ink);}
[class*="st-key-listrow-"] button::after {
  content:"›"; position:absolute; right:4px; top:50%; transform:translateY(-50%);
  font-size:24px; font-weight:600; color:var(--bb-muted);}
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
[data-testid="stAlert"], [data-testid="stAlertContainer"] {border-radius:14px;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {
  background:#F7EEF1; color:#3A2F36; border:0;}
.st-key-empty-review {padding:48px 0 24px; gap:8px;}
.st-key-empty-review [data-testid="stIconMaterial"] {color:var(--bb-muted); font-size:24px;}
.bb-empty-title {font-size:17px; font-weight:600; margin:0 0 8px;}
.bb-empty-body {font-size:14px; color:var(--bb-muted); margin:0;}
@media (max-width:850px) {
  .block-container {padding:1rem 1.25rem 4rem;}
  h1 {font-size:30px!important;}
  .st-key-app-nav {padding:.25rem .5rem; max-width:100%;}
}
</style>
"""


def install() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def empty_state() -> None:
    with st.container(key="empty-review"):
        st.markdown(":material/inbox:")
        st.markdown(
            '<p class="bb-empty-title">Nothing waiting for review</p>'
            '<p class="bb-empty-body">'
            "AI-assisted and manual drafts will appear here before approval.</p>",
            unsafe_allow_html=True,
        )


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
