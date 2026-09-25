# V0.3 modeling-assumption and prior design

This is a **0.3.0 design release**, with no fitted priors, numerical scenario
parameters, sampler or synthetic careers. `empirical_priors` is null. Python
package version 0.1.0 is unchanged; dataset/schema versions are independent.

V0.1 and V0.2 are immutable dependencies. V0.2 was committed as
`4182044e57177d77e643b6b273dbee03cc433eeb` and annotated `v0.2.0` on September 24,
2026. Its release note describes the earlier validated, pre-commit state and is
left intact. No previously tagged project file is edited by V0.3.

| Artifact | Meaning |
| --- | --- |
| prior_definitions.json | 34 evidence constraints, two SME estimates, three unparameterized scenario placeholders; eight uncertainty dimensions |
| research_gaps.json | 13 open research gaps with V0.2 evidence links |
| prior_design.schema.json | Exported PriorDesignBundle JSON Schema |
| prior_design_manifest.json | Exact dataset and schema hashes, pinned V0.2 commit/tag and manifest hash |

The 34 constraints are ten historical requirements and 24 observations bound to
their exact source populations, time windows, quantities and limitations. An
observation is a constraint on what the named source reports about that event;
it is not a lower bound on anyone's future training. Requirements, validity and
task sustainment remain distinct in the original discriminated claim payload.

The excluded V0.2 plan remains evidence for the mortar case study, but cannot
become a requirement or an observation. Engineering/EOD examples are outside
the five requested case studies and remain in V0.2 without new prior definitions.
No V0.2 record is removed or regenerated.

## Validation

Run from the repository root, using the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m blastbridge.validation.reference
.\.venv\Scripts\python.exe -m blastbridge.validation.training_tempo --source-directory research/sources/tempo-downloads
.\.venv\Scripts\python.exe -m blastbridge.validation.priors
.\.venv\Scripts\python.exe scripts/verify_release_history.py --source-archive
git fsck --full
git diff --check
```

The prior CLI is the aggregate V0.3 entry point: it validates V0.1 and V0.2 first,
then V0.3. The older CLIs retain their tagged behavior and do not discover V0.3.
Deleting any V0.3 release file causes prior validation to fail. Source archives
are optional for ordinary loading; the explicit history audit checks all six
claimed V0.1 downloads and reports the known five V0.1/29 V0.2 unavailable
originals. It never claims that zero V0.2 downloads means complete source review.

```python
from blastbridge.data.priors import load_prior_design

design = load_prior_design("data/reference")
assert design.priors.empirical_priors is None
```

Use the loader at ingestion boundaries. `PriorDefinition.model_validate` checks
record shape and design gates; only bundle validation against the frozen evidence
can check source IDs, scope and exact claim equality. Never bypass validation
with `model_construct` or unchecked model copies. JSON Schema describes shapes;
cross-record, source-semantic and provenance gates also require the Python loader.

## Editing and reproducibility

Keep all 12 V0.1/V0.2 JSON release files alongside the four V0.3 files. Reference
IDs and source originals are inherited, not redefined. New evidence or authorized
distribution parameterization requires a separately reviewed schema/release
change; this version cannot activate empirical priors or A/B support by toggling
a flag or supplying a claim of representativeness.

After an actual authorized V0.3 design-data/schema change, review the candidate
with `load_prior_design(path, verify_manifest=False)`. Candidate mode bypasses
only V0.3 hashes, never dependency hashes, source joins or the numeric gate. Export
the new schema and manifest explicitly:

```powershell
.\.venv\Scripts\python.exe scripts/export_prior_design.py --write
```

The exporter validates the candidate before writing and the full release after
writing; it does not alter evidence or definitions. Review changed hashes and run
the full suite. Record the manifest's SHA-256, code commit, dependency release
commits and the environment lock with any future analysis. Hashes detect byte
changes; they do not establish source truth or authenticate unsigned tags.

See [the research note](../../research/notes/prior-design-v0.3.md),
[dependence design](../../research/notes/dependency-modeling-v0.3.md) and
[acquisition roadmap](../../research/notes/data-acquisition-roadmap.md).
