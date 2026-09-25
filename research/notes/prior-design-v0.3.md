# Modeling-assumption and probabilistic-prior design, V0.3

Version 0.3.0, September 24, 2026. Design and validation only. No empirical prior,
numerical scenario distribution, synthetic career, sampler, ML, medical-risk model
or TBI probability has been produced. The only numerical values retained are
unchanged, source-bound V0.2 claim payloads. They are not distribution parameters.

## Frozen dependencies and scope

V0.2 was rechecked against the actual working tree: 323 tests passed, Ruff and
mypy passed, both release CLIs and the source audit passed, and the seven V0.1
JSON files were byte-identical to `v0.1.0`. The 14 intended V0.2 files were staged;
downloads, environments, caches and local audit/build scripts remained ignored.
The authorized commit is:

`4182044e57177d77e643b6b273dbee03cc433eeb`

Commit title: `Research Dataset V0.2 training tempo evidence`.
Annotated tag: `v0.2.0`. Git was clean immediately after freezing; log, tags and
`git fsck --full` passed. No remote was configured, created or pushed to.
`v0.1.0` remains at `0c3ede2dadff3b21dda2c901407a214658f63b9b`.

V0.3 adds new artifacts only. It edits none of the 52 project files in V0.2 and
retains all 12 earlier release JSON files byte-for-byte. The older READMEs and
research notes describe their historical release state; this note and
`data/reference/prior_design_README.md` are the current V0.3 entry points. The
Python package version remains 0.1.0; the design/reference schema is 0.3.0.

## Why V0.2 cannot supply empirical population priors

V0.2 has 40 scoped records and 31 sources, not 40 independently sampled histories.
Its 27 observations have no populated annual observed-frequency field. The
remaining claims comprise ten requirements, one plan and two recollections from
one SME source. News reports select particular exercises; shared manuals,
exercises and respondents create dependence. No representative sampling frame,
complete annual inventory, person-time denominator, or round-by-round attendance
exists. All 29 official sources lack archived originals, with retrieval limitations
recorded. Ten official publication dates and current manual applicability remain
unresolved. Structural validation cannot fix these research limitations.

V0.3 therefore preserves `empirical_priors: null`. Requirements can constrain
interpretation of a source-scoped qualification rule. Unit totals describe named
events. Neither supplies the distribution of completed live-fire sessions across
Army or Marine personnel. A prior family supported by software does not imply
the evidence supports that family, its parameters, or the target population.

## Four non-interchangeable concepts

| Type | Definition | Present treatment |
| --- | --- | --- |
| empirical_prior | A distribution estimated from representative empirical data for a specified population and quantity | Unavailable; no qualifying empirical dataset or admission contract exists in this release |
| evidence_constraint | A source-supported bound, minimum, interval or structural rule with explicit applicability and scope | Ten requirements and 24 observed activity claims retained exactly; no conversion into future population bounds |
| sme_estimate | An explicitly attributed expert estimate with its respondent/time/quantity limits | Two records preserve the existing 13M recollection and weaker Guard belief |
| scenario_assumption | A modeling choice for a hypothetical scenario when empirical support is insufficient | Three named, unparameterized placeholders; no probability, numerical bounds or distribution selection |

An observed rocket count can constrain the description of that exercise. It does
not constrain a future annual minimum. A qualification requirement is conditional
on edition, population, applicability and exceptions; it does not establish
compliance, a firing-day count or a per-person exposure floor. Approximation,
strict inequalities, unknown quantities and subset scopes remain unchanged.

## Typed schema and numerical gate

`PriorDefinition` records stable ID/version/status; population, branch/component,
occupation/weapon references, unit/role/context, quantity, counting unit and time
window; prior type and distribution vocabulary; evidence/source IDs and an anchor;
support, representativeness and confidence class; uncertainty references; rationale
and limitations. `scope_binding` distinguishes a source-only claim from a
hypothetical scenario. `individual_exposure_inference` is always `not_established`.

The future distribution vocabulary is fixed, discrete_uniform, triangular, beta,
normal, lognormal, poisson, negative_binomial, categorical, empirical and none.
**V0.3 accepts only none.** `parameters`, `lower_bound` and `upper_bound` have
null-only types. There is no latent numerical configuration or activation flag.
Raw SME ranges remain inside the exact V0.2 estimate payload, not these fields.
This deliberately conservative schema must be revised under separate authorization
before introducing typed numerical parameter contracts or sampling behavior.

Source-bound definitions must match the anchor's population, time, component,
occupations, weapons, role, context, counting unit, representativeness and entire
claim payload. They must retain the anchor's limitations. The primary evidence
and all source IDs validate against the frozen V0.2 bundle; source IDs must equal
the cited evidence's provenance union. Valid source names alone do not authorize
new numbers or broader populations. R/D/E records cannot pool additional evidence.

Scenario placeholders carry contextual references and all eight uncertainty
dimensions, but no anchor claim or copied SME payload. They remain F/design_only,
with representativeness not_applicable. Population compatibility is checked for
their contextual citations; these references do not promote F to another level.
All confidence classes remain unassessed, with no numeric confidence field.

The 39 shipped definitions comprise 34 evidence constraints (ten R, 24 D), two
SME estimates (E) and three scenario placeholders (F). The V0.2 quarterly mortar
plan is deliberately not promoted to a prior input constraint. Three engineering/
EOD examples remain in V0.2 outside the requested five case studies.

## Evidence-support framework

| Level | Meaning and admission boundary | V0.3 assignments |
| --- | --- | --- |
| A | Representative empirical evidence for the actual estimand, with reviewed sampling, denominators, coverage and empirical qualification | None; blocked in this schema |
| B | Multiple independent official observations, with reviewed source/event/unit/respondent independence | None; distinct IDs or multiple URLs are insufficient; no independence registry is qualified |
| C | Official requirement plus compatible supporting observations; remains a requirement, not a fitted empirical distribution | None shipped; validator permits a requirement anchor plus compatible official observations and rejects SME, plans and unrelated requirements |
| D | Single official observation, restricted to its named unit/event/time | 24 source-bound observations |
| E | SME estimate, without promotion to official or representative empirical support | Two records sharing one source |
| F | Scenario assumption only; contextual references do not make its modeling choices observed | Three placeholders without numbers |
| R | Official requirement only; additional category to avoid falsely assigning C or D | Ten source-bound requirements |

These labels describe evidence support. They are not medical confidence,
probabilities, weights, a numeric quality scale, or proof of current applicability.
R was added because A-F alone has no honest category for an isolated requirement.
No A/B admission can be enabled by a self-declared flag; future support needs a
separately reviewed evidence contract and versioned schema change. C does not
license generalizing any supporting observation beyond its own scope.

## HIMARS and MLRS synthesis

The following separates requirement, activity, ammunition, recollection,
denominators and individual exposure. Evidence IDs refer to the unchanged V0.2
dataset and its source registry, which retain exact locators and historical scope.

| Population | A. Qualification | B. Observed activity | C. Rocket totals | D. SME | E. Missing denominators | F. Individual exposure |
| --- | --- | --- | --- | --- | --- | --- |
| Army 13M / M142 / Active | Reviewed 2020 TC 3-09.8 Table VI six-month interval, resets/exceptions retained | Estonia January 2025 validation example | Three rockets in a depicted sequence; not an exercise inventory | Approx. 4-5 periods/year; approx. 3-12 rockets per launcher crew/event, rough central recollection six | Years/unit, period/event equivalence, attendance, allocation and annual coverage absent | Not established |
| Army 13M / M142 / Guard | Same reviewed manual: twelve-month interval | Wisconsin annual training 2021; Western Strike 2018 | More than 65 practice rockets for Tennessee 1-181 FA at Western Strike | Weaker indirect belief: fewer live fires, perhaps around annual training; no numeric estimate | Crew/launcher/person allocation and comparable complete years absent | Not established |
| Army 13M / M270 / Active | Same reviewed six-month Table VI requirement scope | 2-4 FA exercise, June 2013 | No supported total; capacity is not firing | No M270-specific SME estimate | Annual inventory, crews and attendance absent | Not established |
| Army 13M / M270 / Guard | Same reviewed twelve-month requirement scope | Arkansas 1-142 FA, Western Strike 2018 | 40 practice rockets, unit exercise total | No M270-specific SME estimate | Unit total cannot be allocated to people/crews | Not established |
| Marine / HIMARS / Active | Course curriculum evidence is separate; no annual operational requirement established here | Southern Reach, August 2019 | Two GMLRS as a subset plus unquantified practice rockets; three launchers reported | None; Army recollection does not transfer | Launchers do not establish allocations; MOS and annual coverage unknown | Not established |
| Marine / HIMARS / Reserve | No component-specific annual live-fire requirement established here | Kilo Battery 2/14, WTI 2-22, April 2022 | No supported rocket total | None | MOS, crew allocation, firing days and annual coverage unknown | Not established |

Requirement IDs: `tempo-fa-requirement-active` and
`tempo-fa-requirement-army_national_guard`. Activity IDs:
`tempo-estonia-himars`, `tempo-guard-himars-at`, `tempo-western-strike-himars`,
`tempo-active-mlrs-exercise`, `tempo-western-strike-mlrs`,
`tempo-marine-active-himars`, `tempo-marine-reserve-himars`.
SME IDs: `tempo-sme-active-himars` and `tempo-sme-guard-himars`.

The active SME range and central recollection remain **sme_estimate only**.
Six is not a triangular mode, expected value or point estimate of Army-wide tempo.
Multiplying periods/year by rockets/event would assume unverified equivalence
of periods and events and still not establish individual participation. The
Guard belief is weaker and indirect; no numeric Active-to-Guard conversion is
chosen. M270 and Marine quantities are not filled from the Army HIMARS account.

Estonia's body says annual qualification while captions say semiannual validation;
retain the discrepancy and leave observed frequency null. The Marine source's
M241 typo is not a canonical alias; M142 remains an explicit HIMARS family mapping.
The August 17/22 publication-date disagreement is retained separately from event
dates. V0.1 lacks Marine 0814; operational HIMARS occupation IDs remain unassigned.

## Cannon artillery synthesis

All three Army 13B platform families appear in the historical field-artillery
qualification requirement above. The common six-month Active/twelve-month Guard
interval remains policy scope with exceptions, not annual completed live fires.

| Population | Observed activity and round totals | Denominator/participation boundary | Scenario implication |
| --- | --- | --- | --- |
| 13B / M109 family | Arkansas 2-142 FA, Western Strike 2018: more than 1,100 Paladin rounds; Guard instructor live fire also reported in 2024 | Exercise unit total; no supported allocation across crews or people | No per-crew rate or annual distribution |
| 13B / M777 family | Alabama 1-117 FA, Western Strike 2018: approximately 1,300 rounds, retaining source wording "nearly"; instructor and new-equipment contexts also present | Unit total, not crew/person count; course/activity duration is not firing days | No per-crew rate or annual distribution |
| 13B / M119 family | Diamond Freeze 2011: more than 1,600 rounds, eight crews reported trained/certified; instructor/new-equipment examples add context | Bravo Battery plus two Alpha guns; eight crews do not establish common attendance or equal allocation | Do not divide total by eight or convert result into a firing rate |

IDs: `tempo-western-strike-paladin`, `tempo-western-strike-m777`,
`tempo-active-m119-diamond`, `tempo-guard-artillery-instructors`,
`tempo-army-artillery-students`, `tempo-guard-cannon-net`.
Western Strike artillery and rocket rows share one report/exercise, so their
record count does not establish B support. Student specialties/platform lists do
not imply that every MOS operated every platform. Instructors are a distinct
population; annual teaching load is missing. No cannon-specific SME estimate,
individual exposure count or transferable numerical scenario range is available.

## Mortar synthesis

The reviewed 2019 IWTS twelve-month **crew qualification validity** rule is generic,
with 11C relevance and no weapon-specific IDs. It is preserved separately for
Active and Guard scope, not turned into annual firing frequency for each model.

| Population | Validity / requirement boundary | Observed activity / actual firing | Plans, ambiguities and unknowns |
| --- | --- | --- | --- |
| 11C / M224 | Generic crew validity; no M224-specific frequency established | Guard 2015 annual-training example; active U.S. mentors in January 2014 live-fire teaching context | Instructor course length and foreign student counts cannot supply U.S. annual exposure denominators |
| 11C / M252 | Generic crew validity; no M252-specific frequency established | Vermont Guard Immediate Response 25 live fire | Three-day dry/blank/live progression is not three live-fire sessions; Soltam K6 is not silently mapped to M120 |
| 11C / M120 | Generic crew validity; no completed annual rate | Active July 2013 drills/live-fire/cleaning progression includes one live-fire day; Guard 2015 AT example | Separate quarterly shooting goal is a plan with completion unverified; unit quote about "this" once/year has ambiguous scope |
| 11C / M121 | Generic crew validity, not MORTEP frequency | Active September 2021 MORTEP live-fire activity | Body says rockets while captions identify 120mm rounds; count withheld. Unit-described semiannual MORTEP is not a universal requirement |

IDs: `tempo-mortar-validity-active`,
`tempo-mortar-validity-army_national_guard`, `tempo-guard-mortar-at`,
`tempo-army-mortar-instructors`, `tempo-guard-m252-ir25`,
`tempo-active-m120-training`, `tempo-active-m120-plan`, `tempo-active-m121-mortep`.
The plan stays in V0.2 as a schedule, with no V0.3 source-bound constraint record.
All quantities above lack sufficient individual participation evidence. No
quarterly observed firing rate or person-level annual distribution is introduced.

## Abrams synthesis

| Population | Requirement/validity | Observed activity | Counts and inference boundary |
| --- | --- | --- | --- |
| Army 19K / Abrams 120mm / Active | Generic IWTS vehicle-crew twelve-month validity, not an Abrams-specific firing interval | 3-8 Cavalry, September 2024 M1A2 SEPv3 Table 6 main-gun and coaxial firing | No numeric 120mm total; mixed firing cannot be converted into main-gun rounds |
| Army 19K / Abrams 120mm / Guard | Same generic validity with component-scoped view | Oregon 3-116 Cavalry M1A2 SEP v2 gunnery, April 2018 | Fourteen-day company gunnery and 54 total training days, with 60 planned next year, are not firing-day or attendance counts |

IDs: `tempo-vehicle-validity-active`,
`tempo-vehicle-validity-army_national_guard`, `tempo-active-abrams-table6`,
`tempo-guard-abrams-gunnery`. Gunnery activity is established in the reviewed
reports. Annual individual main-gun firing frequency, per-crew round totals,
attendance and individual exposure remain unestablished. There is no Abrams SME
rate to supply a numerical scenario envelope. Unknown stays unknown.

## Marine Corps synthesis

| Population/context | School or sustainment | Observed activity and weapon-specific counts | Remaining boundary |
| --- | --- | --- | --- |
| 0811, component unspecified, M777-related task | Historical prepared-round task: three-month sustainment; inert/dummy completion permitted | Requirement, not observed firing | No quarterly live-fire rate |
| 0811, Active | Separate from component-unspecified school/task rules | 2/10 Marines M777, Rolling Thunder October 2021 | No round or annual rate; October 16/19 date conflict retained |
| 0811, Reserve | No Reserve-specific annual firing requirement established here | Hotel Battery 3/14, M777 at Dynamic Front, March 2019 | Exercise interval does not establish daily firing or annual rate |
| 0341, component unspecified | Historical observer task: six-month sustainment, live-fire necessity unresolved | Requirement, not observed firing | Preceding task's simulation table is not attributed to this task |
| 0341, Active | No annual execution frequency established | BLT 1/4, 15th MEU, February 2021 mortar live fire; M224/M252 links retained | No rounds or person counts; syndicating page heading is not event provenance |
| 0341, Reserve | No annual execution frequency established | 2/24, April 2016, 81mm mortar training before annual training | Caliber alone does not identify M252; Reserve live fire is not assumed confined to AT |
| Artillery school, component unspecified | Cannoneer five weeks/25 training days; HIMARS 2.5 weeks/13 training days | Curriculum duration only | Training days are not firing days; 0811 student eligibility is not operational HIMARS MOS proof |
| Marine HIMARS, Active | School and operational evidence remain separate | Southern Reach two-GMLRS subset and unknown practice rockets; three launchers | No total or allocation; no annual rate |
| Marine HIMARS, Reserve | WTI support is not proof crew members are instructors | Kilo Battery 2/14 live fire in April 2022 | No weapon-specific count or annual rate; transit-inclusive duration is not firing time |

IDs: `tempo-marine-0811-sustainment`, `tempo-marine-0341-sustainment`,
`tempo-marine-active-cannon`, `tempo-marine-reserve-cannon`,
`tempo-marine-active-mortars`, `tempo-marine-reserve-mortars`,
`tempo-marine-school-cannoneer`, `tempo-marine-school-himars`,
`tempo-marine-active-himars`, `tempo-marine-reserve-himars`.
There is no Marine SME estimate in V0.2 and no justification for transferring
Army 13M recollection to Marines. Active/Reserve differences remain research gaps.

## Future scenario-prior process, without parameters

The proposed workflow is:

```text
source-scoped evidence constraints + separately attributed SME estimates
             + explicit modeling assumptions
                         |
                         v
       candidate scenario prior (only after separate authorization)
                         |
                         v
        sensitivity analysis of assumptions and dependencies
                         |
                         v
        synthetic simulation (separate approval and implementation)
```

First define a target quantity, population/era, counting unit, event boundaries
and denominator. Review whether each source applies to that target; retain the
difference between doctrine and execution. Elicit scenario-specific assumptions
where empirical evidence is absent, record who authorized them and why, and
identify quantities that must remain unknown. Review distribution families for
their support and meaning only after numerical parameterization is authorized.
Do not infer a shape from an SME range or a rough central recollection.

The conservative, central and high-tempo placeholders currently have identical
null parameter structures. Their names impose neither numerical ordering nor
probabilities. Conservative has no clinical/safety meaning; central is not an
empirical mean or median; high-tempo is not a measured upper quantile. A future
design must define the metric along which scenarios differ and evaluate coupled
changes, not assume every input increases together. No scenario is population truth.

No executable numeric candidate is justified today. Annual frequency, per-crew
allocation, instructor workload and nearby/person participation can remain too
poorly bounded even for a useful numerical sensitivity envelope. The framework
supports an explicit decision to leave them unavailable instead of forcing values.

## Uncertainty and dependence

Eight typed dimensions remain separate: annual events, rounds/event, crew
participation, role, nearby exposure, assignment duration, missing years and source
reliability. Every dimension has an explicit aleatory/epistemic/unknown classification,
rationale and propagation plan. The current register assigns epistemic to missing
assignment histories, missing years and source reliability; other dimensions are
unknown/unclassified because variability and lack of knowledge cannot yet be
separated. Future possible aleatory and epistemic components are described without
weights. No aggregate confidence number is computed.

Shared training cycles, deployment preparation, instructor status, component,
occupation and unit type may create dependence. So can shared sources and missingness.
Independent draws are not a default. The separate
[dependency design](dependency-modeling-v0.3.md) distinguishes these issues,
proposes retaining scenario-conditioned uncertainty, and identifies future run
provenance and deduplication needs. It implements no graphical or statistical model.

## Research gaps and acquisition priorities

`data/reference/research_gaps.json` contains 13 open items: representative annual
histories; crew round counts; attendance; instructor workloads; current manual
applicability; individual event links; Active/Guard differences; Marine component
differences; longitudinal variation; source originals; event boundaries; assignment
history/missingness; and sensor/configuration context. Each supplies population,
needed quantity, reason, current evidence IDs, preferred future source, impact
and status. Empty current evidence means unavailable, not negative evidence.

The [data-acquisition roadmap](data-acquisition-roadmap.md) compares logs,
ammunition, qualification, range, attendance, instructor and assignment records;
public longitudinal studies; sensor data; and CONQUER/BETS-related leads. It
separates usefulness for representative priors from usefulness for event
reconstruction. Accessibility is a planning assessment, not a credential or grant
of access. Public discovery checks added no new numerical evidence or V0.2 source
records. No protected data, outreach or access request was attempted.

## Gates before synthetic careers or empirical distribution claims

Before a synthetic-career generator can be implemented, obtain separate approval,
settle assignment/era semantics and the permitted synthetic-only data boundary,
define event identity and person/crew roles, and review a versioned parameter
contract with explicit scenario assumptions, units, dependencies and missingness.
Specify sensitivity and validation criteria, traceability, reproducibility and
unknown-value behavior. Parameters cannot be chosen merely to make a generator
run. A scenario-based synthetic result must carry that label at every stage and
must never feed back into the empirical evidence registry as an observation.

Before claiming empirical population distributions, obtain representative data
for the actual target quantity with reviewed sampling, coverage, denominators,
source independence, temporal applicability, censoring and uncertainty. Specify
the estimation method, clustering/dependence handling and validation across
appropriate units/periods. Review selection and measurement/recall error. Archive
the permitted source/data provenance and reproducible analysis. Official status,
many selected observations, or SME agreement alone does not satisfy these gates.

The repository is ready to support a separately authorized **V0.4 generator
architecture/design discussion** that retains unavailable inputs and these gates.
It is not ready for numerical parameterization, synthetic generation, or claims
of empirically calibrated population tempo. V0.4 is not begun by this task.

## Validation and release status

Tests exercise the empirical/numerical gate, source/SME/scenario separation,
scope equality, raw count precision and denominator preservation, missing and
duplicate IDs, plans versus observations, support-level admission, explicit
uncertainty, research-gap joins, schema freshness, manifest tampering and frozen
dependency hashes. The new prior CLI validates the complete dependency chain.
The explicit history audit verifies both annotated tag targets, V0.1 ancestry,
all tagged reference JSON bytes, unchanged V0.2 project files, source originals
when requested, and the development lock.

Final verification on September 24, 2026, using Python 3.12.10:

| Check | Result |
| --- | --- |
| `python -m pytest` | 481 passed: 323 preserved tests plus 158 V0.3 tests |
| `python -m ruff check .` | All checks passed |
| `python -m ruff format --check .` | 41 files already formatted |
| `python -m mypy` | No issues in 19 source files |
| `python -m pip check` | No broken requirements |
| Reference / training-tempo / prior CLIs | All passed with full manifest verification |
| Schemas and release hashes | All three exported schemas and release manifests validated |
| `scripts/verify_release_history.py --source-archive` | Annotated V0.1/V0.2 tags resolve to pinned commits; V0.1 is an ancestor of V0.2; seven V0.1 and twelve V0.2 JSON files match their tagged bytes; all 52 V0.2 project files unchanged |
| Source archives | Six V0.1 original hashes verified; five V0.1 and 29 V0.2 originals remain unavailable as documented |
| Dependency lock | All 16 development pins match |
| `git fsck --full` / `git diff --check` | Passed |

The V0.3 working tree contains 14 new project files: four JSON release artifacts,
the prior-design reference README, this note, dependency design, acquisition
roadmap, three Python modules, two explicit export/history scripts and one test
module. No tracked V0.2 file is modified. Local seed construction and audit
scripts remain ignored, together with source downloads, environments and caches.
V0.3 remains an unstaged, uncommitted design extension for review; no V0.3 tag or
push is requested or created. `main` remains at the V0.2 commit above.
