"""Offline command: python -m blastbridge.validation.training_tempo."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from blastbridge.data.training_tempo import load_training_tempo, verify_source_originals
from blastbridge.models.training_tempo import TrainingTempoBundle


def summarize(bundle: TrainingTempoBundle) -> dict[str, Any]:
    records = bundle.evidence.records
    return {
        "dataset_version": bundle.evidence.metadata.dataset_version,
        "evidence_records": len(records),
        "source_records": len(bundle.sources.records),
        "by_branch": dict(sorted(Counter(r.branch for r in records).items())),
        "by_component": dict(sorted(Counter(r.component for r in records).items())),
        "by_occupation": dict(
            sorted(Counter(o for r in records for o in r.occupation_ids).items())
        ),
        "occupation_unassigned": sum(not r.occupation_ids for r in records),
        "by_weapon": dict(sorted(Counter(w for r in records for w in r.weapon_system_ids).items())),
        "weapon_unassigned": sum(not r.weapon_system_ids for r in records),
        "by_evidence_type": dict(sorted(Counter(r.evidence_type for r in records).items())),
        "by_claim_kind": dict(sorted(Counter(r.claim.kind for r in records).items())),
        "by_representativeness": dict(
            sorted(Counter(r.representativeness for r in records).items())
        ),
        "original_retrieval": dict(
            sorted(Counter(s.retrieval_method for s in bundle.sources.records).items())
        ),
        "release_hashes": "verified",
        "baseline_reference": "0.1.0 unchanged",
        "count_interpretation": (
            "Linked occupation/platform counts overlap; records are not independent samples."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("data/reference"))
    parser.add_argument("--source-directory", type=Path)
    args = parser.parse_args()
    bundle = load_training_tempo(args.directory)
    result = summarize(bundle)
    if args.source_directory is not None:
        result["source_archive"] = verify_source_originals(bundle, args.source_directory)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
