"""Whole gallery receipt and honest failure, with owned-child cleanup."""

import json
from pathlib import Path
import subprocess
import sys

import psutil
import pytest

from plotsrv_examples.scenarios import gallery


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("fault", [False, True])
def test_gallery_receipt_and_missing_content(fault):
    args = [sys.executable, "-m", "plotsrv_examples", "run", "gallery",
            "--inspect", "--inspect-seconds", "0"]
    if fault:
        args += ["--fault", "missing-evidence"]
    completed = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=65)
    result = json.loads(completed.stdout)
    assert completed.returncode == (1 if fault else 0), completed.stdout + completed.stderr
    assert result["success"] is not fault
    assert result["manual_status"] == "pending"
    assert result["owned_children_reaped"]
    for child in result["children"]:
        assert not psutil.pid_exists(child["pid"])
    if fault:
        assert "absent" in result["error"]
        assert "evidence" not in result
    else:
        assert result["evidence"]["tables"] == "exact rows"
        assert result["evidence"]["plots"] == "decoded PNGs"
        assert "example-mixed" in result["evidence"]["views"]


def test_gallery_rejects_incorrect_table(monkeypatch):
    monkeypatch.setattr(gallery, "wait_evidence", lambda *a, **kw: None)
    def response(port, path, *args):
        if path == "/views":
            return [{"view_id": key, "kind": "artifact"} for key in gallery.ARTIFACTS] + [
                {"view_id": "example-" + name, "kind": kind}
                for name, kind in [("pandas", "table"), ("polars", "table"),
                                   ("matplotlib", "plot"), ("plotnine", "plot")]]
        return {"columns": ["planet", "gravity", "temperature"], "rows": []}
    monkeypatch.setattr(gallery, "_json", response)
    with pytest.raises(ValueError, match="table content"):
        gallery.verify(None, None, 8000)
