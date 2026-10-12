"""Verify immutable V0.1/V0.2/V0.3 tagged trees and optional source archives."""

import argparse
import importlib.metadata
import json
import subprocess
import tempfile
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
V03_COMMIT = "8818adb392ac840baee5d627f4a7e48378cf6ed7"
RELEASES = (
    ("v0.1.0", BASELINE_COMMIT),
    ("v0.2.0", TEMPO_COMMIT),
    ("v0.3.0", V03_COMMIT),
)


def git(*args: str, cwd: Path = ROOT) -> bytes:
    return subprocess.check_output(["git", *args], cwd=cwd)


def extract_reference_tree(tag: str, destination: Path) -> Path:
    """Extract only the tagged reference tree; never substitute current files."""
    root = destination / tag / "data" / "reference"
    names = git("ls-tree", "-r", "--name-only", tag, "--", "data/reference").decode().splitlines()
    if not names:
        raise ValueError(f"{tag} has no data/reference tree")
    for name in names:
        if not name.startswith("data/reference/"):
            raise ValueError(f"unexpected release path: {name}")
        relative = Path(name).relative_to("data/reference")
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git("show", f"{tag}:{name}"))
    return root


def validate_tagged_release(tag: str, destination: Path) -> dict[str, object]:
    """Validate release artifacts from a Git tag's own tree, independent of HEAD."""
    if git("cat-file", "-t", tag).strip() != b"tag":
        raise ValueError(f"{tag} must be an annotated tag")
    expected = dict(RELEASES).get(tag)
    if expected is None or git("rev-parse", f"{tag}^{{commit}}").decode().strip() != expected:
        raise ValueError(f"{tag} is not at its expected immutable release commit")
    reference_root = extract_reference_tree(tag, destination)
    if tag == "v0.1.0":
        bundle = load_reference_bundle(reference_root)
        return {
            "commit": expected,
            "json_files": _json_file_count(tag),
            "sources": len(bundle.sources.records),
        }
    if tag == "v0.2.0":
        bundle = load_training_tempo(reference_root)
        return {
            "commit": expected,
            "json_files": _json_file_count(tag),
            "tempo_evidence": len(bundle.evidence.records),
        }
    bundle = load_prior_design(reference_root)
    return {
        "commit": expected,
        "json_files": _json_file_count(tag),
        "prior_definitions": len(bundle.priors.records),
    }


def _json_file_count(tag: str) -> int:
    names = git("ls-tree", "-r", "--name-only", tag, "--", "data/reference").decode().splitlines()
    return sum(name.endswith(".json") for name in names)


def verify_v02_snapshot_unchanged() -> int:
    """Check V0.2 files against the V0.3 tagged tree, not the moving worktree."""
    baseline_files = git("ls-tree", "-r", "--name-only", "v0.2.0").decode().splitlines()
    git("diff", "--exit-code", "v0.2.0", "v0.3.0", "--", *baseline_files)
    git("merge-base", "--is-ancestor", BASELINE_COMMIT, TEMPO_COMMIT)
    return len(baseline_files)


def verify_development_pins() -> int:
    pins = 0
    for line in (ROOT / "requirements-dev.lock.txt").read_text().splitlines():
        if "==" in line and not line.startswith("#"):
            name, version = line.split("==")
            if importlib.metadata.version(name) != version:
                raise ValueError(f"dependency lock mismatch: {name}")
            pins += 1
    return pins


def verify_source_archive() -> dict[str, object]:
    """Match currently archived source bytes to source records in tagged trees."""
    with tempfile.TemporaryDirectory(prefix="blastbridge-release-audit-") as temporary:
        base = Path(temporary)
        v01 = load_reference_bundle(extract_reference_tree("v0.1.0", base / "v01-source"))
        v02 = load_training_tempo(extract_reference_tree("v0.2.0", base / "v02-source"))
        downloads = ROOT / "research" / "sources" / "downloads"
        v01_verified = 0
        v01_unavailable = 0
        for source in v01.sources.records:
            if source.retrieval_method == "downloaded":
                matches = [
                    path
                    for path in downloads.glob(f"{source.source_id}.*")
                    if sha256(path) == source.content_sha256
                ]
                if len(matches) != 1:
                    raise ValueError(
                        f"V0.1 source archive missing/hash mismatch: {source.source_id}"
                    )
                v01_verified += 1
            elif source.content_sha256 is None:
                v01_unavailable += 1
        return {
            "v01_verified": v01_verified,
            "v01_unavailable": v01_unavailable,
            "v02": verify_source_originals(v02, ROOT / "research" / "sources" / "tempo-downloads"),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-archive", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="blastbridge-release-audit-") as temporary:
        releases = {tag: validate_tagged_release(tag, Path(temporary)) for tag, _ in RELEASES}
    git("fsck", "--full")
    git("diff", "--check")
    pins = verify_development_pins()
    report = {
        "tagged_releases": releases,
        "v02_tracked_files_unchanged_in_v03": verify_v02_snapshot_unchanged(),
        "development_pins_verified": pins,
        "worktree_documentation_is_not_used_for_release_validation": True,
        "source_archive": verify_source_archive() if args.source_archive else None,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
