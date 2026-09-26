"""Release aggregation must fail closed independently of scenario implementations."""

import json
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from plotsrv_examples import suites


PROVENANCE = {"core_reference": {"revision": "test"}, "runtime_candidate": {},
              "relationship": "matching source checkout", "readiness": "ready"}


@pytest.fixture
def harness(monkeypatch):
    monkeypatch.setattr(suites, "SCENARIOS", {"one": ("fake", {}), "two": ("fake", {})})
    monkeypatch.setattr(suites, "report", lambda: PROVENANCE.copy())
    def install(function):
        monkeypatch.setattr(suites.importlib, "import_module", lambda *a: SimpleNamespace(main=function))
    return install


def successful(**kwargs):
    print(json.dumps({"success": True, "evidence": {"observed": True},
                      "owned_children_reaped": True,
                      "provenance": suites.provenance(PROVENANCE)}))
    return 0


def test_success_withholds_manual_signoff(harness, capsys):
    harness(successful)
    assert suites.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["automated_status"] == "passed"
    assert result["manual_status"] == "pending"
    assert result["release_signoff"] == "withheld"
    assert all(item["status"] == "passed" for item in result["results"])


@pytest.mark.parametrize("failure", ["assertion", "dependency", "timeout", "interrupt", "empty", "nonzero", "cleanup"])
def test_required_failure_never_passes(harness, capsys, failure):
    def broken(**kwargs):
        if failure == "assertion":
            raise AssertionError("required sentinel missing")
        if failure == "dependency":
            raise ModuleNotFoundError("required renderer absent")
        if failure == "timeout":
            time.sleep(1)
        if failure == "interrupt":
            raise KeyboardInterrupt
        print(json.dumps({"success": True, "evidence": {} if failure == "empty" else {"observed": True},
                          "owned_children_reaped": failure != "cleanup"}))
        return 1 if failure == "nonzero" else 0
    harness(broken)
    assert suites.main(scenario_timeout=0.02) != 0
    result = json.loads(capsys.readouterr().out)
    assert result["success"] is False
    assert result["automated_status"] != "passed"
    assert result["results"][0]["status"] != "passed"
    assert result["results"][1]["status"] == "not_run"
    assert result["release_signoff"] == "withheld"
    assert signal.getitimer(signal.ITIMER_REAL)[0] == 0


def test_provenance_change_blocks(harness, monkeypatch, capsys):
    harness(successful)
    calls = iter([PROVENANCE, {**PROVENANCE, "core_reference": {"revision": "changed"}}])
    monkeypatch.setattr(suites, "report", lambda: next(calls))
    assert suites.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["success"] is False
    assert "changed" in result["error"]


def test_absent_reference_runs_nothing(harness, monkeypatch, capsys):
    monkeypatch.setattr(suites, "report", lambda: {**PROVENANCE, "readiness": "blocked", "problems": ["absent"]})
    assert suites.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["automated_status"] == "blocked"
    assert all(item["status"] == "not_run" for item in result["results"])


def test_live_timeout_reaps_owned_children():
    import psutil
    completed = subprocess.run(
        [sys.executable, "-m", "plotsrv_examples", "check", "release", "--scenario-timeout", "2"],
        capture_output=True, text=True, timeout=15,
    )
    assert completed.returncode == 1, completed.stderr
    result = json.loads(completed.stdout)
    first = result["results"][0]
    assert first["status"] == "timed_out", result
    assert not result["success"]
    assert first["report"]["owned_children_reaped"]
    for child in first["report"]["children"]:
        assert child["exit"] is not None
        assert not psutil.pid_exists(child["pid"])
