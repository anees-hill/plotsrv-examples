"""Shared bounded demo publishing, resumable example history and public source views."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import ProxyHandler, build_opener

import yaml

ROOT = Path(__file__).resolve().parent
SOURCE_FILES = {
    "retail": ("app.py", "generate_data.py", "plotsrv.yml"),
    "live_import": ("follow.py", "generate_events.py", "reports.py", "plotsrv.yml"),
    "scan_audit": ("run_audit.py", "plotsrv.yml"),
}
PREFIXES = {"retail": "retail", "live_import": "live", "scan_audit": "scans"}


def source_id(demo, filename):
    return PREFIXES[demo] + ":source:" + filename.replace(".", "-")


def public_sources(demo):
    """Read an explicit set of source files; never resolve environment variables."""
    for filename in (*SOURCE_FILES[demo], "publishing.py", "restore.py"):
        path = (
            ROOT / demo / filename
            if filename not in ("publishing.py", "restore.py")
            else ROOT / filename
        )
        # Deployment preserves the portable source config before relocating storage.
        if filename == "plotsrv.yml" and path.with_name("plotsrv.source.yml").is_file():
            path = path.with_name("plotsrv.source.yml")
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            raise ValueError(f"Invalid or oversized public source: {filename}")
        content = path.read_text()
        if filename.endswith(".yml"):
            validate_public_config(yaml.safe_load(content))
        yield source_id(demo, filename), filename, content


def validate_public_config(value):
    if isinstance(value, dict):
        for key, item in value.items():
            lower = str(key).lower()
            if (
                lower
                in {
                    "bearer_token",
                    "token",
                    "password",
                    "secret",
                    "api_key",
                    "authorization",
                }
                and item
            ):
                raise ValueError("Public config contains a literal credential")
            validate_public_config(item)
    elif isinstance(value, list):
        for item in value:
            validate_public_config(item)


class Publisher:
    def __init__(self, demo, *, state_dir=None):
        self.demo = demo
        config_path = Path(
            os.environ.get("PLOTSRV_CONFIG", ROOT / demo / "plotsrv.yml")
        )
        config = yaml.safe_load(config_path.read_text())
        self.base = config["publisher-settings"]["destination"]["url"].rstrip("/")
        parsed = urlsplit(self.base)
        if parsed.scheme != "http" or parsed.hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise ValueError(
                "Demo setup and snapshot verification require a loopback receiver"
            )
        self.opener = build_opener(ProxyHandler({}))
        self.directory = Path(state_dir or ".plotsrv/demo-publishing")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / (demo + "-v1.json")
        self.state = {}

    @contextmanager
    def locked(self):
        with (self.directory / (self.demo + ".lock")).open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.path.exists():
                if self.path.stat().st_size > 65536:
                    raise ValueError("Publisher state exceeds its bound")
                self.state = json.loads(self.path.read_text())
            yield self

    def save(self):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, sort_keys=True))
        temporary.replace(self.path)

    def read(self, route, **query):
        with self.opener.open(
            self.base + route + "?" + urlencode(query), timeout=5
        ) as response:
            body = response.read(1024 * 1024 + 1)
        if len(body) > 1024 * 1024:
            raise ValueError("Receiver metadata response exceeds its bound")
        return json.loads(body)

    def history(self, view):
        result = self.read("/history", view=view, limit=10)
        if not result.get("capability", {}).get("enabled"):
            raise RuntimeError(f"Snapshot storage is not enabled for {view}")
        return result["snapshots"]

    def present(self, view):
        try:
            return bool(self.read("/status", view=view).get("last_updated"))
        except HTTPError as error:
            if error.code == 404:
                return False
            raise

    def wait_snapshot(self, view, label, previous=()):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if any(
                row.get("label") == label and row["snapshot_id"] not in previous
                for row in self.history(view)
            ):
                return
            time.sleep(0.1)
        raise RuntimeError(f"Snapshot was not confirmed for {view}: {label}")

    def seeded(self, view_ids, factory):
        """Seed only missing revisions. Factories yield (id, label, object, kind)."""
        histories = {view: self.history(view) for view in view_ids}
        completed = self.state.setdefault("seeded", [])
        for view in view_ids:
            if view not in completed and any(
                "Illustrative revision 3/3" in (r.get("label") or "")
                for r in histories[view]
            ):
                completed.append(view)
        for revision in (1, 2, 3):
            wanted = {
                view
                for view in view_ids
                if view not in completed
                and not any(
                    f"Illustrative revision {revision}/3" in (row.get("label") or "")
                    for row in histories[view]
                )
            }
            if not wanted:
                continue
            with prepared(factory, revision) as items:
                for view, label, obj, kind in items:
                    if view in wanted:
                        title = f"{label} · Illustrative revision {revision}/3"
                        self.publish(view, title, obj, kind, snapshot=True)
                        if revision == 3:
                            completed.append(view)
                            self.save()
        self.save()

    def current(self, factory):
        with prepared(factory, 3) as items:
            for view, label, obj, kind in items:
                self.publish(
                    view,
                    label + " · Illustrative revision 3/3",
                    obj,
                    kind,
                    snapshot=True,
                )

    def publish(self, view, label, obj, kind, *, snapshot=False, section=None):
        import plotsrv as ps

        digest = fingerprint(obj, kind)
        hashes = self.state.setdefault("hashes", {})
        if (
            hashes.get(view) == digest
            and self.present(view)
            and (
                not snapshot or any(r.get("label") == label for r in self.history(view))
            )
        ):
            return
        # The label carries the seed revision; all snapshot timestamps are real.
        options = {
            "view_id": view,
            "label": label,
            "section": section
            or {
                "retail": "Northstar trading",
                "live_import": "Import operations",
                "scan_audit": "Document scan audit",
            }[self.demo],
            "launch_server": False,
            "async_": False,
        }
        if kind not in ("table", "plot"):
            options.update(kind="artifact", artifact_kind=kind)
        previous = (
            {row["snapshot_id"] for row in self.history(view)} if snapshot else set()
        )
        ps.publish_view(obj, **options)
        if not ps.flush_views(timeout=15):
            raise RuntimeError(f"Publication did not drain: {view}")
        if snapshot:
            self.wait_snapshot(view, label, previous)
        hashes[view] = digest
        self.save()

    def sources(self):
        for view, filename, content in public_sources(self.demo):
            self.publish(
                view,
                filename,
                content,
                "python" if filename.endswith(".py") else "text",
                section="Demo source code",
            )


def fingerprint(obj, kind):
    if kind == "plot":
        output = BytesIO()
        obj.savefig(output, format="png", dpi=105)
        raw = output.getvalue()
        if len(raw) > 1024**2:
            raise ValueError("Demo plot exceeds 1 MiB")
    elif kind == "table":
        if len(obj) > 1800 or len(obj.columns) > 20:
            raise ValueError("Demo table exceeds its bounds")
        raw = obj.to_json(orient="split", date_format="iso").encode()
    else:
        raw = (
            obj
            if isinstance(obj, str)
            else json.dumps(obj, sort_keys=True, allow_nan=False)
        ).encode()
        if len(raw) > 128 * 1024:
            raise ValueError("Demo artifact exceeds 128 KiB")
    return hashlib.sha256(raw).hexdigest()


def close_figure(obj):
    if hasattr(obj, "savefig"):
        import matplotlib.pyplot as plt

        plt.close(obj)


@contextmanager
def prepared(factory, revision):
    """Validate every payload before changing any view; always release figures."""
    items = []
    try:
        for item in factory(revision):
            items.append(item)
            fingerprint(item[2], item[3])
        yield items
    finally:
        for _, _, obj, _ in items:
            close_figure(obj)
