"""Metadata and retained external smoke interface regression checks."""

from pathlib import Path
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "src/smoke-tests/basic-smoke-test.py"


def test_release_metadata_and_portable_lock():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    assert project["project"]["version"] == "2.0.0"
    package = next(p for p in lock["package"] if p["name"] == "plotsrv-examples")
    assert package["version"] == "2.0.0"
    assert not any(p["name"] == "plotsrv" for p in lock["package"])
    assert "plotsrv-examples 2.0.0" in (ROOT / "README.md").read_text()


def test_core_smoke_alias_needs_no_generated_fixtures():
    completed = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "--dry-run", "--publisher-module",
         "smoke_tests.python_objs", "--publisher-delay", "5", "--config", "plotsrv.yml"],
        capture_output=True, text=True, timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    assert "plotsrv.cli_entry serve" in completed.stdout
    assert "src/smoke-tests/python_objs.py" in completed.stdout
    assert "--watch" not in completed.stdout


def test_custom_publisher_failure_propagates_and_cleans_up(tmp_path):
    import psutil
    import re
    from plotsrv_examples.support.lifecycle import available_port
    completed = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "--host", "127.0.0.1",
         "--port", str(available_port()), "--publisher-delay", "0.5",
         "--publisher-script", str(tmp_path / "absent.py")],
        capture_output=True, text=True, timeout=20,
    )
    assert completed.returncode != 0
    assert "Publisher exited with code" in completed.stdout, completed.stdout + completed.stderr
    pids = re.findall(r"Stopping .* process: PID (\d+)", completed.stdout)
    assert pids
    assert all(not psutil.pid_exists(int(pid)) for pid in pids)
