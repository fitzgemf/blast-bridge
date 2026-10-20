# BlastBridge product prototype

An AI-assisted occupational brain-health readiness system that reconstructs longitudinal
blast-exposure history and surfaces service members whose recorded exposure patterns or symptoms
deserve attention.

This hackathon prototype uses invented people, events and reports. It brings four distinct signals
into one review workflow without merging them into a score.

## Four capabilities

1. **AI-assisted record intake:** turn a pasted training record into a proposed structured event.
   Local catalog and fictional-roster lookups ground the proposal; Python validates it.
2. **Longitudinal occupational history:** reconstruct approved activity across dates, people, crews
   and roles, with persistent manual/live-AI/replay provenance.
3. **ML occupational-pattern comparison:** compare event-day cadence with a fictional simulation
   baseline and surface atypical recorded patterns for human review.
4. **Deterministic symptom/follow-up guidance:** record human-confirmed reports and apply the
   existing TBICoE/CDC guidance rules independently of the occupational-pattern model.

## Boundaries

Exposure is not injury. A report after an event is a temporal association, not a cause.
Screening and follow-up are not diagnoses. Unknown is never zero or reassurance.
The prototype does not estimate TBI/CTE probability, diagnose a condition, or infer injury from
physical-event counts. CTE is mentioned only as long-term research motivation.
The AI handles training records only; it does not interpret symptoms or make medical decisions.
MACE 2 is linked as an external resource for medically trained personnel, never reproduced.
Red indicates recorded urgent danger-sign guidance only; amber indicates review/follow-up attention.
Occupational records and routine monitoring use neutral styling.

## Recorder workflow

The organization calendar shows approved records on their recorded dates. Its attention markers
reflect the participants' current readiness assessment at the selected analysis date.
Select a past or current day to begin a training record with that date prefilled.
Future days are visible but disabled and have no markers.
Choose AI-assisted intake or enter manually; both paths lead to the same review screen.
“Load example narrative” fills the input with real text. Empty/short text never calls the model.
AI output remains a proposal until a recorder saves a draft and explicitly approves it.
Approve/Edit/Reject controls bind to the reviewed revision; approval is atomic and repeat-safe.
Drafts and rejected events never enter personnel history.
The person's calendar supports explicitly human symptom entry, review and Confirm.
Confirmed reports and approved training events retain separate records and provenance.

## Readiness precedence

Readiness is computed on demand using the sidebar's **Analysis as of** date:

1. A qualifying recorded danger sign → **Urgent evaluation**.
2. Persistent, function-affecting structured symptoms → **Medical follow-up recommended**.
3. An atypical occupational pattern → **Review priority**.
4. Otherwise → **Routine monitoring**.

ML alone can only produce Review priority. No count value influences a medical-adjacent status.
Reports dated after the analysis date are excluded from the current readiness assessment.
Evidence lines identify their sources separately; routine monitoring is not medical reassurance.

## Occupational-pattern model

The question is: “Does this person's recent recorded occupational activity pattern differ
substantially from patterns in the fictional simulation baseline?”
One attended session day in the simulation maps to one occupational event day; in the product,
one approved training event day for a person maps to one occupational event day.
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

- Unknown-count fraction: the fictional simulation baseline has no count missingness, so unknowns
  would appear atypical by construction. Show a data-quality note instead.
- Distinct weapon families: the fictional simulation baseline has one fictional family; constant.
- Physical-event counts: not comparable across weapon families; the reference family is fictional.
- Symptoms, medical and demographic fields: excluded by design.

IsolationForest uses `n_estimators=100` and `random_state=20261019`, with scikit-learn 1.6.1.
The prototype analytic threshold is the 5th percentile of fictional simulation baseline
`score_samples`; lower values yield “Atypical occupational pattern.” This is not a clinical,
blast or injury threshold. The score is never presented as a medical probability.
Feature medians, IQRs and differing features explain comparison context, not medical risk factors.

## Fictional simulation baseline provenance

The V0.5 fictional generator runs the existing demo scenario with population 30 and seed 20261019.
Analysis windows begin at service start +365 days, advance every 45 days and end at the bounded
service end, producing 2910 windows. The build preserves the original simulation/scenario logic.
Metadata records configuration fingerprint, mapping, versions, feature semantics and model settings.
The fictional generator is NOT an empirical military population model and is NOT medical ground
truth.
The same inputs produce the same generated files; the baseline never includes the product roster's
symptoms, health outcomes or demographic data.

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
reproducible fictional ML baseline
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
- [Occupational-pattern report](examples/fictional/ml-baseline/eval_report.md).

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

## Privacy and governance

Prototype uses fictional data. A production implementation handling health information would
require appropriate identity, authorization, privacy, security and records-governance controls.
Guidance sources were reviewed on 19 Oct 2026; production use requires ongoing source/version
review.
No real people or protected health information belong in this demo.
