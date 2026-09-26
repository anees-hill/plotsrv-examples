"""Owned admission/outage/config workflows; each result requires explicit evidence."""

import http.client
import json
import math
import os
from pathlib import Path
import socket
import sys
import time

import psutil
import yaml

from ..support.lifecycle import (
    LifecycleError, Processes, _json, available_port, interruption_cleanup,
    require_candidate, wait_evidence,
)
from ..workspace import create


def require(condition, message):
    if not condition:
        raise LifecycleError(message)


def catalogue(owner, receiver, port):
    require(receiver.owns_listener(port), "Receiver does not own evidence listener")
    return _json(port, "/views", time.monotonic() + 3, owner)


def publish(owner, repository, cwd, env, port, view_id, text, *, label, probe=False, fault=False):
    report = cwd / (label + ".json")
    command = [sys.executable, str(repository / "examples/watch/admission_publish.py"),
               "--destination", f"http://127.0.0.1:{port}", "--view-id", view_id,
               "--text", text, "--report", str(report)]
    if "EXAMPLE_PUBLISH_KEY" in env:
        command += ["--bearer-token-env", "EXAMPLE_PUBLISH_KEY"]
    if probe:
        command += ["--probe-rejection"]
    child = owner.start([sys.executable, "-c", "pass"] if fault else command,
                        cwd=cwd, env=env, label=label)
    owner.wait(child, timeout=10)
    require(report.is_file(), "Publisher application evidence missing")
    result = json.loads(report.read_text())
    result["diagnostic"] = child.output.decode("utf-8", errors="replace")
    require(result.get("application_result") == 20 and result.get("publication_returned"),
            "Application result missing or changed")
    require(result.get("listeners_after_call") == [] and result.get("descendants_after_call") == [],
            "Publisher created an unexpected listener or child")
    return result


def admission(owner, repository, run, env, port, fault):
    publisher = run / "publisher"
    publisher.mkdir()
    synthetic = "example-only-" + run.name
    server_env = {**env, "EXAMPLE_INGEST_KEY": synthetic}
    publisher_env = {**env, "EXAMPLE_PUBLISH_KEY": synthetic}
    evidence = {}
    for profile, allowed, denied, status, reason in [
        ("keyed", "positive:sample", "wrong-key:sample", 401, "publisher_key_required"),
        ("catalogue", "allowed:sample", "unknown:sample", 403, "view_not_admitted"),
    ]:
        cwd = run / profile
        cwd.mkdir()
        receiver_port = port if profile == "keyed" else available_port()
        receiver = owner.start([sys.executable, "-m", "plotsrv.cli_entry", "serve",
            "--config", str(repository / "configs/current" / (profile + ".yml")),
            "--port", str(receiver_port), "--quiet"], cwd=cwd, env=server_env, label=profile)
        wait_evidence(owner, receiver, receiver_port, timeout=15)
        publish(owner, repository, publisher, publisher_env, receiver_port, allowed,
                "accepted-" + profile, label="positive-" + profile, fault=fault)
        wait_evidence(owner, receiver, receiver_port, timeout=5, view_id=allowed,
                      sentinel="accepted-" + profile)
        denied_env = {**publisher_env, "EXAMPLE_PUBLISH_KEY": "example-only-wrong"} if profile == "keyed" else publisher_env
        rejected = publish(owner, repository, publisher, denied_env, receiver_port, denied,
                           "REJECTED CONTENT", label="denied-" + profile, probe=True)
        require(rejected.get("http_status") == status and
                rejected.get("detail", {}).get("reason") == reason and
                reason in rejected["diagnostic"],
                f"{profile}: expected explicit rejection was not reported")
        ids = {v["view_id"] for v in catalogue(owner, receiver, receiver_port)}
        require(denied not in ids and allowed in ids, "Denied ID visible or positive control absent")
        # Recheck actual accepted content after both denial attempts.
        wait_evidence(owner, receiver, receiver_port, timeout=3, view_id=allowed,
                      sentinel="accepted-" + profile)
        evidence[profile] = {"http_status": status, "reason": reason, "denied_id_absent": True,
                             "positive_content_retained": True, "public_rejection_reported": True}
    return evidence


def outage(owner, repository, run, env, port, fault):
    # Reserve an unlistening port for the whole call: it cannot be acquired by an
    # unrelated service or accidentally turned into a receiver by this example.
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", port))
        result = publish(owner, repository, run, env, port, "outage:sample", "undeliverable",
                         label="outage-publisher", fault=fault)
        require("server_unavailable" in result["diagnostic"], "Outage was not reported by publisher")
        with socket.socket() as probe:
            probe.settimeout(0.2)
            require(probe.connect_ex(("127.0.0.1", port)) != 0,
                    "Unexpected listener at unavailable destination")
    return {**result, "destination_unavailable": True, "unexpected_listener": False}


def config_discovery(owner, repository, run, env, port, fault):
    project, shell = run / "project", run / "shell"
    project.mkdir()
    shell.mkdir()
    source = project / "application.py"
    marker = project / "APPLICATION_EXECUTED"
    source.write_text(
        "from pathlib import Path\nfrom plotsrv import view\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        '@view(view_id="passive:known", label="Distinct label")\ndef known(): return 1\n'
        '@view(view_id="passive:excluded")\ndef excluded(): return 2\n', encoding="utf-8")
    cli = [sys.executable, "-m", "plotsrv.cli_entry"]
    config = project / "generated.yml"
    child = owner.start(cli + ["config", "create", "--config", str(config)],
                        cwd=shell, env=env, label="config-create")
    owner.wait(child, timeout=10)
    require(config.is_file(), "Config create produced no file")
    settings = yaml.safe_load(config.read_text())
    settings["storage-settings"] = {"enabled": False}
    settings["publisher-settings"] = {
        "discovery": {"target": "./application.py", "exact_selection": ["passive:excluded"]},
        "instances": {"chosen": {"discovery": {"exact_selection": ["passive:known"]}}},
    }
    config.write_text(yaml.safe_dump(settings), encoding="utf-8")
    # Populate has no --name; it selects the instance using PLOTSRV_NAME.
    child = owner.start(cli + ["config", "populate", "limits", str(source),
                        "--config", str(config), "--mode", "merge", "--text", "123"],
                        cwd=shell, env={**env, "PLOTSRV_NAME": "chosen"}, label="config-populate")
    owner.wait(child, timeout=10)
    populated = yaml.safe_load(config.read_text())["limits"]["views"]
    require(set(populated) == {"passive:known"}, "Population lost exact ID or instance selection")
    require(not marker.exists(), "Config population executed application code")
    decoy = shell / "plotsrv.yml"
    decoy.write_text("publisher-settings:\n  discovery:\n    target: ./DOES_NOT_EXIST\n", encoding="utf-8")
    receiver = owner.start(cli + ["run", "--config", str(config), "--name", "chosen",
        "--port", str(port), "--no-watch", "--quiet"], cwd=shell,
        env={**env, "PLOTSRV_CONFIG": str(decoy), "PLOTSRV_NAME": "wrong"}, label="passive-run")
    wait_evidence(owner, receiver, port, timeout=15)
    ids = {v["view_id"] for v in catalogue(owner, receiver, port)}
    require(ids == {"passive:known"}, "Passive discovery/CLI config and instance precedence failed")
    require(not marker.exists(), "Passive discovery executed application code")
    if fault:
        require("deliberately:absent" in ids, "Required discovery evidence missing")
    return {"discovered_ids": sorted(ids), "populated_ids": sorted(populated),
            "side_effect_absent": True, "explicit_config_and_name_won": True,
            "config_relative_source_resolved": True}


def main(*, scenario="admission", port=0, inspect=False, inspect_seconds=30, fault=None):
    result = {"scenario": scenario, "success": False, "manual_status": "pending"}
    owner, code = None, 1
    try:
        if not 0 <= port <= 65535 or not math.isfinite(inspect_seconds) or inspect_seconds < 0:
            raise ValueError("Use valid port and finite nonnegative inspection duration")
        provenance = require_candidate()
        result["provenance"] = {k: provenance[k] for k in
                                ("core_reference", "runtime_candidate", "relationship")}
        repository = Path(__file__).resolve().parents[3]
        run = create(repository)
        port = available_port(port)
        result.update(workspace=str(run), port=port)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PLOTSRV_", "EXAMPLE_"))}
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
                   PYTHONPATH=str(Path(provenance["core_reference"]["path"]) / "src"))
        owner = Processes()
        with interruption_cleanup(), owner:
            function = {"admission": admission, "outage": outage, "config-discovery": config_discovery}[scenario]
            result["evidence"] = function(owner, repository, run, env, port, fault)
            if inspect and scenario != "outage":
                print(f"Assurance ready: {scenario}, port {port} ({inspect_seconds:g}s)",
                      file=sys.stderr, flush=True)
                deadline = time.monotonic() + inspect_seconds
                while time.monotonic() < deadline:
                    owner.pump()
                    for child in owner.children:
                        if child.label in ("keyed", "catalogue", "passive-run"):
                            child.require_alive()
                    time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        result["success"], code = True, 0
    except KeyboardInterrupt:
        result["error"], code = "Interrupted; owned children cleaned up", 130
    except (LifecycleError, OSError, ValueError, KeyError, http.client.HTTPException, psutil.Error) as exc:
        result["error"] = str(exc)
    finally:
        if owner is not None:
            result["children"] = [{"label": c.label, "pid": c.process.pid,
                                   "exit": c.process.poll(), "tail": c.diagnostic()}
                                  for c in owner.children]
            result["owned_children_reaped"] = all(c["exit"] is not None for c in result["children"])
        print(json.dumps(result, indent=2), flush=True)
    return code
