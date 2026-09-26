"""Destructive target rejection and real public restart evidence."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from plotsrv_examples.support.storage import OwnedStore
from plotsrv_examples.workspace import create, WorkspaceError

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def owned(tmp_path):
    repo = tmp_path / "examples"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "plotsrv-examples"\n')
    (repo / ".git").mkdir()
    return OwnedStore(repo, create(repo))


class NoLaunch:
    def start(self, *args, **kwargs):
        pytest.fail("Rejected target reached process launch")


@pytest.mark.parametrize("target", ["repository", "parent", "neighbor"])
def test_unowned_clear_rejected_before_launch(owned, target):
    neighbor = create(owned.repository)
    sentinel = neighbor / "sentinel"
    sentinel.write_text("preserve")
    root = {"repository": owned.repository, "parent": owned.run.parent,
            "neighbor": neighbor}[target]
    with pytest.raises(WorkspaceError):
        owned.command(NoLaunch(), {}, "clear", root=root)
    assert sentinel.read_text() == "preserve"


@pytest.mark.parametrize("replacement", ["directory", "symlink", "nested-link", "hardlink", "marker"])
def test_substitution_rejected_before_launch(owned, replacement):
    outside = owned.repository.parent / "external"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_text("preserve")
    if replacement in ("directory", "symlink"):
        owned.root.rename(owned.run / "original")
        if replacement == "directory":
            owned.root.mkdir()
        else:
            owned.root.symlink_to(outside, target_is_directory=True)
    elif replacement == "nested-link":
        (owned.root / "link").symlink_to(outside, target_is_directory=True)
    elif replacement == "hardlink":
        os.link(sentinel, owned.root / "payload")
    else:
        (owned.run / ".plotsrv-examples-owner.json").write_text("{}")
    with pytest.raises((WorkspaceError, OSError)):
        owned.command(NoLaunch(), {}, "clear")
    assert sentinel.read_text() == "preserve"


def test_store_never_adopts_existing_directory(owned):
    with pytest.raises(FileExistsError):
        OwnedStore(owned.repository, owned.run)


@pytest.mark.parametrize("fault", [False, True])
def test_storage_history_public_workflow(fault):
    completed = subprocess.run([sys.executable, "-m", "plotsrv_examples", "run", "storage-history"]
        + (["--fault", "missing-evidence"] if fault else []), cwd=ROOT,
        capture_output=True, text=True, timeout=65)
    result = json.loads(completed.stdout)
    assert completed.returncode == (1 if fault else 0), completed.stdout + completed.stderr
    assert result["success"] is not fault
    assert result["owned_children_reaped"]
    assert result["manual_status"] == "pending"
    if fault:
        assert "evidence missing" in result["error"]
        assert "evidence" not in result
    else:
        evidence = result["evidence"]
        assert evidence["versions"] == [2, 3]
        assert len(set(evidence["retained_ids"])) == 2
        assert evidence["persisted_timestamp"] == evidence["restored_timestamp"]
        assert evidence["restart_arrivals"] == 0
        assert evidence["restart_snapshots_unchanged"]
        assert evidence["unowned_clear_rejected"] and evidence["owned_clear_verified"]
        assert evidence["freshness"] == ["ok", "warn", "error"]
