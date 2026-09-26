"""Finite independent JSONL processes with receiver-side delivery evidence."""

import http.client
import json
import math
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

from ..support.lifecycle import (
    LifecycleError, Processes, _json, available_port, interruption_cleanup,
    require_candidate, wait_evidence,
)
from ..workspace import create


def wait_stream(owner, receiver, port, view_id, session_id, predicate, *, follower=None,
                timeout=5):
    deadline = time.monotonic() + timeout
    last = "expected stream evidence absent"
    while time.monotonic() < deadline:
        owner.pump()
        receiver.require_alive()
        if follower is not None:
            follower.require_alive()
        try:
            if not receiver.owns_listener(port):
                raise LifecycleError("Receiver no longer owns its listener")
            data = _json(port, f"/stream/data?view={view_id}", deadline, owner)
            if data.get("session_id") == session_id and predicate(data):
                return data
        except (OSError, ValueError, http.client.HTTPException) as exc:
            last = str(exc)
        time.sleep(0.02)
    raise LifecycleError(f"Stream evidence timed out: {last}")


def main(*, port=0, inspect=False, inspect_seconds=30, fault=None, stream_format="jsonl"):
    mixed = stream_format == "uvicorn"
    python_logs = stream_format == "python_text"
    result = {"scenario": "stream-http" if mixed else "stream-python-logs" if python_logs else "stream-structured",
              "success": False, "manual_status": "pending"}
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
        config.write_text("storage-settings:\n  enabled: false\n", encoding="utf-8")
        source = run / ("events.log" if mixed else "python.log" if python_logs else "events.jsonl")
        source.write_text('{"pre_attach": true}\n', encoding="utf-8")
        stop_file = run / "stop-follower"
        view_id, session_id = "structured-" + uuid4().hex, uuid4().hex
        env = {key: value for key, value in os.environ.items() if not key.startswith("PLOTSRV_")}
        env.update(PLOTSRV_CONFIG=str(config), PYTHONDONTWRITEBYTECODE="1",
                   PYTHONUNBUFFERED="1", PYTHONPATH=str(Path(provenance["core_reference"]["path"]) / "src"))
        owner = Processes()
        with interruption_cleanup(), owner:
            receiver = owner.start([sys.executable, "-m", "plotsrv.cli_entry", "serve",
                                    "--host", "127.0.0.1", "--port", str(port),
                                    "--config", str(config), "--quiet"],
                                   cwd=run, env=env, label="receiver")
            wait_evidence(owner, receiver, port, timeout=15)
            follower_script = "follow_http.py" if mixed else "follow_text.py" if python_logs else "follow_jsonl.py"
            follower = owner.start([sys.executable, str(repository / "examples/streams" / follower_script),
                                    str(source), "--destination", f"http://127.0.0.1:{port}",
                                    "--view-id", view_id, "--session-id", session_id,
                                    "--stop-file", str(stop_file)], cwd=run, env=env, label="follower")
            wait_stream(owner, receiver, port, view_id, session_id,
                        lambda data: data.get("accepted_records") == 0,
                        follower=follower)
            writer_script = "write_http.py" if mixed else "write_python_logs.py" if python_logs else "write_jsonl.py"
            writer = owner.start([sys.executable, "-c", "pass"] if fault == "missing-evidence" else
                                 [sys.executable, str(repository / "examples/streams" / writer_script), str(source)],
                                 cwd=run, env=env, label="writer")
            owner.wait(writer, timeout=5)
            expected = [{"sequence": n, "synthetic": True, "level": "INFO", "value": n * 3}
                        for n in range(1, 7)]
            accepted = 4 if python_logs else 6
            received = wait_stream(owner, receiver, port, view_id, session_id,
                                  lambda data: data["accepted_records"] == accepted, follower=follower)
            def verify(data):
                if mixed:
                    from .stream_http import verify as verify_http
                    return verify_http(data)
                if python_logs:
                    from .stream_python_logs import verify as verify_logs
                    return verify_logs(data)
                if [r["data"] for r in data["records"]] != expected:
                    raise ValueError("Incorrect structured stream records")
                return {"records": expected}
            verify(received)
            stop_file.touch()
            owner.wait(follower, timeout=6)
            ended = wait_stream(owner, receiver, port, view_id, session_id,
                                lambda data: data.get("lifecycle") == "ended")
            result["evidence"] = {**verify(ended), "pre_attach_absent": True,
                                  "lifecycle": ended["lifecycle"], "source_bytes": source.stat().st_size,
                                  "session_id": session_id, "view_id": view_id}
            if inspect:
                print(f"Stream ready: http://127.0.0.1:{port}/?view={view_id} "
                      f"({inspect_seconds:g}s; Ctrl+C stops)", file=sys.stderr, flush=True)
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
