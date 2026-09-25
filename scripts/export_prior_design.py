"""Explicit V0.3 schema/manifest export; does not regenerate or alter evidence."""

import argparse
import json
from pathlib import Path

from blastbridge.data.priors import (
    PRIOR_FILES,
    TEMPO_COMMIT,
    TEMPO_MANIFEST_SHA256,
    load_prior_design,
)
from blastbridge.data.training_tempo import sha256
from blastbridge.models.priors import PriorDesignBundle, PriorManifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", required=True)
    args = parser.parse_args()
    assert args.write
    root = Path(__file__).resolve().parents[1] / "data/reference"
    load_prior_design(root, verify_manifest=False)
    schema = root / "prior_design.schema.json"
    schema.write_text(
        json.dumps(PriorDesignBundle.model_json_schema(), indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest = PriorManifest.model_validate(
        {
            "version": "0.3.0",
            "files": [
                {"filename": name, "sha256": sha256(root / name)} for name in PRIOR_FILES.values()
            ],
            "schema_sha256": sha256(schema),
            "baseline_tag": "v0.2.0",
            "baseline_commit": TEMPO_COMMIT,
            "baseline_manifest_sha256": TEMPO_MANIFEST_SHA256,
        }
    )
    (root / "prior_design_manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    load_prior_design(root)
    print("V0.3 schema and manifest exported and verified; baseline evidence unchanged.")


if __name__ == "__main__":
    main()
