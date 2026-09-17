# Research Dataset V0.1 evidence review

Dataset, source-registry and schema versions: **0.1.0**. This is a small,
source-scoped public-reference release, not a current force inventory or an
individual exposure dataset. Field citations in the JSON records are the
machine-readable assertion-to-source map; the registry records document versions,
retrieval limitations and hashes when original bytes were downloaded.

## Interpretation boundaries

- DoD Tier-1 classification is a research/prioritization classification, not a
  medical injury rating.
- Absence from Tier-1 does not mean a weapon produces no blast exposure.
- Occupational relationships do not imply diagnosis or health outcome.
- Weapon-family membership does not imply equivalent blast characteristics.
- This dataset describes systems and occupational relationships, not individual
  exposure dose. No medical outcomes, pressures, impulses, safe distances,
  thresholds, rates of training or cumulative scores were curated.

## Verified identities and classification

The controlling Tier-1 source is `dod-report-2021`, Figure 3, printed p. 4 / PDF
p. 7, visually reviewed. It explicitly lists the following:

| Source category | Catalog records |
| --- | --- |
| Shoulder mounted | M3 MAAWS, M136 AT4, M72 LAW |
| .50 caliber weapons | MK15 and M107 sniper rifles; M2A1 and GAU-21 machine guns |
| Indirect fire: howitzers | M119, M777, M109 Paladin |
| Indirect fire: mortars | M224, M252, M120/M121 |
| Breaching charges | Door/wall breaching, represented as an exposure category |

The source combines M120/M121 in one entry. The catalog stores them as separate
identities and does not make them aliases. There are consequently **14 named
Tier-1 weapon records and one Tier-1 exposure-category record**. The schema
preserves four top-level official categories and the howitzer/mortar subcategories.
The count of catalog records is not a claim about how DoD counts systems or charges.

M142 HIMARS and M270 MLRS identities and rocket/missile-launcher descriptions
come from `army-mos-2025`, section 10-13M, and `army-portfolio-2024`, pp. 99/103.
The 120mm Abrams record is scoped to the M256 main-gun configuration documented
in `army-abrams-2015`; it does not imply every historical M1 variant had that gun.
These three systems are not named in the reviewed Tier-1 figure. Their overall
status remains **unknown**, rather than claiming permanent exclusion from every
official list. They have no official Tier-1 category assignment.

All populated caliber and branch fields have their own citations. Calibers come
from explicit text/category headings, not parsing weapon names. Branch lists are
nonexhaustive documented applicability, not assertions of exclusive use.

## Occupations and relationship evidence

Army duty/title/code evidence is from `army-mos-2025`: sections 10-13M, 10-13B,
10-11C, 10-19K, 10-12B and 10-89D. Marine title/code/duty evidence is from
`usmc-mos-fy26`: MOS 0811 p. 3-78 and MOS 0341 p. 3-33. Occupational relevance
labels are explicitly marked curator mappings of those duties. They are not
official medical labels or statements about firing frequency.

| Relationships | Documentation | Practical limit |
| --- | --- | --- |
| Army 13M -> M142, M270 | Direct named launcher duties, section 10-13M | Does not assign both systems to every 13M |
| Army 19K -> scoped Abrams gun | Direct crew/main-gun duties plus documented 120mm configuration | Crew role and individual firing remain unknown |
| USMC 0341 -> M224, M252 | Explicit platform names in historical FY18 MOS summary | Historical scope; FY26 summary uses broader terminology |
| USMC 0811 -> M777 | 2018 T&R loading assessment, 0811-GUNS-1014, p. F-4 | Training association; this assessment alone does not establish live firing or blast |
| Army 13B -> M119, M777, M109 | Official 2024 competition winners identify 13B teams by platform | Observed training examples, not universal assignments |
| Army 11C -> M224, M252, M120 | 2026 Infantry journal discussion plus 11C mortar duties | Contextual evidence, not an adopted equipment authorization |

There are 12 relationships: five direct-duty associations (two historical), one
direct training standard, three observed-training examples and three contextual
associations. No numeric evidence confidence was invented.

12B and 89D are included because the cited duties explicitly involve explosives.
Their catalog entries do not assert a specific door/wall breaching relationship.
General combat-engineer demolition duties and EOD render-safe/disposal work are
not interchangeable with the specific Tier-1 breaching categories.

## Conflicts and terminology

1. `dha-tier1-2023` prints **M135 AT4**; the controlling report prints **M136 AT4**.
   The discrepancy is retained in notes. M136 is used; M135 is neither silently
   corrected in a quotation nor added as a canonical alias.
2. The supplied project scope called 19K **M1 Armor Crewman**. The retrieved Army
   specification uses **Armor Crewmember** and explicitly includes Abrams duties.
   The sourced title is retained. The specification also mentions M10 Booker;
   no claim about its current fielding or a new catalog entry is made.
3. The FY18 Marine 0341 summary names M224/M252, while FY26 says light/medium
   mortar systems. This is a difference in specificity, not proof that those
   systems were withdrawn or that all variants are interchangeable.
4. The DoD list combines M120/M121; the reference schema separates identities.
   M270A1/A2 and M3A1 references likewise do not become interchangeable aliases
   or imply that variant blast measurements transfer to a base platform.
5. The Fort Sill competition headline, body and captions give differing event
   dates/durations. Only the explicit 13B/platform list is used; event dates and
   training durations are not curated.
6. The 2021 figure groups howitzers and mortars under indirect fire, while the
   2023 article presents them as separate headings. The taxonomy retains the
   parent plus both subcategories, without moving rocket artillery into them.

## Remaining unknowns and intentional exclusions

- Overall/current Tier-1 status of HIMARS, MLRS and Abrams remains unknown.
  All positive classifications are scoped to the identified 2021 source.
- M136 and M72 calibers remain null; their names are not used to infer values.
  Rocket-launcher calibers remain null because a munition caliber is not a single
  fixed launcher property. Breaching has no single caliber.
- Branch applicability is uncurated for M121, M136, M72, M107, MK15, M2A1,
  GAU-21 and the breaching category. Other branch arrays are nonexhaustive.
- Exact variants, ammunition, charge configurations, crew positions, PPE,
  environmental conditions and individual assignment histories are not supplied.
- A specific Army 11C -> M121 relationship is not inferred from M120. No
  weapon-specific links are asserted for 12B or 89D at this release.
- Marine occupational-family fields are null pending explicit family curation.
  Source publication dates are null for the Army Chapter 10C snapshot, the exact
  day of the 2024 portfolio, and the ambiguous FY18 indexed cover. Upload dates
  are not substituted for publication dates.
- Six original source files were downloaded and hashed. Five sources were
  reviewed through indexed official text: the DHA article, FY26/FY18 Marine MOS
  manuals, Marine artillery T&R manual, and 2026 Infantry article. Direct retrieval
  returned 403/404 responses. Their original-byte hashes are explicitly null.
  Obtain accessible originals/authorized archives before claiming full source-byte
  reproducibility; the current release reproduces the curated facts and citations.
- Retired provisional IDs `mortar-60mm`, `mortar-81mm`, `mortar-120mm`,
  `caliber-50-systems` and `shoulder-fired-weapons` are not silently mapped to
  specific models. No participant records existed to migrate. Any future imports
  using those coarse IDs need explicit review.
- M3A1, other weapon variants, M10 Booker, generic undifferentiated .50 caliber
  systems, extra occupations, proposed mortar organizations and developmental
  weapons are excluded from this deliberately bounded release. No conclusion
  about their exposure relevance follows from their absence.

## Before training-frequency research

Resolve the research unit (round, discharge, mission, session, duty day or recalled
period), time windows, active/reserve/component and unit differences, specialty
changes, exact weapon variants, crew/instructor roles, and nearby participation.
Acquire versioned training publications and representative execution records;
qualification requirements, authorized ammunition, school repetitions and
actual individual exposure are different quantities. Assess representativeness,
missingness and uncertainty, source rights and data governance. Strengthen the
contextual/historical relationships and obtain the five missing source originals.
Do not infer frequencies from an MOS title, a competition or a loading assessment.

## Before any blast-pressure profiles

Obtain publicly releasable, properly sourced measurements with exact system and
ammunition/configuration, instrument identity and calibration, sampling details,
sensor position/orientation and distances, pressure reference (incident/reflected,
overpressure/absolute), waveform/time history, impulse integration definition,
environment, uncertainty, quality/saturation information and measurement protocol.
Preserve sample-level provenance and distinguish measurements from estimates.
No pressure profile can be derived from the present catalog; comparisons or
aggregation require independent methods and review. Exposure is not injury.

## Release completion and final verification (2026-09-17)

The resumed completion review found the five versioned datasets, exported schema,
release manifest, source review, update procedure and implementation already
complete. No interrupted or malformed release file required repair. The existing
research and release bytes were retained; this section records the final checks.

| Check | Result |
| --- | --- |
| `python -m pytest` | 205 passed |
| `python -m ruff check .` | All checks passed |
| `python -m ruff format --check .` | 26 files already formatted |
| `python -m mypy` | No issues in 13 source files |
| `python -m pip check` | No broken requirements |
| `python -m blastbridge.validation.reference` | All five datasets and release hashes verified |
| Exported schema | Matches the current ReferenceBundle schema, covered by pytest |
| Downloaded source originals | All six SHA-256 hashes match their registry entries |
| Development lock snapshot | All 16 pinned distributions match installed versions |
| Git integrity | `git fsck --full` reports only the expected unborn-branch/no-reference notices |

Validation confirms citation coverage and source-ID unions, source-registry
versions, unique identities and aliases, occupation/weapon relationships,
taxonomy references and cycles, official Tier-1 provenance, and all manifest
dataset/schema hashes. These structural checks do not replace the source review
above or resolve its five missing original-source downloads.

The unchanged release manifest's SHA-256 is
`e424efbce2eb3d7387cf6f4bab3955c9d9ee92448ded543ec0f43011995661c0`.
Dataset, registry and schema versions remain 0.1.0. The editable installation
points to the active local workspace, independently of the retired OneDrive copy.
The sandbox initially could not access the base Python interpreter; the checks
above succeeded outside the sandbox without rebuilding the environment.

Git remains on unborn `main`, with no commits or staged/tracked files and 42
untracked project files. Local source downloads, the virtual environment and tool
caches remain ignored. This is a validated local release, not a committed or
tagged release. The old OneDrive directory still exists; the resumed review did
not attempt deletion or change Windows permissions. See the migration record for
the previously observed deletion denial.

Only this completion section was added during the resumed task. No catalog,
source registry, schema, manifest, Python implementation or test was changed.
Training-frequency research and all later phases remain unstarted; their
prerequisites and the authoritative-source discrepancies remain documented above.
