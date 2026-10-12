# Synthetic career generator architecture V0.4

Status: architecture/schema contracts only, version **0.4.0**. Python package
version remains 0.1.0. No generator, military numerical scenario, production
synthetic career, exposure score, medical outcome, or trained model is included.
All numeric examples in tests are conspicuously fictional software fixtures.

## 1. Simulation configuration

`SimulationConfig` is immutable, typed, and rejects undeclared fields. It requires
simulation/scenario/generator versions, master seed, population size, date range,
all three input dataset versions, and each population, career, assignment,
training, participation, missingness, and uncertainty configuration. No
scientifically meaningful value is inserted by a model default.

Career configuration requires explicit duration, episode-count, and
branch/component-transition bindings. Assignment configuration requires duration,
occupation-selection, and weapon/platform-eligibility bindings. Training requires
cycle context plus distinct event-frequency and rounds-per-event bindings for
every selected component. Participation requires role, nearby-presence, and
instructor-presence bindings. The uncertainty register must cover all eight
dimensions. A missingness rule must be stated even when the mechanism is unknown.
This contract prevents an empty or partially filled config from looking like a
valid run. It does not execute the config.

Every `ParameterBinding` contains a distribution, classification, uncertainty
types, and disjoint provenance references for prior definitions, source evidence,
SME estimates, or scenario assumptions. Evidence constraints retain their V0.3
PriorDefinition IDs; SME estimates have their own ID class and cannot be presented
as empirical priors. `validate_configuration_references` joins these references
against supplied registries and the selected scenario.

## 2. Scenario architecture

`ScenarioDefinition` supports `exploratory_conservative`, `exploratory_central`,
`exploratory_high_tempo`, and `custom`. Labels are names for modeling alternatives;
they do not represent population percentiles, validated rates, epidemiological
groups, injury risk, or severity. Each scenario requires a purpose and population
scope and explicitly lists PriorDefinition IDs, evidence-constraint IDs,
supporting evidence IDs, SME-estimate IDs, scenario assumptions, parameter
bindings, and dependency IDs. The scenario registry validator checks identifiers
and classifications. V0.4 contains no military scenario instances or values.

## 3. Career hierarchy and assignment model

The typed graph is:

```text
SyntheticMember
  -> CareerEpisode[]
      -> AssignmentEpisode[]
          -> TrainingPeriod[]
              -> LiveFireSession[]
                  -> FiringMission[] (when applicable)
                      -> FiringEvent[]
                          -> ParticipantExposure[]
```

Career episodes can represent changes in branch, component, and occupation over
time. Assignments carry occupation/MOS reference, unit type, eligible weapon and
platform references, crew role, instructor/student status, training context, and
deployment/training-cycle status. Those values are required or explicitly nullable
where unknown; a career is not forced to retain one role, platform, or component.
All dates are checked through the member/career/assignment/training/session/mission
chain. Session, mission, and firing timestamps must be timezone-aware.

Army Active, Army National Guard, Army Reserve, Marine Active, and Marine Reserve
are separate component values. Population selection and training configuration are
independently supplied for each component selected in the population scope. There
is no Active-to-Guard conversion shortcut.

The intermediate hierarchy is optional at the domain level when a future weapon
family does not use every level; current table contracts preserve the levels so a
later scenario can state which parents apply. HIMARS/MLRS launches, cannon and
mortar rounds, and Abrams main-gun events must still resolve to one physical
`FiringEvent` identity.

## 4. Physical event identity and participant exposure

`FiringEvent` represents one discharge. It includes a stable `SYN-EVENT-*` ID,
timestamp, system/family IDs, context, session and optional mission parent,
positive round/launch index, optional explicitly known ammunition configuration,
and generation provenance. No pressure, impulse, distance, ammunition, or
configuration is inferred. Duplicate event IDs fail validation.

`ParticipantExposure` is a separate row with its own ID and references to one event,
synthetic member, assignment, role, and participation type. Several participants
can refer to one event. The dataset validator checks the event/member/assignment
joins and participant assignment dates. Unit ammunition totals and
person-event counts remain distinct measures.

Every record ID uses a `SYN-*` namespace. `stable_synthetic_id` makes an ID from an
explicit positive ordinal; future chunking must assign ordinals from a stable
global ordering. Schemas do not contain fields for names, addresses, phone numbers,
SSNs, DoD IDs, EDIPI, or medical-record numbers. The synthetic namespace does not
by itself make arbitrary input safe; no real participant records are accepted by
these generator record models.

## 5. Distribution abstraction

The discriminated `DistributionSpec` covers fixed, discrete uniform, triangular,
beta, normal, lognormal, Poisson, negative binomial, categorical, and empirical
families. Validation checks finite values, support/shape parameters, triangular
ordering and width, integer uniform bounds, unique categorical values, and
categorical probability sum. No BlastBridge military values are attached.

`sample_count` is a separate explicit operation. It rejects negative draws and
does not clamp them to zero. Callers must choose a fractional-count policy
(floor, nearest, or reject); continuous families are not silently cast to
integers. Poisson and negative-binomial samplers return nonnegative integers.
Extreme floating-point inputs can exceed representable output limits; those limits
must be characterized against an approved scenario before production use.

## 6. RNG and reproducibility

The V0.4 RNG uses an isolated `random.Random` instance seeded with version 2 and
uses only the `random()` primitive in distribution transforms. The recorded
algorithm identifier is `python-mt19937-random-v1`. A SHA-256 derivation combines
master seed, generator version, scenario version, canonical JSON fingerprints of
the complete config and scenario (including dataset versions), stream name, and
stable entity key. This avoids process-global RNG state and Python's randomized
`hash()`.

Separate streams exist for population, careers, assignments, training, firing,
participation, and missingness. `stream_seeds` makes the stream seed register
inspectable; entity keys isolate child work. Identical serialized config/scenario,
versions, generator/RNG algorithm, seed, and code produce identical draws in the
same supported Python runtime. Cross-runtime/platform floating-point equivalence
has not been qualified. A sampler/algorithm change requires a generator or RNG
algorithm version change and new golden-vector tests.

## 7. Dependency model

Configuration requires explicit dependency declarations for component to training
configuration, occupation to weapon/platform eligibility, assignment to context,
training cycle to event frequency, event to rounds, role to participation,
instructor status to repeated presence, and deployment preparation to tempo.
Each link has a conditional, joint, independent-assumption, or unknown mode.
Independence requires a declared scenario-assumption ID. `unknown` records that
the dependency is unresolved; it does not claim independence or supply a strength.
No edge coefficients or causal interpretations are assigned in V0.4.

## 8. Uncertainty lineage

Aleatory, epistemic, and unknown/unclassified are separate values. Configuration
must cover career duration, assignment duration, event frequency, rounds per event,
participation, role, missing years, and source support. Every parameter and
generated record retains its uncertainty types and source/assumption lineage.
`QuantityValue` makes unknown and not-applicable values nonnumeric; zero remains a
valid observed value. There is no aggregate confidence score.

## 9. Missingness

`MissingnessRule` represents MCAR, MAR, MNAR, structural missingness,
not-collected, and unknown-reason distinctly. MCAR/MAR/MNAR require explicit
scenario assumptions; MAR/MNAR also require conditioning quantities. Structural
and collection status are not treated as stochastic values. V0.4 makes no claim
about actual BlastBridge dataset missingness.

## 10. Generation provenance

Every hierarchy record carries `GenerationProvenance`: simulation/scenario IDs and
versions, generator version, RNG algorithm, master seed, RNG stream, referenced
parameter IDs, prior/evidence/SME/assumption IDs, generation method, and uncertainty
types. Output validation checks that record run identity and parameter lineage
match the selected config/scenario. Registry validation checks source classes.
Future stored outputs should retain this struct instead of dropping provenance
during tabular export.

## 11. Output schemas and serialization

`OUTPUT_TABLES` declares V0.4 versioned, synthetic-only schemas for:

- `synthetic_members`
- `synthetic_career_episodes`
- `synthetic_assignments`
- `synthetic_training_periods`
- `synthetic_live_fire_sessions`
- `synthetic_firing_missions`
- `synthetic_firing_events`
- `synthetic_participant_exposures`

Each schema has a non-null primary key and logical column types, including nested
provenance structs and list values. `serialize_output` emits JSON-compatible rows
without requiring Pandas, Polars, Parquet, or DuckDB. `validate_output_schemas`
checks declared columns against typed record fields. Future adapters should keep
stable names, explicit nullability, foreign-key identity, and provenance. No
production output table or dataset is created here.

## 12. Non-medical feature contract

`FEATURE_CONTRACTS` reserves career/assignment durations, distinct physical event
counts, participant-event counts, trailing 7/30/365-day event counts, time since
last event, weapon-family counts, role-specific counts, and training density.
Window endpoint/reference-time rules must be selected before implementation.
These contracts explicitly prohibit medical/injury inference. No TBI labels,
injury probabilities, risk scores, or cumulative pressure dose are defined.

## 13. Scaling strategy

For 10 careers, validate the complete typed graph in memory and serialize rows.
At 10,000, generate bounded batches and write temporary partition files, with
stable member/entity ordinals independent of batch boundaries. Validate each
batch's foreign keys locally, then validate run-level uniqueness and counts before
publishing a manifest. At 100,000+, stream table rows by partition and avoid
materializing participant joins or all rows at once. A future Parquet adapter can
partition by simulation ID/table and optional non-sensitive synthetic keys; DuckDB
can query files directly. Do not add a database, distributed queue, or cluster
until memory/throughput measurements justify it. Chunk-seed behavior and atomic
publication remain unimplemented and need integration tests before scale claims.

## 14. Release-history validation

`scripts/verify_release_history.py` now extracts `data/reference` from each
annotated tag's Git tree and runs that release's validators against the extracted
snapshot. V0.1/V0.2 tracked-file preservation is checked between the V0.2 and V0.3
tagged trees, not against present-day documentation. Optional source-archive
checks compare archived source bytes to the tagged source records. A test verifies
that the post-release README differs from the V0.2 copy while the V0.2 tagged
release still validates. Historical tags and their contents were not modified.

## 15. Validation invariants and current limitations

Typed and cross-record checks cover ordered member/career/assignment/training
dates; event/session/mission hierarchy; valid participant references and member
ownership; unique physical event IDs; synthetic-only ID namespace; nonnegative
round indexes; scenario/parameter/evidence class links; per-record provenance;
unknown versus zero; dependency coverage; component/branch compatibility; and
output schema agreement. The test suite uses fictional-only `TEST_*` occupations,
weapons, assumptions, rates, and IDs. Those fixtures live only under `tests/`.

V0.4 has no actual sampler loop, career assembler, production data writer, chunk
orchestration, DB/Parquet dependency, CLI for generation, or real scenario. Typed
schemas cannot establish scientific validity, protect an unreviewed future source,
or prove scale/performance. `python -m blastbridge.validation.simulation` checks
architecture schemas and asserts production generation remains disabled.

## 16. Exact gate before actual synthetic military generation

Before a future release can generate actual synthetic military careers, an approved
scenario must provide numerical values and provenance for every parameter; each
must be classified as empirical prior, evidence constraint, SME estimate, or
scenario assumption. The package must validate those IDs/classes against versioned
registries, record population scope and simulation purpose, define a sensitivity
analysis plan, and record an approved scenario version. The review must resolve
component-specific input support, dependencies, missingness, uncertainty
propagation, temporal/participation definitions, and cross-runtime RNG behavior.
V0.4 has no production generator, and `require_future_generation_approval` fails
closed even if approval metadata is supplied; implementing generation requires a
separate approved release and explicit authorization.
