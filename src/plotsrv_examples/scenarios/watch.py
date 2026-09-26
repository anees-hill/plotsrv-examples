"""Finite local and split-process file workflows using public core entrypoints."""

import http.client
import json
import math
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlencode
from uuid import uuid4

from ..support.lifecycle import (
    LifecycleError, Processes, _json, _response, available_port,
    interruption_cleanup, require_candidate, wait_evidence,
)
from ..workspace import create


def wait_missing(owner, receiver, publisher, port, view_id, sentinel):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        owner.pump()
        receiver.require_alive()
        publisher.require_alive()
        if not receiver.owns_listener(port):
            raise LifecycleError("Receiver lost listener ownership")
        try:
            data = _json(port, "/artifact?" + urlencode({"view": view_id}), deadline, owner)
            if data.get("meta", {}).get("status") == "missing" and sentinel in data.get("html", ""):
                return data
        except (OSError, ValueError, http.client.HTTPException):
            pass
        time.sleep(0.02)
    raise LifecycleError("Missing-source status with retained content was not received")


def main(*, scenario="remote-watch", port=0, inspect=False, inspect_seconds=30, fault=None):
    result = {"scenario": scenario, "success": False, "manual_status": "pending",
              "scope": "local combined watch" if scenario == "local-watch" else
                       "loopback split-process; not two-machine network testing"}
    owner, code = None, 1
    try:
        if not 0 <= port <= 65535 or not math.isfinite(inspect_seconds) or inspect_seconds < 0:
            raise ValueError("Use a valid port and finite nonnegative inspection duration")
        provenance = require_candidate()
        result["provenance"] = {k: provenance[k] for k in
                                ("core_reference", "runtime_candidate", "relationship")}
        repository = Path(__file__).resolve().parents[3]
        run = create(repository)
        receiver_dir, publisher_dir = run / "receiver", run / "publisher"
        receiver_dir.mkdir()
        publisher_dir.mkdir()
        config = receiver_dir / "receiver.yml"
        config.write_text("storage-settings:\n  enabled: false\n", encoding="utf-8")
        publisher_config = publisher_dir / "publisher.yml"
        publisher_config.write_text("{}\n", encoding="utf-8")
        source = publisher_dir / "sample.txt"
        first, second = "first-" + uuid4().hex, "second-" + uuid4().hex
        source.write_text(first, encoding="utf-8")
        (receiver_dir / source.name).write_text("RECEIVER DECOY", encoding="utf-8")
        label = "file-" + uuid4().hex
        view_id = "watch:" + label if scenario == "local-watch" else label
        port = available_port(port)
        result.update(workspace=str(run), port=port)
        env = {k: v for k, v in os.environ.items() if not k.startswith("PLOTSRV_")}
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
                   PYTHONPATH=str(Path(provenance["core_reference"]["path"]) / "src"))
        cli = [sys.executable, "-m", "plotsrv.cli_entry"]
        owner = Processes()
        with interruption_cleanup(), owner:
            if scenario == "local-watch":
                receiver = owner.start(cli + ["watch", str(source), "--config", str(config),
                    "--port", str(port), "--label", label, "--head", "--every", "0.1",
                    "--materialization", "memory", "--quiet"],
                    cwd=receiver_dir, env=env, label="local-watch")
            else:
                receiver = owner.start(cli + ["serve", "--config", str(config),
                    "--host", "127.0.0.1", "--port", str(port), "--quiet"],
                    cwd=receiver_dir, env=env, label="receiver")
            wait_evidence(owner, receiver, port, timeout=15)
            destination = f"http://127.0.0.1:{port}"
            if scenario == "remote-publish":
                command = [sys.executable, str(repository / "examples/watch/publish_file.py"),
                           source.name, "--destination", destination, "--view-id", view_id,
                           "--remove-after-read"]
            else:
                command = cli + ["watch", source.name, "--config", str(publisher_config),
                    "--destination", destination, "--view-id", view_id, "--head", "--every", "0.1"]
            publisher = None
            if scenario != "local-watch":
                publisher = owner.start([sys.executable, "-c", "pass"] if fault else command,
                                        cwd=publisher_dir, env=env, label="publisher")
                if scenario == "remote-publish" or fault:
                    owner.wait(publisher, timeout=10)
            expected = "absent-" + uuid4().hex if fault else first
            wait_evidence(owner, receiver, port, timeout=8, view_id=view_id, sentinel=expected)
            evidence = {"view_id": view_id, "first": first}
            if scenario != "remote-publish":
                source.write_text(second, encoding="utf-8")
                wait_evidence(owner, receiver, port, timeout=8, view_id=view_id, sentinel=second)
                evidence["second"] = second
            if scenario == "remote-watch":
                source.unlink()
                artifact = wait_missing(owner, receiver, publisher, port, view_id, second)
                if str(publisher_dir) in json.dumps(artifact):
                    raise LifecycleError("Publisher path leaked into remote artifact")
                hosted = _response(port, "/watch/source?" + urlencode({"view": view_id}),
                                   time.monotonic() + 3, owner)
                if hosted.decode("utf-8") != second:
                    raise LifecycleError("Hosted content differs after publisher source removal")
                evidence.update(source_status="missing", hosted_content=second,
                                publisher_path_absent=True)
            if scenario != "local-watch":
                if source.exists():
                    raise LifecycleError("Publisher source unexpectedly remains")
                wait_evidence(owner, receiver, port, timeout=3, view_id=view_id,
                              sentinel=second if scenario == "remote-watch" else first)
                evidence["content_after_source_removal"] = True
            result["evidence"] = evidence
            if inspect:
                print(f"Watch ready: http://127.0.0.1:{port}/?view={view_id} "
                      f"({inspect_seconds:g}s; Ctrl+C stops)", file=sys.stderr, flush=True)
                deadline = time.monotonic() + inspect_seconds
                while time.monotonic() < deadline:
                    owner.pump()
                    receiver.require_alive()
                    if scenario == "remote-watch":
                        publisher.require_alive()
                    time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        result["success"], code = True, 0
    except KeyboardInterrupt:
        result["error"], code = "Interrupted; owned children cleaned up", 130
    except (LifecycleError, OSError, ValueError, http.client.HTTPException) as exc:
        result["error"] = str(exc)
    finally:
        if owner is not None:
            result["children"] = [{"label": c.label, "pid": c.process.pid,
                                   "exit": c.process.poll(), "tail": c.diagnostic()}
                                  for c in owner.children]
            result["owned_children_reaped"] = all(c["exit"] is not None for c in result["children"])
        print(json.dumps(result, indent=2), flush=True)
    return code
