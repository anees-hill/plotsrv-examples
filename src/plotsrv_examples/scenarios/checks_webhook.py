"""Deterministic live transitions, bounded webhook failure and manual controls."""

import http.client
import json
import math
import os
from pathlib import Path
import socket
import sys
import time
from urllib.parse import urlencode
from uuid import uuid4

import yaml

from ..support.lifecycle import (LifecycleError, Processes, _json, available_port,
                                 interruption_cleanup, require_candidate, wait_evidence)
from ..support.storage import OwnedStore
from ..workspace import create, owned_directory, _read
from .admission_config import require
from .stream_structured import wait_stream


def control(value):
    if (type(value) is not dict or set(value) != {"revision", "state", "schema"}
            or type(value["revision"]) is not int or not 0 <= value["revision"] <= 6
            or value["state"] not in ("healthy", "failing", "recovered")
            or type(value["schema"]) is not int or value["schema"] not in (1, 2)):
        raise ValueError("Control requires revision 0..6, healthy/failing/recovered state, schema 1/2")
    return value


def fetch(owner, child, port, path, **params):
    require(child.owns_listener(port), "Evidence listener is not owned")
    return _json(port, path + ("?" + urlencode(params) if params else ""), time.monotonic() + 2, owner)


def wait(owner, child, port, path, predicate, *, timeout=15, **params):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        data = fetch(owner, child, port, path, **params)
        if predicate(data):
            return data
        owner.pump()
        time.sleep(0.03)
    raise LifecycleError("Required check/webhook evidence missing: " + path)


def state(data, name="errors"):
    return next(s for s in data["states"] if s["id"] == name)


def main(*, port=0, inspect=False, inspect_seconds=30, fault=None):
    result = {"scenario": "checks-webhook", "success": False, "manual_status": "pending"}
    owner, code = None, 1
    try:
        if not 0 <= port <= 65535 or not math.isfinite(inspect_seconds) or inspect_seconds < 0:
            raise ValueError("Use valid port and finite nonnegative inspection duration")
        provenance = require_candidate()
        result["provenance"] = {k: provenance[k] for k in ("core_reference", "runtime_candidate", "relationship")}
        repository = Path(__file__).resolve().parents[3]
        run = create(repository)
        storage = OwnedStore(repository, run)
        result.update(workspace=str(run))
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PLOTSRV_", "EXAMPLE_"))}
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
                   PYTHONPATH=str(Path(provenance["core_reference"]["path"]) / "src"))
        owner = Processes()
        with interruption_cleanup(), owner, socket.socket() as unavailable, storage.configuration() as config:
            unavailable.bind(("127.0.0.1", 0))  # Reserved, deliberately never listening.
            failed_port = unavailable.getsockname()[1]
            port, sink_port = available_port(port), available_port()
            while sink_port == port:
                sink_port = available_port()
            result["port"] = port
            settings = yaml.safe_load(config.read_text())
            settings["checks-settings"] = {"enabled": True, "rules": [
                {"id": "errors", "source": "checks:metrics", "kind": "state", "path": ["errors"],
                 "op": "gt", "value": 0, "severity": "critical", "notify": ["sink", "unavailable"]},
                {"id": "event", "source": "checks:events", "kind": "event", "path": ["status"],
                 "op": "ge", "value": 500, "notify": ["sink"]}]}
            settings["webhook-settings"] = {"event_cooldown_s": 1, "destinations": {
                "sink": {"url": f"http://127.0.0.1:{sink_port}/hook"},
                "unavailable": {"url": f"http://127.0.0.1:{failed_port}/hook"}}}
            config.write_text(yaml.safe_dump(settings))
            sink = owner.start([sys.executable, str(repository / "examples/checks/sink.py"),
                                "--port", str(sink_port)], cwd=run, env=env, label="webhook-sink")
            wait_evidence(owner, sink, sink_port, timeout=5)
            receiver = owner.start([sys.executable, "-m", "plotsrv.cli_entry", "serve", "--host", "127.0.0.1",
                "--port", str(port), "--config", str(config), "--quiet"], cwd=run, env=env, label="receiver")
            storage.writers.append(receiver)
            wait_evidence(owner, receiver, port, timeout=15)
            application = []

            def publish(label, schema=1):
                require(receiver.owns_listener(port), "Publication listener is not owned")
                previous_context = state(fetch(owner, receiver, port, "/checks"))["context"]
                child = owner.start([sys.executable, str(repository / "examples/checks/publish.py"),
                    "--port", str(port), "--state", label, "--schema", str(schema)], cwd=run, env=env,
                    label="publish-" + label)
                owner.wait(child, timeout=10)
                report = json.loads(child.output)
                require(report["application_result"] == 20 and report["publication_returned"],
                        "Application result changed")
                application.append(report)
                expected = "triggered" if label == "failing" else "ok"
                checked = wait(owner, receiver, port, "/checks", lambda d:
                    state(d)["state"] == expected and state(d)["context"] != previous_context)
                columns = ["job", "rows"] + (["quality"] if schema == 2 else [])
                wait(owner, receiver, port, "/table/data", lambda d: d["columns"] == columns
                     and len(d["rows"]) == 2 and d["rows"][1]["rows"] == 200 + report["errors"],
                     view="checks:table")
                return checked

            baseline = publish("healthy")
            require(baseline["events"] == [], "Healthy baseline manufactured events")
            require(fetch(owner, sink, sink_port, "/status")["records"] == [], "Baseline notified")
            generation = baseline["generation"]
            triggered = publish("failing", 2)
            require([e["event_type"] for e in triggered["events"]] == ["triggered"], "Trigger missing")
            unchanged = publish("failing", 2)
            require(unchanged["cursor"] == triggered["cursor"], "Unchanged failure created event")
            recovered = publish("recovered")
            require([e["event_type"] for e in recovered["events"]] == ["triggered", "recovered"],
                    "Recovery transition missing")
            require(not recovered["history_gap"] and recovered["generation"] == generation,
                    "Check history gap/generation changed")
            failed = wait(owner, receiver, port, "/checks", lambda d: any(
                n["destination"] == "unavailable" and n["failures"] == 6 and n["queued"] == 0
                for n in state(d)["notifications"]), timeout=20)
            failure = next(n for n in state(failed)["notifications"] if n["destination"] == "unavailable")
            require(failure["delivered"] == 0 and failure["attempts"] == 3
                    and failure["last_failure"] == "network_unavailable"
                    and state(failed)["state"] == "ok" and len(failed["events"]) == 2,
                    "Delivery failure changed check semantics")

            source, stop = run / "events.jsonl", run / "stop-follower"
            source.write_text("")
            session = uuid4().hex
            follower = owner.start([sys.executable, str(repository / "examples/streams/follow_jsonl.py"),
                str(source), "--destination", f"http://127.0.0.1:{port}", "--view-id", "checks:events",
                "--session-id", session, "--stop-file", str(stop)], cwd=run, env=env, label="event-follower")
            wait_stream(owner, receiver, port, "checks:events", session,
                        lambda d: d["accepted_records"] == 0, follower=follower)
            with source.open("a") as output:
                output.write('{"status":200}\n{"status":503}\n')
            wait_stream(owner, receiver, port, "checks:events", session,
                        lambda d: d["accepted_records"] == 2, follower=follower)
            events = wait(owner, receiver, port, "/checks", lambda d: len(d["events"]) == 3)
            require([e["event_type"] for e in events["events"]] == ["triggered", "recovered", "match"]
                    and state(events, "event")["state"] == "ok", "Event match semantics incorrect")
            stop.touch()
            owner.wait(follower, timeout=6)
            received = wait(owner, sink, sink_port, "/status", lambda d: len(d["records"]) == 3)
            payloads = [r["payload"] for r in received["records"]]
            require([p["event_id"] for p in payloads] == [e["event_id"] for e in events["events"]],
                    "Sink event identities/order differ from checks")
            require([p["event_type"] for p in payloads] == ["triggered", "recovered", "match"]
                    and all(p["generation"] == generation for p in payloads), "Sink payload mismatch")
            require(all(r["identity_headers_match"] and r["bytes"] <= 8192 for r in received["records"])
                    and [p["observed_value"] for p in payloads] == [3, 0, 503]
                    and [(p["previous_state"], p["current_state"]) for p in payloads[:2]] ==
                        [("ok", "triggered"), ("triggered", "ok")], "Webhook evidence fields incorrect")
            wait(owner, receiver, port, "/history", lambda d: d["count"] == 2, view="checks:table")
            table = fetch(owner, receiver, port, "/table/data", view="checks:table")
            require(table["columns"] == ["job", "rows"], "Manual table schema absent")
            if fault:
                raise LifecycleError("Required check/webhook evidence missing: deliberate failure drill")
            control_file = run / "control.json"
            control_file.write_text(json.dumps({"revision": 0, "state": "recovered", "schema": 1}))
            result["manual"] = {"status": "manual-pending", "prepared": True,
                "available_during_inspection_only": True,
                "control_file": str(control_file), "url": f"http://127.0.0.1:{port}",
                "items": ["Compare", "My Views schema drift", "focus", "check attention", "snapshot arrows"]}
            if inspect:
                print(f"Checks ready for manual inspection: http://127.0.0.1:{port}; edit {control_file}",
                      file=sys.stderr, flush=True)
                deadline, revision = time.monotonic() + inspect_seconds, 0
                while time.monotonic() < deadline:
                    owner.pump()
                    receiver.require_alive()
                    sink.require_alive()
                    with owned_directory(repository, run) as fd:
                        raw = _read(fd, "control.json")
                    try:
                        value = control(json.loads(raw))
                    except (ValueError, TypeError):
                        # Editors may briefly save partial JSON. Never publish
                        # invalid controls, and keep the overall inspection deadline.
                        time.sleep(0.05)
                        continue
                    if value["revision"] > revision:
                        publish(value["state"], value["schema"])
                        revision = value["revision"]
                    time.sleep(0.05)
            result["manual"]["applied_controls"] = application[4:]
            result["evidence"] = {"baseline_events": 0, "state_events": ["triggered", "recovered"],
                "unchanged_failure_silent": True, "event_matches": 1, "generation": generation,
                "sink_payloads": payloads, "sink_identity_headers_verified": True,
                "sink_payload_sizes": [r["bytes"] for r in received["records"]],
                "unavailable": failure, "application_reports": application[:4],
                "manual_prepared": True}
        result["success"], code = True, 0
    except KeyboardInterrupt:
        result["error"], code = "Interrupted; owned children cleaned up", 130
    except (LifecycleError, OSError, ValueError, KeyError, StopIteration, http.client.HTTPException) as exc:
        result["error"] = str(exc)
    finally:
        if owner:
            result["children"] = [{"label": c.label, "pid": c.process.pid, "exit": c.process.poll(),
                                   "tail": c.diagnostic()} for c in owner.children]
            result["owned_children_reaped"] = all(c["exit"] is not None for c in result["children"])
        print(json.dumps(result, indent=2), flush=True)
    return code
