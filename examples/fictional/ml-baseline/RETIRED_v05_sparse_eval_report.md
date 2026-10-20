> RETIRED / HISTORICAL — this evaluated the retired V0.5 sparse demo scenario model. It is NOT the current readiness model. Current evaluation: examples/fictional/ml-reference-himars/reference_report.md

# Prototype longitudinal-pattern evaluation

FICTIONAL SIMULATION BASELINE — NOT CLINICAL DATA

This compares recorded occupational activity with a fictional simulation baseline. It is not a medical risk score.

Fictional simulation baseline windows: 2910.
Model parameters: `{"n_estimators": 100, "random_state": 20261019}`.
Threshold rule: 5th percentile of fictional-baseline score_samples (5th percentile; fitted threshold -0.639603714).
Expected flagged share of fictional simulation baseline windows by construction: 5%. Actual share: 4.983%.
Two independent fits: identical.

Features:
- `events_30d`: Occupational events in prior 30 days
- `events_90d`: Occupational events in prior 90 days
- `events_365d`: Occupational events in prior 365 days
- `days_since_previous_event`: Days since previous occupational event
- `max_events_14d`: Most occupational events within any 14-day period (prior 365 days)
- `recent_vs_earlier_cadence`: Recent cadence minus earlier cadence (events per 30 days)

Deliberately excluded:
- unknown-count fraction: The fictional simulation baseline has no count missingness, so any unknown would look atypical by construction. It is reported as a data-quality note instead.
- distinct weapon families: The fictional simulation baseline has one fictional family, so the feature is constant.
- physical-event counts: Not comparable across families, and the fictional simulation baseline family is fictional.
- symptoms, medical and demographic fields: Excluded by design.

Analysis as of: 2026-10-19.
Expected labels are pre-registered hypotheses; observed mismatches are retained.

| Scenario | Expected | Actual | PASS/MISMATCH |
| --- | --- | --- | --- |
| distributed | Typical recorded pattern | Typical recorded pattern | PASS |
| tightly clustered recent | Atypical occupational pattern | Atypical occupational pattern | PASS |
| missing-count history | Typical recorded pattern | Typical recorded pattern | PASS |
| sparse | Typical recorded pattern | Typical recorded pattern | PASS |
| recent cadence change | Atypical occupational pattern | Atypical occupational pattern | PASS |

Missing-count scenario data-quality note: 3 of 3 records in the prior 365 days have an unknown activity count (not used by the pattern model).

There are no medical labels; this evaluation does not measure injury prediction.

Seeded fictional roster (approved training event days only):

| Person | events_30d | events_90d | events_365d | days_since_previous_event | max_events_14d | recent_vs_earlier_cadence | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Avery Kestrel (FICTIONAL) | 1.000000 | 1.000000 | 4.000000 | 27.000000 | 1.000000 | 0.000000 | Atypical occupational pattern |
| Jordan Pike (FICTIONAL) | 1.000000 | 2.000000 | 4.000000 | 27.000000 | 1.000000 | 0.444444 | Atypical occupational pattern |
| Riley Marsh (FICTIONAL) | 1.000000 | 2.000000 | 5.000000 | 27.000000 | 1.000000 | 0.333333 | Atypical occupational pattern |
| Sam Okafor-Lind (FICTIONAL) | 0.000000 | 1.000000 | 2.000000 | 55.000000 | 1.000000 | 0.222222 | Typical recorded pattern |
| Casey Thorne (FICTIONAL) | 1.000000 | 1.000000 | 3.000000 | 27.000000 | 1.000000 | 0.111111 | Typical recorded pattern |
| Morgan Vale (FICTIONAL) | 1.000000 | 1.000000 | 3.000000 | 27.000000 | 1.000000 | 0.111111 | Typical recorded pattern |
| Taylor Brook (FICTIONAL) | 1.000000 | 1.000000 | 2.000000 | 27.000000 | 1.000000 | 0.222222 | Typical recorded pattern |
| Devon Ashby (FICTIONAL) | 0.000000 | 0.000000 | 1.000000 | 118.000000 | 1.000000 | -0.111111 | Typical recorded pattern |
| Quinn Halloway (FICTIONAL) | 0.000000 | 2.000000 | 3.000000 | 55.000000 | 1.000000 | 0.555556 | Typical recorded pattern |
| Reese Calder (FICTIONAL) | 0.000000 | 1.000000 | 2.000000 | 55.000000 | 1.000000 | 0.222222 | Typical recorded pattern |
| Emerson Tull (FICTIONAL) | 0.000000 | 2.000000 | 3.000000 | 55.000000 | 1.000000 | 0.555556 | Typical recorded pattern |
| Harper Yoon (FICTIONAL) | 0.000000 | 1.000000 | 1.000000 | 83.000000 | 1.000000 | 0.333333 | Typical recorded pattern |
