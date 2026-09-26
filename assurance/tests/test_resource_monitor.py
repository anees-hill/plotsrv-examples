"""Bounded retention, figure cleanup, and real receiver evidence."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import signal
import select

import psutil
import pytest

ROOT = Path(__file__).resolve().parents[2]


def monitor():
    spec = importlib.util.spec_from_file_location(
        "resource_example", ROOT / "examples/resource_monitor/main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_long_retention_with_real_measurements(monkeypatch):
    example = monitor()
    sizes = []
    monkeypatch.setattr(example, "publish", lambda history, destination: sizes.append(len(history)))
    result = example.run("http://127.0.0.1:1", samples=200, history_size=7, interval=0.001)
    assert max(sizes) == result["retained"] == 7
    assert result["samples"] == 200
    assert 0 <= result["last"]["cpu_percent"] <= 100
    assert result["open_figures"] == 0


def test_figure_cleanup_on_publication_failure(monkeypatch):
    example = monitor()
    def fail_plot(obj, **kwargs):
        if kwargs["view_id"] == "resource-cpu_percent":
            raise RuntimeError("publication failed")
    monkeypatch.setattr(example, "publish_view", fail_plot)
    with pytest.raises(RuntimeError, match="publication failed"):
        example.publish([example.snapshot(0.001)], "http://127.0.0.1:1")
    assert not example.plt.get_fignums()


@pytest.mark.parametrize("fault", [False, True])
def test_resource_receiver_and_cleanup(fault):
    args = [sys.executable, "-m", "plotsrv_examples", "run", "resource-monitor",
            "--inspect", "--inspect-seconds", "1"]
    if fault:
        args += ["--fault", "missing-evidence"]
    completed = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=65)
    result = json.loads(completed.stdout)
    assert completed.returncode == (1 if fault else 0), completed.stdout + completed.stderr
    assert result["owned_children_reaped"]
    assert all(not psutil.pid_exists(child["pid"]) for child in result["children"])
    if not fault:
        assert result["evidence"]["measurements"]["retained"] == 2
        assert result["evidence"]["plots"] == "decoded PNGs"


def test_inspection_interrupt_reaps_children():
    child = subprocess.Popen(
        [sys.executable, "-m", "plotsrv_examples", "run", "resource-monitor",
         "--inspect", "--inspect-seconds", "300"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert select.select([child.stderr], [], [], 30)[0], "inspection did not start"
        assert "Resource monitor:" in child.stderr.readline()
        child.send_signal(signal.SIGINT)
        stdout, stderr = child.communicate(timeout=15)
        result = json.loads(stdout)
        assert child.returncode == 130, stdout + stderr
        assert result["owned_children_reaped"]
        assert all(not psutil.pid_exists(c["pid"]) for c in result["children"])
    finally:
        if child.poll() is None:
            child.send_signal(signal.SIGTERM)
            child.communicate(timeout=15)
