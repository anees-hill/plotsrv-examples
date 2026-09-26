"""Owned weather-demo lifecycle and receiver evidence."""

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
    status = ("synthetic sample" if summary["mode"] == "sample" else "configured live input")
    status += " available" if summary["success"] else " unavailable"
    wait_evidence(owner, receiver, port, timeout=timeout,
                  view_id="weather-status", sentinel=status)
    expected = {"weather-status": "artifact"}
    if summary["success"]:
        expected.update({"weather-observations": "table", "weather-temperature": "plot"})
    views = _json(port, "/views", time.monotonic() + timeout, owner)
    if {v["view_id"]: v["kind"] for v in views} != expected:
        raise ValueError("Weather views absent or incorrect")
    if summary["success"]:
        table = _json(port, "/table/data?view=weather-observations",
                      time.monotonic() + timeout, owner)
        rows = table.get("rows", [])
        if len(rows) != summary["count"] or not 1 <= len(rows) <= 1000:
            raise ValueError("Weather table count incorrect")
        for row in rows:
            if (row["source"] not in status or not -100 <= row["temperature_c"] <= 70
                    or not 0 <= row["humidity_percent"] <= 100
                    or row["temperature_f"] != round(row["temperature_c"] * 1.8 + 32, 2)):
                raise ValueError("Weather table transformation incorrect")
        if summary["mode"] == "sample":
            expected_rows = [
                {"time": f"2026-01-01T0{i}:00:00+00:00", "temperature_c": t,
                 "humidity_percent": h, "temperature_f": f, "source": "synthetic sample"}
                for i, (t, h, f) in enumerate([(10.0, 70.0, 50.0),
                                               (12.0, 65.0, 53.6), (14.0, 60.0, 57.2)])]
            if rows != expected_rows:
                raise ValueError("Weather sample rows incorrect")
        png = _response(port, "/plot?view=weather-temperature",
                        time.monotonic() + timeout, owner, max_bytes=2 * 1024 * 1024)
        with Image.open(io.BytesIO(png)) as image:
            if image.format != "PNG" or min(image.size) < 100:
                raise ValueError("Weather plot invalid")
            image.verify()
    return {"views": sorted(expected), "status": status,
            "count": summary.get("count", 0)}


def main(*, port=0, inspect=False, inspect_seconds=30, fault=None, mode="sample"):
    result = {"scenario": "weather-demo", "success": False, "manual_status": "pending"}
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
                [sys.executable, str(repository / "demos/public_weather/main.py"),
                 "--destination", f"http://127.0.0.1:{port}", "--mode", mode],
                cwd=run, env=env, label="publisher")
            try:
                owner.wait(publisher, timeout=30)
            except LifecycleError:
                if publisher.process.poll() != 1:
                    raise
            lines = publisher.output.decode().splitlines()
            if not lines:
                raise ValueError("Weather publisher produced no evidence")
            summary = json.loads(lines[-1])
            result["evidence"] = verify(owner, receiver, port, summary)
            result["success"] = summary["success"]
            if not summary["success"]:
                result["error"] = summary["error"]
            if inspect:
                print(f"Weather demo: http://127.0.0.1:{port} (Ctrl+C stops)",
                      file=sys.stderr, flush=True)
                deadline = time.monotonic() + inspect_seconds
                while time.monotonic() < deadline:
                    owner.pump()
                    receiver.require_alive()
                    time.sleep(0.05)
        code = 0 if result["success"] else 1
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
