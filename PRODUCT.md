# BlastBridge product prototype

AI-assisted occupational blast-exposure records and human review for military training,
with longitudinal histories and separate occupational-pattern and symptom-follow-up signals.

This hackathon prototype uses invented people, events and reports. It brings structured records
and distinct attention signals into one review workflow without merging them into a score.

## Current capabilities

1. **Text, photo and manual intake:** turn text or a photographed training record into a structured
   proposal with Claude, or enter it manually. Catalog/fictional-roster tools and a Python gate
   ground AI proposals; Unknown stays Unknown. All paths share one **Review event** decision:
   **Approve event**, **Edit**, **Save for later** or **Discard**.
2. **Longitudinal occupational history:** reconstruct approved activity across dates, people, crews
   and roles, with persistent manual/live-AI/replay provenance.
3. **ML occupational-pattern comparison:** compare HIMARS event-day cadence with the SME-informed
   fictional HIMARS scenario reference; only elevated atypical cadence surfaces an ML review signal.
4. **Deterministic symptom/follow-up guidance:** record human-confirmed reports and apply the
   existing TBICoE/CDC guidance rules independently of the occupational-pattern model.
5. **Ask BlastBridge and Review Brief:** a bounded analyst queries existing evidence and produces
   a first-class Review brief with numbered, clickable citations to captured structured sources.
   Medical sections remain code-owned deterministic guidance, not model interpretation.
6. **Evidence Intelligence:** surface possible duplicate records, compare fields, inspect an
   Evidence map and prepare a reconstruction with explicit conflicts and source provenance.
   Human decisions remain necessary; possible shared events are not confirmed duplicates.

## Boundaries

Exposure is not injury. A report after an event is a temporal association, not a cause.
Screening and follow-up are not diagnoses. Unknown is never zero or reassurance.
The prototype does not estimate TBI/CTE probability, diagnose a condition, or infer injury from
physical-event counts. CTE is mentioned only as long-term research motivation.
AI intake structures training records; the analyst can relay code-owned symptom/follow-up text.
Neither interprets symptoms or makes medical decisions.
MACE 2 is linked as an external resource for medically trained personnel, never reproduced.
Urgent attention uses red; medical follow-up uses amber; occupational review priority uses muted violet.
Routine monitoring is quiet. Destructive record actions use restrained red text/borders.

## Recorder workflow

Top navigation has **Home**, **People** and **Review**. Home starts with a full-width organization
calendar and a compact selected-day card. Neutral dots mark approved training dates; red dots
mark only the date of a confirmed urgent danger-sign report, within the analysis date.
Current readiness never colors historical training dates. Blue diamonds on a person's calendar
mark confirmed symptom reports; neither calendar uses amber attention markers.
Select a past or current day and **+ Log** to describe, upload or manually enter a training event,
with the selected date prefilled. **Open record** opens the hidden Training record page.
Future days are visible but disabled and have no markers.
Choose **Describe / paste training record**, **Upload / photograph record** or **Enter manually**.
All paths converge on the unsaved **Review event** surface. **Load example narrative** fills the
input with fictional text; empty/short text never calls the model. The demo board photo has a
SHA-256-matched replay; other images require live AI or manual entry. Image bytes stay session-only.
**Approve event** saves the validated proposal and approves that exact saved revision, without a
mandatory second Review stop. If approval fails after saving, the event remains a draft with an
explicit notice and a path to Review; approval is never automatically retried.
**Save for later** creates a draft only; **Edit** returns to the prefilled manual form and then the
same Review event surface; **Discard** clears the unsaved proposal.
An explicit source date is kept when it differs from calendar context, with a visible warning.
Saved-draft Approve/Edit/Reject controls bind to the reviewed revision; approval is atomic and repeat-safe.
Drafts and rejected events never enter personnel history.
The person's calendar supports explicitly human symptom entry, review and Confirm.
Confirmed reports and approved training events retain separate records and provenance.
People opens as a searchable roster. A selected person has a full-width calendar, a visible
deterministic attention band for non-routine states, and three
separate insight cards: Exposure pattern, Symptoms and Follow-up. Evidence, reference metadata,
guidance/sources and chronological detail remain in collapsed expanders.
Review has **Training drafts** and **Follow-up** tabs. Training drafts are saved items awaiting a
decision, including saved-for-later and reconstructed drafts. Its navigation badge counts pending
training drafts only. Hidden logging, person-detail, training-record and Follow-up routes remain
available. Human approval and symptom confirmation stay explicit.
Home's **Demo / Advanced** expander holds the analysis date, recorded-events table and confirmed
demo reset. Reset restores the fictional records and the 19 Oct 2026 analysis/calendar date.

## Readiness precedence

Readiness is computed on demand using **Analysis as of** in Home's **Demo / Advanced**:

1. A qualifying recorded danger sign → **Urgent evaluation**.
2. Persistent, function-affecting structured symptoms → **Medical follow-up recommended**.
3. An atypical elevated occupational cadence → **Review priority**.
4. Otherwise → **Routine monitoring**.

ML alone can only produce Review priority. No count value influences a medical-adjacent status.
Reports dated after the analysis date are excluded from the current readiness assessment.
Evidence lines identify their sources separately; routine monitoring is not medical reassurance.

## Occupational-pattern model

The question is: “Does this person's recorded HIMARS occupational cadence differ substantially
from the SME-informed fictional HIMARS scenario reference?” Only approved HIMARS records
(`m142-himars`) enter this comparison. Other weapon records remain visible but are excluded,
with their number reported. One fictional live-fire period/session maps to one occupational event
day as a prototype scenario assumption, not evidence establishing equivalent event boundaries.
Dates are distinct, later dates are ignored, and windows exclude their lower endpoint and include
their upper endpoint. The six features are:

- `events_30d`: occupational event days in `(analysis_as_of − 30 days, analysis_as_of]`.
- `events_90d`: occupational event days in `(analysis_as_of − 90 days, analysis_as_of]`.
- `events_365d`: occupational event days in `(analysis_as_of − 365 days, analysis_as_of]`.
- `days_since_previous_event`: days since the most recent event at or before analysis_as_of,
  capped at 730; 730 when no prior event is recorded.
- `max_events_14d`: the largest number of event days in `(d − 14 days, d]` for event-day
  endpoints `d` in the prior 365 days; zero when there is no endpoint.
- `recent_vs_earlier_cadence`: `events_90d / 3 − (events_365d − events_90d) / 9`,
  expressed as recent minus earlier events per 30 days.

Deliberately excluded:

- Unknown-count fraction: the date-only fictional reference has no count missingness; adding it
  would make unknowns atypical by construction. Show a data-quality note instead.
- Distinct weapon families: constant within this HIMARS-only prototype comparison.
- Physical-event counts: not comparable across weapon families; the fictional reference uses dates.
- Symptoms, medical and demographic fields: excluded by design.

IsolationForest uses `n_estimators=100` and `random_state=20261019`, with scikit-learn 1.6.1.
The prototype analytic threshold is the 5th percentile of fictional HIMARS scenario reference
`score_samples`; lower values are raw anomalies before directional interpretation. This is not a
clinical, blast or injury threshold. The score is never presented as a medical probability.
Feature medians, IQRs and differing features explain comparison context, not medical risk factors.

Prototype interpretation rule: an atypical comparison is 'elevated' only when at least one
recent-activity feature (30/90/365-day events, most events in 14 days, recent-minus-earlier cadence)
exceeds the 95th percentile of the SME-informed fictional HIMARS scenario reference. Not clinical.
Bounds use reference rows only and NumPy's default linear quantile method, with strict `>` checks;
days since the previous event is excluded from direction. The forest, its parameters and the
5th-percentile raw anomaly threshold are unchanged.

The four interpreted statuses are:

- **Not enough applicable recorded history for this prototype comparison.** Coverage/reference
  unavailable; no ML readiness signal.
- **Typical recorded pattern.** No raw anomaly; no ML readiness signal.
- **Unusual lower activity pattern — informational only.** A raw anomaly without an activity
  feature above its elevation bound; no ML readiness signal.
- **Atypical elevated occupational cadence.** A raw anomaly with at least one activity feature
  strictly above its bound; ML can contribute Review priority only.

Only elevated atypical cadence can create Review priority; reduced activity is informational.
This is an occupational-pattern observation, not a medical risk result.

### Reference provenance and coverage

Evidence `tempo-sme-active-himars` says “approximately 4–5 live-fire training periods per year.”
It is one retrospective SME recollection, with representativeness unknown, no verified logs or
sampling frame, and unverified period/event boundaries and participant coverage. It does not
establish Army-wide frequency, individual exposure frequency, a prior distribution or medical
truth. Prior design `design-sme-active-himars` remains support level E, `source_only`, with
`distribution_family none` and null parameters. The two rate endpoints are source-bound;
their equal representation and all date-placement choices are prototype assumptions, not evidence.

The tiny deterministic fixture builder outputs fictional occupational dates only. V5-2 executes
independent `binding_offsets` placement and refuses `evenly_spaced` because it has no executable
algorithm. That engine cannot express this career-wide scenario unchanged, so it is not used.
No simulation semantics or evidence/prior records are changed.

The scenario uses seed 20261020, 60 fictional careers at each endpoint (120 independent fictional
careers), six 365-day years per career, starts at 1 Jan 2015 plus a deterministic 0–364-day offset,
k distinct days drawn uniformly within each fictional year (least-informative placement given
only a per-year count), using deterministic per-career/year seeds.
Version 2 replaces only version 1's even spacing and ±20-day jitter, which made clustering
unrepresentable and failed the pre-registered clustered/increase gates; those gates and the
5th-percentile threshold remain unchanged.
Windows begin at career start +365 days and advance every 45 days through career end.
These are repeated observations of the same fictional careers, not independent subjects.
Metadata retains assumptions, verbatim source limitations, rate summaries, zero shares, feature
medians/IQRs and SHA256 fingerprints of the CSV bytes and canonical builder constants.
The reference is fictional and is not an empirical military model or medical ground truth.

The analytic coverage rule requires HIMARS records beginning at least 365 days before the analysis
date and at least one HIMARS day in the prior 365-day window. This avoids treating absent records
as absent activity. It is not a medical threshold. Available results are “Typical recorded pattern”
or one of the two directional atypical statuses; none establishes injury or its absence.
The unavailable state is “Not enough applicable recorded history for this prototype comparison.”
Its reason identifies out-of-scope history, a shorter recording window, no recent HIMARS record,
or an unavailable reference. It contributes no ML readiness signal and is not reassurance.

Fictional demo history is arranged: EVT-DEMO-B1–B3 (Oct 2025–Mar 2026) were added so
most of the roster has the 365-day history the comparison requires, and EVT-DEMO-C1–C3
(Oct 2026) were constructed so Reese Calder demonstrates an elevated-cadence comparison.
The model, threshold, reference and rules were not changed for the demo.
Some people intentionally retain short or M270-only history to demonstrate the unavailable state.
The V0.5 sparse demo scenario is now only a secondary stress test.

## Research → product mapping

<table>
<tr><th>Research or component</th><th>Product use</th></tr>
<tr><td>weapon catalog</td><td>
AI normalization and structured event identity
</td></tr>
<tr><td>occupation/system catalog</td><td>
occupational context
</td></tr>
<tr><td>training-tempo research</td><td>
informed which longitudinal cadence variables are meaningful and documented what cannot be treated
as empirical population frequency
</td></tr>
<tr><td>evidence/support-level work</td><td>
provenance, uncertainty, unknown handling
</td></tr>
<tr><td>physical-event vs ParticipantExposure distinction</td><td>
prevents participant count from multiplying physical events
</td></tr>
<tr><td>V0.5 fictional generator</td><td>
secondary stress-test data (the readiness model uses the SME-informed fictional HIMARS scenario
reference built by scripts/build_himars_reference.py)
</td></tr>
<tr><td>symptom research</td><td>
participant symptom records
</td></tr>
<tr><td>TBICoE/CDC guidance</td><td>
deterministic medical-follow-up boundaries
</td></tr>
<tr><td>AI intake</td><td>
reduces operational data-entry burden
</td></tr>
<tr><td>IsolationForest</td><td>
identifies atypical recorded occupational patterns only
</td></tr>
</table>

## Evaluation

- [Live intake report](examples/fictional/intake/eval_report_live.md).
- [Deterministic intake report](examples/fictional/intake/eval_report_deterministic.md).
- [Occupational-pattern report](examples/fictional/ml-reference-himars/reference_report.md).

The [retired V0.5 sparse report](examples/fictional/ml-baseline/RETIRED_v05_sparse_eval_report.md)
is historical only and does not evaluate the current readiness model.

Intake reports distinguish model performance from scripted tests of the Python gate.
Pattern hypotheses are fixed before evaluation; mismatches are retained rather than tuned away.
Medical guidance is deterministic and is not an ML evaluation. There are no medical labels;
the pattern evaluation does not measure injury prediction.

## Run the demo

From the repository root, use Python 3.12 with the optional `app` dependencies installed.
In PowerShell, optionally configure live intake in the launching session without writing a key file:

```powershell
$secret = Read-Host "Optional Anthropic API key" -AsSecureString
$env:ANTHROPIC_API_KEY = [Net.NetworkCredential]::new("", $secret).Password
python -m streamlit run app/streamlit_app.py
```

Without a key, run the Streamlit command alone and choose **Use demo replay**, or enter manually.
The replay uses its recorded fictional narrative and reference date, not the recorder's pasted text.
The calendar and readiness views use the independently selected analysis date.
**Reset to demo state** requires confirmation and restores the fictional records and 19 Oct 2026
analysis/calendar state. It deletes recorded events and symptom reports in the demo database.
Ask replays require the bundled analysis date. If prompted, **Use demo date (19 Oct 2026)** changes
only session analysis/calendar dates and clears prior Ask state; it does not reset stored records.
Repeat the suggested request after switching dates. Live AI reads `ANTHROPIC_API_KEY` from the
launching environment; the app does not load `.env` files.

## Privacy and governance

Prototype uses fictional data. A production implementation handling health information would
require appropriate identity, authorization, privacy, security and records-governance controls.
Guidance sources were reviewed on 19 Oct 2026; production use requires ongoing source/version
review.
No real people or protected health information belong in this demo.
