"""Enforce the separation between fictional and real approval types."""

from pathlib import Path

import pytest


def test_approval_types_are_not_substitutable(tmp_path, monkeypatch):
    try:
        from mypy import api
    except ImportError:
        pytest.skip("mypy is unavailable; install the dev dependencies")

    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("MYPYPATH", str(root / "src"))
    stdout, stderr, exit_code = api.run(
        [
            "--config-file",
            str(root / "pyproject.toml"),
            "--strict",
            "--warn-unused-ignores",
            "--follow-imports=silent",
            "--cache-dir",
            str(tmp_path / "mypy-cache"),
            str(root / "tests" / "typing_fictional_approval.py"),
        ]
    )
    assert exit_code == 0, stdout + stderr
