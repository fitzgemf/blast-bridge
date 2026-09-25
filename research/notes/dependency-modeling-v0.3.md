# Dependence and uncertainty propagation design, V0.3

Status: design only, 0.3.0, September 24, 2026. No Bayesian network, ML model,
sampler, joint distribution, correlation coefficient or simulation is implemented.
The relationships below are hypotheses for a future approved design, not
empirically fitted links. Existing evidence supplies context, not causal proof.

## Two distinct kinds of dependence

Evidence dependence comes first. Four Western Strike platform counts share a
report and exercise; Active/Guard qualification views share manuals; two HIMARS
SME records share one recollection. Different record IDs, platforms, captions or
syndicated URLs do not establish independent evidence. Preserve source, exercise,
unit, time and respondent groups before evaluating any B support claim. No
independence registry is qualified in V0.3, so B is unavailable.

Future activity dependence is a different problem: multiple quantities may
change together. It must not be inferred from record-count correlations in this
selectively reported evidence set.

| Possible dependency | Meaning for later design | Present limitation |
| --- | --- | --- |
| Component, unit type and qualification structure | Condition policy applicability on the actual formation/edition; separate compliance from policy | Current applicability and complete execution histories missing |
| Training cycle and deployment preparation to events/year and rounds/event | A common context may affect both; separate marginal draws could yield implausible combinations | No joint annual panel or correlation magnitude |
| Occupation, era and assignment to available weapon systems | Use reviewed historical occupation/weapon relationships and exact assignment context | MOS alone does not establish participation, current fielding or a unique weapon |
| Instructor assignment to opportunities and role | Course repetitions and rotations may differ from operational crews | Annual teaching load and attendance unknown |
| Unit event to participating crews and people | Shared event identity precedes any person attribution; observations from one event cluster | Roster, attendance and round allocation absent |
| Crew participation, role and nearby presence | Operating, supervising and being nearby are distinct relations to the same discharge | Distance, orientation and personnel linkage unknown |
| Assignment duration, missing years and reporting | Coverage/censoring and selection may affect apparent rates | No evidence that missing reports are random or zero |
| Source reliability to multiple claims | A transcription ambiguity or retrieval problem can affect every claim from that source | No validated scalar reliability weight |

Do not impose signs or strengths as facts. Even a plausible positive association
between event frequency and rounds/event may vary by context or ammunition
constraints. A later approved sensitivity analysis can compare independently
drawn and explicitly coupled alternatives only after those alternatives and their
assumptions are recorded. Independence itself is an assumption needing review.

## Proposed propagation contract

Keep each future run's quantities, provenance types and uncertainty dimensions
separate. Preserve source-bound counts as source facts, SME values as recollection,
and selected scenario choices as assumptions. The eight uncertainty records in
`prior_definitions.json` are the current typed contract; none contains a weight.

| Dimension | Current classification | Later separation needed |
| --- | --- | --- |
| Annual event count | Unknown/unclassified | Conditional year-to-year variation could be aleatory; coverage and distribution ignorance are epistemic |
| Rounds/event | Unknown/unclassified | Event/configuration variation could be aleatory; allocation and event-definition gaps are epistemic |
| Crew participation | Unknown/unclassified | Actual rotation variation versus unknown attendance linkage |
| Role | Unknown/unclassified | Real role changes versus incomplete role records; retain unknown category |
| Nearby exposure | Unknown/unclassified | Changing positions/configurations versus unknown presence and measurement validity |
| Assignment duration | Epistemic for current data | Missing dates/transfers/censoring; future career variation requires separate justification |
| Missing years | Epistemic | Unknown observation coverage and selection; missing is not zero |
| Source reliability | Epistemic | Retrieval, recall, measurement and transcription limitations, tracked per source |

Aleatory means variability conditional on a defined population/context and model;
epistemic means lack of knowledge. A variable can involve both, but V0.3 does not
assign proportions or disguise that mixture as a measured decomposition. The
explicit unknown/unclassified value is used where the present evidence cannot
separate them. These are methodological classifications, not clinical confidence.

For a future authorized simulator, an outer layer could retain alternative
epistemic assumptions and an inner layer could represent justified conditional
aleatory variation. This is a design option, not an implemented algorithm. Keep
scenario-conditioned results separate; do not average scenarios using invented
probabilities. Do not report a narrow Monte Carlo interval as if it included
uncertainty about unsupported assumptions.

Any future output would need an immutable run manifest recording scenario/version,
all quantity-specific assumptions, evidence/source IDs, population/time boundaries,
dependency choices, missingness treatment, seed, code/dependency hashes and
observation-versus-assumption flags. Validate temporal order, roles, event identity
and denominator consistency before aggregation. The current project writes none
of these simulated records.

## Counting identities that must remain unresolved

`annual periods × rockets per crew/event` is not an authorized identity: periods
and events are not established as equivalent, and crew/person participation is
unknown. Unit round totals divided by crews presume an allocation that sources
do not support. Exercise duration is not firing days; validity is not completion;
sensor triggers are not automatically unique discharges or valid measurements.

Person-event relations may be many-to-many: several people can be present at one
discharge, and one person can attend many events. Future designs must prevent
duplicate counting across sensors, reports, crews and roles. A hierarchical event
index may help, but no hierarchy, stochastic graph or coefficients are inferred
or implemented here. Pressure/impulse attribution requires independently validated
measurement context. No path from these counts to TBI probability or a medical
risk score is part of this design.

## Gate before implementation

First resolve counting units, scenario population/era, assignment semantics and
which inputs remain unknown. Then obtain separately authorized elicitation or
representative empirical evidence, review independence and dependencies, specify
quantity-specific assumptions and a sensitivity plan, and approve a numerical
parameter schema. Unsupported dimensions must be omitted or explicitly unknown;
they must not receive convenient defaults. The present evidence cannot select a
joint distribution or numerical scenario envelope.
