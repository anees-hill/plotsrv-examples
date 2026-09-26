"""Reproducibility, upper bounds, and owned cleanup of generated fixture data."""

import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from plotsrv_examples.fixtures import MAX_LINES, MAX_ROWS, generate
from plotsrv_examples.workspace import MARKER, RUNS, clean


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "examples"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "plotsrv-examples"\n')
    (root / ".git").mkdir()
    return root


def contents(run):
    return {p.name: p.read_bytes() for p in run.iterdir() if p.name != MARKER}


def test_reproducible_manifest_and_cleanup(repo):
    first = generate(repo, seed=123, rows=41, lines=12)
    second = generate(repo, seed=123, rows=41, lines=12)
    assert first != second
    assert contents(first) == contents(second)
    manifest = json.loads((first / "fixtures.json").read_text())
    assert manifest["seed"] == 123
    assert manifest["large_rows"] == 41
    assert manifest["lines"] == 12
    assert len(manifest["files"]) == 5
    for name, evidence in manifest["files"].items():
        data = (first / name).read_bytes()
        assert evidence == {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        assert b"\r" not in data
    for name, count in (("100_20.csv", 100), ("1000_20.csv", 1000), ("6000_20.csv", 41)):
        with (first / name).open(newline="") as source:
            rows = list(csv.reader(source))
        assert len(rows) == count + 1
        assert all(len(row) == 20 for row in rows)
    text = (first / "long_text.txt").read_text().splitlines()
    assert len(text) == 12
    assert text[0] == "fixture line 00000: value=0123"
    assert text[-1] == "fixture line 00011: value=0464"
    neighbor = contents(second)
    clean(repo, first)
    assert list(first.iterdir()) == [first / MARKER]
    assert contents(second) == neighbor


def test_seed_changes_data(repo):
    first = generate(repo, seed=0, rows=1, lines=1)
    second = generate(repo, seed=1, rows=1, lines=1)
    assert (first / "6000_20.csv").read_bytes() != (second / "6000_20.csv").read_bytes()


@pytest.mark.parametrize("kwargs", [
    {"rows": 0}, {"rows": MAX_ROWS + 1}, {"rows": True}, {"rows": 1.5},
    {"lines": 0}, {"lines": MAX_LINES + 1}, {"seed": -1}, {"seed": 2**32},
])
def test_invalid_bounds_create_no_state(repo, kwargs):
    with pytest.raises(ValueError):
        generate(repo, **kwargs)
    assert not (repo / RUNS).exists()


def test_maximum_generation_is_bounded(repo):
    run = generate(repo, seed=2**32 - 1, rows=MAX_ROWS, lines=MAX_LINES)
    assert sum(p.stat().st_size for p in run.iterdir()) < 16 * 1024 * 1024
    with (run / "6000_20.csv").open() as source:
        assert sum(1 for _ in source) == MAX_ROWS + 1
    clean(repo, run)


def test_cli_generation_and_unowned_cleanup_rejection(repo):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src")}
    command = [sys.executable, "-B", "-m", "plotsrv_examples"]
    result = subprocess.run(command + ["fixtures-create", "--rows", "3", "--lines", "2"],
                            cwd=repo, env=env, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    run = Path(result.stdout.strip())
    assert run.parent == repo / RUNS
    rejected = subprocess.run(command + ["workspace-clean", str(repo)], cwd=repo,
                              env=env, text=True, capture_output=True, timeout=30)
    assert rejected.returncode == 2
    assert "Workspace rejected" in rejected.stderr
    assert (repo / "pyproject.toml").is_file()
    cleaned = subprocess.run(command + ["workspace-clean", str(run)], cwd=repo,
                             env=env, capture_output=True, timeout=30)
    assert cleaned.returncode == 0
    assert list(run.iterdir()) == [run / MARKER]
