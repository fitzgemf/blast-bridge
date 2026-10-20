# BlastBridge

Hackathon product prototype: see [PRODUCT.md](PRODUCT.md).

A Python 3.12 research foundation for longitudinal reconstruction of occupational
blast exposure among U.S. military service members.

**Blast exposure and brain injury are not equivalent.** BlastBridge does not
diagnose TBI, predict whether a person has TBI, assign injury probabilities, or
define medical risk thresholds. Symptom records are self-reports; linking one
to an exposure does not establish causation.

Research Dataset V0.1 contains 18 weapon/category records, 8 occupational
specialties, 12 supported relationships, 10 taxonomy nodes and 11 official
sources. Dataset and schema versions begin at **0.1.0**. The original typed
research records and validation remain available. The project has no web
application, trained model, NLP extraction, unsupported exposure scores, or
provider-summary generator. V0.5 is the fictional synthetic-engine foundation:
an in-memory assembler, ExecutionMapping, minimal JSON persistence, and one
committed fictional demo career, using generator 0.5.0 and unchanged output
schema 0.4.0. Only a fictional, content-gated engine exists; real generation
remains unauthorized. It makes no medical inference. Exposure is not injury.

Research Dataset V0.2 adds **40 training-tempo evidence records**, **31 source
records** (29 official, one SME recollection and one research-definition source),
eight counting definitions, a separate schema and a separate release manifest.
The V0.1 JSON release remains byte-identical to commit
`0c3ede2dadff3b21dda2c901407a214658f63b9b`, annotated tag `v0.1.0`.
V0.2 separates requirements, reported activity, plans and retrospective estimates;
it supplies no fitted priors or individual exposure frequencies. All 29 official
V0.2 sources lack archived originals and retain explicit retrieval limitations.
See the [V0.2 review and validation](research/notes/training-tempo-v0.2.md).
Dataset/schema versions are independent of the Python package version, which
remains 0.1.0. V0.3 prior and uncertainty design is complete; no empirical
population priors were justified. No production synthetic careers have been
generated, and no ML models have been trained. The V0.5 fictional foundation
builds on the V0.4 configuration, scenario, distribution, RNG, provenance,
hierarchy, validation, and output-schema contracts. Scale, chunking, manifests,
and golden-vector work are deferred. See the
[V0.4 architecture note](research/notes/synthetic-generator-architecture-v0.4.md).

## Setup (Windows PowerShell)

Python is restricted to 3.12.x; `.python-version` also records this choice.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m blastbridge.validation.reference
.\.venv\Scripts\python.exe -m blastbridge.validation.training_tempo --source-directory research/sources/tempo-downloads
.\.venv\Scripts\python.exe -m blastbridge.validation.priors
.\.venv\Scripts\python.exe -m blastbridge.validation.simulation
.\.venv\Scripts\python.exe scripts\verify_release_history.py --source-archive
```

On other platforms, substitute `python3.12` and `.venv/bin/python`.
Development dependency versions used for verification are recorded in
`requirements-dev.lock.txt`; install that file before the editable package to
reproduce those tool versions. The version ranges in pyproject.toml describe
compatibility, while the lock snapshot records the tested environment.

## Design

**Pydantic v2** provides validation at construction/import boundaries, typed
nested models, JSON serialization and JSON Schema generation. Dataclasses would
require custom runtime parsing and validation for each ingestion path.
[Pydantic model validators](https://pydantic.dev/docs/validation/latest/concepts/validators/)
support the cross-field checks here.

All seven requested records are public in `blastbridge.models`:
ServiceMember, Assignment, WeaponSystem, ExposureEvent, SensorReading,
SymptomReport, and DataSource. Enumerations live in `models.enums`.

- Stable anonymous local IDs link career assignments, exposures, sensor readings,
  and symptom reports. Names, contact details, exact birth dates and military
  identifiers are excluded. Age at service entry is optional.
- Record provenance supplies sources and evidence kind. `Evidence[T]` attaches
  independent provenance to counts, distances, orientation and symptom duration.
  Pressure and impulse each carry a value, their own unit and provenance.
- Evidence kinds separate **measured**, **estimated**, **self_reported**,
  **synthetic**, and **documented** facts. Documented accommodates official career
  records without calling them measurements. Source type describes the source;
  evidence kind describes how a particular value was obtained.
- Every estimate requires at least one cited source, confidence in [0, 1], and a
  nonempty method note. Confidence is a research annotation, not injury probability.
  No confidence value is supplied by default. A rubric remains to be decided.
- Measured observations require a sensor source; symptom reports require a
  self-report source. Synthetic observations require an explicit synthetic source,
  and cannot be inserted into real records or linked to real members.
- Event pressure/impulse fields accept measured observations (or explicitly
  synthetic values in synthetic records), never undocumented weapon defaults.
  Sensor availability alone does not assert that a valid measurement exists.
  Sensor quality is retained independently from confidence.
- Unknown quantities use `None`, never zero. Unknown symptoms use `None`;
  `False` means explicitly absent. Unknown PPE uses `None`; an empty tuple means
  explicitly no PPE reported. Enum values include unknown where appropriate.
- Rounds and firing events are distinct nonnegative integer counts, with no
  assumed conversion. Distances use meters, durations hours, and orientation
  degrees in [0, 360) with a required free-text reference frame.
- Pressure and impulse use separate dimension-specific units. There are no
  automatic conversions, physiological thresholds, clinical severity scales,
  unit-based risk limits, or cumulative dose calculations.
- Dates are ordered, timestamps require timezone offsets, numeric strings and
  booleans cannot silently become counts, nonfinite values are rejected, and
  unknown fields fail validation. Records are frozen with tuple collections;
  revalidate complete records when making changes.
- Branch/component can change at assignment level. The reference layer now has
  typed occupational specialties and separate weapon relationships. Assignment's
  existing free-text MOS field is retained; automatic reconciliation of historical
  assignments to the new vocabulary is not implemented.
- The canonical reference catalog requires field-level citations and official
  DoD/DHA list evidence for known Tier-1 status. Classification is scoped to the
  reviewed 2021 report. HIMARS, MLRS and Abrams remain unknown, with no Tier-1
  category assigned. This classification is not a medical injury rating.
- `ResearchDataset` adds unique-ID, relationship ownership, synthetic-boundary,
  weapon-reference and career-date checks to a closed batch. Synthetic members
  and real members require separate batches. Symptoms may be
  reported after service ends. Individual records alone cannot validate links.

## Example: a recalled exposure count

This small code example illustrates schema use; it is not a research dataset,
a military frequency assumption, or an exposure estimate.

```python
from datetime import datetime, timezone

from blastbridge.models import DataSource, Evidence, ExposureEvent, Provenance
from blastbridge.models.enums import DataKind, SourceType

source = DataSource(
    source_id="example-report",
    source_type=SourceType.RETROSPECTIVE_SELF_REPORT,
    citation="Illustrative report locator; replace with an approved source ID",
)
reported = Provenance(kind=DataKind.SELF_REPORTED, sources=(source,))
event = ExposureEvent(
    exposure_id="example-event",
    member_id="anonymous-example",
    timestamp=datetime(2025, 1, 1, 12, tzinfo=timezone.utc),
    weapon_system_id="m777",
    rounds=Evidence[int](value=2, provenance=reported),
    provenance=reported,
)
payload = event.model_dump_json()
assert ExposureEvent.model_validate_json(payload) == event
```

Use `load_weapon_catalog("data/reference/weapons.json")` from
`blastbridge.data.catalog` to validate the complete reference release and return
canonical weapon records. The return type is now `CanonicalWeapon`, distinct
from the original observation-layer `WeaponSystem`. Call
`ExposureEvent.model_json_schema()` for a machine-readable schema.
Deserialize external inputs with `model_validate` or `model_validate_json`;
do not use validation-bypassing construction/copy methods for ingestion.

## Repository layout

```text
BlastBridge/
  README.md
  pyproject.toml
  requirements-dev.lock.txt
  .python-version
  .gitignore
  src/blastbridge/
    __init__.py
    py.typed
    models/       # Core records plus versioned reference schemas
    data/         # Reference bundle, source registry and catalog loaders
    simulation/   # Reserved; no implementation
    features/     # Reserved; no implementation
    validation/   # Cross-record integrity
  data/
    raw/          # Empty; ignored except .gitkeep
    curated/      # Empty; ignored except .gitkeep
    synthetic/    # Empty; ignored except .gitkeep
    reference/    # Sources, weapons, occupations, relationships, taxonomy,
                  # exported schema and release manifest
                  # plus separately manifested training_tempo* V0.2 files
  research/
    sources/      # Source-register guidance
    notes/        # Decisions needed before dataset work
  tests/
  notebooks/      # Guidance only
```

The working repository has moved out of OneDrive. This reduces accidental cloud
synchronization; it does not approve the repository for PHI, PII, controlled
military information or actual participant records. During development use only
public references and explicitly fictional/synthetic demonstration records.
Do not store actual medical records, SSNs, DoD IDs, EDIPI, names, addresses or
exact birth dates. Only the fictional, content-gated synthetic engine is
implemented; real generation remains unauthorized, and no medical inference
is supported. Exposure is not injury.
See [data governance](research/notes/data-governance.md) and the
[migration record](research/notes/repository-migration.md).

Before dataset work, resolve the governance, career/date semantics, measurement
definitions, official source review, confidence rubric and symptom instruments
listed in [dataset decisions](research/notes/dataset-decisions.md).
Reference evidence, conflicts and remaining unknowns are documented in the
[V0.1 research review](research/notes/reference-v0.1.md). Read
[reference guidance](data/reference/README.md) for validation and reproducible updates.
No repository license is selected; choose licensing and data-use terms before
publishing or distributing the project.
