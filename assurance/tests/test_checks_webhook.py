"""Real webhook delivery/failure and manual-control preparation, without a browser."""

import json
from pathlib import Path
import select
import subprocess
import sys
import time

import pytest

from plotsrv_examples.scenarios.checks_webhook import control

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("value", [None, {}, {"revision": True, "state": "failing", "schema": 1},
    {"revision": 7, "state": "failing", "schema": 1},
    {"revision": 1, "state": "execute", "schema": 1},
    {"revision": 1, "state": "failing", "schema": False},
    {"revision": 1, "state": "failing", "schema": 1, "url": "http://external"}])
def test_invalid_controls_cannot_choose_destinations(value):
    with pytest.raises(ValueError):
        control(value)


def test_checks_webhook_failure_drill():
    done = subprocess.run([sys.executable, "-m", "plotsrv_examples", "run", "checks-webhook",
                           "--fault", "missing-evidence"], cwd=ROOT,
                          capture_output=True, text=True, timeout=60)
    result = json.loads(done.stdout)
    assert done.returncode == 1, done.stdout + done.stderr
    assert not result["success"] and "evidence missing" in result["error"]
    assert "evidence" not in result and result["owned_children_reaped"]


def test_checks_webhook_and_manual_controls():
    process = subprocess.Popen([sys.executable, "-m", "plotsrv_examples", "run", "checks-webhook",
        "--inspect", "--inspect-seconds", "4"], cwd=ROOT, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 45
        ready = ""
        while time.monotonic() < deadline and process.poll() is None:
            if select.select([process.stderr], [], [], 0.1)[0]:
                line = process.stderr.readline()
                if "Checks ready for manual inspection:" in line:
                    ready = line
                    break
        assert ready, "Manual preparation did not become ready"
        path = Path(ready.split("; edit ", 1)[1].strip())
        path.write_text(json.dumps({"revision": 1, "state": "failing", "schema": 2}))
        stdout, stderr = process.communicate(timeout=20)
        result = json.loads(stdout)
        assert process.returncode == 0, stdout + stderr
    finally:
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=10)
    assert result["success"] and result["owned_children_reaped"]
    assert result["manual_status"] == "pending"
    assert result["manual"]["status"] == "manual-pending"
    assert result["manual"]["applied_controls"][-1]["schema"] == 2
    assert result["manual"]["applied_controls"][-1]["state"] == "failing"
    evidence = result["evidence"]
    assert evidence["baseline_events"] == 0 and evidence["unchanged_failure_silent"]
    assert evidence["state_events"] == ["triggered", "recovered"]
    assert evidence["event_matches"] == 1
    assert evidence["sink_identity_headers_verified"]
    assert all(0 < size <= 8192 for size in evidence["sink_payload_sizes"])
    assert [p["event_type"] for p in evidence["sink_payloads"]] == ["triggered", "recovered", "match"]
    assert evidence["unavailable"]["failures"] == 6
    assert evidence["unavailable"]["attempts"] == 3
    assert evidence["unavailable"]["queued"] == evidence["unavailable"]["delivered"] == 0
    assert all(r["application_result"] == 20 for r in evidence["application_reports"])
