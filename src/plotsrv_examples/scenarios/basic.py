"""One real receiver/publisher check; faults exercise assurance honesty."""

import json
import math
import os
from pathlib import Path
import sys
from uuid import uuid4

from ..support.lifecycle import (
    LifecycleError, Processes, available_port, interruption_cleanup,
    require_candidate, wait_evidence,
)
from ..workspace import create, owned_directory


def main(*, port=0, evidence_timeout=3.0, fault=None):
    result = {"scenario": "basic-publication", "success": False, "fault": fault,
              "manual_status": "pending", "release_signoff": "withheld"}
    owner = None
    code = 1
    try:
        if not 0 <= port <= 65535:
            raise ValueError("port must be between 0 and 65535")
        if not math.isfinite(evidence_timeout) or evidence_timeout <= 0:
            raise ValueError("evidence timeout must be finite and positive")
        provenance = require_candidate()
        result["provenance"] = {key: provenance[key] for key in
                                ("core_reference", "runtime_candidate", "relationship")}
        port = available_port(port)
        result["port"] = port
        repository = Path(__file__).resolve().parents[3]
        run = create(repository)
        result["workspace"] = str(run)
        config = run / "plotsrv.yml"
        with owned_directory(repository, run) as fd:
            config_fd = os.open("plotsrv.yml", os.O_WRONLY | os.O_CREAT | os.O_EXCL
                                | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(config_fd, "w") as output:
                output.write("storage-settings:\n  enabled: false\n")
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("PLOTSRV_")}
        env.update(PLOTSRV_CONFIG=str(config), PYTHONDONTWRITEBYTECODE="1",
                   PYTHONUNBUFFERED="1", MPLCONFIGDIR=str(run / "matplotlib-cache"),
                   XDG_CACHE_HOME=str(run / "cache"))
        # Explicitly execute the already-validated source candidate and this
        # example from the isolated cwd; never rely on relative PYTHONPATH.
        env["PYTHONPATH"] = os.pathsep.join([
            str(Path(provenance["core_reference"]["path"]) / "src"),
            str(repository / "src"),
        ])
        view_id = "assurance-" + uuid4().hex
        sentinel = "plotsrv-sentinel-" + uuid4().hex
        result.update(view_id=view_id, sentinel=sentinel)
        owner = Processes()
        with interruption_cleanup(), owner:
            receiver_args = [sys.executable, "-m", "plotsrv.cli_entry", "serve",
                             "--host", "127.0.0.1", "--port", str(port),
                             "--config", str(config), "--quiet"]
            if fault == "startup":
                receiver_args[-2] = str(run / "absent-config.yml")
            receiver = owner.start(receiver_args, cwd=run, env=env, label="receiver")
            result["receiver_pid"] = receiver.process.pid
            wait_evidence(owner, receiver, port, timeout=15)
            print(f"Receiver ready: pid={receiver.process.pid} port={port}", file=sys.stderr, flush=True)
            publisher_args = [sys.executable, "-m", "plotsrv_examples.scenarios.publish_basic",
                              f"http://127.0.0.1:{port}", view_id, sentinel]
            if fault == "missing-evidence":
                publisher_args.append("--skip")
            if fault == "high-output":
                publisher_args.append("--high-output")
            publisher = owner.start(publisher_args, cwd=run, env=env, label="publisher")
            result["publisher_pid"] = publisher.process.pid
            owner.wait(publisher, timeout=15)
            result["publisher_exit"] = publisher.process.returncode
            wait_evidence(owner, receiver, port, timeout=evidence_timeout,
                          view_id=view_id, sentinel=sentinel)
            result["evidence"] = {"logical_view": True, "artifact_sentinel": True}
        result["success"] = True
        code = 0
    except KeyboardInterrupt:
        result["error"] = "Interrupted; owned-child cleanup attempted"
        code = 130
    except (LifecycleError, OSError, ValueError) as exc:
        result["error"] = str(exc)
    finally:
        if owner is not None:
            result["children"] = [
                {"label": child.label, "pid": child.process.pid,
                 "exit": child.process.poll(), "output_bytes": child.total_bytes,
                 "retained_bytes": len(child.output),
                 "tail": child.output.decode("utf-8", errors="replace")}
                for child in owner.children
            ]
            result["owned_children_reaped"] = all(c["exit"] is not None for c in result["children"])
        print(json.dumps(result, indent=2), flush=True)
    return code
