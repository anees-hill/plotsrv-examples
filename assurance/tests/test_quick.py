"""Real current-core CLI integration; missing prerequisites fail, never skip."""

import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import time

import psutil
import pytest


REPOSITORY = Path(__file__).resolve().parents[2]
COMMAND = [sys.executable, "-m", "plotsrv_examples", "check", "quick"]


def run(*args, env=None):
    completed = subprocess.run(COMMAND + list(args), cwd=REPOSITORY,
                               env=env, capture_output=True, text=True, timeout=35)
    return completed, json.loads(completed.stdout)


def assert_clean(result):
    assert result["owned_children_reaped"]
    for child in result["children"]:
        assert child["exit"] is not None
        assert not psutil.pid_exists(child["pid"])
        assert child["retained_bytes"] <= 65536
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", result["port"]), timeout=0.2)


def test_real_publication_and_bounded_high_output():
    completed, result = run("--fault", "high-output")
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert result["success"]
    assert result["publisher_exit"] == 0
    assert result["evidence"] == {"logical_view": True, "artifact_sentinel": True}
    assert result["provenance"]["relationship"] == "matching source checkout"
    publisher = next(c for c in result["children"] if c["label"] == "publisher")
    assert publisher["output_bytes"] >= 4 * 1024 * 1024
    assert publisher["retained_bytes"] == 65536
    assert_clean(result)


def test_zero_publisher_exit_without_data_fails_nonzero():
    completed, result = run("--fault", "missing-evidence", "--evidence-timeout", "0.4")
    assert completed.returncode == 1
    assert result["publisher_exit"] == 0
    assert not result["success"]
    assert "logical view" in result["error"] and "absent" in result["error"]
    assert "evidence" not in result
    assert_clean(result)


def test_real_receiver_startup_failure_is_prompt():
    began = time.monotonic()
    completed, result = run("--fault", "startup")
    assert completed.returncode == 1
    assert not result["success"]
    assert time.monotonic() - began < 10
    assert len(result["children"]) == 1
    assert "absent-config.yml" in result["children"][0]["tail"]
    assert result["children"][0]["exit"] != 0
    assert_clean(result)


def test_busy_unrelated_listener_survives_check():
    with socket.socket() as neighbor:
        neighbor.bind(("127.0.0.1", 0))
        neighbor.listen()
        port = neighbor.getsockname()[1]
        completed, result = run("--port", str(port))
        assert completed.returncode == 1
        assert "unavailable" in result["error"]
        assert "receiver_pid" not in result
        assert "workspace" not in result
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass


def test_different_imported_candidate_blocks_before_launch(tmp_path):
    package = tmp_path / "plotsrv"
    package.mkdir()
    (package / "__init__.py").write_text("# Deliberately different candidate\n")
    completed, result = run(env={**os.environ, "PYTHONPATH": str(tmp_path)})
    assert completed.returncode == 1
    assert "Candidate/reference rejected" in result["error"]
    assert "does not match" in result["error"]
    assert "workspace" not in result
    assert "receiver_pid" not in result


@pytest.mark.parametrize("interrupt", [signal.SIGINT, signal.SIGTERM])
def test_interrupt_real_receiver_leaves_no_owned_listener(interrupt):
    process = subprocess.Popen(COMMAND + ["--fault", "missing-evidence", "--evidence-timeout", "20"],
                               cwd=REPOSITORY, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        readable, _, _ = select.select([process.stderr], [], [], 20)
        assert readable, "runner did not announce readiness"
        line = process.stderr.readline()
        assert line.startswith("Receiver ready:"), line
        process.send_signal(interrupt)
        stdout, stderr = process.communicate(timeout=12)
        assert process.returncode == 130, stdout + stderr
        result = json.loads(stdout)
        assert not result["success"]
        assert "Interrupted" in result["error"]
        assert_clean(result)
    finally:
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=12)
        process.stdout.close()
        process.stderr.close()
