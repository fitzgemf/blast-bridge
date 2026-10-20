# Prototype longitudinal-pattern evaluation — SME-informed fictional HIMARS scenario reference

SME-INFORMED FICTIONAL HIMARS SCENARIO REFERENCE — NOT CLINICAL DATA

This compares recorded HIMARS occupational cadence with an SME-informed fictional HIMARS scenario reference. It is not a medical risk score.

A deterministic date-fixture builder is used because V5-2 executes independent binding_offsets draws and has no executable evenly_spaced algorithm for career-wide session placement. The simulation engine is unchanged.

## Reference revision

v1 used even spacing with ±20-day jitter; it made max_events_14d constant and the reference unable to represent clustering, so pre-registered clustered/increase gates failed. v2 replaces only the placement assumption; gates and the 5th-percentile threshold are unchanged.

Evidence: tempo-sme-active-himars; prior design: design-sme-active-himars.
Source wording: approximately 4–5 live-fire training periods per year.

Source limitations:
- No generalization to Army-wide, current Active Army or individual exposure frequency.
- Retrospective recollection, not an official rate, population truth, prior distribution or medical exposure value.
- Single retrospective account; no dates, service duration, logs, sampling frame or independent verification. Period and event may have different boundaries.
- Approximate average recollection of live-fire periods; boundaries and participant coverage unverified.
- Source wording is retained; this is a research activity mapping. No equivalence of sessions, rounds, days, qualifications or individual exposures is assumed.
- Scope is limited to the named requirement, unit, school or exercise; no population frequency is inferred.
- support level E, source_only, distribution_family none

Scenario assumptions:
- career_start: "2015-01-01" — prototype scenario assumption — not evidence
- career_start_offset_days: [0, 364] — prototype scenario assumption — not evidence
- career_years: 6 — prototype scenario assumption — not evidence
- careers_per_rate: 60 — prototype scenario assumption — not evidence
- first_window_offset_days: 365 — prototype scenario assumption — not evidence
- placement: "k distinct days drawn uniformly within each fictional year (least-informative placement given only a per-year count)" — prototype scenario assumption — not evidence
- rate_assignment: "each career retains one endpoint rate for all six fictional years" — prototype scenario assumption — not evidence
- rates: [4, 5] — source-bound endpoints of approximately 4–5 per year; not a fitted distribution
- reference_seed: 20261020 — prototype scenario assumption — not evidence
- seed_derivation: "first 8 SHA256 bytes of colon-separated seed:career:year:event; event=0 for the per-year placement draw, year=event=-1 for the career offset" — prototype scenario assumption — not evidence
- step_days: 45 — prototype scenario assumption — not evidence
- unit_mapping: "one fictional period/session equals one fictional occupational event day" — prototype scenario assumption — not evidence
- year_days: 365 — prototype scenario assumption — not evidence

one fictional period/session equals one fictional occupational event day — prototype scenario assumption — not evidence
Independent fictional careers: 120; repeated analysis windows: 4920.
Windows are repeated observations of the same fictional careers, not independent subjects.
Sessions per career-year: {"mean": 4.5, "median": 4.5}.
Zero shares: {"events_30d": 0.6709349593495935, "events_365d": 0.0, "events_90d": 0.26991869918699185}.
Fingerprint: `{"builder_constants_sha256": "141e71a84606c3351741f41a4665a59bbcad565def8c0de1bbb6312de6a0909a", "reference_features_sha256": "f2ea7324f4b9a81f80fb610d5d6a38bddc923c5ae03d8b5f6f033d2611a2a6aa"}`.
Model parameters: `{"n_estimators": 100, "random_state": 20261019}`.
prototype analytic threshold: 5th percentile of reference score_samples; not clinical, blast or injury
A comparison requires HIMARS-scope records beginning at least 365 days before analysis_as_of and at least one HIMARS event day in (analysis_as_of - 365 days, analysis_as_of]. This is an analytic coverage rule, not a medical threshold.
Expected flagged reference-window share by construction: 5%. Actual share: 4.959%.
Two independent fits: identical.

| Feature | Median | IQR q25–q75 |
| --- | --- | --- |
| events_30d | 0.000000 | 0.000000–1.000000 |
| events_90d | 1.000000 | 0.000000–2.000000 |
| events_365d | 4.000000 | 4.000000–5.000000 |
| days_since_previous_event | 51.000000 | 22.000000–95.000000 |
| max_events_14d | 1.000000 | 1.000000–2.000000 |
| recent_vs_earlier_cadence | 0.000000 | -0.333333–0.222222 |

Deliberately excluded:
- unknown-count fraction: The fictional HIMARS scenario reference models dates only, with no count missingness. Unknown activity counts are reported as data-quality notes instead.
- distinct weapon families: The fictional HIMARS scenario reference covers HIMARS only, so the feature is constant.
- physical-event counts: Not comparable across weapon families; the fictional reference contains dates only.
- symptoms, medical and demographic fields: Excluded by design.

Analysis as of 2026-10-19. Expectations are pre-registered; no tuning.
The clustered and increase gates were also used once to diagnose reference v1 (see Reference revision), so they are not strictly held out from v2.
Held-out histories retain phase .35 and jitter ±7; they are not drawn from the reference's uniform within-year placement.

| Scenario | Expected | Actual | PASS/MISMATCH | Reason |
| --- | --- | --- | --- | --- |
| distributed 4/year | Typical recorded pattern | Typical recorded pattern | PASS | Applicable HIMARS history |
| distributed 5/year | Typical recorded pattern | Typical recorded pattern | PASS | Applicable HIMARS history |
| clearly clustered recent | Atypical occupational pattern | Atypical occupational pattern | PASS | Applicable HIMARS history |
| sharp recent increase | Atypical occupational pattern | Atypical occupational pattern | PASS | Applicable HIMARS history |
| history only 200 days long | Not enough applicable recorded history for this prototype comparison. | Not enough applicable recorded history for this prototype comparison. | PASS | recorded history shorter than the 365-day comparison window |
| no recent HIMARS record | Not enough applicable recorded history for this prototype comparison. | Not enough applicable recorded history for this prototype comparison. | PASS | no HIMARS record in the prior 365 days |
| M270-only history | Not enough applicable recorded history for this prototype comparison. | Not enough applicable recorded history for this prototype comparison. | PASS | outside the HIMARS prototype scope |

There are no medical labels; this evaluation does not measure injury prediction.

Seeded fictional roster (HIMARS-scope event days only):

| Person | events_30d | events_90d | events_365d | days_since_previous_event | max_events_14d | recent_vs_earlier_cadence | Status | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Avery Kestrel (FICTIONAL) | 2.000000 | 2.000000 | 5.000000 | 6.000000 | 1.000000 | 0.333333 | Typical recorded pattern | Applicable HIMARS history |
| Jordan Pike (FICTIONAL) | 1.000000 | 2.000000 | 4.000000 | 27.000000 | 1.000000 | 0.444444 | Typical recorded pattern | Applicable HIMARS history |
| Riley Marsh (FICTIONAL) | 1.000000 | 2.000000 | 5.000000 | 27.000000 | 1.000000 | 0.333333 | Typical recorded pattern | Applicable HIMARS history |
| Sam Okafor-Lind (FICTIONAL) | 0.000000 | 1.000000 | 2.000000 | 55.000000 | 1.000000 | 0.222222 | Not enough applicable recorded history for this prototype comparison. | recorded history shorter than the 365-day comparison window |
| Casey Thorne (FICTIONAL) | 2.000000 | 2.000000 | 6.000000 | 13.000000 | 1.000000 | 0.222222 | Typical recorded pattern | Applicable HIMARS history |
| Morgan Vale (FICTIONAL) | 1.000000 | 1.000000 | 5.000000 | 27.000000 | 1.000000 | -0.111111 | Typical recorded pattern | Applicable HIMARS history |
| Taylor Brook (FICTIONAL) | 2.000000 | 2.000000 | 4.000000 | 6.000000 | 1.000000 | 0.444444 | Typical recorded pattern | Applicable HIMARS history |
| Devon Ashby (FICTIONAL) | 1.000000 | 1.000000 | 3.000000 | 13.000000 | 1.000000 | 0.111111 | Not enough applicable recorded history for this prototype comparison. | recorded history shorter than the 365-day comparison window |
| Quinn Halloway (FICTIONAL) | 1.000000 | 2.000000 | 5.000000 | 17.000000 | 1.000000 | 0.333333 | Typical recorded pattern | Applicable HIMARS history |
| Reese Calder (FICTIONAL) | 3.000000 | 4.000000 | 7.000000 | 6.000000 | 3.000000 | 1.000000 | Atypical occupational pattern | Applicable HIMARS history |
| Emerson Tull (FICTIONAL) | 1.000000 | 2.000000 | 5.000000 | 17.000000 | 1.000000 | 0.333333 | Typical recorded pattern | Applicable HIMARS history |
| Harper Yoon (FICTIONAL) | 0.000000 | 0.000000 | 0.000000 | 730.000000 | 0.000000 | 0.000000 | Not enough applicable recorded history for this prototype comparison. | outside the HIMARS prototype scope |

V0.5 sparse demo scenario — secondary stress test only; not the reference
Windows flagged by the new model: 84.124%.
