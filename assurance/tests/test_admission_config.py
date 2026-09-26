"""Real denial, outage and passive discovery evidence with failure drills."""

import json
from pathlib import Path
import subprocess
import sys

import psutil
import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("scenario", ["admission", "outage", "config-discovery"])
@pytest.mark.parametrize("fault", [False, True])
def test_admission_outage_discovery(scenario, fault):
    completed = subprocess.run(
        [sys.executable, "-m", "plotsrv_examples", "run", scenario]
        + (["--fault", "missing-evidence"] if fault else []),
        cwd=ROOT, capture_output=True, text=True, timeout=50)
    result = json.loads(completed.stdout)
    assert completed.returncode == (1 if fault else 0), completed.stdout + completed.stderr
    assert result["success"] is not fault
    assert result["owned_children_reaped"]
    assert result["children"]
    assert all(not psutil.pid_exists(child["pid"]) for child in result["children"])
    if fault:
        assert "evidence missing" in result["error"]
        assert "evidence" not in result
        return
    evidence = result["evidence"]
    if scenario == "admission":
        assert evidence["keyed"]["http_status"] == 401
        assert evidence["catalogue"]["http_status"] == 403
        for profile in evidence.values():
            assert profile["denied_id_absent"] and profile["positive_content_retained"]
            assert profile["public_rejection_reported"]
    elif scenario == "outage":
        assert evidence["application_result"] == 20 and evidence["publication_returned"]
        assert evidence["destination_unavailable"] and not evidence["unexpected_listener"]
        assert evidence["listeners_after_call"] == evidence["descendants_after_call"] == []
        assert "server_unavailable" in evidence["diagnostic"]
    else:
        assert evidence["discovered_ids"] == evidence["populated_ids"] == ["passive:known"]
        assert evidence["side_effect_absent"]
        assert evidence["explicit_config_and_name_won"] and evidence["config_relative_source_resolved"]
        assert not (Path(result["workspace"]) / "project/APPLICATION_EXECUTED").exists()
