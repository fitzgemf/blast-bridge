"""Offline command: python -m blastbridge.validation.reference [reference-directory]."""

import argparse
import json
from pathlib import Path

from blastbridge.data.reference import load_reference_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("data/reference"))
    args = parser.parse_args()
    bundle = load_reference_bundle(args.directory)
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
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
