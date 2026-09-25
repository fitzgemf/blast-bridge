"""Load V0.3 design artifacts against frozen V0.1/V0.2 release bytes."""

from pathlib import Path

from blastbridge.data.reference import load_reference_bundle, read_json
from blastbridge.data.training_tempo import load_training_tempo, sha256
from blastbridge.models.priors import PriorDesignBundle, PriorManifest

TEMPO_COMMIT = "4182044e57177d77e643b6b273dbee03cc433eeb"
TEMPO_MANIFEST_SHA256 = "7f18f8fa64873e908499c7e21ed4f22d7293c03b1034f197d3709b32b6a17e6c"
PRIOR_FILES = {"priors": "prior_definitions.json", "gaps": "research_gaps.json"}
PRIOR_RELEASE_FILES = (
    *PRIOR_FILES.values(),
    "prior_design.schema.json",
    "prior_design_manifest.json",
)


def load_prior_design(directory: str | Path, *, verify_manifest: bool = True) -> PriorDesignBundle:
    root = Path(directory)
    tempo = load_training_tempo(root)
    if sha256(root / "training_tempo_manifest.json") != TEMPO_MANIFEST_SHA256:
        raise ValueError("V0.2 baseline manifest changed")
    bundle = PriorDesignBundle.model_validate(
        {key: read_json(root / name) for key, name in PRIOR_FILES.items()}
    )
    bundle.validate_evidence(tempo, load_reference_bundle(root))
    if verify_manifest:
        manifest = PriorManifest.model_validate(read_json(root / "prior_design_manifest.json"))
        if manifest.baseline_commit != TEMPO_COMMIT:
            raise ValueError("V0.2 baseline commit mismatch")
        if manifest.baseline_manifest_sha256 != TEMPO_MANIFEST_SHA256:
            raise ValueError("V0.2 baseline manifest dependency mismatch")
        schema = root / "prior_design.schema.json"
        if sha256(schema) != manifest.schema_sha256:
            raise ValueError("prior design schema hash mismatch")
        if read_json(schema) != PriorDesignBundle.model_json_schema():
            raise ValueError("prior design schema export is stale")
        for entry in manifest.files:
            if sha256(root / entry.filename) != entry.sha256:
                raise ValueError(f"prior design release hash mismatch: {entry.filename}")
    return bundle
