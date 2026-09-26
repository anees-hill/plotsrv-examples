"""Public workflows must deliver content, reject missing evidence and reap children."""

import json
from pathlib import Path
import subprocess
import sys

import psutil
import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("scenario", ["local-watch", "remote-publish", "remote-watch"])
@pytest.mark.parametrize("fault", [False, True])
def test_file_workflow(scenario, fault):
    completed = subprocess.run(
        [sys.executable, "-m", "plotsrv_examples", "run", scenario]
        + (["--fault", "missing-evidence"] if fault else []),
        cwd=ROOT, capture_output=True, text=True, timeout=40)
    result = json.loads(completed.stdout)
    assert completed.returncode == (1 if fault else 0), completed.stdout + completed.stderr
    assert result["success"] is not fault
    assert result["owned_children_reaped"]
    assert result["children"]
    assert all(not psutil.pid_exists(child["pid"]) for child in result["children"])
    if fault:
        assert "Receiver evidence timed out" in result["error"]
        assert "evidence" not in result
    else:
        evidence = result["evidence"]
        assert evidence["first"].startswith("first-")
        if scenario != "remote-publish":
            assert evidence["second"].startswith("second-")
        if scenario != "local-watch":
            assert evidence["content_after_source_removal"]
            assert not (Path(result["workspace"]) / "publisher/sample.txt").exists()
        if scenario == "remote-watch":
            assert evidence["source_status"] == "missing"
            assert evidence["hosted_content"] == evidence["second"]
            assert evidence["publisher_path_absent"]
