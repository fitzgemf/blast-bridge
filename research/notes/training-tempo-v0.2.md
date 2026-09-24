# Research Dataset V0.2: training tempo evidence

## Scope and counting definitions

These are BlastBridge research definitions, not asserted universal military
definitions. They were established before curating frequency values. Source terms
are retained separately, with a cited mapping and explicit ambiguity. No unit
conversion, annualization, individual exposure attribution, or prior distribution
is implied by these definitions.

| Counting unit | Research definition | Boundary |
| --- | --- | --- |
| firing_event | One discrete weapon discharge, rocket launch, mortar/artillery/tank round, shoulder-fired launch, or explosive detonation. | A salvo, mission or exercise may contain many; a reported round allocation is not proof of firing. |
| exposure_event | One person's potential presence in one blast-generating event, regardless of who operated the weapon. | Requires person/participation evidence; does not assert measured blast, dose or injury. |
| firing_mission | A tactically grouped sequence of one or more firing events. | Source mission counts do not determine round counts. |
| live_fire_session | A continuous or logically grouped training period involving live fire. | Session boundaries must be source-defined; not automatically a day or exercise. |
| training_event | A larger training activity that may contain one or more live-fire sessions. | May also contain dry fire, simulation and nonfiring activity. |
| qualification_cycle | A formal qualification or certification requirement spanning one or more tables, sessions or events. | Validity interval and completion requirement do not establish actual live-fire frequency. |
| duty_day | A calendar/training day during which exposure-producing activity occurs. | Exercise duration alone does not count exposure-producing days. |
| annual_training_period | A Reserve Component or National Guard training period that may contain multiple training events. | The name does not establish its length, firing days, or each person's attendance. |

Additional quantities such as rounds, crews and launchers are count denominators,
not interchangeable event units. The schema preserves a unit total independently
of any reported crew/launcher count; it does not divide them. Approximate bounds
and recollected central values are raw estimate attributes, never distribution
parameters. Unknown is null; zero requires explicit supporting evidence.

## Frozen baseline

V0.1 was verified with 205 passing tests and frozen on 2026-09-17 at commit
`0c3ede2dadff3b21dda2c901407a214658f63b9b`, annotated local tag `v0.1.0`.
All 42 intended files were committed, with source downloads, environments and
caches excluded. Git status was clean and `git fsck --full` passed. No remote
was created and nothing was pushed. V0.1 release files will remain byte-identical;
V0.2 is an additive, separately manifested research extension.

## Resumed completion review (2026-09-24)

The filesystem and Git state, rather than prior conversation, were used to resume
this work. `main` was and remains at the baseline commit above. The annotated
`v0.1.0` tag resolves to that exact commit. The V0.1 note describes its earlier
pre-commit state; it is retained as a historical artifact, not a current Git status.
All seven V0.1 JSON release files were compared byte-for-byte with their Git blobs.
The tag/history and those release files were not changed.

The interrupted work already contained 40 evidence records, 31 source records,
eight counting definitions, a complete exported schema/manifest, typed loaders,
validation commands and 118 additional tests. The initial resumed test run passed
all 323 tests. Mypy and pip check passed; Ruff found exactly 10 E501 errors and
three files requiring formatting. This note previously ended at the baseline
section. Remaining work was formatting, integrity review and release guidance.

Ruff formatting was applied only to the tempo loader, tempo CLI and tempo tests.
One long CLI summary string was split with implicit string concatenation, retaining
the same value. The root README, reference update guidance and source guidance
were updated. No curated research, schema or manifest bytes were regenerated or
edited, and no new source search was needed. The Python package remains 0.1.0;
the separately versioned research extension is 0.2.0. No commit, new tag or push
was performed, and no V0.3 work began.

## Evidence inventory

Counts below are records or record links, not participants, independent samples,
units observed over a year, or exposure totals. Occupation and platform links can
overlap and include explicitly marked curator relevance/family mappings.

| Dimension | Breakdown |
| --- | --- |
| Branch | Army 30; Marine Corps 10 |
| Component | Active 17; Army National Guard 14; Army Reserve 1; Marine Corps Reserve 3; unknown 5 |
| Occupation | Army 11C 8; 12B 2; 13B 8; 13M 10; 19K 4; 89D 1; USMC 0341 3; 0811 5; unassigned 2 |
| Weapon/platform | M142 HIMARS 10; M270 MLRS 4; M109 Paladin 5; M119 6; M777 9; M120 3; M121 1; M224 3; M252 2; M1 Abrams 120mm family 2; unassigned 10 |
| Evidence type | Official unit training report 27; qualification requirement 6; doctrinal requirement 2; school requirement 2; training calendar/schedule 1; SME 2 |
| Claim kind | Observation 27; requirement 10; estimate 2; schedule 1; assumption 0 |
| Representativeness | Single-unit example 24; school environment 6; service-wide requirement 6; component-wide requirement 2; unknown 2 |
| Source type | Official 29; SME 1; research definition 1 |

No peer-reviewed observations, range/ammunition records, official after-action
summaries or government-report evidence records are present. All 27 observed
frequency fields remain null. All 40 individual-exposure inferences remain
`not_established`, and numeric confidence is unassigned throughout.

## Strongest retained findings

These findings summarize the existing curated records, with their historical
scope and indexed-text limitations. They are not a fresh verification of current
military policy. Each named evidence ID resolves in
`data/reference/training_tempo_evidence.json`; its citation locators and source
URL are retained in the adjacent source registry.

### HIMARS and MLRS

`tempo-fa-requirement-active` and `tempo-fa-requirement-army_national_guard`
preserve the reviewed TC 3-09.8 (2020, Change 1) Table VI qualification intervals:
six months for Regular Army and twelve months for Guard, with higher-echelon
resets and command exceptions. This is a qualification requirement, not observed
annual live-fire attendance or a population frequency distribution.

The strongest quantitative exercise example is Western Strike 2018: Tennessee
1-181 FA reported more than 65 HIMARS practice rockets; Arkansas 1-142 FA reported
40 MLRS practice rockets (`tempo-western-strike-himars`, `-mlrs`). These are unit
exercise totals. The Estonia January 2025 record retains three rockets from a
depicted sequence, not a complete exercise total. Wisconsin's 2021 annual-training
report supports HIMARS certification activity without a numeric annual rate.

The existing former-13M recollection is preserved separately as SME evidence:
approximately 4-5 active-duty live-fire periods per year, and approximately 3-12
rockets per launcher crew per training event, with six recalled as a central
value. Period/event boundaries, years, unit, attendance and independent records
are missing. The Guard statement is an indirect, less certain belief about fewer
live fires, perhaps around annual training; it has no numeric frequency or rocket
estimate. The two records share one source and are not independent observations.
Neither recollection defines a prior or authorizes multiplying these quantities.

### Cannon artillery

Western Strike supplies more than 1,100 Paladin rounds for Arkansas 2-142 FA and
approximately 1,300 M777 rounds for Alabama 1-117 FA. These two records and the
HIMARS/MLRS records share one report and exercise. They cannot be treated as four
independent samples of annual tempo. The source's "nearly" qualification remains
visible alongside the approximate M777 count.

`tempo-active-m119-diamond` retains more than 1,600 rounds during Diamond Freeze
2011 and eight reported gun crews. The source does not establish equal allocation
or common participation, so rounds are not divided by eight. The field-artillery
qualification requirement above also covers the mapped cannon families. Guard
instructor/new-equipment and Army school examples add context, but course length
and an 18-day training period do not establish firing-day counts or teaching load.

### Mortars

The reviewed 2019 IWTS rule preserves twelve-month mortar crew qualification
validity, not twelve-month observed frequency. The active M120 example separates
one live-fire day from a three-day drills/firing/cleaning progression. Its
platoon leader's quarterly shooting goal is a separate schedule record with
`completion_verified=false`, not an achieved four-session annual count.

Guard examples support M120/M224 activity during 2015 annual training and M252
live fire at Immediate Response 25. The active M121 MORTEP source has conflicting
ammunition wording; its numeric round count is deliberately withheld. None of
these reports establishes an individual or population annual firing frequency.

### Abrams

`tempo-active-abrams-table6` supports M1A2 SEPv3 Table 6 main-gun and coaxial firing
in September 2024, with no numeric 120mm count. Mixed weapons cannot become a
main-gun round total. `tempo-guard-abrams-gunnery` supports Oregon Guard M1A2 SEP v2
gunnery in April 2018: a fourteen-day company gunnery period and 54 reported total
training days (60 planned for the next year) do not establish firing days.
The twelve-month IWTS vehicle-crew qualification-validity records are generic,
with 19K relevance, and do not assert an Abrams-specific firing interval.

### Marine Corps

The active HIMARS Southern Reach 2019 record reports two GMLRS rockets plus an
unquantified practice-rocket quantity, with three launchers participating. Two is
only a subset, not all rockets, and cannot be allocated across launchers or crews.
Reserve HIMARS live fire in 2022 and active/reserve M777 and mortar examples
establish opportunities without annual rates. The 2/24 reserve mortar example
occurred before upcoming annual training, so reserve activity is not assumed to
occur exclusively during annual training. Its 81mm caliber alone does not justify
a specific M252 link.

The reviewed 0811 prepared-round task has three-month sustainment with inert/dummy
completion permitted; it does not require quarterly live firing. The 0341 observer
task has six-month sustainment with live-fire necessity unresolved. Cannoneer
course duration (five weeks/25 training days) and HIMARS course duration
(2.5 weeks/13 training days) do not establish firing days. The V0.1 vocabulary
lacks 0814; operational HIMARS examples do not invent that occupation or assume
0811 for every operator.

## Conflicts and conservative decisions

| Source/issue | Retained interpretation |
| --- | --- |
| Estonia HIMARS body says annual qualification; captions say semiannual validation/certification | Preserve both terms; do not infer an observed annual frequency or override doctrine from news wording. |
| M121 report calls ammunition rockets; captions identify 120mm rounds | Retain the discrepancy; withhold the numeric ammunition count. |
| Marine HIMARS body typo M241 | Preserve source wording; HIMARS supports an explicit curator mapping to M142, not a new canonical alias. |
| Marine HIMARS publication header August 17, 2019 versus index August 22 | Registry retains header date and unresolved discrepancy; event dates remain August 13-15. |
| Rolling Thunder video page October 16 versus caption October 19, 2021 | Retain October-level scope; leave exact event day unresolved. |
| Marine infantry simulation table precedes the selected 0341 task | Do not attribute the preceding task's simulation permission to this task. |
| Generic caliber/platform terms, including Soltam K6 and reserve 81mm mortars | Do not silently equate them to a V0.1 model ID. |
| Qualification validity, sustainment, course length and exercise duration | Retain their own meanings; do not convert them into observed live-fire frequency. |

Active/Guard views of the same qualification rule, multiple platform totals from
Western Strike and multiple claims from one article are intentional dependent
records, not accidental duplicates. Occupation relevance is not proof that every
linked MOS operated every listed weapon. The V0.1 source conflicts remain
documented in `reference-v0.1.md` and were not silently revised.

## Source originals, completeness and evidence gaps

All 29 official V0.2 source records use `indexed_official_text` and have explicit
retrieval limitations, null original-byte hashes and no claimed local filename.
The ignored `tempo-downloads/` files are failed-retrieval metadata, not originals.
The source registry identifies every missing original by ID, title and URL;
there is no downloaded official V0.2 exception. The SME and definition records
are local provenance rather than missing publications. Ten official publication
dates are unknown and explicitly null, not interrupted or guessed metadata.
Current applicability of the historical manuals remains unverified.

All six claimed V0.1 original downloads still match their recorded SHA-256 hashes;
five V0.1 originals remain unavailable. Those baseline and extension registry
counts must not be added and described as distinct documents without deduplication.
The extension's entire official evidence set has limited source-byte
reproducibility. Structural validation does not prove the truth or completeness
of indexed passages or replace a future original-document review.

There is no representative longitudinal unit/crew/person sampling frame, complete
annual event inventory, attendance-by-round log, or supported allocation of unit
ammunition across crews and people. Army Reserve has only one engineering example;
Marine Reserve and school/instructor coverage are sparse. Safety staff, nearby
crews and observers lack usable attendance/distance records. Exact ammunition,
variant/configuration, firing-day boundaries, deployment effects, unit/year
heterogeneity and instructor teaching loads remain unresolved. News selection
bias and shared-source dependence prevent treating record counts as sample sizes.

Facts still too uncertain to model include population annual live-fire rates,
Active-to-Guard conversion factors, per-person rounds/exposures, quantitative
between-unit variability, qualification compliance, a link from each qualification
cycle to a fixed number of live sessions, and blast pressure/impulse or injury
probabilities. Unknowns remain null; no assumptions were promoted to observations.

The evidence base is sufficient to inform the questions, counting vocabulary and
provenance constraints of a later V0.3 design discussion. It is **not sufficient
to estimate or validate empirical population priors**. A future approved design
would need source-original review, representative execution/denominator evidence
and explicit handling of elicited assumptions and source dependence. No prior
families or parameters, synthetic careers, ML, NLP, RAG, UI, TBI prediction or
medical-risk scores were designed or implemented in this completion task.

## Verification and commit readiness

Final checks are run from the repository root using the existing Python 3.12.10
virtual environment. Where the sandbox could not access the base interpreter,
the same commands used approved execution outside the sandbox; the environment
was not recreated and no files outside BlastBridge were edited.

| Check | Result |
| --- | --- |
| `python -m pytest` | 323 passed (205 baseline plus 118 V0.2 tests) |
| `python -m ruff check .` | All checks passed after formatting cleanup |
| `python -m ruff format --check .` | 31 files already formatted |
| `python -m mypy` | No issues in 16 source files |
| `python -m pip check` | No broken requirements |
| `python -m blastbridge.validation.reference` | V0.1 release and V0.2 extension validate |
| `python -m blastbridge.validation.training_tempo --source-directory research/sources/tempo-downloads` | 40 evidence, 31 sources; release hashes verified; 0 downloaded, 29 unavailable, 2 local provenance records |
| Schema checks | Both exported schemas match their models; release/schema hashes match |
| Additional local read-only audit | 52 release/retrieval JSON files parse with duplicate-key rejection; 24 implementation/test/scratch Python files parse; no partial release files |
| Duplicate/provenance/link checks | No duplicate IDs or identical evidence under different IDs, duplicate source URLs, orphan sources, dangling citations, invalid occupation/weapon links or SME/assumption promotions found |
| Baseline source originals and environment | Six source hashes verified; all 16 development lock pins match |
| Git checks | `git diff --check` and `git fsck --full` pass; annotated baseline tag resolves correctly; all seven baseline JSON files byte-identical to Git |

V0.2 manifest SHA-256:
`7f18f8fa64873e908499c7e21ed4f22d7293c03b1034f197d3709b32b6a17e6c`.
The existing manifest retains its original September 17 generation timestamp,
which is distinct from this September 24 verification date.

V0.2 is ready to commit as a scoped, structurally validated research release with
the source-original and representativeness limitations above. This is not a claim
of fully archived or population-representative evidence. The intended working
tree consists of four modified tracked files (root README, reference README,
source README and reference CLI) and ten new V0.2 files (five release JSON files,
this note, three Python modules and one test module). Nothing is staged or
committed by this task. Existing downloads, fetch/build scripts, the local audit
script, environments and caches remain ignored.
