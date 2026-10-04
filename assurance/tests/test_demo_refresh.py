"""Content, history seeding and configuration contracts for the richer demos."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demos"))
from publishing import Publisher, public_sources, validate_public_config


def module(demo, filename, monkeypatch):
    directory = ROOT / "demos" / demo
    monkeypatch.syspath_prepend(str(directory))
    spec = importlib.util.spec_from_file_location(
        demo + "_" + filename.replace(".", "_"), directory / filename
    )
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_retail_financial_model_and_connected_patterns(monkeypatch):
    data = module("retail", "generate_data.py", monkeypatch)
    rows = data.make_orders()
    assert rows == data.make_orders() and len(rows) == 1680
    assert {r["order_date"][:7] for r in rows} == {
        f"{y}-{m:02}"
        for y, months in [(2025, range(1, 13)), (2026, range(1, 7))]
        for m in months
    }
    for row in rows:
        assert row["order_value_gbp"] == round(
            row["unit_price_gbp"] * row["quantity"] * (1 - row["discount_pct"] / 100), 2
        )
        assert row["margin_gbp"] == round(
            row["order_value_gbp"] - row["unit_cost_gbp"] * row["quantity"], 2
        )

    def returns(group):
        return sum(r["returned"] for r in group) / len(group)

    shells = [r for r in rows if r["product"] == "Summit Rain Shell"]
    assert returns([r for r in shells if r["size"] == "M"]) > 3 * returns(
        [r for r in shells if r["size"] != "M"]
    )

    def delivery(group):
        return sum(r["fulfillment_days"] for r in group) / len(group)

    west = [r for r in rows if r["region"] == "West"]
    assert (
        delivery([r for r in west if "2025-03" <= r["order_date"] < "2025-07"])
        > delivery([r for r in west if r["order_date"] >= "2025-07"]) + 3
    )
    app = module("retail", "app.py", monkeypatch)
    report = app.trading_report(rows)
    assert "| Category |" in report and "five" in report and "fifteen" in report
    assert f"£{sum(r['margin_gbp'] for r in rows):,.2f}" in report
    for revision in (1, 2, 3):
        assert data.make_orders(1, revision=revision)


def test_import_editions_agree_and_remain_bounded(monkeypatch):
    reports = module("live_import", "reports.py", monkeypatch)
    counts = []
    for revision in (1, 2, 3):
        rows = reports.make_batch(revision)
        info = reports.manifest(rows, revision)
        counts.append(info["counts"]["rejected"])
        assert (
            info["counts"]["records"]
            == info["counts"]["accepted"] + info["counts"]["rejected"]
            == len(rows)
        )
        html = reports.html_report(rows, info)
        assert len(html.encode()) < 128 * 1024
        assert "simulated" in html and "no JavaScript" in html
        assert "<script" not in html and "<link" not in html
        assert html.count("<details>") == 1
        assert "Illustrative batch" in html
    assert counts[0] > counts[1] > counts[2] > 0
    rows = reports.make_batch(3)
    rows[0]["record_id"] = "<script>alert(1)</script>"
    rows[0]["validation_issue"] = "bad"
    html = reports.html_report(rows, reports.manifest(rows, 3))
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_configs_admit_sources_and_bound_history(monkeypatch):
    for demo, prefix in [
        ("retail", "retail"),
        ("live_import", "live"),
        ("scan_audit", "scans"),
    ]:
        config = yaml.safe_load((ROOT / "demos" / demo / "plotsrv.yml").read_text())
        assert config["ui-settings"]["icon_url"] == "https://plotsrv.com"
        sources = list(public_sources(demo))
        assert any(filename == "plotsrv.yml" for _, filename, _ in sources)
        assert any(filename == "publishing.py" for _, filename, _ in sources)
        for view, _, text in sources:
            assert view in config["server-settings"]["admission"]["allowed_ids"]
            assert config["storage-settings"]["views"][view] == {
                "enabled": False,
                "latest_enabled": False,
            }
            assert len(text) < 65536
        if demo != "scan_audit":
            assert config["storage-settings"]["default_keep_last"] == 3
            assert not config["storage-settings"]["streams"]["enabled"]
    config = yaml.safe_load((ROOT / "demos/retail/plotsrv.yml").read_text())
    enabled = {
        k for k, v in config["freshness-settings"]["views"].items() if v["enabled"]
    }
    assert enabled == {"retail:orders", "retail:guide"}
    from plotsrv.checks_config import parse_checks

    rules = parse_checks(
        yaml.safe_load((ROOT / "demos/scan_audit/plotsrv.yml").read_text())[
            "checks-settings"
        ]
    )
    assert rules[0].source == "scans:metrics" and rules[0].path == ("review_count",)


def test_public_configs_do_not_expand_credentials(monkeypatch):
    monkeypatch.setenv("PLOTSRV_RETAIL_TOKEN", "must-never-be-published")
    assert all(
        "must-never-be-published" not in text for _, _, text in public_sources("retail")
    )
    with pytest.raises(ValueError, match="credential"):
        validate_public_config({"publisher-settings": {"bearer_token": "secret"}})
    validate_public_config({"bearer_token_env": "PLOTSRV_RETAIL_TOKEN"})


def test_seeding_resumes_after_snapshot_write_before_state_save(tmp_path, monkeypatch):
    import plotsrv

    history = []
    published = []
    publisher = Publisher("retail", state_dir=tmp_path)
    monkeypatch.setattr(publisher, "history", lambda view: list(history))
    monkeypatch.setattr(publisher, "present", lambda view: bool(history))
    monkeypatch.setattr(plotsrv, "flush_views", lambda **kwargs: True)

    def publish(obj, **kwargs):
        published.append(obj)
        history.insert(
            0, {"label": kwargs["label"], "snapshot_id": str(len(published))}
        )
        del history[3:]

    monkeypatch.setattr(plotsrv, "publish_view", publish)
    factory = lambda revision: [
        ("retail:guide", "Report", {"revision": revision}, "json")
    ]
    original = publisher.wait_snapshot

    def interrupt(*args):
        raise RuntimeError("interrupted after durable write")

    monkeypatch.setattr(publisher, "wait_snapshot", interrupt)
    with pytest.raises(RuntimeError):
        publisher.seeded(["retail:guide"], factory)
    monkeypatch.setattr(publisher, "wait_snapshot", original)
    publisher.seeded(["retail:guide"], factory)
    assert published == [{"revision": 1}, {"revision": 2}, {"revision": 3}]
    publisher.seeded(["retail:guide"], factory)
    assert len(published) == 3 and len(history) == 3
    assert json.loads(publisher.path.read_text())["seeded"] == ["retail:guide"]


def test_known_scan_defect_is_measured_and_reported(tmp_path, monkeypatch):
    from datetime import date, timedelta

    audit = module("scan_audit", "run_audit.py", monkeypatch)
    for offset in range(3):
        rows, metrics, _ = audit.make_report(
            date(2026, 10, 4) + timedelta(days=offset), tmp_path
        )
        assert rows[0]["quality"] == "review" and "dim" in rows[0]["flags"]
        assert metrics["review_count"] >= 1
        note = audit.comparison(metrics, None, rows)
        assert "| Scan |" in note and "SHEET-01" in note and "calibration" in note


def test_invalid_later_payload_cannot_partially_publish_a_batch(tmp_path, monkeypatch):
    import plotsrv

    publisher = Publisher("live_import", state_dir=tmp_path)
    calls = []
    monkeypatch.setattr(
        plotsrv, "publish_view", lambda *args, **kwargs: calls.append(args)
    )

    def content(revision):
        yield "live:recent", "Good", {"revision": revision}, "json"
        yield "live:report", "Oversized", "x" * (128 * 1024 + 1), "html"

    with pytest.raises(ValueError, match="128 KiB"):
        publisher.current(content)
    assert not calls


def test_retail_freshness_transitions_use_real_publication_time(tmp_path):
    import os
    import subprocess

    script = """
from datetime import datetime,timedelta,timezone
from plotsrv import store
store.set_artifact(obj='report',kind='markdown',view_id='retail:guide')
store.set_artifact(obj='source',kind='text',view_id='retail:source:app-py')
base=datetime.fromisoformat(store.get_status(view_id='retail:guide')['last_updated'])
class Clock(datetime):
    offset=0
    @classmethod
    def now(cls,tz=None):return base+timedelta(seconds=cls.offset)
store.datetime=Clock
for seconds,state in [(0,'ok'),(601,'warn'),(901,'error')]:
    Clock.offset=seconds
    assert store.get_freshness(view_id='retail:guide')['state']==state
    assert store.get_freshness(view_id='retail:source:app-py')['state']=='disabled'
assert store.get_status(view_id='retail:guide')['last_updated']==base.isoformat()
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={
            **os.environ,
            "PLOTSRV_CONFIG": str(ROOT / "demos/retail/plotsrv.yml"),
            "PLOTSRV_RETAIL_TOKEN": "fixture-only-token",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
