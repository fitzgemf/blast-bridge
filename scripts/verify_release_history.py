"""Read-only V0.1/V0.2 Git and archive integrity audit; works with unstaged V0.3."""

import argparse
import importlib.metadata
import json
import subprocess
from pathlib import Path

from blastbridge.data.priors import TEMPO_COMMIT, load_prior_design
from blastbridge.data.reference import load_reference_bundle
from blastbridge.data.training_tempo import (
    BASELINE_COMMIT,
    load_training_tempo,
    sha256,
    verify_source_originals,
)

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-archive", action="store_true")
    args = parser.parse_args()
    totals = {}
    for tag, commit in (("v0.1.0", BASELINE_COMMIT), ("v0.2.0", TEMPO_COMMIT)):
        if git("cat-file", "-t", tag).strip() != b"tag":
            raise ValueError(f"{tag} must be an annotated tag")
        if git("rev-parse", f"{tag}^{{commit}}").decode().strip() != commit:
            raise ValueError(f"{tag} moved")
        names = git("ls-tree", "-r", "--name-only", tag, "data/reference").decode().splitlines()
        paths = [name for name in names if name.endswith(".json")]
        for name in paths:
            if (ROOT / name).read_bytes() != git("show", f"{tag}:{name}"):
                raise ValueError(f"tagged release bytes changed: {name}")
        totals[tag] = {"commit": commit, "identical_json_files": len(paths)}
    baseline_files = git("ls-tree", "-r", "--name-only", "v0.2.0").decode().splitlines()
    # Explicit paths exclude new V0.3 artifacts even after those files are staged.
    git("diff", "--exit-code", "v0.2.0", "--", *baseline_files)
    git("merge-base", "--is-ancestor", BASELINE_COMMIT, TEMPO_COMMIT)
    git("fsck", "--full")
    git("diff", "--check")
    load_prior_design(ROOT / "data/reference")
    pins = 0
    for line in (ROOT / "requirements-dev.lock.txt").read_text().splitlines():
        if "==" in line and not line.startswith("#"):
            name, version = line.split("==")
            if importlib.metadata.version(name) != version:
                raise ValueError(f"dependency lock mismatch: {name}")
            pins += 1
    archive: dict[str, object] | None = None
    if args.source_archive:
        sources = load_reference_bundle(ROOT / "data/reference").sources.records
        downloads = ROOT / "research/sources/downloads"
        verified = 0
        for source in sources:
            if source.retrieval_method == "downloaded":
                matches = [
                    p
                    for p in downloads.glob(f"{source.source_id}.*")
                    if sha256(p) == source.content_sha256
                ]
                if len(matches) != 1:
                    raise ValueError(
                        f"baseline original missing or hash mismatch: {source.source_id}"
                    )
                verified += 1
        archive = {
            "v01_verified": verified,
            "v01_unavailable": sum(s.content_sha256 is None for s in sources),
            "v02": verify_source_originals(
                load_training_tempo(ROOT / "data/reference"),
                ROOT / "research/sources/tempo-downloads",
            ),
        }
    print(
        json.dumps(
            {
                "tags": totals,
                "unchanged_v02_tracked_files": len(baseline_files),
                "development_pins_verified": pins,
                "source_archive": archive,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
