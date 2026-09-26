"""Owned gallery lifecycle and receiver evidence; publication lives in examples/."""

import io
import json
import math
import os
from pathlib import Path
import sys
import time

from PIL import Image

from ..support.lifecycle import (
    LifecycleError, Processes, _json, _response, available_port,
    interruption_cleanup, require_candidate, wait_evidence,
)
from ..workspace import create, owned_directory


ARTIFACTS = {
    "example-file": "ExampleService",
    "example-direct": "rows_processed", "example-function": "Earth",
    "example-class": "Hubble", "example-nested": "nitrogen",
    "example-mixed": "heterogeneous example", "example-array": "array",
    "example-async": "completed", "example-exception-explicit": "Explicit example failure",
    "example-exception-captured": "Captured example failure",
    "example-exception-decorated": "Decorated example failure",
    "gallery-text": "Gallery text sentinel", "gallery-markdown": "Gallery markdown sentinel",
    "gallery-html": "Gallery HTML sentinel",
}


def verify(owner, receiver, port, *, timeout=5):
    for view_id, sentinel in ARTIFACTS.items():
        wait_evidence(owner, receiver, port, timeout=timeout,
                      view_id=view_id, sentinel=sentinel)
    expected = {**{key: "artifact" for key in ARTIFACTS},
                "example-pandas": "table", "example-polars": "table",
                "example-matplotlib": "plot", "example-plotnine": "plot"}
    views = _json(port, "/views", time.monotonic() + timeout, owner)
    actual = {view["view_id"]: view["kind"] for view in views}
    if any(actual.get(key) != kind for key, kind in expected.items()):
        raise ValueError(f"Gallery kinds missing or incorrect: {actual}")
    for name in ("pandas", "polars"):
        table = _json(port, f"/table/data?view=example-{name}", time.monotonic() + timeout, owner)
        if table.get("columns") != ["planet", "gravity", "temperature"] or table.get("rows") != [
            {"planet": "Earth", "gravity": 9.81, "temperature": 15},
            {"planet": "Mars", "gravity": 3.71, "temperature": -63},
            {"planet": "Jupiter", "gravity": 24.79, "temperature": -110},
        ]:
            raise ValueError(f"Incorrect gallery {name} table content")
    for name in ("matplotlib", "plotnine"):
        png = _response(port, f"/plot?view=example-{name}", time.monotonic() + timeout,
                        owner, max_bytes=2 * 1024 * 1024)
        with Image.open(io.BytesIO(png)) as image:
            if image.format != "PNG" or min(image.size) < 100:
                raise ValueError(f"Incorrect gallery {name} image")
            image.verify()
    page = _response(port, "/", time.monotonic() + timeout, owner,
                     max_bytes=1024 * 1024).decode("utf-8")
    if ("<title>plotsrv examples gallery</title>" not in page
            or "Examples gallery" not in page
            or 'ps-viewselect__entry--feature' not in page
            or 'data-pin-view="example-pandas"' not in page
            or 'data-pin-view="gallery-html"' not in page):
        raise ValueError("Gallery UI configuration was not rendered")
    receiver.require_alive()
    return {"views": sorted(expected), "tables": "exact rows", "plots": "decoded PNGs",
            "artifacts": "rendered sentinels", "ui_config": "rendered title and view browser"}


def main(*, port=0, inspect=False, inspect_seconds=30, fault=None):
    result = {"scenario": "gallery", "success": False, "manual_status": "pending"}
    owner = None
    code = 1
    try:
        if not 0 <= port <= 65535 or not math.isfinite(inspect_seconds) or inspect_seconds < 0:
            raise ValueError("Use a valid port and finite nonnegative inspection duration")
        provenance = require_candidate()
        result["provenance"] = {key: provenance[key] for key in
                                ("core_reference", "runtime_candidate", "relationship")}
        repository = Path(__file__).resolve().parents[3]
        port = available_port(port)
        run = create(repository)
        result.update(port=port, workspace=str(run))
        config = run / "plotsrv.yml"
        with owned_directory(repository, run) as fd:
            handle = os.open("plotsrv.yml", os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(handle, "w") as output:
                output.write((repository / "configs/current/demo-ui.yml").read_text(encoding="utf-8"))
        env = {key: value for key, value in os.environ.items() if not key.startswith("PLOTSRV_")}
        env.update(PLOTSRV_CONFIG=str(config), PYTHONDONTWRITEBYTECODE="1",
                   PYTHONUNBUFFERED="1", MPLBACKEND="Agg", MPLCONFIGDIR=str(run / "mpl"),
                   XDG_CACHE_HOME=str(run / "cache"),
                   PYTHONPATH=str(Path(provenance["core_reference"]["path"]) / "src"))
        owner = Processes()
        with interruption_cleanup(), owner:
            receiver = owner.start([sys.executable, "-m", "plotsrv.cli_entry", "serve",
                                    "--host", "127.0.0.1", "--port", str(port),
                                    "--config", str(config), "--quiet"],
                                   cwd=run, env=env, label="receiver")
            wait_evidence(owner, receiver, port, timeout=15)
            publisher = owner.start(
                [sys.executable, "-c", "pass"] if fault == "missing-evidence" else
                [sys.executable, str(repository / "examples/gallery.py"), "--port", str(port)],
                cwd=run, env=env, label="publisher")
            owner.wait(publisher, timeout=45)
            result["evidence"] = verify(owner, receiver, port)
            if inspect:
                print(f"Gallery ready: http://127.0.0.1:{port} ({inspect_seconds:g}s; Ctrl+C stops)",
                      file=sys.stderr, flush=True)
                deadline = time.monotonic() + inspect_seconds
                while time.monotonic() < deadline:
                    owner.pump()
                    receiver.require_alive()
                    time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        result["success"] = True
        code = 0
    except KeyboardInterrupt:
        result["error"] = "Interrupted; owned children cleaned up"
        code = 130
    except (LifecycleError, OSError, ValueError) as exc:
        result["error"] = str(exc)
    finally:
        if owner is not None:
            result["children"] = [{"label": c.label, "pid": c.process.pid,
                                    "exit": c.process.poll(), "tail": c.diagnostic()}
                                   for c in owner.children]
            result["owned_children_reaped"] = all(c["exit"] is not None for c in result["children"])
        print(json.dumps(result, indent=2), flush=True)
    return code
