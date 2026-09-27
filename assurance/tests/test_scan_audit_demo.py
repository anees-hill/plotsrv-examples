"""The JPEGs have measurable defects and repeatable cross-run comparisons."""

from datetime import date
import importlib.util
from pathlib import Path


def _module():
    path = Path(__file__).resolve().parents[2] / "demos/scan_audit/run_audit.py"
    spec = importlib.util.spec_from_file_location("scan_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_synthetic_jpegs_and_day_comparison(tmp_path):
    module = _module()
    first_day = date(2026, 9, 27)
    rows, first, run_dir = module.make_report(first_day, tmp_path)
    assert len(rows) == 10 and all((run_dir / f"sheet-{n:02d}.jpg").exists() for n in range(1, 11))
    assert any("dim" in row["flags"] for row in rows)
    assert any("low contrast" in row["flags"] for row in rows)
    assert any("skewed" in row["flags"] for row in rows)
    _, second, _ = module.make_report(date(2026, 9, 28), tmp_path)
    assert "Compared with 2026-09-27" in module.comparison(second, first)
    assert first["review_count"] != second["review_count"]
