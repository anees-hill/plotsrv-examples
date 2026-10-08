"""Packaged installation must be separate from the editable source candidate."""

import json
from pathlib import Path
import subprocess
import sys

import psutil

from plotsrv_examples.doctor import report
from plotsrv_examples import wheel_smoke


ROOT = Path(__file__).resolve().parents[2]


def test_missing_wheel_does_not_pass(tmp_path, capsys):
    assert wheel_smoke.main(tmp_path / "absent.whl") == 1
    result = json.loads(capsys.readouterr().out)
    assert result["success"] is False and "evidence" not in result
    assert result["children"] == []


def test_wheel_requires_explicit_artifact():
    completed = subprocess.run([sys.executable, "-B", "-m", "plotsrv_examples", "check", "wheel"],
                               cwd=ROOT, capture_output=True, text=True, timeout=5)
    assert completed.returncode == 2
    assert "requires --wheel-path" in completed.stderr


def test_real_wheel_installation_and_assets(tmp_path):
    candidate = report()
    assert candidate["readiness"] == "ready", candidate
    built = subprocess.run(["uv", "build", "--wheel", "--out-dir", str(tmp_path),
                            candidate["core_reference"]["path"]],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    wheels = list(tmp_path.glob("plotsrv-*.whl"))
    assert len(wheels) == 1
    completed = subprocess.run([sys.executable, "-B", "-m", "plotsrv_examples", "check", "wheel",
                               "--wheel-path", str(wheels[0])],
                              cwd=ROOT, capture_output=True, text=True, timeout=240)
    result = json.loads(completed.stdout)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert result["success"] and result["owned_children_reaped"]
    assert result["candidate"]["version"] == candidate["core_reference"]["declared_version"]
    assert Path(result["candidate"]["module"]).is_relative_to(Path(result["environment"]["path"]))
    assert not Path(result["environment"]["path"]).exists()
    assert result["candidate"]["dependencies"]
    assert len(result["wheel"]["sha256"]) == 64
    assert result["manual_status"] == "pending"
    assert any(a.endswith(".js") for a in result["evidence"]["local_assets"])
    assert all(not psutil.pid_exists(c["pid"]) for c in result["children"])
