"""Store commands restricted to a freshly created, identity-verified owned store."""

from contextlib import contextmanager
import os
from pathlib import Path
import stat
import sys

import yaml

from ..workspace import WorkspaceError, owned_directory, _flags, _identity, _walk
from .lifecycle import LifecycleError


def _reject_hardlinks(fd):
    for name in os.listdir(fd):
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise WorkspaceError("Multiply linked store file rejected")
        if stat.S_ISDIR(info.st_mode):
            child = os.open(name, _flags(), dir_fd=fd)
            try:
                _reject_hardlinks(child)
            finally:
                os.close(child)


class OwnedStore:
    def __init__(self, repository, run):
        self.repository, self.run = Path(repository), Path(run)
        with owned_directory(self.repository, self.run) as fd:
            os.mkdir("store", mode=0o700, dir_fd=fd)  # Never adopt an existing store.
            child = os.open("store", _flags(), dir_fd=fd)
            try:
                self.identity = _identity(child)
            finally:
                os.close(child)
        self.root = self.run / "store"
        self.writers = []

    @contextmanager
    def verified(self, root=None):
        if root is not None and Path(root) != self.root:
            raise WorkspaceError("Unowned store rejected")
        with owned_directory(self.repository, self.run) as fd:
            child = os.open("store", _flags(), dir_fd=fd)
            try:
                if _identity(child) != self.identity:
                    raise WorkspaceError("Store identity changed")
                _walk(child, self.identity[0])
                _reject_hardlinks(child)
                yield
            finally:
                os.close(child)

    @contextmanager
    def configuration(self, *, enabled=True):
        # No caller-supplied YAML, inherited instance, or arbitrary root can select
        # the destructive target. Unique exclusive config is removed after use.
        from uuid import uuid4
        with self.verified():
            path = self.run / ("storage-" + uuid4().hex + ".yml")
            settings = {"storage-settings": {"enabled": enabled,
                "root_dir": str(self.root), "default_keep_last": 2,
                "default_min_store_interval": None,
                "latest": {"enabled": True, "restore_on_startup": True, "restore_scope": "all"}},
                "freshness-settings": {"enabled": True, "expected_every": "2s",
                    "warn_after": "3s", "overdue_after": "5s"}}
            with path.open("x", encoding="utf-8") as stream:
                stream.write(yaml.safe_dump(settings))
            try:
                yield path
            finally:
                path.unlink()

    def command(self, owner, env, action, *, view=None, root=None):
        if action not in ("stats", "list", "clear"):
            raise WorkspaceError("Unsupported owned store command")
        with self.verified(root):
            if any(c.process.poll() is None for c in self.writers):
                raise LifecycleError("Stop owned storage writers before store commands")
            with self.configuration() as config:
                args = [sys.executable, "-m", "plotsrv.cli_entry", "store",
                        "--config", str(config), action]
                if view is not None:
                    if action == "stats":
                        raise WorkspaceError("stats does not accept a view")
                    args += ["--view", view]
                if action == "clear":
                    args += (["--all"] if view is None else []) + ["--yes"]
                clean_env = {k: v for k, v in env.items() if not k.startswith("PLOTSRV_")}
                child = owner.start(args, cwd=self.run, env=clean_env, label="store-" + action)
                owner.wait(child, timeout=10)
                return child.output.decode("utf-8", errors="replace")
