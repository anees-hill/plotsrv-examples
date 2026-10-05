"""Shared bounded demo publishing and resumable example history."""

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
            }
            if not wanted:
                continue
            with prepared(factory, revision) as items:
                for view, label, obj, kind in items:
                    if view in wanted:
                        title = self.seed_label(label, revision)
                        # Recognise old bundles as well as the new business labels.
                        # History confirms a write even if the journal save failed.
                        if not any(
                            row.get("label") == title
                            or f"Illustrative revision {revision}/3" in (row.get("label") or "")
                            for row in histories[view]
                        ):
                            self.publish(view, title, obj, kind, snapshot=True)
                        if revision == 3:
                            completed.append(view)
                            self.save()
        self.save()

    def seed_label(self, label, revision):
        if revision == 3:
            return label
        period = {
            "retail": ("through December 2025", "through March 2026"),
            "live_import": ("Initial validation", "Corrections applied"),
        }[self.demo][revision - 1]
        return f"{label} · {period}"

    def current(self, factory):
        with prepared(factory, 3) as items:
            for view, label, obj, kind in items:
                self.publish(
                    view,
                    label,
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
        # Historical labels describe the business period; capture times are real.
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
