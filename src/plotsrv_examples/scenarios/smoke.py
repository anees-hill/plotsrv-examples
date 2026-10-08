"""Release regressions shared with the command-by-command manual smoke guide."""

import csv
import http.client
import io
import json
import math
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlencode

from ..smoke_inputs import prepare, table_rows
from ..support.lifecycle import (LifecycleError, Processes, _json, _response,
                                 available_port, interruption_cleanup, require_candidate,
                                 wait_evidence)
from .admission_config import require
from .observe_etl import observation


class Smoke:
    def __init__(self, owner, repository, run, env, port):
        self.owner, self.repository, self.run, self.env, self.port = owner, repository, run, env, port
        self.receiver = None

    def start(self, config="memory", *extra):
        self.receiver = self.owner.start(
            [sys.executable, "-m", "plotsrv.cli_entry", "run" if extra else "serve",
             *([str(self.run / "discovery")] if extra else []),
             "--config", str(self.run / (config + ".yml")), "--host", "127.0.0.1",
             "--port", str(self.port), "--quiet", *extra],
            cwd=self.run, env=self.env, label="receiver-" + config)
        wait_evidence(self.owner, self.receiver, self.port, timeout=15)
        return self.receiver

    def stop(self):
        self.receiver.process.terminate()
        deadline = time.monotonic() + 5
        while self.receiver.process.poll() is None and time.monotonic() < deadline:
            self.owner.pump()
            time.sleep(0.02)
        require(self.receiver.process.poll() is not None, "Receiver did not stop")

    def publish(self, script="smoke/publish.py", *args, config="memory"):
        env = {**self.env, "PLOTSRV_CONFIG": str(self.run / (config + ".yml"))}
        child = self.owner.start([sys.executable, str(self.repository / "examples" / script),
                                  "--port", str(self.port), *args],
                                 cwd=self.run, env=env, label=script)
        self.owner.wait(child, timeout=40)
        return child

    def read(self, endpoint, **params):
        require(self.receiver.owns_listener(self.port), "Evidence listener is not owned")
        path = endpoint + ("?" + urlencode(params) if params else "")
        return _json(self.port, path, time.monotonic() + 5, self.owner, max_bytes=2 * 1024 * 1024)

    def bytes(self, endpoint, **params):
        require(self.receiver.owns_listener(self.port), "Evidence listener is not owned")
        return _response(self.port, endpoint + "?" + urlencode(params),
                         time.monotonic() + 5, self.owner, max_bytes=2 * 1024 * 1024)

    def artifact(self, view, sentinel):
        wait_evidence(self.owner, self.receiver, self.port, timeout=5, view_id=view, sentinel=sentinel)
        return self.read("/artifact", view=view)


def publication_modes(smoke):
    smoke.start()
    variants = []
    for version, (style, async_) in enumerate(
            (("direct", False), ("decorator", False), ("direct", True), ("decorator", True)), 1):
        args = ["--style", style, "--version", str(version)] + (["--async"] if async_ else [])
        child = smoke.publish("smoke/publish.py", *args)
        require('"drained": true' in child.output.decode(), "Publish queue did not drain")
        smoke.artifact("smoke-text", f"smoke-version-{version}")
        for backend in ("pandas", "polars"):
            data = smoke.read("/table/data", view="smoke-" + backend)
            require(data["rows"] == table_rows(1200, version), "Published table rows differ")
            exported = list(csv.DictReader(io.StringIO(smoke.bytes(
                "/table/export", view="smoke-" + backend).decode())))
            require(exported == [{k: str(v) for k, v in row.items()} for row in table_rows(1200, version)],
                    "Exported table differs from received content")
        variants.append({"style": style, "async": async_, "version": version})
    markup = smoke.artifact("smoke-html", "html-smoke")["html"]
    require("<script" not in markup.lower() and "smokeEscape" not in markup,
            "Remote HTML script was not removed")
    smoke.publish("exceptions.py")
    for name in ("explicit", "captured", "decorated"):
        smoke.artifact("example-exception-" + name, name.capitalize() + " example failure")
    smoke.stop()
    smoke.start("no-tracebacks")
    # Publisher enabled, receiver disabled: exercise receiver policy separately.
    smoke.publish("exceptions.py")
    for view in smoke.read("/views"):
        if view["view_id"].startswith("example-exception-"):
            try:
                blocked = smoke.read("/artifact", view=view["view_id"])
            except ValueError as exc:
                if ": HTTP 404" not in str(exc):
                    raise
            else:
                require(blocked["kind"] != "traceback" and "example failure" not in blocked["html"],
                        "Disabled receiver accepted traceback content")
    # Publisher disabled, receiver enabled: start fresh to avoid old content.
    smoke.stop()
    smoke.start()
    smoke.publish("exceptions.py", config="no-tracebacks")
    require(not any(v["view_id"].startswith("example-exception-") for v in smoke.read("/views")),
            "Disabled publisher sent tracebacks")
    smoke.stop()
    smoke.start("bounded")
    smoke.publish(config="bounded")
    data = smoke.read("/table/data", view="smoke-pandas")
    require(len(data["rows"]) == 10 and len(data["columns"]) == 5,
            "Configured table render limits were ignored")
    require(smoke.artifact("smoke-text", "smoke-version-1")["truncation"]["truncated"],
            "Configured text truncation was ignored")
    smoke.stop()
    modes = []
    for mode in ("publish", "show", "watch"):
        args = ["--mode", mode, "--config", str(smoke.run / "memory.yml"), "--seconds", "8"]
        if mode == "watch":
            args += ["--watch", str(smoke.run / "small.csv")]
        attached = smoke.owner.start([sys.executable, str(smoke.repository / "examples/lifecycle.py"),
                                     "--port", str(smoke.port), *args],
                                    cwd=smoke.run, env=smoke.env, label="attached-" + mode)
        smoke.receiver = attached
        wait_evidence(smoke.owner, attached, smoke.port, timeout=15)
        if mode == "publish":
            smoke.artifact("example-lifecycle", "attached")
        else:
            deadline = time.monotonic() + 5
            kind = "plot" if mode == "show" else "table"
            matching = []
            while time.monotonic() < deadline:
                matching = [v for v in smoke.read("/views") if v["kind"] == kind]
                if matching:
                    try:
                        if mode == "watch":
                            if smoke.read("/table/data", view=matching[0]["view_id"])["rows"] == table_rows(99):
                                break
                        elif smoke.bytes("/plot", view=matching[0]["view_id"]).startswith(b"\x89PNG"):
                            break
                    except ValueError:
                        pass
                time.sleep(0.03)
            else:
                raise LifecycleError("Attached content did not arrive: " + mode)
            require(bool(matching), "Attached content did not arrive")
            if mode == "watch":
                require(smoke.read("/table/data", view=matching[0]["view_id"])["rows"] == table_rows(99),
                        "Attached watched table differs")
            else:
                require(smoke.bytes("/plot", view=matching[0]["view_id"]).startswith(b"\x89PNG"),
                        "Patched show did not publish a PNG")
        smoke.owner.wait(attached, timeout=15)
        modes.append(mode)
    # Leave a receiver available for inspection, with positive content.
    smoke.start()
    smoke.publish()
    return {"publication_variants": variants, "csv_exports": "exact 1200 rows for both backends",
            "html": "remote script removed", "tracebacks": "enabled and independently disabled at each end",
            "render_limits": {"rows": 10, "columns": 5, "text_truncated": True}, "attached_modes": modes}


def watch_formats(smoke):
    evidence = {}
    for materialization in ("memory", "file"):
        smoke.start("memory", "--watch", str(smoke.run / "large.csv"), "--watch-label", "large",
                    "--watch-head", "--watch-materialization", materialization, "--watch-every", "0.1")
        deadline = time.monotonic() + 5
        data = None
        while time.monotonic() < deadline:
            try:
                data = smoke.read("/table/data", view="watch:large")
                if data["rows"] == table_rows():
                    break
            except ValueError:
                pass
            time.sleep(0.03)
        require(data is not None and data["rows"] == table_rows(), "Watched CSV content differs or is absent")
        require(smoke.bytes("/table/export", view="watch:large") == (smoke.run / "large.csv").read_bytes(),
                "Watched CSV raw export differs")
        limited = smoke.read("/table/data", view="watch:large", limit=7)
        require(limited["rows"] == table_rows()[:7], "Explicit row preview limit was ignored")
        evidence[materialization] = {"rows": 1200, "preview_limit": 7, "export": "exact source bytes"}
        smoke.stop()
    for mode, included, excluded in (("head", "HEAD-SENTINEL", "TAIL-SENTINEL"),
                                      ("tail", "TAIL-SENTINEL", "HEAD-SENTINEL")):
        smoke.start("memory", "--watch", str(smoke.run / "window.txt"), "--watch-label", "window",
                    "--watch-" + mode, "--watch-max-bytes", "512", "--watch-every", "0.1")
        artifact = smoke.artifact("watch:window", included)
        require(excluded not in artifact["html"], "Watch byte window includes the opposite end")
        evidence[mode] = {"included": included, "excluded": excluded, "max_bytes": 512}
        smoke.stop()
    args = []
    for suffix in ("json", "yml", "md", "html"):
        args += ["--watch", str(smoke.run / ("sample." + suffix)), "--watch-label", suffix, "--watch-head"]
    smoke.start("memory", *args, "--watch-every", "0.1", "--watch-materialization", "memory")
    for suffix, sentinel in (("json", "json-smoke"), ("yml", "yaml-smoke"),
                              ("md", "markdown-smoke"), ("html", "html-smoke")):
        smoke.artifact("watch:" + suffix, sentinel)
    evidence["formats"] = ["csv", "text", "json", "yaml", "markdown", "html"]
    return evidence


def observation_changes(smoke):
    smoke.start()
    control = smoke.run / "observation-control.json"
    control.write_text(json.dumps({"revision": 0, "state": "healthy"}))
    follower = smoke.owner.start([sys.executable, str(smoke.repository / "examples/observation/changes.py"),
        "--port", str(smoke.port), "--control-file", str(control), "--seconds", "60"],
        cwd=smoke.run, env={**smoke.env, "PLOTSRV_CONFIG": str(smoke.run / "memory.yml")},
        label="observation-publisher")
    sessions, states = [], []
    for revision, state in enumerate(("healthy", "failing", "recovered")):
        control.write_text(json.dumps({"revision": revision, "state": state}))
        deadline = time.monotonic() + 10
        expected = 3 if state == "failing" else 0
        while time.monotonic() < deadline:
            smoke.owner.pump()
            follower.require_alive()
            try:
                projection, provenance = observation(smoke.owner, smoke.receiver, smoke.port,
                                                     "smoke-observe:metrics")
                fields = {r["field"]: r for r in projection["rows"] if r["surface"] == "Fields"}
                artifact = smoke.read("/artifact", view="smoke-observe:metrics")["html"]
                if str(fields["errors"]["value"]) == str(expected) and (
                        revision == 0 or f"Supplied value changed by {'3' if revision == 1 else '-3'}" in artifact):
                    break
            except (LifecycleError, ValueError, KeyError):
                pass
            time.sleep(0.05)
        else:
            raise LifecycleError("Observation state/change evidence missing: " + state)
        sessions.append(provenance["provenance"]["publisher_session"])
        require(not projection["examples"], "Observation examples unexpectedly exported")
        if revision == 0:
            require("No comparable changes to display" in artifact, "First observation invented changes")
        orders_deadline = time.monotonic() + 5
        row = None
        while time.monotonic() < orders_deadline:
            orders, _ = observation(smoke.owner, smoke.receiver, smoke.port, "smoke-observe:orders")
            row = next((r for r in orders["rows"] if r["surface"] == "Fields" and r["field"] == "amount"), None)
            if row is not None and str(row["missing"]) == str(expected):
                break
            time.sleep(0.05)
        require(row is not None and str(row["missing"]) == str(expected),
                "Observed amount field absent or missingness did not follow state")
        states.append({"state": state, "errors": expected, "observed_missing": row["missing"]})
    require(len(set(sessions)) == 1 and sessions[0], "Observation changes crossed publisher sessions")
    control.write_text('{"stop":true}')
    smoke.owner.wait(follower, timeout=8)
    return {"states": states, "publisher_session": sessions[0], "metric_changes": [3, -3],
            "first_capture": "no comparison", "examples_exported": False}


WORKFLOWS = {"publication-modes": publication_modes, "watch-formats": watch_formats,
             "observation-changes": observation_changes}


def main(*, scenario="publication-modes", port=0, inspect=False, inspect_seconds=30, fault=None):
    result = {"scenario": scenario, "success": False, "manual_status": "pending"}
    owner, code = None, 1
    try:
        if not 0 <= port <= 65535 or not math.isfinite(inspect_seconds) or inspect_seconds < 0:
            raise ValueError("Use valid port and finite nonnegative inspection duration")
        candidate = require_candidate()
        result["provenance"] = {k: candidate[k] for k in ("core_reference", "runtime_candidate", "relationship")}
        repository = Path(__file__).resolve().parents[3]
        run, port = prepare(repository), available_port(port)
        result.update(workspace=str(run), port=port)
        env = {k: v for k, v in os.environ.items() if not k.startswith("PLOTSRV_")}
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1", MPLBACKEND="Agg",
                   MPLCONFIGDIR=str(run / "mpl"), XDG_CACHE_HOME=str(run / "cache"),
                   PYTHONPATH=str(Path(candidate["core_reference"]["path"]) / "src"))
        owner = Processes()
        with interruption_cleanup(), owner:
            smoke = Smoke(owner, repository, run, env, port)
            evidence = WORKFLOWS[scenario](smoke)
            if fault:
                raise LifecycleError("Required smoke evidence missing: deliberate failure drill")
            result["evidence"] = evidence
            if inspect:
                print(f"Smoke ready: http://127.0.0.1:{port} ({inspect_seconds:g}s)", file=sys.stderr, flush=True)
                deadline = time.monotonic() + inspect_seconds
                while time.monotonic() < deadline:
                    owner.pump()
                    smoke.receiver.require_alive()
                    time.sleep(0.05)
        result["success"], code = True, 0
    except KeyboardInterrupt:
        result["error"], code = "Interrupted; owned children cleaned up", 130
    except (LifecycleError, OSError, ValueError, KeyError, StopIteration, http.client.HTTPException) as exc:
        result["error"] = str(exc)
    finally:
        result["children"] = [{"label": c.label, "pid": c.process.pid, "exit": c.process.poll(),
                               "tail": c.diagnostic()} for c in owner.children] if owner else []
        result["owned_children_reaped"] = all(c["exit"] is not None for c in result["children"])
        print(json.dumps(result, indent=2), flush=True)
    return code
