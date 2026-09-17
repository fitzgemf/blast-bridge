# Decisions before research dataset development

1. Governance: intended research use, consent/IRB requirements as applicable,
   approved storage, access controls, retention, deletion, and sharing rules.
   Anonymous local IDs alone do not guarantee anonymity; career histories may
   reidentify people. The development repository is outside cloud synchronization
   but is not approved for any real participant records; see data-governance.md.
2. Population and career semantics: branches/components, service episodes,
   transfers, breaks in service, occupational specialty systems (MOS/rating/AFSC),
   assignment overlap, and unknown or partial service dates. V1 has one service
   span; assignment branch/component can describe changes inside that span.
3. Event granularity: a discharge, grouped session, or recalled period; counting
   rules for rounds versus firing events, nearby participation, multiple weapons,
   and deduplication of reports describing the same event. Do not infer counts
   from a military occupation.
4. Time: source timezone, uncertain dates, recalled ranges, event duration,
   sensor clock synchronization. V1 requires exact timezone-aware timestamps
   for events/readings/reports; do not manufacture precision for old recollections.
   Date comparisons use the timestamp's recorded local date.
5. Ontology: verified weapon variants, ammunition/charge, platform configuration,
   crew roles, environments, PPE detail, and official DoD Tier-1 definition/version.
   Category placeholders must be distinguished from specific systems.
   V0.1 now supplies source-cited weapons, occupations and relationships; the
   remaining uncertainties and historical scope are listed in reference-v0.1.md.
6. Measurement: pressure definition (incident/reflected, overpressure, reference),
   impulse integration interval, sensor placement/orientation, calibration,
   saturation/clipping and quality review. Explicit units alone do not make
   quantities comparable. No automatic unit conversion or dose aggregation exists.
7. Provenance: source-review rules, conflicts, uncertainty bounds, field-level
   overrides, estimate methods, and a reproducible confidence rubric. Confidence
   is optional except for estimates; it must never be invented to fill missing
   data. Assumptions and synthetic sources are not measurements.
8. Symptoms: instrument selection and permissions, time windows, per-symptom
   severity/duration versus report-level values, follow-up and medical evaluation
   semantics. V1 severity is an unvalidated descriptive self-report label.
   An exposure link expresses an association in a record, not causation.
9. Dataset operations: schema versions/migrations, globally consistent source
   identifiers, lineage snapshots, correction history, import/export formats,
   record ownership, and enforcement of referential integrity at ingestion.
   ResearchDataset validates closed in-memory batches, not a storage system.
10. Future ML design (requires separate approval): research questions, synthetic
    labeling and separate storage, member-level train/test separation, leakage,
    representativeness, bias, and anomaly evaluation. No injury labels, risk
    thresholds, or clinical prediction targets are supplied by this scaffold.

Limitations: V1 record provenance covers unwrapped descriptive fields together;
counts, distances, orientation, pressure, impulse and duration have independent
provenance. Split records or extend the schema when those descriptive fields
have conflicting sources or different evidence kinds. Missing objects are
unknown; there is no imputation. Detached model construction cannot check that
IDs exist; use ResearchDataset for cross-record validation. Pydantic copy/update
and construction APIs can bypass validation: do not use model_construct() or
model_copy(update=...) with untrusted data; validate complete payloads instead.
