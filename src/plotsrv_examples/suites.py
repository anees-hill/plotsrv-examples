"""Required deterministic release coverage; manual approval is never inferred."""

from contextlib import redirect_stdout
from datetime import datetime, timezone
import importlib
import io
import json
import math
import signal
import sys

from .doctor import report


# Stable names are shared by list, release reports, and the coverage matrix.
SCENARIOS = {
    "basic-publication": ("basic", {}),
    "gallery": ("gallery", {}),
    "stream-structured": ("stream_structured", {}),
    "stream-http": ("stream_http", {}),
    "stream-python-logs": ("stream_python_logs", {}),
    "observe-etl": ("observe_etl", {}),
    "local-watch": ("watch", {"scenario": "local-watch"}),
    "remote-publish": ("watch", {"scenario": "remote-publish"}),
    "remote-watch": ("watch", {"scenario": "remote-watch"}),
    "admission": ("admission_config", {"scenario": "admission"}),
    "outage": ("admission_config", {"scenario": "outage"}),
    "config-discovery": ("admission_config", {"scenario": "config-discovery"}),
    "storage-history": ("storage_history", {}),
    "checks-webhook": ("checks_webhook", {}),
    "resource-monitor": ("resource_monitor", {}),
    "weather-demo": ("weather_demo", {"mode": "sample"}),
}


class ScenarioTimeout(RuntimeError):
    pass


def provenance(value):
    return {key: value[key] for key in
            ("core_reference", "runtime_candidate", "relationship")}


def execute(name, *, timeout, fault=None):
    """Bound each scenario while allowing its owned-process contexts to unwind."""
    module, kwargs = SCENARIOS[name]
    output = io.StringIO()
    result = {"id": name, "required": True, "status": "failed"}
    def expired(signum, frame):
        raise ScenarioTimeout(f"Required scenario exceeded {timeout:g}s")
    previous = signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, timeout)
        with redirect_stdout(output):
            function = importlib.import_module(f".scenarios.{module}", __package__).main
            code = function(**kwargs, fault=fault)
        result["exit_code"] = code
        evidence = json.loads(output.getvalue())
        result["report"] = evidence
        if (code == 0 and evidence.get("success") is True
                and evidence.get("evidence")
                and evidence.get("owned_children_reaped") is True):
            result["status"] = "passed"
        else:
            result["error"] = evidence.get("error", "Required evidence or cleanup incomplete")
        if code == 130:
            result["status"] = "interrupted"
    except ScenarioTimeout as exc:
        result.update(status="timed_out", error=str(exc))
    except KeyboardInterrupt:
        result.update(status="interrupted", error="Interrupted")
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        if "report" not in result and output.getvalue():
            try:
                result["report"] = json.loads(output.getvalue())
            except ValueError:
                result["output_tail"] = output.getvalue()[-65536:]
    return result


def main(*, scenario_timeout=120.0, fault=None):
    result = {
        "suite": "release", "success": False, "automated_status": "blocked",
        "release_signoff": "withheld", "manual_status": "pending",
        "manual_checklist": "assurance/manual-checklist.md",
        "tester": None, "browser": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "required_scenarios": list(SCENARIOS), "results": [],
    }
    code = 1
    previous = signal.signal(signal.SIGTERM, signal.default_int_handler)
    try:
        if not math.isfinite(scenario_timeout) or scenario_timeout <= 0:
            raise ValueError("Scenario timeout must be finite and positive")
        before = report()
        result["provenance"] = provenance(before)
        if before["readiness"] != "ready":
            raise ValueError("Candidate/reference rejected: " + "; ".join(before["problems"]))
        for name in SCENARIOS:
            print(f"Required scenario: {name}", file=sys.stderr, flush=True)
            item = execute(name, timeout=scenario_timeout,
                           fault=fault if name == "basic-publication" else None)
            result["results"].append(item)
            if item["status"] == "passed" and item["report"].get("provenance") != result["provenance"]:
                item.update(status="failed", error="Scenario candidate/reference changed")
            if item["status"] != "passed":
                result["automated_status"] = "failed"
                code = 130 if item["status"] == "interrupted" else 1
                break
        after = report()
        result["provenance_after"] = provenance(after)
        if after["readiness"] != "ready" or result["provenance_after"] != result["provenance"]:
            raise ValueError("Core/reference or runtime provenance changed during suite")
        if len(result["results"]) == len(SCENARIOS) and all(
                item["status"] == "passed" for item in result["results"]):
            result.update(success=True, automated_status="passed")
            code = 0
    except KeyboardInterrupt:
        result.update(success=False, automated_status="interrupted", error="Interrupted")
        code = 130
    except Exception as exc:
        result["success"] = False
        code = 1
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        signal.signal(signal.SIGTERM, previous)
        completed = {item["id"] for item in result["results"]}
        result["results"].extend({"id": name, "required": True, "status": "not_run"}
                                 for name in SCENARIOS if name not in completed)
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        print(json.dumps(result, indent=2), flush=True)
    return code


def listing():
    print(json.dumps({"quick": ["basic-publication"], "release": list(SCENARIOS),
                      "manual_checklist": "assurance/manual-checklist.md"}, indent=2))
    return 0
