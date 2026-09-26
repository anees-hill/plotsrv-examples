"""Finite ETL application output and independent public receiver evidence."""

import html
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlencode
from uuid import uuid4

from ..support.lifecycle import (
    LifecycleError, Processes, _json, available_port, interruption_cleanup,
    require_candidate, wait_evidence,
)
from ..workspace import create


EXPECTED = {
    "scope": "all transformed paid orders in this synthetic batch",
    "currency_unit": "cents", "paid_orders": 42, "net_cents": 61925,
    "regions": {
        "north": {"orders": 14, "gross_cents": 20825, "discount_cents": 700, "net_cents": 20125},
        "south": {"orders": 14, "gross_cents": 21000, "discount_cents": 0, "net_cents": 21000},
        "west": {"orders": 14, "gross_cents": 20800, "discount_cents": 0, "net_cents": 20800},
    },
}


def output_documents(child):
    documents = []
    for line in child.output.decode().splitlines():
        if line.startswith("{"):
            documents.append(json.loads(line))
    return documents


def observation(owner, receiver, port, view_id):
    wait_evidence(owner, receiver, port, timeout=5, view_id=view_id,
                  sentinel="How this observation was captured")
    artifact = _json(port, "/artifact?" + urlencode({"view": view_id}),
                     time.monotonic() + 5, owner)
    markup = artifact["html"]
    if artifact["meta"].get("observation_version") != 1:
        raise ValueError("Missing public observation version")
    projection = re.search(r'<div hidden data-observation-data="1">(.*?)</div>', markup, re.S)
    details = re.search(r'<h4>Technical provenance</h4><pre[^>]*>(.*?)</pre>', markup, re.S)
    if not projection or not details:
        raise ValueError("Missing public observation projection/provenance")
    return json.loads(html.unescape(projection[1])), json.loads(html.unescape(details[1]))


def verify(owner, receiver, port, prefix):
    orders, provenance = observation(owner, receiver, port, prefix + ":orders")
    metrics, metric_provenance = observation(owner, receiver, port, prefix + ":metrics")
    for info in (provenance, metric_provenance):
        if (info["captured_at_unix_s"] <= 0
                or info["provenance"]["origin"] != "python_publisher"
                or info["provenance"]["consistency"] != "best_effort"
                or not info["provenance"].get("publisher_session")
                or info["sampling"]["unbiased_random"] is not False):
            raise ValueError("Incorrect observation provenance")
    if provenance["provenance"]["publisher_session"] != metric_provenance["provenance"]["publisher_session"]:
        raise ValueError("Observations did not originate in the same publisher session")
    if provenance["provenance"]["selection"] != {"fields": [], "path": []}:
        raise ValueError("Unexpected order selection")
    expected_metrics = {"input_orders": 48, "paid_orders": 42, "cancelled_orders": 6, "net_cents": 61925}
    if metric_provenance["provenance"]["selection"] != {"fields": list(expected_metrics), "path": ["batch"]}:
        raise ValueError("Incorrect selected metric branch")
    fields = {row["field"]: row for row in orders["rows"] if row["surface"] == "Fields"}
    if set(fields) != {"order_id", "region", "gross_cents", "discount_cents", "net_cents"}:
        raise ValueError("Missing observed order columns")
    for row in fields.values():
        if not (0 < row["inspected"] <= 32 < 42) or row["evidence"] != "Observed sample":
            raise ValueError(f"Incorrect bounded scope: {row}")
    if fields["order_id"]["observed_min"] != "2" or fields["order_id"]["observed_max"] != "48":
        raise ValueError("Expected sampled endpoint order IDs absent")
    if orders["examples"] or metrics["examples"]:
        raise ValueError("Examples unexpectedly exported")
    supplied = {row["field"]: row for row in metrics["rows"] if row["surface"] == "Fields"}
    if set(supplied) != set(expected_metrics):
        raise ValueError("Missing supplied metrics")
    for name, value in expected_metrics.items():
        if str(supplied[name]["value"]) != str(value) or supplied[name]["evidence"] != "Supplied metric":
            raise ValueError("Incorrect supplied metric content/scope")
    # Compare the public ordinary JSON artifact independently of publisher stdout.
    wait_evidence(owner, receiver, port, timeout=5, view_id=prefix + ":regional-totals", sentinel="61925")
    custom = _json(port, "/artifact?" + urlencode({"view": prefix + ":regional-totals"}),
                   time.monotonic() + 5, owner)
    values = re.findall(r'<pre[^>]*data-json-text-view="1"[^>]*>(.*?)</pre>', custom["html"], re.S)
    if not any(json.loads(html.unescape(re.sub(r"<[^>]+>", "", value))) == EXPECTED for value in values):
        raise ValueError("Incorrect received custom aggregate")
    return {"application_result": EXPECTED, "observed_fields": sorted(fields),
            "metrics": expected_metrics, "sample_scope": "base_sample",
            "publisher_session": provenance["provenance"]["publisher_session"],
            "custom_aggregate": "exact received JSON", "drained": True}


def main(*, port=0, inspect=False, inspect_seconds=30, fault=None):
    result = {"scenario": "observe-etl", "success": False, "manual_status": "pending"}
    owner, code = None, 1
    try:
        if not 0 <= port <= 65535 or not math.isfinite(inspect_seconds) or inspect_seconds < 0:
            raise ValueError("Use a valid port and finite nonnegative inspection duration")
        candidate = require_candidate()
        result["provenance"] = {key: candidate[key] for key in ("core_reference", "runtime_candidate", "relationship")}
        repository = Path(__file__).resolve().parents[3]
        run, port = create(repository), available_port(port)
        result.update(workspace=str(run), port=port)
        config = run / "plotsrv.yml"
        config.write_text("storage-settings:\n  enabled: false\n", encoding="utf-8")
        env = {key: value for key, value in os.environ.items() if not key.startswith("PLOTSRV_")}
        env.update(PLOTSRV_CONFIG=str(config), PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
                   PYTHONPATH=str(Path(candidate["core_reference"]["path"]) / "src"))
        prefix = "etl-" + uuid4().hex
        owner = Processes()
        with interruption_cleanup(), owner:
            receiver = owner.start([sys.executable, "-m", "plotsrv.cli_entry", "serve", "--host",
                                    "127.0.0.1", "--port", str(port), "--config", str(config), "--quiet"],
                                   cwd=run, env=env, label="receiver")
            wait_evidence(owner, receiver, port, timeout=15)
            for name in ("etl", "custom"):
                command = [sys.executable, str(repository / f"examples/observation/{name}.py"),
                           "--port", str(port), "--view-prefix", prefix]
                if fault == "missing-evidence" and name == "etl":
                    # Successful application output without observation must fail assurance.
                    command = [sys.executable, "-c", "import json; print(json.dumps(" + repr({"application_result": EXPECTED}) + "))"]
                publisher = owner.start(command, cwd=run, env=env, label=name)
                owner.wait(publisher, timeout=20)
                documents = output_documents(publisher)
                if not any(doc.get("application_result") == EXPECTED for doc in documents):
                    raise ValueError("Incorrect application result: " + publisher.diagnostic())
                if name == "etl" and fault is None and not any(doc.get("accepted_work_drained") is True for doc in documents):
                    raise ValueError("Observation did not drain")
            result["evidence"] = verify(owner, receiver, port, prefix)
            if inspect:
                print(f"Observation ready: http://127.0.0.1:{port} ({inspect_seconds:g}s; Ctrl+C stops)", file=sys.stderr, flush=True)
                deadline = time.monotonic() + inspect_seconds
                while time.monotonic() < deadline:
                    owner.pump()
                    receiver.require_alive()
                    time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        result["success"], code = True, 0
    except KeyboardInterrupt:
        result["error"], code = "Interrupted; owned children cleaned up", 130
    except (LifecycleError, OSError, ValueError, KeyError) as exc:
        result["error"] = str(exc)
    finally:
        if owner is not None:
            result["children"] = [{"label": child.label, "pid": child.process.pid,
                                    "exit": child.process.poll(), "tail": child.diagnostic()} for child in owner.children]
            result["owned_children_reaped"] = all(child["exit"] is not None for child in result["children"])
        print(json.dumps(result, indent=2), flush=True)
    return code
