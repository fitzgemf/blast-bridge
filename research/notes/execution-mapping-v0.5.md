# Execution mapping contract V0.5

Status: approved V5-1b execution contract. This defines declarations and refusal
checks only. It samples no values and generates no career data. The assembler is
pending V5-2; serialization, chunking, CLI, and golden vectors are separate tasks.
See [executable semantics](synthetic-generation-semantics-v0.5.md),
[models](../../src/blastbridge/simulation/models.py), and
[validator](../../src/blastbridge/simulation/execution.py).

All models inherit the immutable `ResearchModel` contract and reject undeclared
fields. Scenario-created Identifier values use lowercase `test-`. `TEST_` text
categories cannot populate Identifier fields. Enum values, record/field references,
quantity names, and structural operation names retain their contract spellings.
Catalog identifiers never supply execution values, eligibility, or codebooks.

## Input contract

`ExecutionMapping` contains `mapping_id`, `mapping_version`,
`execution_generator_version`, `scenario_id`, `scenario_version`, `field_bindings`,
`codebooks`, `eligibility`, `role_presence_rules`, `placement_rules`,
`missingness_targets`, `record_lineage`, and `evaluation_order`.

- `FieldBinding`: `parameter_id`, `record_type`, `field_name`, `value_type`, `unit`,
  `rounding`, `count_meaning`, `counting_interval`. Record types are exactly the
  eight hierarchy model names. Value types are `int`, `float`, `date`,
  `duration_hours`, `degrees`, `meters`, `categorical`, `identifier`. Numeric
  operations require units. Rounding is `floor`, `ceil`, or `reject`; there is no
  `nearest`. Count meaning is the closed set `sessions`, `missions`,
  `physical_discharges`; counts also require an explicit counting interval.
- `Codebook`: `field_ref` and exactly one of `permitted_values` or `numeric_codes`.
  The former is a tuple of direct categorical Identifier values; the latter is a
  tuple of `(integer code, Identifier value)` pairs. Values must be valid `test-`
  identifiers. Numeric selections permit only fixed or discrete-uniform support
  wholly covered by the code table. Continuous/unbounded codes are refused.
- `EligibilityRelation`: `occupation_id`, `eligible_weapon_ids`,
  `eligible_platform_ids`. Every value must occur in a fictional codebook.
- `RolePresenceRule`: `quantity` (one of `role_participation`,
  `nearby_participation`, `instructor_repeated_presence`), `parameter_id`, `role_id`,
  `participation_type`, `presence_parameter_id`, `presence_semantics`,
  `presence_description`, `repetition_scope`, `instructor_status`, `student_status`.
  Presence semantics are explicit `boolean_code` (0 absent, 1 present) or
  `probability` (an explicit binding with support in [0,1]); repetition scope is
  `per_event` or `per_session`. Missing/ambiguous statuses are refused. A false
  presence decision produces no association; true produces one association for
  the declared occurrence. No proximity or crew-size defaults exist.
- `PlacementRule`: `record_type`, `timezone`, `shape`, `shape_parameter_id`,
  `start_parameter_id`, `end_parameter_id`, `offset_parameter_id`,
  `duration_parameter_id`, `partition_parameter_id`, `count_parameter_id`,
  `mission_applicability_parameter_id`, `unit`, `rounding`, `count_meaning`,
  `counting_interval`, `containment`, `clip`, `resample`. Every time-bearing record
  needs one complete rule. Member service uses start/end binding references;
  career, assignment, and training require offset/duration/partition references;
  sessions require offset/duration/count; missions additionally require count and
  applicability references; events require offset/applicability references.
  Session and mission counts must declare their matching count meaning and interval;
  partitions also require explicit rounding, and applicability uses boolean codes.
  Date placements use day offsets from the configured simulation/parent span;
  timestamps use hour offsets within parent UTC spans. `timezone` is `UTC`,
  containment is inclusive, and clipping/resampling are prohibited. `binding_offsets`
  supplies explicit offsets; `uniform`, `evenly_spaced`, and `midnight` require an
  explicit scenario shape selector. No shape or time value is inferred from prose.
  Out-of-bounds draws will abort the future assembler before publication.
- `MissingnessTarget`: `target_quantity`, `field_ref`, `latent_never_none`,
  `mcar_probability_parameter_id`. The closed field allowlist is
  `AssignmentEpisode.platform_id`, `AssignmentEpisode.crew_role`,
  `FiringEvent.ammunition_configuration_id`. Structural missingness alone permits
  nullable latent values. MCAR/not-collected require a never-None latent guarantee.
  MCAR requires an execution binding with fixed probability in [0,1] and the
  rule's scenario assumption. MCAR consumes exactly one missingness-stream draw
  per eligible occurrence, including p=0 and p=1, when implemented in V5-2.
  Structural and not-collected masks are deterministic. `None` means not-applicable
  for structural columns and unknown for not-collected/MCAR columns, with the
  single meaning retained by the corresponding configuration rule.
- `RecordLineage`: `record_type`, `parameter_ids`, `rng_stream`. It cites every
  sampled/derived/carried/placed/selected/masked input and applicable ancestor
  input. Required uncertainty, dependency, and missingness assumptions/types must
  already occur in the contributing binding tuples. Provenance must equal their
  union, with stable parameter ordering and first-occurrence deduplication; no
  posterior, confidence, or numerical uncertainty propagation is performed.

`evaluation_order` is structural: sampling, parents before children, then
placement and masking. Scenario-made operation names require `test-` identifiers;
contract record/quantity/operation names are exempt. Operation order does not
replace per-operation RNG keys or make input iteration order a seed component.

## Numbered refusal rules

The validator raises the first violation before any RNG or hierarchy row. Rules
are identified in deterministic error messages and have individual negative tests.

| Rule | Refusal |
| --- | --- |
| 1a | Required configured quantity has no execution consumption mapping |
| 1b | Multiple bindings write the same record field |
| 1c | Field, placement, role, MCAR, or lineage parameter is outside configured/scenario intersection |
| 1d | Field absent from its hierarchy model |
| 1e | Write to engine-owned synthetic identity, FK, or provenance |
| 2a | Value type/unit incompatible with the actual model field |
| 2b | Distribution cannot produce that value type |
| 3a | Integer/count conversion lacks explicit rounding |
| 3b | Numeric binding lacks units |
| 3c | Count binding lacks count meaning or counting interval |
| 3d | Cross-quantity frequency/tempo conversion, including tempo to physical discharges |
| 4a | Identifier/categorical field lacks a codebook |
| 4b | Codebook value is not a valid `test-` Identifier |
| 4c | Numeric support lies outside the table, or categorical support outside permitted values |
| 4d | `TEST_` category used for an Identifier field |
| 4e | Mapping/codebook/eligibility/placement identifier collides with reference catalog |
| 4f | Both or neither codebook representations supplied |
| 5a | Required participation quantity lacks a unique role/presence rule |
| 5b | Identifier used as a ParticipationType/bool decision, or invalid boolean-code support |
| 5c | Presence semantics absent/undocumented or probability interpretation invalid |
| 5d | Instructor/student status absent, conflicting, or inconsistent with participation type |
| 6a | Missing/incomplete placement for a time-bearing record |
| 6b | Non-UTC, unordered span, non-inclusive containment, clipping, or resampling |
| 6c | Built-in placement shape lacks an explicit scenario selector |
| 7a | Missingness target outside nullable-scalar allowlist |
| 7b | Required/collection/PK/FK/time/role/provenance target or record deletion |
| 7c | Non-structural mask on nullable latent values |
| 7d | MCAR probability not fixed, not in [0,1], not an execution assumption binding, or wrong assumption |
| 7e | MCAR probability mapping and rule do not correspond |
| 7f | Duplicate/overlapping targets or rules |
| 7g | Conditioning quantities on a supported mask |
| 7h | No supported allowlist rule, or rules and target mappings do not cover each other |
| 8a | Missing record lineage, governing input, registered assumption/type, or correct stream |
| 9a | Mapping scenario ID/version differs from supplied scenario |
| 9b | Wrong execution generator version, empirical/evidence/SME lineage, empirical distribution, or nonfictional content |

The fictional gate executes first and may refuse with the existing V5-1 content
message before a numbered semantic check. The validator never parses assumption,
dependency, presence, or missingness prose to invent a value or placement operation.

## Config slot, fingerprint, and integration

`SimulationConfig.execution_bindings: tuple[ParameterBinding, ...] = ()` is optional
for existing inputs. `configured_parameter_bindings(config)` includes it, so
reference validation and `SyntheticOutput` enforce exact config/scenario matches,
declared assumptions, and the unchanged binding-lineage union for execution inputs.
Adding even this empty field changes `rng._fingerprint`: it now appears in config
`model_dump`. This is accepted because no golden vectors are pinned before V5-6.

`ExecutionMapping.canonical_json()` serializes the WHOLE mapping with sorted keys,
fixed `(',', ':')` separators, deterministic Python float representation, and no
NaN/infinity. `fingerprint()` is SHA-256 of its UTF-8 bytes. Mapping version and every
nested value participate. V5-2/V5-6 must incorporate this fingerprint into RNG seed
derivation before generating any data; the current RNG API is unchanged here.

`execution_generator_version` matches `EXECUTION_GENERATOR_VERSION`, currently
`0.4.0`. Config/provenance and output-schema literals stay `0.4.0` until V5-6.
Mapping version is independently versioned and is included in its fingerprint.

`authorize_fictional_execution(config, scenario, approval, mapping)` requires the
mapping, gates config/scenario/mapping content, applies the existing fictional
approval/reference checks, then validates execution semantics. The original
`authorize_fictional_generation` and real future-generation gate are unchanged.
`generate` requires and authorizes a mapping, preserves dependency/MCAR refusal,
and otherwise raises `assembler pending V5-2`. No career data is generated here.

## Field-source coverage hardening (V5-1b correction 2)

Rule **1f** requires exactly one latent-value source for every non-engine-owned
field in every hierarchy model. The source taxonomy is a `FieldBinding`, a
placement-owned time field, the role/presence writer of association role/type, or
an explicit `FieldDerivation`. All writers participate in the **1b** conflict
check. Missingness is a subsequent mask, and cannot substitute for a latent source.

Time fields (`service_start`, `service_end`, `start_date`, `end_date`, `start_time`,
`end_time`, `timestamp`) are placement-only: bindings and derivations writing them
are refused by **1e**. `FiringEvent.round_or_launch_index` is engine-owned. EVENT
placement requires a count, `physical_discharges` meaning, interval, and rounding.
Frequency bindings may drive only SESSION/session counts; rounds bindings may
drive only EVENT/physical-discharge counts. All other uses, including MISSION
counts, are refused by **3d**. Source parameter spelling never supplies semantics.

`ExecutionMapping.derivations` defaults to an empty tuple. Each `FieldDerivation`
contains `record_type`, `field_name`, `operation`, `parameter_ids`, optional
`selector_parameter_id`, `source_field_ref`, `codebook_field_ref`, and explicit
`component_codes`/`status_codes` tables. The closed operation set is:

- `component_selection`: configured component weights and transition selector,
  with explicit integer-to-Component codes covered by fixed/discrete support.
- `branch_from_component`: explicit CareerEpisode.component-to-branch operation
  using the existing branch/component enum relationship.
- `eligibility_weapons`: explicit copying of the eligible weapon tuple for the
  assignment occupation; eligibility values must be declared in codebooks.
- `identifier_codebook`: an explicit selector and matching field codebook,
  with the existing categorical/numeric support checks.
- `carry_forward`: an explicit source field of a parent or the same record.
- `assignment_status`: an explicit per-assignment selector and
  `(code, instructor_bool, student_bool)` table. This single atomic source writes
  both assignment status fields; conflicting True/True entries are refused.

Every derivation reference passes the configured/scenario intersection, fictional
identifier/catalog gate, lineage checks, and whole-mapping fingerprint. Derivation
fields must exist, cannot be engine/placement-owned, and cannot supply implicit
values. The positive fixture declares branch/component, every assignment field,
and event weapon/family/context/ammunition sources explicitly.

Role rules are checked individually: INSTRUCTOR requires True/False, STUDENT
False/True, no rule permits True/True or missing status. The three rules need not
share one status pair, and do not write assignment status fields. Assignment flags
come from the independent, explicit assignment-status source.

Previously unnumbered refusals now have exact numbered messages: **4g** for
eligibility identifiers absent from codebooks; **7i** for missing/duplicate
structural evaluation operations; **7j** for invalid parent/sample/place/mask order.
These additions do not implement an assembler or generate career data.


### Eligibility selectors, scalar carry-forward, and assignment status

`AssignmentEpisode.platform_id` is derivation-only: `eligibility_platform`
selects through its explicit selector binding and target codebook from the
occupation's `eligible_platform_ids`, using `AssignmentEpisode.occupation_id`.
`FiringEvent.weapon_system_id` is derivation-only: `assignment_weapon` selects
through its explicit selector binding and target codebook from the owning
assignment's `weapon_system_ids`. The assignment weapon set itself comes from
`eligibility_weapons`. Plain field bindings and alternative derivation operations
cannot write these fields (1e). Every occupation codebook value requires exactly
one eligibility relation (4h); selector support must be a subset of each applicable
occupation's eligible set (4i), so execution cannot guess eligibility.

`carry_forward` requires the same source and destination field name and scalar
string-compatible types; tuple/list sources or destinations are refused (2a).
Each role/presence status pair must occur in the assignment-status `status_codes`
(5e). Presence applies only when the owning assignment's derived status matches
the rule's pair. A mismatch yields no participant row, never a guessed status or
presence. These declarations define semantics only; assembly remains pending V5-2.
