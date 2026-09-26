"""Owned, quiescent run directories. Cleanup retains the ownership marker.

Descriptor-relative traversal never follows symlinks. Unsupported platforms fail
closed. Stop all producers before cleanup; this is not a hostile-user sandbox.
"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import tomllib
from uuid import uuid4


MARKER = ".plotsrv-examples-owner.json"
RUNS = ".plotsrv-runs"


class WorkspaceError(ValueError):
    """The requested path does not satisfy the ownership contract."""


def _flags():
    required = (os.open, os.stat, os.mkdir, os.unlink, os.rmdir)
    if (not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY")
            or not all(fn in os.supports_dir_fd for fn in required)
            or os.listdir not in os.supports_fd):
        raise WorkspaceError("Safe descriptor-relative workspaces are unsupported")
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


@contextmanager
def _directory(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise WorkspaceError("Use an absolute path without parent traversal")
    fd = os.open(path.anchor, _flags())
    try:
        for part in path.parts[1:]:
            child = os.open(part, _flags(), dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _read(fd, name):
    handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(handle, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise WorkspaceError(f"Not a regular, singly linked file: {name}")
        data = source.read(65537)
        if len(data) > 65536:
            raise WorkspaceError(f"Oversized metadata: {name}")
        return data


def _repository(fd):
    project = tomllib.loads(_read(fd, "pyproject.toml").decode())
    if project.get("project", {}).get("name") != "plotsrv-examples":
        raise WorkspaceError("Not a plotsrv-examples repository")
    info = os.stat(".git", dir_fd=fd, follow_symlinks=False)
    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
        raise WorkspaceError("Invalid repository Git boundary")


def _identity(fd):
    info = os.fstat(fd)
    return [info.st_dev, info.st_ino]


def _owner(repo, repo_fd, run_fd, name):
    return {"format": "plotsrv-examples/workspace-v1", "repository": str(repo),
            "repository_identity": _identity(repo_fd), "run": name,
            "directory_identity": _identity(run_fd)}


def create(repository: Path) -> Path:
    """Create a fresh run; never adopt an existing directory."""
    repo = Path(repository)
    with _directory(repo) as repo_fd:
        _repository(repo_fd)
        try:
            os.mkdir(RUNS, mode=0o700, dir_fd=repo_fd)
        except FileExistsError:
            pass
        runs_fd = os.open(RUNS, _flags(), dir_fd=repo_fd)
        try:
            if _identity(runs_fd)[0] != _identity(repo_fd)[0]:
                raise WorkspaceError("Run root crosses a filesystem boundary")
            name = "run-" + uuid4().hex
            os.mkdir(name, mode=0o700, dir_fd=runs_fd)
            run_fd = os.open(name, _flags(), dir_fd=runs_fd)
            try:
                marker_fd = os.open(MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                                    | os.O_NOFOLLOW, 0o600, dir_fd=run_fd)
                with os.fdopen(marker_fd, "w") as marker:
                    json.dump(_owner(repo, repo_fd, run_fd, name), marker)
                    marker.write("\n")
            finally:
                os.close(run_fd)
        finally:
            os.close(runs_fd)
    return repo / RUNS / name


def _walk(fd, device, *, delete=False, root=False):
    for name in os.listdir(fd):
        if root and name == MARKER:
            continue
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if info.st_dev != device or stat.S_ISLNK(info.st_mode):
            raise WorkspaceError(f"Symlink or filesystem boundary rejected: {name}")
        if stat.S_ISDIR(info.st_mode):
            child = os.open(name, _flags(), dir_fd=fd)
            try:
                if _identity(child) != [info.st_dev, info.st_ino]:
                    raise WorkspaceError("Directory changed during traversal")
                _walk(child, device, delete=delete)
            finally:
                os.close(child)
            if delete:
                os.rmdir(name, dir_fd=fd)
        elif stat.S_ISREG(info.st_mode):
            if delete:
                os.unlink(name, dir_fd=fd)
        else:
            raise WorkspaceError(f"Special file rejected: {name}")


@contextmanager
def owned_directory(repository: Path, run: Path):
    """Yield a verified directory descriptor for bounded run operations."""
    repo, run = Path(repository), Path(run)
    if run.parent != repo / RUNS or not run.name.startswith("run-"):
        raise WorkspaceError("Cleanup requires a direct child of the run directory")
    with _directory(repo) as repo_fd:
        _repository(repo_fd)
        with _directory(run) as run_fd:
            if _identity(run_fd)[0] != _identity(repo_fd)[0]:
                raise WorkspaceError("Run crosses a filesystem boundary")
            actual = json.loads(_read(run_fd, MARKER))
            if actual != _owner(repo, repo_fd, run_fd, run.name):
                raise WorkspaceError("Workspace ownership marker does not match")
            yield run_fd


def clean(repository: Path, run: Path) -> None:
    """Clear a verified run's contents, retaining its directory and marker."""
    with owned_directory(repository, run) as run_fd:
        device = os.fstat(run_fd).st_dev
        # Reject unsafe existing entries before removing any ordinary files.
        _walk(run_fd, device, root=True)
        _walk(run_fd, device, delete=True, root=True)
