# Data-acquisition roadmap, V0.3

September 24, 2026. This is a planning document, not an access request or a data
collection protocol. No protected or restricted data was requested or retrieved.
Likely accessibility below is a planning assessment, not a promise of access,
an assertion of current program enrollment, or permission to store records here.
The repository remains a public-reference/design workspace without participant
records. The V0.2 evidence registry is unchanged.

## Sequence and decision value

Start with permitted originals of the 29 V0.2 official sources and current manual
applicability. These can improve verification of source-bound requirements, but
cannot fix population representativeness. Next prioritize deidentified, linked
unit-year event histories with ammunition and attendance denominators. These would
address the central prior-design gaps more directly than accumulating more news
articles. Measurement datasets become valuable for event reconstruction when they
carry adequate timing, configuration and person-event linkage.

Before acquiring participant data, establish a responsible custodian, documented
purpose, minimum necessary variables, approved storage/access controls, permitted
linkages, retention/deletion rules, and any required institutional, ethics, consent
or data-use review. These are acquisition prerequisites, not legal conclusions
about a particular dataset. Use approved deidentified extracts; names, military
identifiers, precise unit/date combinations and location traces may permit
reidentification. Do not copy restricted logs into this repository.

| Candidate data | Variable it could resolve | Likely accessibility / governance assessment | Population-prior value | Exposure-event reconstruction value |
| --- | --- | --- | --- | --- |
| Official source originals and supersession notices | Exact wording, date, exception and historical/current applicability | Public versions/authorized archives first; retain permitted bytes, hashes and version; redistribution rights may differ | Establishes requirement scope, not realized population rates | Helps interpret events, without proving attendance |
| Unit training logs | Defined events, activity dates, training cycle, complete observed years | Public summaries may exist; granular logs require owner review and may reveal operations/unit locations | High only with a defined sampling frame, coverage, comparable units and zero-event years | High when linked to exact events and rosters |
| Ammunition expenditure records | Rounds fired, platform/ammunition, event/unit/crew allocation | Likely requires custodian review; expenditure may differ from authorization, issue or return; operational details may be sensitive | Useful conditional counts if fired quantities and denominators are verified | High for discharge inventories; alone cannot attribute people |
| Qualification records | Completion, lapse, attempts, crew configuration and exceptions | Manuals may be public; individual records may be protected personnel data | Distinguishes validity from execution; qualification-only sampling can miss other firing | Links particular completed activities when firing is recorded |
| Range logs | Sessions, weapon lanes, timing, ammunition and event identifiers | Public availability uncertain; unit, location and date sensitivity needs review | Potential session counts; not representative without coverage information | Useful for deduplicating events and aligning sensors |
| Attendance/crew rosters | Who attended, role, rotation and time present | Deidentified extracts and approved linkage needed; direct identifiers excluded | Supplies denominators missing from unit totals | Essential for operator/crew/observer/safety and nearby-person relations |
| Instructor records | Course iterations, teaching load, role and live-fire attendance | School aggregate summaries may be available; individual workloads need personnel/privacy review | Can support a separately sampled instructor population | Useful when rotations are tied to particular live-fire events |
| Assignment/observation-coverage histories | Duration, transfers, era, missing years and censoring | Individual histories require approved deidentification and limited linkage | Essential to define person-time and missingness; cannot assume missing at random | Defines eligible assignment intervals, without proving firing attendance |
| Public longitudinal studies | Within/between-person and year variation; sampling and missingness methods | Publications may be public; usable microdata/code and permissions must be checked per study | Potentially valuable if the target population, quantity and representativeness match | Depends on event resolution and measurement metadata |
| Sensor datasets | Waveforms, pressure/impulse, timing, configuration, quality and saturation | Public excerpts may exist; raw records may require an agreement; device position/timing can identify people or operations | Selected instrumented events rarely establish annual population tempo alone | High with calibration, position/orientation, ammunition, attendance and unique-event linkage |
| CONQUER-related data | Instrumented event exposure context and source/platform/role linkage | Public research describes the program; underlying extract availability and current access process are unverified; contact would require separate authorization | Do not assume instrumented participants or events represent all unit-years | Potentially useful measured-event records if raw data and required metadata are lawfully accessible |
| BETS-related datasets | Recalled exposure histories, event terminology and recall uncertainty | Instrument descriptions/publications may be accessible; respondent-level data and version-specific access are unverified; linked health data requires additional governance | Recollection remains self-report; assess selection, recall, validation and denominators before using for empirical quantities | May support retrospective history with uncertainty, not measured waveforms or automatic event identity |

## Public discovery anchors

The 2023 primary CONQUER paper describes a pilot using body-worn sensors during
training. Its published abstract supports considering instrumented training data
as an acquisition category. It does not establish public access to the underlying
archive or representative annual histories. This review used indexed abstract
text; direct PMC opening presented a browser challenge. No raw archive was
downloaded. [CONQUER dynamic-monitoring study](https://pmc.ncbi.nlm.nih.gov/articles/PMC10248048/).

The official CDMRP article identifies BETS as the **Blast Exposure Threshold
Survey**, a source of recalled exposure-history information. Treating survey
responses as a potential history source does not authorize use of the article's
separate symptom/risk-index work. BlastBridge will not import those medical
prediction methods. The article is a discovery lead, not a microdata access
agreement. [CDMRP research overview, March 23, 2026](https://cdmrp.health.mil/pubs/press/2026/CDMRP_TBI_research_highlight.aspx).

Both links were reviewed on September 24, 2026 for roadmap identification only;
they are not new V0.2 sources and supply no V0.3 numerical prior parameters.
Public program descriptions do not imply that credentials, datasets or licenses
are available. No outreach or application was submitted.

## Acceptance criteria for future evidence

For empirical population priors, require an explicit target quantity and counting
unit, target population/era, a defensible sampling/coverage design, complete
denominators, source independence review, missingness/censoring analysis and
validation on held-out units or periods appropriate to the estimand. Retain actual
zero activity separately from unobserved activity. Assess clustering and changes
in doctrine, unit structure, ammunition and mission. A large selected dataset is
not representative merely because it is large.

For event reconstruction, require a supported chain from discharge/session to
unit, crew, person attendance/role and any measurement, with clock alignment,
deduplication and explicit unknowns. Sensor-only data cannot fill unobserved years;
ammunition totals cannot create person-level participation. Exposure opportunities,
measured pressure/impulse and medical outcomes remain different quantities.

For future SME elicitation, record respondent expertise and relevant service
scope without identifiable details, distinguish first-hand from indirect accounts,
define period/session/event, elicit uncertainty and variability separately, and
record selection/recall limitations. A later elicited scenario remains an
assumption unless representative empirical evidence independently qualifies it.

The 13 machine-readable gaps in `data/reference/research_gaps.json` connect these
priorities to current evidence and modeling impact. They remain open until the
appropriate evidence and review exist; acquiring a URL alone does not close one.
