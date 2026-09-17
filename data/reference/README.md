# Research Dataset V0.1

All five reference datasets, their source registry and their schema begin at
version **0.1.0**. Each JSON dataset is an object with `metadata` and `records`.
This replaces the provisional unversioned weapons array.

| File | Contents |
| --- | --- |
| sources.json | 11 official source records, publication/version/retrieval metadata |
| weapons.json | 18 canonical weapon or exposure-category records |
| occupations.json | 6 Army and 2 Marine occupational specialties |
| occupation_weapon_relationships.json | 12 independently cited relationships |
| taxonomy.json | 6 official category nodes and 4 research-family nodes |
| reference.schema.json | Exported ReferenceBundle JSON Schema |
| release_manifest.json | Dataset versions, exact SHA-256 file hashes and schema hash |

## Loading and validation

Run commands from the repository root with the installed Python 3.12 environment:

```powershell
.\.venv\Scripts\python.exe -m blastbridge.validation.reference
```

```python
from blastbridge.data.reference import load_reference_bundle, load_source_registry
from blastbridge.data.catalog import load_weapon_catalog

release = load_reference_bundle("data/reference")
registry = load_source_registry("data/reference/sources.json")
weapons = load_weapon_catalog("data/reference/weapons.json")
assert registry == release.sources
```

`load_reference_bundle` validates schema, populated-fact citation coverage,
source and relationship references, official provenance, aliases, taxonomy
parents/cycles, metadata and release hashes, entirely offline. Single source
registry loading validates its own records; it cannot check other datasets.
Weapon loading validates the entire neighboring reference release.

Reference models live in `blastbridge.models.reference`. `CanonicalWeapon` and
`OccupationalSpecialty` are separate from the original research-record schemas.
No implicit conversion or assignment-to-occupation reconciliation is performed.
Occupation records do not duplicate weapon lists: obtain related weapon families
through the cited relationship records and each weapon's family.

Each populated fact has a `facts` entry with a field path, one or more registry
source IDs and exact section/page/paragraph locators. Array members have separate
paths (for example `aliases.0`). Record-level `source_ids` must equal the union
of cited sources. Local IDs and the schema's field names are internal identifiers,
not claims of official nomenclature. `curator_mapping` explicitly marks normalized
labels or editorial interpretations rather than pretending those labels are
verbatim source terminology. Notes also have citations.

Unknown caliber/date fields are null, unknown Tier-1 status is explicit, and an
empty service-branch array means not curated. Populated branch arrays are not
exhaustive. No missing datum is filled from a name. A family is a grouping for
research, not a substitute for the source system's identity or measured blast
characteristics. No numeric confidence has been assigned to reference assertions.

Only official or peer-reviewed source types are accepted by the registry.
Current identity, occupation, relationship and classification facts require an
official citation; a peer-reviewed-only future annotation needs an explicit schema
extension. Known Tier-1 facts require a source identified as an official DoD/DHA
list with a locator. Negative status additionally requires a scoped complete list
and explanatory notes. No negative Tier-1 claims are shipped in this release.
Domain checks prevent obvious attribution errors; they cannot prove that a cited
passage actually supports a claim. Human source review remains required.

Name matching normalizes Unicode, case, whitespace and punctuation to detect
alias/canonical/ID collisions. It does not infer aliases or merge variants. M120
and M121 remain distinct; M3A1 is not silently merged into M3. Retired generic
seed IDs require human review, not automatic one-to-many expansion.

## Reproducible updates

1. Work on a candidate copy or branch. Preserve the previous released data,
   schema and manifest before editing. Keep stable source/system/occupation IDs;
   never reuse an ID for a different entity. Record corrections and supersession.
2. Review original public authoritative documents. Record publication dates only
   when established; use null otherwise. Record document version, UTC access
   date, source organization, URL, exact locator and retrieval limitations.
   Hash downloaded original bytes. Do not store long quotations or unpublished
   participant/controlled material. Keep local source downloads ignored by Git.
3. Cite every new or changed fact, including each alias and branch. Distinguish
   direct evidence from curator mappings. Keep historical scopes and conflicting
   terminology visible. Do not elevate source presence into proof of a claim.
4. Bump the relevant dataset and registry versions when contents/source sets
   change. Use semantic versions: patch for corrections compatible with the
   existing interpretation; minor for additive records/compatible new information;
   major for incompatible definitions or identity/meaning changes. Before 1.0,
   explicitly document any incompatible change even if using a minor increment.
   V0.1 validates core X.Y.Z versions; prerelease/build suffixes are not accepted.
   Schema changes require a new supported schema version and migration review.
5. Update every dataset's source_registry_version to the actual registry used.
   Run candidate validation with `load_reference_bundle(path,
   verify_manifest=False)` while editing. This bypasses only release byte hashes;
   provenance, schema and reference checks still run. Never use this bypass for
   experiments or to suppress a validation failure.
6. Export `ReferenceBundle.model_json_schema()` to reference.schema.json using
   UTF-8 and LF newlines. Rebuild the manifest with hashlib.sha256 over the exact
   bytes of all five JSON datasets and the exported schema, after content review.
   Do not automatically refresh hashes during ordinary loading. Review the changes
   before treating the candidate as a release.
7. Run pytest, Ruff lint/format, mypy, pip check and the reference-validation CLI.
   Commit/tag approved releases and retain their full artifacts. No commit/tag
   has been fabricated for the initially uncommitted repository.
8. Experiments must retain the exact release files and record the manifest's own
   SHA-256, dataset versions, registry version, schema version/hash, code commit
   (once one exists) and environment lock. A version string or mutable URL alone
   is insufficient to reproduce a source set.

Hashes detect byte changes; they do not authenticate an unsigned manifest or
establish factual correctness. `.gitattributes` fixes LF to prevent platform
newline conversion from changing reference hashes. Export/copy all seven release
files together. Six sources have original-byte hashes; five indexed official
sources lack downloadable original bytes in this environment. The release makes
this limitation explicit and does not claim complete source-byte reproducibility.
Obtain approved original archives before an experiment requires that guarantee.

See [the evidence review](../../research/notes/reference-v0.1.md) for source scopes,
uncertainties, conflicts and prerequisites for future frequency/measurement work.
