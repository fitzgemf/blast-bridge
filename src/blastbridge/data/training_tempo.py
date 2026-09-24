"""Offline V0.2 loading, with an immutable dependency on the V0.1 reference release."""

import hashlib
from pathlib import Path

from blastbridge.data.reference import load_reference_bundle, read_json
from blastbridge.models.training_tempo import TempoManifest, TrainingTempoBundle

BASELINE_COMMIT = "0c3ede2dadff3b21dda2c901407a214658f63b9b"
BASELINE_MANIFEST_SHA256 = "e424efbce2eb3d7387cf6f4bab3955c9d9ee92448ded543ec0f43011995661c0"
TEMPO_FILES = {
    "sources": "training_tempo_sources.json",
    "evidence": "training_tempo_evidence.json",
    "taxonomy": "training_tempo_taxonomy.json",
}
TEMPO_RELEASE_FILES = (
    *TEMPO_FILES.values(),
    "training_tempo.schema.json",
    "training_tempo_manifest.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_training_tempo(
    directory: str | Path, *, verify_manifest: bool = True
) -> TrainingTempoBundle:
    """Candidate mode bypasses only V0.2 byte hashes, never V0.1 or relational checks."""
    root = Path(directory)
    reference = load_reference_bundle(root)
    if sha256(root / "release_manifest.json") != BASELINE_MANIFEST_SHA256:
        raise ValueError("V0.1 baseline manifest changed")
    bundle = TrainingTempoBundle.model_validate(
        {key: read_json(root / filename) for key, filename in TEMPO_FILES.items()}
    )
    bundle.validate_reference_links(reference)
    if verify_manifest:
        manifest = TempoManifest.model_validate(read_json(root / "training_tempo_manifest.json"))
        if manifest.baseline_git_commit != BASELINE_COMMIT:
            raise ValueError("V0.1 baseline commit mismatch")
        if manifest.baseline_manifest_sha256 != BASELINE_MANIFEST_SHA256:
            raise ValueError("V0.1 manifest dependency mismatch")
        if sha256(root / "training_tempo.schema.json") != manifest.schema_sha256:
            raise ValueError("training tempo schema hash mismatch")
        if (
            read_json(root / "training_tempo.schema.json")
            != TrainingTempoBundle.model_json_schema()
        ):
            raise ValueError("training tempo schema export is stale")
        for entry in manifest.files:
            if sha256(root / entry.filename) != entry.sha256:
                raise ValueError(f"training tempo release hash mismatch: {entry.filename}")
    return bundle


def verify_source_originals(bundle: TrainingTempoBundle, directory: str | Path) -> dict[str, int]:
    """Explicit source-archive audit. A missing/mutated claimed download is an error."""
    root = Path(directory)
    verified = 0
    unavailable = 0
    local = 0
    for source in bundle.sources.records:
        if source.retrieval_method == "downloaded":
            assert source.local_filename is not None
            path = root / source.local_filename
            if not path.is_file() or sha256(path) != source.content_sha256:
                raise ValueError(f"source original missing or hash mismatch: {source.source_id}")
            verified += 1
        elif source.retrieval_method == "indexed_official_text":
            unavailable += 1
        else:
            local += 1
    return {
        "verified_downloads": verified,
        "unavailable_originals": unavailable,
        "local_notes": local,
    }
