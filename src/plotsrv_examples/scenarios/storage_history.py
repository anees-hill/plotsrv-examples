"""Public history and restart evidence inside a fresh owned store."""

import http.client
import json
import math
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlencode

from ..support.lifecycle import (LifecycleError, Processes, _json, available_port,
                                 interruption_cleanup, require_candidate, wait_evidence)
from ..support.storage import OwnedStore
from ..workspace import create, WorkspaceError
from .admission_config import publish, require

VIEW = "history:versions"


def read(owner, receiver, port, endpoint, **query):
    require(receiver.owns_listener(port), "Evidence listener is not owned")
    return _json(port, endpoint + "?" + urlencode({"view": VIEW, **query}),
                 time.monotonic() + 2, owner)


def until(owner, receiver, port, endpoint, predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = read(owner, receiver, port, endpoint)
        if predicate(value):
            return value
        owner.pump()
        time.sleep(0.03)
    raise LifecycleError("Required storage evidence missing: " + endpoint)


def main(*, port=0, inspect=False, inspect_seconds=30, fault=None):
    result = {"scenario": "storage-history", "success": False, "manual_status": "pending"}
    owners, code = [], 1
    try:
        if not 0 <= port <= 65535 or not math.isfinite(inspect_seconds) or inspect_seconds < 0:
            raise ValueError("Use valid port and finite nonnegative inspection duration")
        provenance = require_candidate()
        result["provenance"] = {k: provenance[k] for k in
                                ("core_reference", "runtime_candidate", "relationship")}
        repository = Path(__file__).resolve().parents[3]
        run = create(repository)
        store = OwnedStore(repository, run)
        result["workspace"] = str(run)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PLOTSRV_", "EXAMPLE_"))}
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
                   PYTHONPATH=str(Path(provenance["core_reference"]["path"]) / "src"))
        port = available_port(port)
        result["port"] = port
        cli = [sys.executable, "-m", "plotsrv.cli_entry", "serve"]
        evidence = {}
        with interruption_cleanup():
            for stage in ("disabled", "publish", "restart"):
                owner = Processes()
                owners.append(owner)
                with owner, store.configuration(enabled=stage != "disabled") as config:
                    receiver = owner.start(cli + ["--config", str(config), "--port", str(port), "--quiet"],
                                           cwd=run, env=env, label=stage)
                    store.writers.append(receiver)
                    wait_evidence(owner, receiver, port, timeout=15)
                    if stage == "disabled":
                        publish(owner, repository, run, env, port, VIEW, "storage-off",
                                label="disabled-publish")
                        wait_evidence(owner, receiver, port, timeout=5, view_id=VIEW, sentinel="storage-off")
                        history = read(owner, receiver, port, "/history")
                        require(history["count"] == 0 and history["result"] == "unavailable",
                                "Disabled history did not report unavailable")
                        evidence["storage_disabled"] = True
                    elif stage == "publish":
                        require(read(owner, receiver, port, "/history")["count"] == 0,
                                "Storage-off publication persisted")
                        ids = []
                        for version in (1, 2, 3):
                            sentinel = f"recognisable-version-{version}"
                            publish(owner, repository, run, env, port, VIEW, sentinel,
                                    label=f"version-{version}")
                            wait_evidence(owner, receiver, port, timeout=5, view_id=VIEW, sentinel=sentinel)
                            history = until(owner, receiver, port, "/history", lambda h:
                                h["count"] == min(version, 2) and h["snapshots"][0]["snapshot_id"] not in ids)
                            ids.append(history["snapshots"][0]["snapshot_id"])
                        require({s["snapshot_id"] for s in history["snapshots"]} == set(ids[1:]),
                                "Retention did not keep versions two and three")
                        for snapshot, version in zip(reversed(history["snapshots"]), (2, 3)):
                            artifact = read(owner, receiver, port, "/artifact", snapshot=snapshot["snapshot_id"])
                            require(f"recognisable-version-{version}" in artifact["html"], "Historical content mismatch")
                        before = read(owner, receiver, port, "/status")
                        require(before["freshness"]["state"] == "ok", "Published data was not fresh")
                        until(owner, receiver, port, "/status", lambda s: s["freshness"]["state"] == "warn")
                        until(owner, receiver, port, "/status", lambda s: s["freshness"]["state"] == "error")
                        retained = [s["snapshot_id"] for s in history["snapshots"]]
                        evidence.update(retained_ids=retained, versions=[2, 3], freshness=["ok", "warn", "error"])
                    else:
                        status = wait_evidence(owner, receiver, port, timeout=5, view_id=VIEW,
                                               sentinel="recognisable-version-3")
                        status = read(owner, receiver, port, "/status")
                        require(status["restored_from_storage"] and status["restore_source"] == "latest",
                                "Restored provenance absent")
                        require(status["last_updated"] == persisted_time and
                                status["freshness"]["state"] == "error", "Restart reset freshness time")
                        require(status["data_activity"]["events"] == [] and status["last_data_arrival_at"] is None,
                                "Restart manufactured a publication arrival")
                        after = read(owner, receiver, port, "/history")
                        require([s["snapshot_id"] for s in after["snapshots"]] == retained,
                                "Restart changed retained snapshot identities")
                        for snapshot, version in zip(reversed(after["snapshots"]), (2, 3)):
                            artifact = read(owner, receiver, port, "/artifact", snapshot=snapshot["snapshot_id"])
                            require(f"recognisable-version-{version}" in artifact["html"],
                                    "Restart lost historical content")
                        month = before["last_updated"][:7]
                        calendar = read(owner, receiver, port, "/history/month", month=month)
                        require(calendar["timezone"] == "UTC" and calendar["days"], "UTC history days absent")
                        evidence.update(restored_timestamp=status["last_updated"], restart_arrivals=0,
                                        restart_snapshots_unchanged=True, calendar_days=calendar["days"])
                        if fault:
                            raise LifecycleError("Required storage evidence missing: deliberate failure drill")
                        if inspect:
                            print(f"History ready for manual inspection at http://127.0.0.1:{port}",
                                  file=sys.stderr, flush=True)
                            end = time.monotonic() + inspect_seconds
                            while time.monotonic() < end:
                                receiver.require_alive()
                                owner.pump()
                                time.sleep(0.03)
                if stage == "publish":
                    inspector = Processes()
                    owners.append(inspector)
                    with inspector:
                        persisted = store.command(inspector, env, "list", view=VIEW)
                    persisted_time = persisted.split("latest:\n", 1)[1].split()[0]
                    evidence["persisted_timestamp"] = persisted_time
            owner = Processes()
            owners.append(owner)
            with owner:
                try:
                    store.command(owner, env, "clear", root=repository)
                except WorkspaceError:
                    evidence["unowned_clear_rejected"] = True
                else:
                    raise LifecycleError("Unowned clear was not rejected")
                stats = store.command(owner, env, "stats")
                listing = store.command(owner, env, "list", view=VIEW)
                require("snapshot_count: 2" in stats and "latest_count: 1" in stats and
                        all(s in listing for s in retained), "Store CLI disagrees with history")
                evidence["store_stats"] = stats
                evidence["store_list"] = listing
                evidence["clear"] = store.command(owner, env, "clear", view=VIEW)
                empty = store.command(owner, env, "stats")
                require("snapshot_count: 0" in empty and "latest_count: 0" in empty,
                        "Owned clear left stored versions")
                evidence["owned_clear_verified"] = True
        result.update(success=True, evidence=evidence)
        code = 0
    except KeyboardInterrupt:
        result["error"], code = "Interrupted; owned children cleaned up", 130
    except (LifecycleError, OSError, ValueError, KeyError, http.client.HTTPException) as exc:
        result["error"] = str(exc)
    finally:
        result["children"] = [{"label": c.label, "pid": c.process.pid, "exit": c.process.poll(),
                               "tail": c.diagnostic()} for o in owners for c in o.children]
        result["owned_children_reaped"] = all(c["exit"] is not None for c in result["children"])
        print(json.dumps(result, indent=2), flush=True)
    return code
