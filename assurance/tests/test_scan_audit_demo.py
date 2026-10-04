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
    assert first["review_count"] >= 1 and second["review_count"] >= 1
    assert f"{second['review_count']-first['review_count']:+.1f}" in module.comparison(second, first)


def test_skew_tracks_rotation_not_footer_or_brightness(tmp_path):
    from datetime import timedelta
    module = _module()
    for offset in range(14):
        day = date(2026, 9, 27) + timedelta(days=offset)
        rows, _, _ = module.make_report(day, tmp_path)
        for number, row in enumerate(rows, 1):
            rotated = (day.toordinal() * 3 + number * 7) % 17 == 0
            # Low-contrast scans may have no measurable registration line.
            if row["skew_degrees"] is not None:
                assert abs(row["skew_degrees"] - (4 if rotated else 0)) < 0.5
            if not rotated:
                assert "skewed" not in row["flags"]


def test_failed_runs_are_bounded_and_same_day_retry_preserves_comparison(tmp_path, monkeypatch):
    import json
    from datetime import timedelta
    import pytest
    module = _module()
    published = []
    monkeypatch.setattr(module, "publish", lambda *args: published.append(args))
    first = date(2026, 9, 27)
    module.complete(first, tmp_path)
    state = (tmp_path / "state.json").read_text()
    unrelated = tmp_path / "important"
    unrelated.mkdir()
    (unrelated / "keep.txt").write_text("keep")

    def fail(*args):
        raise RuntimeError("injected publication failure")

    monkeypatch.setattr(module, "publish", fail)
    for offset in range(1, 6):
        with pytest.raises(RuntimeError):
            module.complete(first + timedelta(days=offset), tmp_path)
        assert len(list(tmp_path.glob("????-??-??"))) <= 3
        assert (tmp_path / "state.json").read_text() == state
        assert json.loads((tmp_path / "job-status.json").read_text())["status"] == "failed"
    assert (unrelated / "keep.txt").read_text() == "keep"
    monkeypatch.setattr(module, "publish", lambda *args: published.append(args))
    day = first + timedelta(days=5)
    module.complete(day, tmp_path)
    note = published[-1][2]
    module.complete(day, tmp_path)
    assert published[-1][2] == note
    assert "2026-09-27" in note
    assert json.loads((tmp_path / "job-status.json").read_text())["status"] == "succeeded"


def test_completion_view_waits_for_successful_observation(tmp_path, monkeypatch):
    import plotsrv
    import pytest
    module = _module()
    calls = []
    monkeypatch.setenv("PLOTSRV_DEBUG", "0")
    monkeypatch.setattr(plotsrv, "publish_view", lambda obj, **kw: calls.append(kw))
    monkeypatch.setattr(plotsrv, "flush_views", lambda **kw: True)
    monkeypatch.setattr(plotsrv, "get_observation_stats", lambda: {"last_error": "delivery_failed"})
    metrics = {"run_date": "2026-09-27"}
    with pytest.raises(RuntimeError):
        module.publish([], metrics, "done", tmp_path / "sheet-01.jpg")
    assert "scans:changes" not in [call["view_id"] for call in calls]
    monkeypatch.setattr(plotsrv, "get_observation_stats", lambda: {"last_error": None})
    module.publish([], metrics, "done", tmp_path / "sheet-01.jpg")
    assert calls[-1]["view_id"] == "scans:changes"
    assert all("2026-09-27" in call["label"] for call in calls)
