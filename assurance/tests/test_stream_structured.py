"""Real post-attach receipt, missing evidence, and inspection interruption."""

import json
from pathlib import Path
import select
import signal
import subprocess
import sys

import psutil
import pytest


ROOT = Path(__file__).resolve().parents[2]
COMMAND = [sys.executable, "-m", "plotsrv_examples", "run", "stream-structured"]


def assert_reaped(result):
    assert result["owned_children_reaped"]
    assert {child["label"] for child in result["children"]} == {"receiver", "writer", "follower"}
    for child in result["children"]:
        assert not psutil.pid_exists(child["pid"])


@pytest.mark.parametrize("fault", [False, True])
@pytest.mark.parametrize("scenario", ["stream-structured", "stream-http", "stream-python-logs"])
def test_delivery_and_missing_evidence(fault, scenario):
    completed = subprocess.run(COMMAND[:-1] + [scenario] + (["--fault", "missing-evidence"] if fault else []),
                               cwd=ROOT, capture_output=True, text=True, timeout=35)
    result = json.loads(completed.stdout)
    assert completed.returncode == (1 if fault else 0), completed.stdout + completed.stderr
    assert result["success"] is not fault
    assert_reaped(result)
    if fault:
        assert "Stream evidence timed out" in result["error"]
        assert "evidence" not in result
    else:
        evidence = result["evidence"]
        assert evidence["pre_attach_absent"]
        assert evidence["lifecycle"] == "ended"
        if scenario == "stream-structured":
            assert evidence["records"] == [
                {"sequence": n, "synthetic": True, "level": "INFO", "value": n * 3}
                for n in range(1, 7)]
        elif scenario == "stream-http":
            assert evidence["fallback_without_http"] and evidence["traceback_unattributed"]
            assert evidence["request_count"] == 3 and evidence["inspected_count"] == 6
            assert evidence["event_kinds"] == ["http_request", "http_request", "traceback",
                                               "text", "text", "http_request"]
        else:
            assert evidence["log_events"] == 3 and evidence["raw_records"] == 4
            assert evidence["unrecognised_text_retained"]
            assert "Warnings and errors" in evidence["suggestions"]
        assert evidence["source_bytes"] < 1024


@pytest.mark.parametrize("scenario", ["stream-structured", "stream-http", "stream-python-logs"])
def test_inspection_interrupt_keeps_log_fixed_and_reaps_children(scenario):
    process = subprocess.Popen(COMMAND[:-1] + [scenario, "--inspect", "--inspect-seconds", "60"],
                               cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True)
    try:
        readable, _, _ = select.select([process.stderr], [], [], 25)
        assert readable, "Inspection did not become ready"
        assert "Stream ready:" in process.stderr.readline()
        # At readiness the writer/follower have already exited; only receiver remains.
        live = psutil.Process(process.pid).children()
        assert len(live) == 1
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=10)
        result = json.loads(stdout)
        assert process.returncode == 130, stdout + stderr
        assert not result["success"]
        assert_reaped(result)
        source_name = "events.log" if scenario == "stream-http" else "python.log" if scenario == "stream-python-logs" else "events.jsonl"
        source = Path(result["workspace"]) / source_name
        assert source.stat().st_size == result["evidence"]["source_bytes"] < 1024
        assert len(source.read_text().splitlines()) == (10 if scenario == "stream-http" else 5 if scenario == "stream-python-logs" else 7)
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=10)
