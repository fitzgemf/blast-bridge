from pathlib import Path

from scripts.verify_release_history import ROOT, git, validate_tagged_release


def test_historical_release_audit_uses_tagged_tree_after_readme_changes(tmp_path: Path):
    tagged_readme = git("show", "v0.2.0:README.md")
    current_readme = (ROOT / "README.md").read_bytes()
    assert tagged_readme != current_readme

    result = validate_tagged_release("v0.2.0", tmp_path)

    assert result["commit"] == "4182044e57177d77e643b6b273dbee03cc433eeb"
    assert result["tempo_evidence"] == 40
