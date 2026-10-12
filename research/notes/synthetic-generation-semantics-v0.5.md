# Synthetic generation executable semantics V0.5

Status: proposed implementation contract for review; documentation only. Applies
only to explicitly fictional scenarios. It does not enable generation, change
V0.4 schemas, approve military scenarios, or remove the existing generation gate.
Sources: [V0.4 architecture](synthetic-generator-architecture-v0.4.md),
[model contracts](../../src/blastbridge/simulation/models.py), and the existing
simulation RNG and output validators. Serialized enum values below are exact.

## 1. Validation and refusal boundary

After typed model validation, the FIRST preflight gate is the content-enforced
`validate_fictional_scenario`: all parameters must be `SCENARIO_ASSUMPTION`,
scenario-supplied identifiers must use `TEST_` IDs, prior/evidence/SME ID groups
must be empty, no `EmpiricalDistribution` is permitted, and no reference entities
may be supplied or resolved. Apply these checks across config, scenario, lineage,
and the execution mapping, including categorical identifiers and codebooks.
Schema-defined enum values, quantity names, and generated `SYN-*` IDs retain their
contract spellings; they are not scenario-supplied entity identifiers.

Only after that guard passes, perform `validate_configuration_references` using
fictional scenario registries and then execution-semantics preflight. All gates
precede child RNG creation, hierarchy rows, batch yields, and output writers.
ALL scenario/entity identifiers, eligibility relations, and codebooks come only
from the fictional execution mapping/scenario, NEVER from `data/reference`.
Inspect every
configured dependency, including component training dependencies, every missingness
rule, all bindings, and every required execution mapping. Refusal means a
`ValueError` identifying the construct ID/target, rejected value, and reason;
there are zero generated rows and no published output. Valid V0.4 metadata is not
necessarily executable V0.5 input. Unsupported declarations are not silently
ignored, even when their branch would receive no sampled members.

A versioned, reviewed execution mapping must associate quantity identifiers with
bindings, units, categorical codes, output fields, and placement operations. This
is an implementation prerequisite, not a field already present in these models.
No interpretation of `rule_description`, `rationale`, assumption prose, scenario
label, or parameter-ID spelling constitutes such a mapping. Missing or ambiguous
mappings fail preflight. A later invalid draw aborts the whole run before output
publication; no clipping, retry-until-valid, or partially successful return.

## 2. Dependency modes

- `independent_assumption` (`INDEPENDENT_ASSUMPTION`): supported. There is no
  serialized `independent` value. Require its non-null `scenario_assumption_id`
  to resolve in `ScenarioDefinition.assumptions`. Sample the output's explicitly
  mapped binding without modifying its distribution using the input quantities.
  Independence does not override structural joins, component-specific config
  selection, branch compatibility, or weapon eligibility checks. Preserve the
  independence assumption and uncertainty labels in affected record lineage.
- `conditional`: refused at execution preflight. `rule_description` has no
  machine-readable conditioning function, coefficients, or distribution lookup.
  Do not parse its prose or invent a multiplier.
- `joint`: refused at execution preflight. There is no joint sampler, dependence
  matrix, copula, or executable joint-support contract.
- `unknown`: refused at execution preflight. An unresolved dependency cannot be
  sampled as though independence had been established.

Dependency semantics are checked only after the content-enforced fictional guard
and fictional reference validation in section 1. All required dependency pairs
remain declared. Supporting independent assumptions
is a fictional sensitivity choice, not a claim that real quantities are independent.

## 3. Missingness mechanisms and targets

`MissingnessRule` contains `target_quantity`, `mechanism`, conditioning IDs,
assumption ID, and rationale; it contains no probability or output-field mapping.
Therefore MCAR support requires an explicit reviewed mapping to a probability
`ParameterBinding` and target. Merely declaring MCAR is insufficient. The mapping
must be reproducibly versioned in scenario/config inputs; the current schemas do
not by themselves provide this execution contract. Until that prerequisite is
implemented and reviewed, such an input is refused before any row. Do not add a
hidden default rate, interpret a prose percentage, or assume a target ID is a
binding ID. This note specifies the operation once that prerequisite is satisfied.

For V0.5, an MCAR probability binding must be `fixed`, with finite value p in
[0, 1], classified and linked to the rule's declared scenario assumption. Variable
probability distributions and conditioning are outside this first implementation.
For each eligible target occurrence, obtain one `random()` draw u from
`child_rng(config, scenario, MISSINGNESS, occurrence_key)` and mask iff u < p.
Use exactly one draw even at p = 0 or p = 1. The occurrence key includes the stable
entity path and target identifier. Apply after the latent quantity has been
sampled; missingness cannot change training, firing, or participation draws.
Duplicate rules for one target and overlapping masks are refused at preflight.

| Serialized mechanism | V0.5 operation |
| --- | --- |
| `mcar` | Supported subject to the explicit fixed-p mapping above; stochastic field mask on the `missingness` stream. No conditioning quantities; declared assumption required. |
| `mar` | Refused: conditioning IDs alone do not define the conditional missingness probability. |
| `mnar` | Refused: neither a latent-value selection function nor its assumptions are executable. |
| `structural_missing` | Supported for an explicitly mapped target: deterministically not applicable on every occurrence in the declared scope; no RNG draw. |
| `not_collected` | Supported for an explicitly mapped target: deterministically unknown on every occurrence in the declared scope; no RNG draw. |
| `unknown_reason` | Refused: no executable decision about whether or how to mask. |

For this release, deterministic rule scope is all occurrences of the mapped
target. Conditional structural scope is refused; prose is not a predicate.
`condition_quantity_ids` must be empty for supported deterministic mechanisms.

A mask never deletes a hierarchy record, physical event, participant association,
primary key, parent reference, required timestamp, required role, or provenance.
Targets are restricted to representable nullable scalar fields: assignment
`platform_id`/`crew_role` and event `ammunition_configuration_id`, or an explicitly
mapped `QuantityValue` where the chosen output actually supports that type.
`QuantityValue` is not currently a hierarchy table field; its existence does not
permit adding a column. Any other target fails preflight, including collection
fields and required booleans. Required-field or whole-record omission would break
counts and joins and is refused in V0.5.

`MissingnessConfiguration.rules` requires at least one rule. Since MAR, MNAR,
and unknown-reason rules are refused, every executable fictional config must
contain at least one supported rule mapped to a nullable scalar: `platform_id`,
`crew_role`, or `ammunition_configuration_id`. V5-2 fixtures and
`examples/fictional/` must be designed around this requirement; an empty rule list
or a `QuantityValue`-only plan cannot satisfy it in the current output schemas.

MCAR or not-collected masking of a nullable scalar is allowed ONLY when the
execution mapping declares and guarantees that its latent value is never `None`.
Otherwise refuse at preflight, regardless of the MCAR probability, including zero.
`structural_missing` is the ONLY mechanism allowed on targets whose latent value
can be `None`; its unconditional mask makes every resulting `None` mean
not-applicable. For MCAR/not-collected columns, every resulting `None` means
unknown and can arise only from masking. An unexpected latent `None` in a declared
non-null latent target aborts the run before publication. No mixed interpretation
of `None` is permitted within a masked column. A future implementation test must
show that every `None` in each masked column has exactly one meaning, and that
nullable latent targets are refused for MCAR/not-collected.

For MCAR and not-collected masks, `QuantityValue` becomes `state=unknown,
value=None`; structural masks become `state=not_applicable, value=None`. Nullable
scalar targets become `None` for all three mechanisms; their mechanism is retained
in the referenced configuration, because a nullable scalar cannot encode a reason
itself. Do not replace unknown with zero, false, an empty list, or a sentinel ID.
An unmasked observed numeric zero stays observed zero. For a nullable scalar,
the single meaning of `None` is fixed by its mapped mechanism and retained
configuration lineage; unknown and not-applicable must never collide. Physical absence of participation selected by the
participation binding is not a missingness mask.

## 4. Uncertainty and lineage preservation

Exact uncertainty values are `aleatory`, `epistemic`, and
`unknown_unclassified` (enum member `UNKNOWN`). All are supported as labels,
including unknown/unclassified; that label does not license an unresolved
dependency or missingness mechanism. Preserve identifiers and labels verbatim on
every record's `GenerationProvenance`. No aggregate confidence, variance
propagation, uncertainty weighting, posterior update, or numerical propagation
is computed. This is lineage preservation only.

Each record must cite all configured bindings used to sample, derive, carry
forward, place, select, or mask its contents, including relevant ancestor choices.
Its prior, evidence, SME, assumption, and uncertainty tuples are the exact union
of those bindings' corresponding tuples, deduplicated in first-occurrence order
under a stable parameter-ID ordering. Never reclassify sources or replace unknown
with aleatory. Run identity, seed, algorithm, stream and generation method remain
explicit. Preserve lineage even when the selected value is unknown or masked.

Cover all eight uncertainty dimensions: `career_duration`, `assignment_duration`,
`training_event_frequency`, `rounds_per_event`, `participation`, `role`,
`missing_years`, and `source_support`. For every affected record, the applicable
`UncertaintyLineage`, dependency assumption/types, and missingness assumption
must already be represented in its contributing configured bindings. Otherwise
refuse at preflight: existing output validation requires provenance to equal the
binding-lineage union, and rejects scenario-only parameter IDs or extra source IDs.
This compatibility requirement must be resolved by reviewed input mappings before
implementation; neither silently dropping register lineage nor inserting extra
provenance is acceptable. Original dimension associations remain in the retained
config; `GenerationProvenance` stores the union, not a per-dimension mapping.

## 5. Training, participation, and time windows

After the content-enforced fictional guard, all selections and placement are
driven solely by explicitly mapped fictional scenario bindings. Identifiers,
eligibility relations, and codebooks are supplied only by that fictional mapping
and scenario, never loaded from `data/reference`. `cycle_context` controls the mapped training context/cycle status;
select the component's own `training_event_frequency` and `rounds_per_event`
bindings. The execution mapping must specify frequency units, counting interval,
fractional-count policy, and whether a count means sessions, missions, or physical
discharges. Never convert tempo into rounds or infer deployment multipliers.

`role_participation`, `nearby_participation`, and
`instructor_repeated_presence` must have explicit mappings to role identifiers,
`ParticipationType`, presence decisions, and repetition scope. `DistributionSpec`
includes `CategoricalDistribution` with text categories: a categorical binding
whose categories are valid `TEST_` identifiers for its target identifier field
maps directly to that field, without a numeric codebook. Validate every category
at preflight and refuse categories that are not valid identifiers for the target
field or are absent from the fictional mapping's allowed identifiers. This direct
mapping does not turn `TEST_` identifiers into booleans or `ParticipationType`
enum values; those operations still need explicit field-appropriate semantics.
Only NUMERIC bindings used to select identifier/category fields need a codebook
translating numeric values into valid field values. Refuse a missing required
numeric codebook, invalid code, ambiguous
instructor/student status, or undocumented probability interpretation. Do not
assume everyone fires, invent crew size, or assign nearby people by proximity.
A false presence decision produces no participant row; a true decision produces
one association per selected member/assignment/event/type, with a stable role.
Multiple people reference the same physical event; they do not duplicate it.

The scenario execution mapping must specify service placement, career/assignment
partitioning, training-period placement, session/mission durations and offsets,
event offsets, and whether a mission is applicable. None is supplied by the
current duration bindings alone. Refuse incomplete placement specifications at
preflight; do not default to uniform dates, midnight, evenly spaced events,
whole-assignment training, or a mission per session. This explicitly chooses
scenario-driven windows over an engine-invented scheduling policy.

Use UTC-aware timestamps for V0.5 placement. Date bounds are inclusive, matching
existing graph validators: simulation contains service; service contains career;
career contains assignment; assignment contains training period. A session's UTC
start/end dates must lie within the training period; its complete timestamps lie
within that period's inclusive calendar days. Mission intervals are inclusive
subintervals of their session. An event timestamp lies within its session and,
when `mission_id` is supplied, within that mission in the same session. A
participant's assignment covers the event's UTC calendar date and belongs to that
member. Start <= end everywhere; equal endpoints are allowed. No clipping or
resampling of a placement that exceeds bounds. Validate the assembled graph before
publication. Adjacent windows may share a boundary, but each event has one explicit
session/mission ownership; boundary membership never creates a second event.
Trailing feature-window semantics remain outside this generation contract.

## 6. Determinism contract

Use existing `child_rng` with the exact config, scenario, named `RngStream`, and
stable entity key. Streams are `population`, `career`, `assignment`, `training`,
`firing`, `participation`, and `missingness` (singular `career`/`assignment`).
Assign population selection to population; career choices to career; assignment
choices to assignment; cycle/session placement to training; missions/discharges to
firing; presence/role decisions to participation; masks to missingness.

Define canonical entity paths from one-based global member ordinal and one-based
local career/assignment/training/session/mission/event/participant ordinals.
Append the operation and parameter ID (or target ID for masks) to each key, using
an unambiguous length-prefixed encoding. Each operation owns one child RNG; consume
its draws in the documented sampler order, never recreate it between draws of the
same operation. Distinct operations and occurrences use distinct keys. Do not
include chunk number, worker ID, wall clock, mutable counters, or process hash.

Allocate table-wide positive ID ordinals in lexicographic numeric entity-path
order before filtering masks or partitioning output, using deterministic prefix
counts where hierarchy sizes vary. Parallel chunks must derive the same global
ordinals, not restart numbering. Retain stable ordering in tables and lineage.
Canonical reassembly yields identical rows and IDs for chunk sizes 1, N, or an
unchunked run and for reversed worker completion order. Missingness never renumbers
latent identities. No process-global RNG or engine-invented global state.

Keep SHA-256 seed derivation over master seed, generator/scenario versions,
canonical complete config/scenario fingerprint, stream and entity key. Retain
`python-mt19937-random-v1`, version-2 seeding, and distribution transforms using
`random()` only. Identical inputs, code, mappings, algorithm, and supported Python
runtime must produce identical canonical output. Mapping changes must change
fingerprinted inputs/version; sampler or draw-order changes require a version
change and new golden vectors. Cross-runtime floating-point equality is not
promised. Current models pin generator/provenance version to `0.4.0`; a later
reviewed implementation task must resolve V0.5 versioning, not label new engine
behavior as the unchanged V0.4 generator.

## 7. Support and refusal summary

“Supported” below is an execution recommendation subject to complete reviewed
mappings, valid lineage, and the fictional-only gate; it is not existing code.

| Construct | V0.5 decision | Enforcement point |
| --- | --- | --- |
| Content-enforced fictional guard | Required: assumption-only parameters, `TEST_` scenario identifiers, empty prior/evidence/SME IDs, no empirical distributions/reference entities | FIRST preflight gate, before fictional reference validation and semantics preflight |
| Dependency `independent_assumption` | Supported with declared, preserved assumption | Fictional guard, model/reference validation, then execution preflight |
| Dependency `conditional` | Refused | Execution preflight, before any row/RNG/writer |
| Dependency `joint` | Refused | Execution preflight, before any row/RNG/writer |
| Dependency `unknown` | Refused | Execution preflight, before any row/RNG/writer |
| Missingness `mcar` | Supported only with explicit fixed-p/target mapping and never-None latent scalar; otherwise refused | Execution preflight; one missingness-stream draw per eligible occurrence |
| Missingness `mar` | Refused | Execution preflight |
| Missingness `mnar` | Refused | Execution preflight |
| Missingness `structural_missing` | Supported deterministic not-applicable mask | Target/scope preflight, then field masking |
| Missingness `not_collected` | Supported deterministic unknown mask only for never-None latent scalar | Target/scope preflight, then field masking |
| Missingness `unknown_reason` | Refused | Execution preflight |
| Nullable latent target with MCAR/not-collected | Refused; only structural missingness may target latent None | Execution preflight; unexpected latent None aborts before publication |
| Missingness rule coverage | At least one supported rule on `platform_id`, `crew_role`, or `ammunition_configuration_id` required | Model validation and execution preflight |
| Required-field/record deletion; ambiguous/duplicate targets | Refused | Execution preflight |
| All three uncertainty types | Supported verbatim lineage only | Binding/register compatibility preflight and per-record output validation |
| Unrepresented assumption/register lineage | Refused | Execution preflight |
| Complete scenario role/window mappings | Supported without defaults | Execution preflight; draw bounds and graph validation before publication |
| Missing codebooks, units, counts, or placements | Refused | Execution preflight |
| Invalid sampled count/code/window | Refused; whole run aborted | Draw/assembly validation before publication |
| Stable per-operation child RNG and global ordinals | Required | Generation planning and chunk-equivalence verification |
| Nonfictional scenarios or absent generation authorization | Refused | Fictional content guard FIRST in preflight; authorization gate before execution |

Review prerequisites: approve the input representation for fixed MCAR probability,
target mappings, categorical codebooks, scheduling and lineage compatibility;
these are absent from the current contracts. No free-text fallback is acceptable.
This note intentionally leaves incomplete scenarios non-executable rather than
making unsupported claims of immediately available generation.
