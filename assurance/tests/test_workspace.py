"""Filesystem boundary cases using disposable repositories and sentinel files."""

import os

import pytest

from plotsrv_examples.workspace import MARKER, RUNS, WorkspaceError, clean, create


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "examples"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "plotsrv-examples"\n')
    (root / ".git").mkdir()
    return root


def test_owned_cleanup_preserves_neighbors_and_marker(repo):
    run = create(repo)
    neighbor = create(repo)
    sentinel = neighbor / "sentinel"
    sentinel.write_text("keep")
    marker = (run / MARKER).read_bytes()
    (run / "nested").mkdir()
    (run / "nested/data").write_text("generated")
    (run / "config.yml").write_text("generated")
    clean(repo, run)
    clean(repo, run)  # Idempotent, without removing its ownership boundary.
    assert list(run.iterdir()) == [run / MARKER]
    assert (run / MARKER).read_bytes() == marker
    assert sentinel.read_text() == "keep"


@pytest.mark.parametrize("target", ["repository", "parent", "runs", "outside", "unowned"])
def test_unowned_cleanup_rejected(repo, target):
    create(repo)
    unowned = repo / RUNS / "run-unowned"
    unowned.mkdir()
    targets = {"repository": repo, "parent": repo.parent,
               "runs": repo / RUNS, "outside": repo.parent / "outside",
               "unowned": unowned}
    (unowned / "sentinel").write_text("keep")
    with pytest.raises((WorkspaceError, OSError)):
        clean(repo, targets[target])
    assert (unowned / "sentinel").read_text() == "keep"


@pytest.mark.parametrize("change", ["missing", "malformed", "copied", "symlink"])
def test_invalid_marker_rejected(repo, change):
    run, other = create(repo), create(repo)
    marker = run / MARKER
    if change == "missing":
        marker.unlink()
    elif change == "malformed":
        marker.write_text("{}")
    elif change == "copied":
        marker.write_bytes((other / MARKER).read_bytes())
    else:
        marker.unlink()
        marker.symlink_to(other / MARKER)
    (run / "sentinel").write_text("keep")
    with pytest.raises((WorkspaceError, OSError)):
        clean(repo, run)
    assert (run / "sentinel").read_text() == "keep"


@pytest.mark.parametrize("destination", ["directory", "file", "missing"])
def test_nested_symlinks_rejected_before_deletion(repo, destination):
    run = create(repo)
    external = repo.parent / "outside"
    external.mkdir()
    (external / "sentinel").write_text("keep")
    targets = {"directory": external, "file": external / "sentinel",
               "missing": external / "missing"}
    (run / "ordinary").write_text("keep on rejection")
    (run / "nested").mkdir()
    (run / "nested/link").symlink_to(targets[destination])
    with pytest.raises(WorkspaceError):
        clean(repo, run)
    assert (external / "sentinel").read_text() == "keep"
    assert (run / "ordinary").read_text() == "keep on rejection"


def test_symlink_run_and_ancestor_rejected(repo):
    run = create(repo)
    link = repo / RUNS / "run-link"
    link.symlink_to(run, target_is_directory=True)
    with pytest.raises(OSError):
        clean(repo, link)
    alias = repo.parent / "alias"
    alias.symlink_to(repo, target_is_directory=True)
    with pytest.raises(OSError):
        create(alias)
    with pytest.raises(OSError):
        clean(alias, alias / RUNS / run.name)


def test_symlink_runs_root_rejected(repo):
    outside = repo.parent / "outside"
    outside.mkdir()
    (repo / RUNS).symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        create(repo)
    assert list(outside.iterdir()) == []


def test_parent_traversal_rejected(repo):
    run = create(repo)
    with pytest.raises(WorkspaceError):
        clean(repo, run / ".." / run.name)


def test_moved_run_rejected(repo):
    run = create(repo)
    renamed = run.with_name("run-renamed")
    run.rename(renamed)
    with pytest.raises(WorkspaceError):
        clean(repo, renamed)


def test_wrong_repository_rejected(repo):
    (repo / "pyproject.toml").write_text('[project]\nname = "plotsrv"\n')
    with pytest.raises(WorkspaceError):
        create(repo)
    assert not (repo / RUNS).exists()


def test_replaced_directory_cannot_reuse_marker(repo):
    run = create(repo)
    marker = (run / MARKER).read_bytes()
    run.rename(run.with_name("run-original"))
    run.mkdir()
    (run / MARKER).write_bytes(marker)
    (run / "sentinel").write_text("keep")
    with pytest.raises(WorkspaceError):
        clean(repo, run)
    assert (run / "sentinel").read_text() == "keep"


def test_special_file_rejected_before_deletion(repo):
    run = create(repo)
    (run / "sentinel").write_text("keep")
    os.mkfifo(run / "pipe")
    with pytest.raises(WorkspaceError):
        clean(repo, run)
    assert (run / "sentinel").read_text() == "keep"


def test_unsupported_platform_fails_closed(repo, monkeypatch):
    monkeypatch.setattr(os, "supports_dir_fd", set())
    with pytest.raises(WorkspaceError):
        create(repo)
    assert not (repo / RUNS).exists()
