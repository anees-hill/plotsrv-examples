"""Owned resource-monitor lifecycle and receiver evidence."""

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


def verify(owner, receiver, port, summary, *, timeout=5):
    expected = {"resource-pandas": "table", "resource-polars": "table",
                "resource-cpu_percent": "plot", "resource-memory_percent": "plot"}
    views = _json(port, "/views", time.monotonic() + timeout, owner)
    actual = {view["view_id"]: view["kind"] for view in views}
    if actual != expected:
        raise ValueError(f"Resource views absent or incorrect: {actual}")
    for name in ("pandas", "polars"):
        table = _json(port, f"/table/data?view=resource-{name}",
                      time.monotonic() + timeout, owner)
        rows = table.get("rows", [])
        if len(rows) != summary["retained"] or rows[-1] != summary["last"]:
            raise ValueError("Resource table does not match final measurements")
        for row in rows:
            for key in ("cpu_percent", "memory_percent", "disk_percent"):
                if not isinstance(row[key], (int, float)) or not 0 <= row[key] <= 100:
                    raise ValueError("Invalid percentage measurement")
            if not math.isfinite(row["memory_used_gb"]) or row["memory_used_gb"] < 0:
                raise ValueError("Invalid memory measurement")
    for metric in ("cpu_percent", "memory_percent"):
        png = _response(port, f"/plot?view=resource-{metric}",
                        time.monotonic() + timeout, owner, max_bytes=2 * 1024 * 1024)
        with Image.open(io.BytesIO(png)) as image:
            if image.format != "PNG" or min(image.size) < 100:
                raise ValueError("Invalid resource plot")
            image.verify()
    if summary["retained"] > summary["history_size"] or summary["open_figures"]:
        raise ValueError("Resource history or figures were not bounded")
    receiver.require_alive()
    return {"views": sorted(expected), "measurements": summary, "plots": "decoded PNGs"}


def main(*, port=0, inspect=False, inspect_seconds=30, fault=None):
    result = {"scenario": "resource-monitor", "success": False, "manual_status": "pending"}
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
                output.write("storage-settings:\n  enabled: false\n"
                             "security-settings:\n  tracebacks_enabled: true\n")
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
                [sys.executable, str(repository / "examples/resource_monitor/main.py"),
                 "--destination", f"http://127.0.0.1:{port}", "--history-size", "2",
                 "--duration", str(inspect_seconds if inspect else 0)],
                cwd=run, env=env, label="publisher")
            if inspect:
                print(f"Resource monitor: http://127.0.0.1:{port} (Ctrl+C stops)",
                      file=sys.stderr, flush=True)
            owner.wait(publisher, timeout=45 + (inspect_seconds if inspect else 0))
            lines = publisher.output.decode().splitlines()
            if not fault and not lines:
                raise ValueError("Resource publisher produced no summary")
            summary = {} if fault else json.loads(lines[-1])
            result["evidence"] = verify(owner, receiver, port, summary)
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
