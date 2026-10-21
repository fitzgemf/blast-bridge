"""Quiet, date-first presentation helpers for the Streamlit application."""

from html import escape
from zlib import crc32

import streamlit as st

CSS = """
<style>
:root {--bb-ink:#261B22; --bb-muted:#8C8188; --bb-line:#EEE7EA; --bb-pink:#EC5D7B;}
[data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] {margin-bottom:0!important;}
[data-testid="stMarkdownContainer"] > :last-child,
[data-testid="stCaptionContainer"] > :last-child {margin-bottom:0!important;}
html, body, [data-testid="stApp"] {
  background:#FFF9FA; color:var(--bb-ink); font-variant-numeric:lining-nums;}
html, body, [data-testid="stApp"], button, input, textarea, select {
  font-family:"Trebuchet MS",Candara,"Segoe UI",sans-serif!important;}
.block-container {max-width:880px; padding:.75rem 2rem 4rem; min-width:0;}
[data-testid="stHeader"] {background:transparent;}
[data-testid="stToolbar"], [data-testid="stDecoration"], footer {display:none;}
h1 {font-size:34px!important; font-weight:700!important; letter-spacing:-.02em; padding:0;}
h2 {font-size:24px!important; font-weight:600!important; letter-spacing:-.025em;}
h3 {font-size:20px!important; font-weight:700!important; padding:.25rem 0;}
p {font-size:15.5px; font-weight:400; line-height:1.45;}
[data-testid="stCaptionContainer"] {color:var(--bb-muted); font-size:.84rem;}
[data-testid="stVerticalBlock"] {gap:.5rem;}
[data-testid="stCaptionContainer"] p {font-size:13.5px; margin-bottom:.5rem;}
.bb-sub {color:var(--bb-muted); margin:0 0 .5rem;}
.bb-brand {display:flex; align-items:center; justify-content:space-between; gap:1rem;}
.bb-brand h1 {margin:0; padding:0 0 .5rem;}
.bb-demo {font-size:.69rem; letter-spacing:.12em; color:var(--bb-muted); white-space:nowrap;}
.bb-pill {display:inline-block; color:var(--bb-muted); font-size:.84rem; line-height:1.6;}
.bb-pill.review {color:#7768B6;}
.bb-pill.medical {color:#9A6420;}
.bb-pill.urgent {color:#C84747; font-weight:600;}
.bb-pill.fictional {font-size:.69rem; letter-spacing:.12em;}
.bb-label {font-size:12px; font-weight:600; letter-spacing:.04em;
  color:var(--bb-muted); margin-bottom:.25rem;}
.bb-value {font-size:1rem; margin-bottom:.8rem;}
[data-testid="stButton"] button, [data-testid="stPopover"] button {
  border-radius:999px; border:1px solid var(--bb-line); background:white;
  color:var(--bb-ink); box-shadow:none; min-height:42px;}
[data-testid="stButton"] button:hover, [data-testid="stPopover"] button:hover {
  border-color:#EC5D7B; color:#C2456A; background:#FFF0F4;}
[data-testid="stButton"] button[kind="primary"], .st-key-log-action button {
  background:#EC5D7B; color:white; border-color:transparent; font-weight:600;}
[data-testid="stButton"] button[kind="primary"]:hover, .st-key-log-action button:hover {
  background:#C54764; color:white;}
[data-testid="stButton"] button[kind="tertiary"] {
  border:0; background:transparent; padding:0 8px; min-height:36px; color:var(--bb-ink);}
[data-testid="stButton"] button[kind="tertiary"]:hover {
  background:#FFF0F4; color:#C2456A; text-decoration:underline;}
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
.st-key-app-nav {background:transparent; padding:.25rem .5rem;
  border:0; width:100%; max-width:480px; margin:0 auto .5rem;}
.st-key-app-nav [data-testid="stPageLink"] {display:flex; justify-content:center;}
.st-key-app-nav [data-testid="stPageLink"] a {
  justify-content:center; border-radius:999px; padding:.5rem 1rem; color:var(--bb-muted);}
.st-key-app-nav [data-testid="stPageLink"] a[aria-current="page"] {
  background:#FFF0F4; color:var(--bb-ink);}
.st-key-app-nav [data-testid="stPageLink"] a:hover {background:#FFF0F4;}
.st-key-cal-org, .st-key-cal-person {padding:0; background:transparent; gap:2px!important;}
:is(.st-key-cal-org,.st-key-cal-person) [data-testid="stCaptionContainer"] {margin-top:8px;}
:is(.st-key-cal-org,.st-key-cal-person) [data-testid="stExpander"] summary {
  padding:8px 0; min-height:36px;}
:is(.st-key-cal-org,.st-key-cal-person) [data-testid="stVerticalBlock"] {gap:2px;}
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
:is(.st-key-cal-org,.st-key-cal-person) button p span {font-size:.65rem;}
:is(.st-key-cal-org,.st-key-cal-person) button[kind="primary"] p span {color:white!important;}
:is(.st-key-cal-org,.st-key-cal-person) [class*="st-key-day-"] button p::after {
  content:""; display:block; height:6px;}
[class*="st-key-month-nav-"] {width:100%; margin:0 0 .5rem;}
[class*="st-key-month-nav-"] [data-testid="stHorizontalBlock"] {
  gap:4px; align-items:center;}
[class*="st-key-month-nav-"] [data-testid="stColumn"] {flex:0 0 36px!important;}
[class*="st-key-month-nav-"] [data-testid="stColumn"]:first-child {flex:1 1 0!important;}
:is(.st-key-cal-org,.st-key-cal-person) [class*="st-key-month-nav-"] button {
  width:36px!important; height:36px; min-height:36px; color:var(--bb-ink);
  display:flex; align-items:center; justify-content:center;}
:is(.st-key-cal-org,.st-key-cal-person) [class*="st-key-month-nav-"] button p,
:is(.st-key-cal-org,.st-key-cal-person) [class*="st-key-month-nav-"] button p span {
  font-size:28px; font-weight:400; line-height:1; height:auto; padding:0;}
:is(.st-key-cal-org,.st-key-cal-person) [class*="st-key-month-nav-"] button:disabled {
  color:var(--bb-muted);}
:is(.st-key-cal-org,.st-key-cal-person) button:hover {background:#FFF0F4;}
:is(.st-key-cal-org,.st-key-cal-person) button[kind="primary"] {
  background:#EC5D7B; color:white; box-shadow:none;}
:is(.st-key-cal-org,.st-key-cal-person) button:disabled {opacity:.3; background:transparent;}
:is(.st-key-cal-org,.st-key-cal-person)
  [class*="st-key-day-"][class*="-today"] button:not([kind="primary"]) {
  outline:1px solid #D9CDD2; outline-offset:2px;}
.bb-month {font-size:24px; font-weight:700; text-align:left; padding:.25rem 0;}
.bb-month {font-variant-numeric:lining-nums tabular-nums;}
.bb-weekday {font-size:.75rem; color:var(--bb-muted); text-align:center;}
[class*="st-key-row-"] {padding:.8rem 0; border-bottom:1px solid var(--bb-line);}
[class*="st-key-row-"] [data-testid="stButton"] button {
  border:0; background:transparent; font-size:1.25rem;}
[class*="st-key-insight-"] {padding:1rem 0; border-bottom:1px solid var(--bb-line);}
.st-key-proposed-draft, .st-key-decision-summary, .st-key-approval-summary {
  background:white; padding:24px; border-radius:16px; box-shadow:none;}
.st-key-training-event-fields, .st-key-review-event-fields, [class*="st-key-crew-fields-"] {
  padding:1rem 0; border-bottom:1px solid var(--bb-line);}
[data-testid="stExpander"], [data-testid="stExpander"] details {
  border:0!important; border-radius:0!important;
  border-bottom:1px solid var(--bb-line)!important; background:transparent;}
[data-testid="stExpander"] {border-bottom:0!important;}
[data-testid="stExpander"] summary {
  padding:10px 0; min-height:44px; color:var(--bb-muted);}
[data-testid="stExpander"] summary > span {flex-direction:row-reverse; width:100%; gap:.5rem;}
[data-testid="stExpander"] summary > span > div {flex:1; min-width:0;}
[data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
  font-size:20px; font-weight:400; color:var(--bb-muted); margin-right:0;}
[data-testid="stExpander"] summary:hover {background:transparent;}
[data-testid="stExpander"] summary p {font-size:14px;}
[data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stTextArea"] [data-baseweb="textarea"] {
  background:white!important; border:1px solid var(--bb-line)!important; border-radius:16px;}
input, textarea {background:white!important;}
[data-testid="stTextArea"] label {margin-bottom:.25rem;}
.st-key-f_mode [role="radiogroup"] {
  background:white; border:1px solid var(--bb-line); border-radius:24px; padding:4px; gap:4px;
  flex-direction:row; align-items:center;}
.st-key-f_mode label[data-testid="stRadioOption"] {
  min-height:42px; padding:.5rem 1rem; border-radius:20px; margin:0;
  display:flex; align-items:center;}
.st-key-f_mode label[data-testid="stRadioOption"]:has(input:checked) {background:#FFF0F4;}
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
.bb-compact {font-size:14px; line-height:1.5; margin:0 0 2px;}
.bb-compact.muted {font-size:13px; color:var(--bb-muted);}
[class*="st-key-insight-"] {padding:0;}
[class*="st-key-insight-"] summary p {
  font-size:14px; line-height:1.5; white-space:pre-line; color:var(--bb-muted);}
[class*="st-key-insight-"] summary p strong {
  font-size:16px; font-weight:600; color:var(--bb-ink);}
[class*="st-key-insight-"] summary p span {font-size:10px;}
[class*="st-key-surface-"] {background:#FFF0F4; border-radius:28px; padding:16px 28px;}
.bb-home-date {font-size:20px; font-weight:600; line-height:28px; margin:0;}
[data-testid="stElementContainer"]:has(.bb-home-date) {
  min-height:28px; margin:0 0 4px;}
.st-key-selected-day h3, .st-key-person-selected-day h3 {font-weight:600!important;}
.st-key-attention-heading {margin-top:8px; justify-content:space-between;}
.st-key-attention-heading [data-testid="stPageLink"] {white-space:nowrap;}
.st-key-surface-org .st-key-log-action [data-testid="stPopover"] {justify-content:flex-end;}
.st-key-surface-org .st-key-log-action button {min-width:96px; padding:.5rem 1rem;}
.st-key-ai-workspace {background:white; border:1px solid var(--bb-line);
  border-radius:16px; padding:24px;}
.st-key-proposed-draft {margin-top:16px;}
.bb-avatar {width:40px; height:40px; border-radius:50%; display:flex;
  align-items:center; justify-content:center; font-size:14px; font-weight:600;
  pointer-events:none; position:absolute; left:0; top:50%; transform:translateY(-50%);}
[class*="st-key-listrow-"]:has(.bb-avatar) {position:relative;}
[class*="st-key-listrow-"]:has(.bb-avatar) button {padding-left:56px;}
[class*="st-key-listrow-"] > [data-testid="stElementContainer"]:has(.bb-avatar) {
  position:absolute; inset:0; pointer-events:none; z-index:1; margin:0;}
[class*="st-key-listrow-"]:has(.bb-avatar) [data-testid="stMarkdown"],
[class*="st-key-listrow-"]:has(.bb-avatar) [data-testid="stMarkdown"] div:not(.bb-avatar),
[class*="st-key-listrow-"]:has(.bb-avatar) [data-testid="stMarkdownContainer"] {
  position:static;}
[class*="st-key-listrow-"] .bb-avatar {
  position:absolute; left:0; top:50%; transform:translateY(-50%);}
.st-key-person-header {position:relative; padding-left:72px; gap:4px;}
.st-key-person-header .bb-avatar {width:56px; height:56px; top:0;
  transform:none; font-size:18px;}
.st-key-person-header > [data-testid="stElementContainer"]:has(.bb-avatar) {
  position:absolute; left:0; top:0; width:56px;}
.st-key-person-header .bb-brand h1 {padding-bottom:0;}
.st-key-person-header [data-testid="stCaptionContainer"] p {margin-bottom:0;}
.st-key-person-header [data-testid="stExpander"] summary {padding:4px 0; min-height:36px;}
.st-key-person-selected-day {gap:4px;}
.st-key-person-selected-day h3 {padding:0;}
.st-key-person-selected-day [data-testid="stCaptionContainer"] p {margin-bottom:0;}
[class*="st-key-insight-"] summary {position:relative; padding:14px 0 14px 56px;
  min-height:72px;}
[class*="st-key-insight-"] summary p > span:first-child {
  position:absolute; left:0; top:50%; transform:translateY(-50%); width:40px; height:40px;
  display:flex; align-items:center; justify-content:center; border-radius:50%; font-size:12px;
  background:color-mix(in srgb, currentColor 14%, transparent);}
.st-key-back-people button {
  border:0; background:transparent; color:var(--bb-muted); min-height:28px; padding:0;}
.st-key-symptom-log {margin:4px 0;}
.st-key-proposed-draft [data-testid="stVerticalBlock"] {gap:4px;}
.st-key-proposed-draft .bb-value {margin-bottom:12px;}
.st-key-draft-crews {gap:2px!important;}
.bb-crew-heading {font-size:15.5px; font-weight:600; line-height:1.5; margin:16px 0 4px;}
.st-key-draft-issues {margin-top:16px;}
[data-testid="stTabs"] [role="tablist"] {border-bottom:1px solid var(--bb-line); gap:1.5rem;}
[data-testid="stTabs"] [role="tab"] {padding:.75rem .2rem;}
[data-testid="stMetric"] {padding:.5rem 0;}
[data-testid="stMetricValue"] {font-size:1.65rem;}
[data-testid="stVerticalBlockBorderWrapper"] {box-shadow:none;}
[data-testid="stAlert"], [data-testid="stAlertContainer"] {border-radius:14px;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {
  background:#F7EEF1; color:#3A2F36; border:0;}
.st-key-empty-review {padding:48px 0 24px; margin-left:0; gap:8px;}
.st-key-empty-review [data-testid="stIconMaterial"] {color:var(--bb-muted); font-size:24px;}
.bb-empty-title {font-size:17px; font-weight:600; margin:0 0 8px;}
.bb-empty-body {font-size:14px; color:var(--bb-muted); margin:0;}
[class*="st-key-ask-workspace-"] {background:white; border:1px solid var(--bb-line);
  border-radius:16px; padding:24px; margin:16px 0; gap:8px;}
[class*="st-key-ask-workspace-"] h3 {font-size:20px!important;}
[class*="st-key-ask-workspace-"] [data-testid="stForm"] {border:0; padding:0;}
.bb-ask-activity {font-size:13.5px; color:var(--bb-muted); line-height:1.5;}
.bb-ask-section {font-size:15.5px; font-weight:600; margin:8px 0 0;}
.bb-ask-count {font-size:13.5px; color:var(--bb-muted);}
[class*="st-key-ask-workflow-"] {padding:8px 0; border-bottom:1px solid var(--bb-line);}
[class*="st-key-ask-medical-"] {background:#FBF1E4; border-radius:16px; padding:16px;}
[class*="st-key-ask-draft-"] {background:#FFF0F4; border-radius:16px; padding:16px;}
@media (max-width:850px) {
  .block-container {padding:1rem 1.25rem 4rem;}
  h1 {font-size:30px!important;}
  .st-key-app-nav {padding:.25rem .5rem; max-width:100%;}
  [class*="st-key-surface-"] {padding:16px;}
  .st-key-ai-workspace, .st-key-proposed-draft {padding:16px;}
  [class*="st-key-ask-workspace-"] {padding:16px;}
}
</style>
"""


def install() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def surface(key: str):
    return st.container(key=f"surface-{key}")


def profile(name: str) -> None:
    palette = (
        ("#F3F0FA", "#7768B6"),
        ("#FFF0F4", "#C2456A"),
        ("#FBF1E4", "#9A6420"),
        ("#F1ECEE", "#6F6469"),
    )
    background, foreground = palette[crc32(name.encode()) % len(palette)]
    words = name.split()
    initials = (words[0][0] + words[-1][0]).upper() if words else ""
    st.markdown(
        f'<div class="bb-avatar" aria-hidden="true" '
        f'style="background:{background};color:{foreground}">{escape(initials)}</div>',
        unsafe_allow_html=True,
    )


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


def row(
    title: str,
    subtitle: str,
    *,
    key: str,
    state: str = "",
    tone: str = "gray",
    avatar: bool = False,
) -> bool:
    """A single real button is the complete list-row hit target."""
    display_name = title
    title = markdown_text(title)
    subtitle = markdown_text(subtitle)
    text = f"**{title}**\n{subtitle}"
    if state:
        text += f"\n:{tone}[{markdown_text(state)}]"
    with st.container(key=f"listrow-{key}"):
        if avatar:
            profile(display_name)
        return st.button(text, key=key, width="stretch")


def markdown_text(value: str) -> str:
    for character in ("\\", "*", "_", "[", "]", "`", "<", ">"):
        value = value.replace(character, "\\" + character)
    return value


def compact_line(text: str, *, muted: bool = False) -> None:
    style = "bb-compact muted" if muted else "bb-compact"
    st.markdown(f'<div class="{style}">{escape(text)}</div>', unsafe_allow_html=True)


def crew_heading(text: str) -> None:
    st.markdown(f'<div class="bb-crew-heading">{escape(text)}</div>', unsafe_allow_html=True)


def analyst_activity(lines: list[str]) -> None:
    for line in lines:
        st.markdown(f'<div class="bb-ask-activity">✓ {escape(line)}</div>', unsafe_allow_html=True)


def analyst_section(title: str, text: str, records: int, checks: int) -> None:
    count = (
        f"{records} {'record' if records == 1 else 'records'} used"
        if records
        else f"{checks} evidence {'check' if checks == 1 else 'checks'}"
    )
    st.markdown(
        f'<div class="bb-ask-section">{escape(title)}</div>'
        f'<div class="bb-ask-count">{escape(count)}</div>',
        unsafe_allow_html=True,
    )
    st.write(text)


def analyst_recommendation(title: str, rationale: str, *, medical: bool, key: str) -> None:
    style = "medical" if medical else "workflow"
    with st.container(key=f"ask-{style}-{key}"):
        st.caption(
            "Medical guidance — from the deterministic follow-up rules"
            if medical
            else "Workflow recommendation"
        )
        st.write(f"**{markdown_text(title)}**")
        st.write(rationale)


def action(label: str, container_key: str, *, primary: bool = False) -> bool:
    with st.container(key=container_key):
        return st.button(label, type="primary" if primary else "tertiary")


def insight(title: str, summary: str, tone: str):
    text = f":{tone}[●] **{markdown_text(title)}**\n{markdown_text(summary)}"
    return st.expander(text)


def actions():
    return st.container(horizontal=True, horizontal_alignment="left", gap="small")
