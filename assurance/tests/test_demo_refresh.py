"""Content, history seeding and configuration contracts for the richer demos."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demos"))
from publishing import Publisher


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


def test_configs_bound_history_and_keep_featured_views_fresh():
    for demo, stale in [
        ("retail", "retail:summary"),
        ("live_import", "live:manifest"),
        ("scan_audit", None),
    ]:
        config = yaml.safe_load((ROOT / "demos" / demo / "plotsrv.yml").read_text())
        assert config["ui-settings"]["icon_url"] == "https://demo.plotsrv.com"
        ids = config["server-settings"]["admission"]["allowed_ids"]
        assert not any(":source:" in view for view in ids)
        assert set(config["description-settings"]["views"]) == set(ids)
        assert all(
            len(d) <= 512 for d in config["description-settings"]["views"].values()
        )
        if stale:
            enabled = {
                k
                for k, v in config["freshness-settings"]["views"].items()
                if v["enabled"]
            }
            assert enabled == {stale}
            assert config["storage-settings"]["default_keep_last"] == 3
            assert not config["storage-settings"]["streams"]["enabled"]
            for feature in config["ui-settings"]["featured_views"]:
                assert feature["view"] != stale
                assert feature["thumbnail"].startswith("previews/")
        else:
            assert config["ui-settings"]["featured_views"] == []
    retail = yaml.safe_load((ROOT / "demos/retail/plotsrv.yml").read_text())
    assert retail["storage-settings"]["latest"]["restore_scope"] == "all"
    for entry in retail["ui-settings"]["compact_views"]:
        assert retail["storage-settings"]["views"][entry["view"]] == {
            "enabled": False,
            "latest_enabled": False,
        }
    from plotsrv.checks_config import parse_checks

    rules = parse_checks(
        yaml.safe_load((ROOT / "demos/scan_audit/plotsrv.yml").read_text())[
            "checks-settings"
        ]
    )
    assert rules[0].source == "scans:metrics" and rules[0].path == ("review_count",)


def test_retail_summary_reconciles_with_orders(monkeypatch):
    app = module("retail", "app.py", monkeypatch)
    rows = app.make_orders()
    summary = app.dataset_summary(rows)
    assert summary["coverage"]["rows"] == len(rows)
    assert {
        field
        for group in summary["coverage"]["field_names"].values()
        for field in group.split(", ")
    } == set(rows[0])
    assert summary["reporting_period"] == {
        "from": "2025-01-01",
        "through": "2026-06-30",
        "months": 18,
    }
    assert summary["totals"]["booked_sales_gbp"] == round(
        sum(r["order_value_gbp"] for r in rows), 2
    )
    for groups in [summary["by_category"], summary["by_region"]]:
        assert sum(g["orders"] for g in groups.values()) == len(rows)
        assert (
            round(sum(g["booked_sales_gbp"] for g in groups.values()), 2)
            == summary["totals"]["booked_sales_gbp"]
        )
    assert summary["data_quality"]["duplicate_order_ids"] == 0
    assert summary["data_quality"]["financial_reconciliation_errors"] == 0
    assert (
        sum(summary["returns"]["by_reason"].values())
        == summary["totals"]["returned_orders"]
    )
    assert len(json.dumps(summary)) < 128 * 1024
    # The transmitted JSON tree also stays inside the unchanged receiver cap.
    from plotsrv.http_publish import _container_item_count
    from plotsrv.publisher import _to_publish_payload

    payload = _to_publish_payload(
        summary,
        kind="artifact",
        artifact_kind="json",
        label=None,
        section=None,
        update_limit_s=None,
        force=False,
    )
    assert _container_item_count(payload["artifact"]) <= 2000
    assert payload["artifact"]["meta"]["truncated"] is False


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


@pytest.mark.parametrize(
    "demo,stale,featured,token",
    [
        ("retail", "retail:summary", "retail:guide", "PLOTSRV_RETAIL_TOKEN"),
        ("live_import", "live:manifest", "live:report", "PLOTSRV_LIVE_TOKEN"),
    ],
)
def test_freshness_transitions_use_real_publication_time(
    tmp_path, demo, stale, featured, token
):
    import os
    import subprocess

    script = """
from datetime import datetime,timedelta,timezone
from plotsrv import store
store.set_artifact(obj='report',kind='markdown',view_id='STALE_VIEW')
store.set_artifact(obj='source',kind='text',view_id='FEATURED_VIEW')
base=datetime.fromisoformat(store.get_status(view_id='STALE_VIEW')['last_updated'])
class Clock(datetime):
    offset=0
    @classmethod
    def now(cls,tz=None):return base+timedelta(seconds=cls.offset)
store.datetime=Clock
for seconds,state in [(0,'ok'),(601,'warn'),(901,'error')]:
    Clock.offset=seconds
    assert store.get_freshness(view_id='STALE_VIEW')['state']==state
    assert store.get_freshness(view_id='FEATURED_VIEW')['state']=='disabled'
assert store.get_status(view_id='STALE_VIEW')['last_updated']==base.isoformat()
"""
    script = script.replace("STALE_VIEW", stale).replace("FEATURED_VIEW", featured)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={
            **os.environ,
            "PLOTSRV_CONFIG": str(ROOT / "demos" / demo / "plotsrv.yml"),
            token: "fixture-only-token",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
