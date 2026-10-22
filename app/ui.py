"""Quiet, date-first presentation helpers for the Streamlit application."""

import os
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from enum import StrEnum
from html import escape
from zlib import crc32

import streamlit as st

from blastbridge.models.enums import EventType
from blastbridge.models.training_tempo import TrainingContext
from blastbridge.product.agent import IntakeResult, ProviderError
from blastbridge.product.analyst import AnalystRun
from blastbridge.product.analyst_tools import SymptomProposal, ToolTrace
from blastbridge.product.calendar_view import DEMO_STORY_DATE
from blastbridge.product.evidence import Signal
from blastbridge.product.models import CrewPosition
from blastbridge.product.readiness import ReadinessStatus

CSS = """
<style>
:root {--bb-ink:#211F22; --bb-muted:#6B6569; --bb-line:#D8D2D4; --bb-accent:#713E53;
  --bb-accent-hover:#5D3144; --bb-surface:#FAF8F6; --bb-soft:#E6D9DE;
  --bb-review:#67578C; --bb-followup:#83561C; --bb-urgent:#B64747;}
/* Shell and typography. */
[data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] {margin-bottom:0!important;}
[data-testid="stMarkdownContainer"] > :last-child,
[data-testid="stCaptionContainer"] > :last-child {margin-bottom:0!important;}
html, body, [data-testid="stApp"] {
  background:#F1EFEC; color:var(--bb-ink); font-variant-numeric:lining-nums;}
html, body, [data-testid="stApp"], button, input, textarea, select {
  font-family:Georgia,"Times New Roman",serif!important;}
.block-container {max-width:880px; padding:16px 32px 64px; min-width:0;}
[data-testid="stMain"] {scroll-padding-top:80px;}
h1, h2, h3, [id] {scroll-margin-top:80px;}
[data-testid="stHeader"] {display:none;}
[data-testid="stToolbar"], [data-testid="stDecoration"], footer {display:none;}
h1 {font-size:34px!important; font-weight:700!important; letter-spacing:-.02em; padding:0;}
h2 {font-size:24px!important; font-weight:600!important; letter-spacing:-.025em;}
h3 {font-size:20px!important; font-weight:700!important; padding:.25rem 0;}
p {font-size:15.5px; font-weight:400; line-height:1.45;}
[data-testid="stCaptionContainer"] {color:var(--bb-muted); font-size:.84rem;}
[data-testid="stVerticalBlock"] {gap:.5rem;}
[data-testid="stCaptionContainer"] p {
  color:var(--bb-muted)!important; font-size:13.5px; margin-bottom:8px;}
.bb-sub {color:var(--bb-muted); margin:0 0 .5rem;}
.bb-brand {display:flex; align-items:center; justify-content:space-between; gap:1rem;}
.bb-brand h1 {margin:0; padding:0 0 .5rem;}
.bb-demo {font-size:.69rem; letter-spacing:.12em; color:var(--bb-muted); white-space:nowrap;}
.bb-pill {display:inline-block; color:var(--bb-muted); font-size:.84rem; line-height:1.6;}
.bb-pill.review {color:var(--bb-review);}
.bb-pill.medical {color:var(--bb-followup);}
.bb-pill.urgent {color:var(--bb-urgent); font-weight:600;}
.bb-pill.approved {color:#3F6652;}
.bb-pill.fictional {font-size:.69rem; letter-spacing:.12em;}
.bb-label {font-size:12px; font-weight:600; letter-spacing:.04em;
  color:var(--bb-muted); margin-bottom:.25rem;}
.bb-value {font-size:1rem; margin-bottom:.8rem;}
[data-testid="stButton"] button, [data-testid="stPopover"] button {
  border-radius:6px; border:1px solid var(--bb-line); background:var(--bb-surface);
  color:var(--bb-ink); box-shadow:none; min-height:42px;}
[data-testid="stButton"] button:hover, [data-testid="stPopover"] button:hover {
  border-color:var(--bb-accent); color:var(--bb-accent-hover); background:var(--bb-soft);}
/* Controls and citation chips. */
[class*="st-key-brief-citations-"],
[class*="st-key-brief-citations-"] [data-testid="stHorizontalBlock"] {
  gap:2px 6px!important;}
[class*="st-key-brief-citations-"] [data-testid="stButton"] button {
  min-height:24px; padding:2px 6px; font-size:12px;}
[class*="st-key-brief-citations-"] [data-testid="stButton"] button p {
  font-size:12px; line-height:1.2; margin:0; white-space:nowrap;}
[data-testid="stButton"] button[kind="primary"], .st-key-log-action button {
  background:var(--bb-accent); color:white; border-color:transparent; font-weight:600;}
[data-testid="stButton"] button[kind="primary"]:hover, .st-key-log-action button:hover {
  background:var(--bb-accent-hover); color:white;}
[data-testid="stButton"] button[kind="tertiary"] {
  border:0; background:transparent; padding:0 8px; min-height:36px; color:var(--bb-ink);}
[data-testid="stButton"] button[kind="tertiary"]:hover {
  background:var(--bb-soft); color:var(--bb-accent-hover); text-decoration:underline;}
[class*="st-key-brief-citations-"] button:is(:focus,:focus-visible,:active),
[class*="st-key-brief-citations-"] button[kind="secondary"],
[class*="st-key-brief-citations-"] button:hover {
  background:var(--bb-soft)!important; color:var(--bb-accent)!important;
  outline:none!important; box-shadow:none!important; border-style:solid!important;}
[class*="st-key-brief-citations-"] button,
[class*="st-key-brief-citations-"] button * {
  text-decoration:none!important; outline:none!important; border-bottom:0!important;}
[class*="st-key-brief-citations-"] button::before,
[class*="st-key-brief-citations-"] button::after {display:none!important; content:none!important;}
[class*="st-key-discard-"] button, [class*="st-key-reject-"] button {
  color:#B64747!important; border-color:#B64747!important; background:transparent!important;}
[class*="st-key-followup-action-"] button {
  color:#744A16; border-color:#A36B24; background:#F1E5D3;}
[class*="st-key-followup-action-"] button:hover {background:#E9D8BD; color:#744A16;}
.st-key-log-action, .st-key-symptom-log {margin:.5rem 0 .5rem;}
.st-key-log-action [data-testid="stPopover"], .st-key-symptom-log [data-testid="stButton"] {
  display:flex; justify-content:center;}
.st-key-log-action [data-testid="stPopover"] button, .st-key-symptom-log button {
  border-radius:6px!important; height:40px; min-width:120px; padding:8px 16px;}
.st-key-log-action [data-testid="stPopover"] button svg {display:none;}
.st-key-log-action [data-testid="stPopover"] button [data-testid="stIconMaterial"] {
  display:none;}
[data-testid="stPopoverBody"] [data-testid="stButton"] button {
  width:100%; border:0; background:transparent; color:var(--bb-ink);
  border-radius:0; justify-content:flex-start; text-align:left;}
/* Native navigation stays above the scrolling content. */
.st-key-app-nav {position:sticky; top:0; z-index:100; background:#242126;
  padding:4px 8px; border-radius:10px; border:0; width:100%; margin:0 auto 16px;
  box-shadow:0 1px 0 var(--bb-line);}
/* Streamlit wraps the nav container in a 52 px layout wrapper; stick the wrapper so the nav
   stays pinned within the full-height page block. The page-coloured band hides content
   scrolling beneath the nav's rounded corners. */
[data-testid="stLayoutWrapper"]:has(> .st-key-app-nav) {
  position:sticky; top:0; z-index:100; background:#F1EFEC; padding-top:8px;}
.st-key-app-nav [data-testid="stPageLink"] {display:flex; justify-content:center;}
.st-key-app-nav [data-testid="stPageLink"] a {
  justify-content:center; border-radius:6px; padding:.5rem 1rem; color:#E6DFE3;}
.st-key-app-nav [data-testid="stPageLink"] :is(a,p,span,svg) {color:#E6E1E3!important;}
.st-key-app-nav [data-testid="stPageLink"] svg {fill:currentColor;}
.st-key-app-nav [class*="st-key-nav-item-"][class*="-active"] [data-testid="stPageLink"] a {
  background:var(--bb-accent); color:#FAF8F6; font-weight:600;}
.st-key-app-nav [class*="-active"] [data-testid="stPageLink"] :is(a,p,span,svg) {
  color:#FAF8F6!important;}
.st-key-app-nav [data-testid="stPageLink"] a:hover {
  background:var(--bb-accent-hover); color:#FAF8F6;}
/* Calendars. */
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
:is(.st-key-cal-org,.st-key-cal-person) button:hover {background:var(--bb-soft);}
:is(.st-key-cal-org,.st-key-cal-person) button[kind="primary"] {
  background:#713E53; color:white; box-shadow:none;}
:is(.st-key-cal-org,.st-key-cal-person) button:disabled {opacity:.3; background:transparent;}
:is(.st-key-cal-org,.st-key-cal-person)
  [class*="st-key-day-"][class*="-today"] button:not([kind="primary"]) {
  outline:1px solid #D9CDD2; outline-offset:2px;}
.bb-month {font-size:24px; font-weight:700; text-align:left; padding:4px 0;
  font-variant-numeric:lining-nums tabular-nums;}
.bb-weekday {font-size:.75rem; color:var(--bb-muted); text-align:center;}
[class*="st-key-row-"] {padding:.8rem 0; border-bottom:1px solid var(--bb-line);}
[class*="st-key-row-"] [data-testid="stButton"] button {
  border:0; background:transparent; font-size:1.25rem;}
[class*="st-key-insight-"] {padding:0; border-bottom:1px solid var(--bb-line);}
.st-key-proposed-draft, .st-key-decision-summary, .st-key-approval-summary {
  background:var(--bb-surface); padding:24px; border-radius:12px; box-shadow:none;}
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
/* Native form surfaces. */
[data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stTextArea"] [data-baseweb="textarea"] {
  background:var(--bb-surface)!important; border:1px solid var(--bb-line)!important;
  border-radius:6px;}
input, textarea {background:var(--bb-surface)!important;}
[data-testid="stDateInput"] [data-baseweb="input"],
[data-testid="stNumberInput"] [data-baseweb="input"],
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
  background:var(--bb-surface)!important; border:1px solid var(--bb-line)!important;
  border-radius:6px;}
[data-testid="stDateInput"] [data-baseweb="input"] > div,
[data-baseweb="select"] > div > div {background:var(--bb-surface)!important;}
[data-baseweb="select"] svg {color:var(--bb-muted);}
[data-baseweb="popover"] [role="listbox"],
[data-baseweb="popover"] [role="option"] {background:var(--bb-surface)!important;}
[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="popover"] [role="option"][aria-selected="true"] {
  background:var(--bb-soft)!important;}
:is([data-baseweb="input"],[data-baseweb="textarea"]):focus-within,
[data-baseweb="select"]:focus-within > div {
  border-color:var(--bb-accent)!important; box-shadow:0 0 0 1px var(--bb-accent)!important;}
[data-testid="stTextArea"] label {margin-bottom:.25rem;}
.st-key-f_mode [role="radiogroup"] {
  background:var(--bb-surface); border:1px solid var(--bb-line); border-radius:10px;
  padding:4px; gap:4px;
  flex-direction:row; align-items:center;}
.st-key-f_mode label[data-testid="stRadioOption"] {
  min-height:42px; padding:.5rem 1rem; border-radius:6px; margin:0;
  display:flex; align-items:center;}
.st-key-f_mode label[data-testid="stRadioOption"]:has(input:checked) {background:var(--bb-soft);}
.st-key-f_mode label[data-testid="stRadioOption"] > div > div:first-child {display:none;}
.st-key-f_mode label[data-testid="stRadioOption"] p {margin:0;}
/* People and deterministic attention. */
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
[class*="st-key-listrow-"][class*="-attention-"] {
  border-left:4px solid var(--attention-color); padding-left:12px;}
[class*="-attention-urgent"], .st-key-attention-band-urgent {
  --attention-color:#B64747; --attention-text:var(--bb-urgent);}
[class*="-attention-followup"], .st-key-attention-band-followup {
  --attention-color:#A36B24; --attention-text:var(--bb-followup);}
[class*="-attention-review"], .st-key-attention-band-review {
  --attention-color:#67578C; --attention-text:var(--bb-review);}
[class*="st-key-listrow-"][class*="-attention-"] button p span {
  color:var(--attention-text)!important;}
[class*="st-key-listrow-"][class*="-attention-"] button p span strong {
  color:var(--attention-text); font-size:14px;}
[class*="st-key-listrow-"][class*="-attention-"] .bb-avatar {left:12px;}
[class*="st-key-attention-band-"] {
  border-left:4px solid var(--attention-color); padding:12px 16px;
  background:var(--bb-surface); border-radius:6px; margin:8px 0;}
[class*="st-key-attention-band-"] strong {color:var(--attention-text);}
[class*="st-key-insight-"] summary p {
  font-size:14px; line-height:1.5; white-space:pre-line; color:var(--bb-muted);}
[class*="st-key-insight-"] summary p strong {
  font-size:16px; font-weight:600; color:var(--bb-ink);}
[class*="st-key-insight-"] summary p span {font-size:10px;}
[class*="st-key-surface-"] {background:var(--bb-surface); border-radius:12px; padding:16px 28px;}
.bb-home-date {font-size:20px; font-weight:600; line-height:28px; margin:0;}
[data-testid="stElementContainer"]:has(.bb-home-date) {
  min-height:28px; margin:0 0 4px;}
.st-key-selected-day, .st-key-person-selected-day {gap:8px; margin-top:16px;}
.st-key-selected-day h3, .st-key-person-selected-day h3 {
  font-weight:600!important; padding:0;}
[class*="st-key-selected-day-heading-"] [data-testid="stColumn"] {min-width:0;}
[class*="st-key-selected-day-heading-"] .st-key-log-action,
[class*="st-key-selected-day-heading-"] .st-key-symptom-log {margin:0;}
.st-key-attention-heading {margin-top:8px; justify-content:space-between;}
.st-key-attention-heading [data-testid="stPageLink"] {white-space:nowrap;}
.st-key-surface-org .st-key-log-action [data-testid="stPopover"] {justify-content:flex-end;}
.st-key-surface-org .st-key-log-action button {min-width:96px; padding:.5rem 1rem;}
.st-key-ai-workspace {background:var(--bb-surface); border:1px solid var(--bb-line);
  border-radius:12px; padding:24px;}
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
.st-key-person-header {position:relative; padding-left:72px; gap:4px;}
.st-key-person-header .bb-avatar {width:56px; height:56px; top:0;
  transform:none; font-size:18px;}
.st-key-person-header > [data-testid="stElementContainer"]:has(.bb-avatar) {
  position:absolute; left:0; top:0; width:56px;}
.st-key-person-header .bb-brand h1 {padding-bottom:0;}
.st-key-person-header [data-testid="stCaptionContainer"] p {margin-bottom:0;}
.st-key-person-header [data-testid="stExpander"] summary {padding:4px 0; min-height:36px;}
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
[data-testid="stAlert"], [data-testid="stAlertContainer"] {border-radius:10px;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {
  background:var(--bb-soft); color:var(--bb-ink); border:0;}
.st-key-empty-review {padding:48px 0 24px; margin-left:0; gap:8px;}
.st-key-empty-review [data-testid="stIconMaterial"] {color:var(--bb-muted); font-size:24px;}
.bb-empty-title {font-size:17px; font-weight:600; margin:0 0 8px;}
.bb-empty-body {font-size:14px; color:var(--bb-muted); margin:0;}
/* Analyst composer and source cards. */
[class*="st-key-ask-workspace-"] {background:var(--bb-surface); border:1px solid var(--bb-line);
  border-radius:12px; padding:24px; margin:16px 0; gap:8px;}
[class*="st-key-ask-workspace-"] h3 {font-size:20px!important;}
[class*="st-key-ask-workspace-"] [data-testid="stForm"] {border:0; padding:0;}
[class*="st-key-ask-workspace-"] [data-testid="stTextInput"]
  :is([data-testid="stTextInputRootElement"],[data-baseweb="input"]) {
  border:1px solid var(--bb-line)!important; border-radius:6px;
  background:var(--bb-surface)!important;}
[class*="st-key-ask-workspace-"] [data-testid="stTextInput"]
  :is([data-testid="stTextInputRootElement"],[data-baseweb="input"]):focus-within {
  border-color:var(--bb-accent)!important; box-shadow:0 0 0 2px var(--bb-soft);}
[class*="st-key-ask-workspace-"] input::placeholder {color:var(--bb-muted); opacity:1;}
[class*="st-key-ask-suggestions-"] {gap:8px;}
[class*="st-key-ask-suggestions-"] [data-testid="stButton"] button[kind="tertiary"] {
  min-height:32px; border:1px solid var(--bb-line); border-radius:999px; padding:4px 12px;
  background:transparent; color:var(--bb-accent); text-decoration:none;}
[class*="st-key-ask-suggestions-"] button p {font-size:13px; line-height:1.25;}
[class*="st-key-ask-suggestions-"] [data-testid="stButton"] button:hover {
  background:var(--bb-soft); border-color:var(--bb-accent); text-decoration:none;}
.bb-source-fields {display:grid; grid-template-columns:minmax(0,35%) minmax(0,1fr);
  gap:8px 16px; margin:8px 0 16px; font-size:14px; line-height:1.5;}
.bb-source-fields dt {color:var(--bb-muted); font-size:13px; font-weight:600;}
.bb-source-fields dd {margin:0; overflow-wrap:anywhere;}
.bb-ask-activity {font-size:13.5px; color:var(--bb-muted); line-height:1.5;}
.bb-ask-section {font-size:15.5px; font-weight:600; margin:8px 0 0;}
.bb-ask-count {font-size:13.5px; color:var(--bb-muted);}
/* Agent trace uses a single list, with raw I/O available separately. */
[class*="st-key-agent-trace-"] .bb-trace-row {
  display:grid; grid-template-columns:24px minmax(0,1fr); gap:8px;
  padding:12px 0; border-bottom:1px solid var(--bb-line); font-size:14px;}
[class*="st-key-agent-trace-"] .bb-trace-number,
[class*="st-key-agent-trace-"] .bb-trace-meta {color:var(--bb-muted); font-size:13px;}
[class*="st-key-agent-trace-"] .bb-trace-heading {
  display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 8px;}
[class*="st-key-agent-trace-"] .bb-trace-heading code {
  font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:12px;
  background:var(--bb-soft); color:var(--bb-ink); padding:2px 4px; border-radius:4px;}
[class*="st-key-agent-trace-"] .bb-trace-summary {margin-top:4px; overflow-wrap:anywhere;}
[class*="st-key-ask-workflow-"] {padding:8px 0; border-bottom:1px solid var(--bb-line);}
[class*="st-key-ask-medical-"] {background:#F1E5D3; border-radius:12px; padding:16px;}
[class*="st-key-ask-draft-"] {background:var(--bb-soft); border-radius:12px; padding:16px;}
@media (max-width:850px) {
  .block-container {padding:1rem 1.25rem 4rem;}
  h1 {font-size:30px!important;}
  [class*="st-key-surface-"] {padding:16px;}
  .st-key-ai-workspace, .st-key-proposed-draft {padding:16px;}
  [class*="st-key-ask-workspace-"] {padding:16px;}
}
@media (max-width:520px) {
  .bb-source-fields {grid-template-columns:minmax(0,1fr); gap:4px;}
  .bb-source-fields dd {margin-bottom:8px;}
}
</style>
"""


def install() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def surface(key: str):
    return st.container(key=f"surface-{key}")


def profile(name: str) -> None:
    palette = (
        ("#E5DFED", "#67578C"),
        ("#E6D9DE", "#713E53"),
        ("#F1E5D3", "#83561C"),
        ("#E4DFDB", "#746E72"),
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
            "Drafts you save for later and reconstructed records awaiting approval "
            "will appear here.</p>",
            unsafe_allow_html=True,
        )


def brand(title: str = "BlastBridge") -> None:
    st.markdown(
        f'<div class="bb-brand"><h1>{escape(title)}</h1>'
        '<span class="bb-demo">FICTIONAL DEMO</span></div>',
        unsafe_allow_html=True,
    )


def analysis_date(selected: date | None = None) -> date:
    return selected if selected is not None else DEMO_STORY_DATE


def use_suggested_replay(has_replay: bool, live_available: bool) -> bool:
    return has_replay and (
        os.environ.get("BLASTBRIDGE_DEMO_MODE", "").lower() == "replay" or not live_available
    )


def with_demo_fallback(
    live: Callable[[], AnalystRun],
    replay: Callable[[], AnalystRun],
    *,
    replay_name: str = "suggested",
    replay_index: int = 0,
) -> tuple[AnalystRun, bool]:
    if replay_name == "log_event" or replay_index > 0:
        return live(), False
    try:
        result = live()
    except ProviderError:
        return replay(), True
    return (replay(), True) if result.provider_error else (result, False)


def image_with_demo_fallback(
    live: Callable[[], IntakeResult],
    replay: Callable[[], IntakeResult] | None,
    *,
    live_available: bool,
) -> tuple[IntakeResult, bool]:
    if use_suggested_replay(replay is not None, live_available):
        assert replay is not None
        return replay(), False
    if not live_available:
        raise ValueError("Live AI isn't available for this image. Use manual entry.")
    if replay is None:
        return live(), False
    try:
        result = live()
    except ProviderError:
        return replay(), True
    return (replay(), True) if result.provider_error else (result, False)


def human_label(value: StrEnum) -> str:
    if value is TrainingContext.QUALIFICATION:
        return "Qualification"
    return value.value.replace("_", " ").capitalize()


def evidence_display(field: str, value: object, weapon_names: Mapping[str, str]) -> str:
    if value is None:
        return "Unknown"
    if value is True:
        return "Activity recorded"
    if field == "weapon_system_id":
        return weapon_names.get(str(value), "Weapon not resolved")
    try:
        if field == "event_type":
            return human_label(EventType(str(value)))
        if field == "training_context":
            return human_label(TrainingContext(str(value)))
        if field.startswith("member:") and isinstance(value, (tuple, list)) and len(value) == 2:
            return f"{value[0]} · {CrewPosition(value[1]).label}"
    except ValueError:
        return "Needs review"
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    return str(value)


def signal_display(signal: Signal, names: Mapping[str, str]) -> str:
    if signal.name == "participant_overlap":
        return "Shared participants: " + ", ".join(
            names.get(person_id, "Shared participant") for person_id in signal.evidence
        )
    if signal.name == "same_context" and len(signal.evidence) == 2:
        return "Same activity and context: " + " · ".join(
            evidence_display(field, value, {})
            for field, value in zip(
                ("event_type", "training_context"), signal.evidence, strict=True
            )
        )
    if signal.name == "same_location":
        return "Same location: " + "; ".join(signal.evidence)
    return "Shared recorded evidence"


def source_label(index: int, on_date: date) -> str:
    return f"Range record {'A' if index == 0 else 'B'} · {on_date:%d %b %Y}"


def symptom_prefill(proposal: SymptomProposal) -> tuple[dict[str, object], tuple[str, ...]]:
    values: dict[str, object] = {}
    labels = []
    for key, label, value in (
        ("sym_w_event", "Linked event", proposal.event_id),
        ("sym_w_relationship", "Temporal relationship", proposal.temporal_relationship),
        ("sym_w_date", "Report date", proposal.report_date),
        ("sym_w_persistence", "Persistence", proposal.persistence),
        ("sym_w_impact", "Functional impact", proposal.functional_impact),
        ("sym_w_source", "Source", proposal.source),
        ("sym_w_note", "Note", proposal.note),
    ):
        if value is not None:
            values[key] = value
            labels.append(label)
    if proposal.symptoms:
        values.update({f"sym_w_s_{item.value}": True for item in proposal.symptoms})
        labels.append("Symptoms")
    return values, tuple(labels)


def intake_result_for_mode(
    result: IntakeResult | None, stored_mode: str | None, entry_mode: str
) -> IntakeResult | None:
    return result if stored_mode == entry_mode else None


def navigation_section(page_key: str) -> str | None:
    return {
        "dashboard": "dashboard",
        "new": "dashboard",
        "history": "history",
        "person": "history",
        "followup": "history",
        "inbox": "inbox",
        "review": "inbox",
    }.get(page_key)


def review_badge(count: int) -> str:
    return f"Review {count}" if count > 0 else "Review"


def attention_tone(status: ReadinessStatus) -> str:
    return {
        ReadinessStatus.URGENT_EVALUATION: "urgent",
        ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED: "followup",
        ReadinessStatus.REVIEW_PRIORITY: "review",
        ReadinessStatus.ROUTINE_MONITORING: "routine",
    }[status]


def navigation(pages: dict, current_page: str, pending_count: int) -> None:
    active = navigation_section(current_page)
    with st.container(key="app-nav"):
        for column, key, title in zip(
            st.columns(3),
            ("dashboard", "history", "inbox"),
            ("Home", "People", review_badge(pending_count)),
            strict=True,
        ):
            with column:
                with st.container(key=f"nav-item-{key}-{'active' if key == active else 'idle'}"):
                    st.page_link(pages[key], label=title)


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


def trace_row(step: ToolTrace, number: int, display_names: Mapping[str, str]) -> str:
    """Format captured tool activity without rendering model text as Markdown."""
    inputs = []
    for key, value in step.input.items():
        if key == "person_id":
            inputs.append(display_names.get(str(value), "Person"))
        elif key in ("event_ids", "source_ids") and isinstance(value, (list, tuple)):
            inputs.append(f"{len(value)} records")
        elif key in ("event_id", "event_ref"):
            inputs.append("1 record")
        else:
            inputs.append(f"{key.replace('_', ' ')}: {value}")
    summary = step.summary
    if step.scope == "validation":
        code, separator, path = summary.partition(":")
        wording = {
            "MEDICAL_CONTENT": "medical wording withheld",
            "UNKNOWN_REF": "unknown evidence reference",
        }.get(code, code)
        summary = f"{wording}: {path}" if separator else wording
    badge = "nested intake" if step.scope == "nested" else step.scope
    scope = f'<span class="bb-trace-meta">{escape(badge)}</span>' if badge != "outer" else ""
    status = "✓ ok" if step.ok else "! issue"
    return (
        f'<div class="bb-trace-row"><span class="bb-trace-number">{number}</span><div>'
        f'<div class="bb-trace-heading"><code>{escape(step.tool)}</code>{scope}'
        f'<span>{status}</span><span class="bb-trace-meta">'
        f"{len(step.evidence_refs)} evidence</span></div>"
        f'<div class="bb-trace-meta">{escape(one_line(" · ".join(inputs)) or "—")}</div>'
        f'<div class="bb-trace-summary">{escape(one_line(summary))}</div></div></div>'
    )


def trace_verdict(run: AnalystRun) -> str:
    if run.fallback:
        return "Grounded ✓ — model wording withheld; deterministic text shown"
    if run.grounded:
        return "Grounded ✓ — every section cites evidence returned by a tool"
    return f"Not grounded — {run.error}" if run.error else "Not grounded"


def definition_list(fields: Sequence[tuple[str, str]]) -> None:
    entries = "".join(
        f"<dt>{escape(one_line(name))}</dt><dd>{escape(one_line(value))}</dd>"
        for name, value in fields
    )
    st.markdown(f'<dl class="bb-source-fields">{entries}</dl>', unsafe_allow_html=True)


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
    attention = tone in ("urgent", "followup", "review")
    if state:
        if attention:
            markdown_tone = {"urgent": "red", "followup": "orange", "review": "violet"}[tone]
            text += f"\n:{markdown_tone}[● **{markdown_text(state)}**]"
        else:
            text += f"\n:{tone}[{markdown_text(state)}]"
    row_key = f"listrow-{key}-attention-{tone}" if attention else f"listrow-{key}"
    with st.container(key=row_key):
        if avatar:
            profile(display_name)
        return st.button(text, key=key, width="stretch")


def one_line(value: object) -> str:
    """Collapse whitespace so a blank line cannot end an inline HTML block."""
    return " ".join(str(value).split())


def markdown_text(value: str) -> str:
    for character in ("\\", "*", "_", "[", "]", "`", "<", ">"):
        value = value.replace(character, "\\" + character)
    return value


def compact_line(text: str, *, muted: bool = False) -> None:
    style = "bb-compact muted" if muted else "bb-compact"
    st.markdown(f'<div class="{style}">{escape(one_line(text))}</div>', unsafe_allow_html=True)


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
    # Model-written text: escaped Markdown, so links/images/HTML in it never render.
    st.markdown(markdown_text(text))


def analyst_recommendation(
    title: str, rationale: str, *, medical: bool, key: str, action_label: str | None = None
) -> bool:
    style = "medical" if medical else "workflow"
    with st.container(key=f"ask-{style}-{key}"):
        st.caption(
            "Medical guidance — from the deterministic follow-up rules"
            if medical
            else "Workflow recommendation"
        )
        st.write(f"**{markdown_text(title)}**")
        st.markdown(markdown_text(rationale))
        if action_label is not None:
            return st.button(action_label, key=f"ask-action-{key}")
    return False


def action(label: str, container_key: str, *, primary: bool = False) -> bool:
    with st.container(key=container_key):
        return st.button(label, type="primary" if primary else "tertiary")


def insight(title: str, summary: str, tone: str):
    text = f":{tone}[●] **{markdown_text(title)}**\n{markdown_text(summary)}"
    return st.expander(text)


def actions():
    return st.container(horizontal=True, horizontal_alignment="left", gap="small")
