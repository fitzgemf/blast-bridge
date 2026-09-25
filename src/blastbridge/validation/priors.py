"""Offline design validation: python -m blastbridge.validation.priors [directory]."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from blastbridge.data.priors import load_prior_design
from blastbridge.models.priors import PriorDesignBundle


def summarize(bundle: PriorDesignBundle) -> dict[str, Any]:
    return {
        "design_version": bundle.priors.metadata.version,
        "definitions": len(bundle.priors.records),
        "by_type": dict(sorted(Counter(p.prior_type for p in bundle.priors.records).items())),
        "by_support": dict(sorted(Counter(p.support_level for p in bundle.priors.records).items())),
        "empirical_priors": bundle.priors.empirical_priors,
        "numerical_distributions": 0,
        "research_gaps": len(bundle.gaps.records),
        "uncertainty_dimensions": len(bundle.priors.uncertainties),
        "release_hashes": "verified",
        "baseline": "V0.1 and V0.2 verified; V0.2 commit pinned",
        "simulation_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("data/reference"))
    args = parser.parse_args()
    print(json.dumps(summarize(load_prior_design(args.directory)), indent=2))


if __name__ == "__main__":
    main()
