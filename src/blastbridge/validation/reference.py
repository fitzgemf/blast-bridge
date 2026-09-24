"""Offline command: python -m blastbridge.validation.reference [reference-directory]."""

import argparse
import json
from pathlib import Path

from blastbridge.data.reference import load_reference_bundle
from blastbridge.data.training_tempo import TEMPO_RELEASE_FILES, load_training_tempo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("data/reference"))
    args = parser.parse_args()
    bundle = load_reference_bundle(args.directory)
    tempo_paths = [args.directory / name for name in TEMPO_RELEASE_FILES]
    tempo_count = None
    if any(path.exists() for path in tempo_paths):
        # A partial V0.2 release is an error, never silently downgraded to V0.1.
        tempo_count = len(load_training_tempo(args.directory).evidence.records)
    print(
        json.dumps(
            {
                "source_registry_version": bundle.sources.metadata.dataset_version,
                "schema_version": bundle.sources.metadata.schema_version,
                "sources": len(bundle.sources.records),
                "weapons": len(bundle.weapons.records),
                "occupations": len(bundle.occupations.records),
                "relationships": len(bundle.relationships.records),
                "taxonomy_categories": len(bundle.taxonomy.records),
                "tier1_verified": sum(w.dod_tier1_status == "yes" for w in bundle.weapons.records),
                "tier1_unknown": sum(
                    w.dod_tier1_status == "unknown" for w in bundle.weapons.records
                ),
                "release_hashes": "verified",
                "training_tempo_evidence_records": tempo_count,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
