"""Real loopback receivers: publication, durable history, restoration and browser UI."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import ProxyHandler, build_opener

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
HISTORY = {
    "retail": [
        "retail:" + v
        for v in ("orders", "sales", "categories", "returns", "fulfillment", "guide")
    ],
    "live_import": [
        "live:" + v
        for v in ("recent", "exceptions", "manifest", "outcomes", "durations", "report")
    ],
}


class Receiver:
    def __init__(self, demo, directory):
        self.demo, self.directory = demo, directory
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.base = f"http://127.0.0.1:{port}"
        cfg = yaml.safe_load((ROOT / "demos" / demo / "plotsrv.yml").read_text())
        cfg["server-settings"]["bind"]["port"] = port
        cfg["publisher-settings"]["destination"]["url"] = self.base
        cfg["storage-settings"]["root_dir"] = str(directory / "store")
        if demo == "retail":
            cfg["ui-settings"]["logo"] = str(ROOT / "demos/retail/northstar.svg")
        for feature in cfg["ui-settings"].get("featured_views", []):
            feature["thumbnail"] = str(ROOT / "demos" / demo / feature["thumbnail"])
        self.config = directory / "plotsrv.yml"
        self.config.write_text(yaml.safe_dump(cfg, sort_keys=False))
        self.cfg = cfg
        self.env = {
            **os.environ,
            "PLOTSRV_CONFIG": str(self.config),
            "PLOTSRV_DEBUG": "1",
            cfg["server-settings"]["ingestion"][
                "bearer_token_env"
            ]: "fixture-only-token",
        }
        self.opener = build_opener(ProxyHandler({}))
        self.process = None
        self.logs = []

    def get(self, route, **query):
        with self.opener.open(
            self.base + route + "?" + urlencode(query), timeout=10
        ) as response:
            return json.load(response)

    def start(self):
        log = (self.directory / f"receiver-{len(self.logs)}.log").open("w")
        self.logs.append(log)
        command = (
            [sys.executable, str(ROOT / "demos/retail/serve.py")]
            if self.demo == "retail"
            else [
                str(Path(sys.executable).with_name("plotsrv")),
                "serve",
                "--config",
                str(self.config),
            ]
        )
        self.process = subprocess.Popen(
            command,
            cwd=self.directory,
            env=self.env,
            stdout=log,
            stderr=log,
        )
        for _ in range(150):
            if self.process.poll() is not None:
                raise AssertionError(Path(log.name).read_text())
            try:
                self.get("/status")
                return
            except OSError:
                time.sleep(0.1)
        raise AssertionError("receiver did not become ready")

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=15)
        for log in self.logs:
            log.close()

    def publish(self, restore=False):
        scripts = {
            "retail": "app.py",
            "live_import": "reports.py",
            "scan_audit": "run_audit.py",
        }
        command = (
            [sys.executable, str(ROOT / "demos/restore.py"), self.demo]
            if restore
            else [sys.executable, str(ROOT / "demos" / self.demo / scripts[self.demo])]
        )
        result = subprocess.run(
            command,
            cwd=self.directory,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(scope="module", params=["retail", "live_import", "scan_audit"])
def receiver(request, tmp_path_factory):
    instance = Receiver(request.param, tmp_path_factory.mktemp("demo-" + request.param))
    try:
        instance.start()
        instance.publish()
        yield instance
    finally:
        instance.stop()


def test_history_logs_and_restart(receiver):
    r = receiver
    if r.demo in HISTORY:
        before = {v: r.get("/history", view=v)["snapshots"] for v in HISTORY[r.demo]}
        for rows in before.values():
            assert len(rows) == 3
            assert {
                row["label"].split("Illustrative revision ")[-1] for row in rows
            } == {"1/3", "2/3", "3/3"}
        r.publish()
        assert before == {
            v: r.get("/history", view=v)["snapshots"] for v in HISTORY[r.demo]
        }
    assert not any(":source:" in v["view_id"] for v in r.get("/views"))
    if r.demo == "retail":
        for view in ("retail:log:orders", "retail:log:fulfillment"):
            assert r.get("/history", view=view)["count"] == 0
            assert "data-plotsrv-pre" in r.get("/artifact", view=view)["html"]
    descriptions = {v["view_id"]: v["description"] for v in r.get("/views")}
    assert all(
        descriptions[v] == description
        for v, description in r.cfg["description-settings"]["views"].items()
        if v in descriptions
    )
    if r.demo == "scan_audit":
        assert (
            r.get("/checks", view="scans:metrics")["states"][0]["state"] == "triggered"
        )
    r.stop()
    r.start()
    r.publish(restore=True)
    if r.demo in HISTORY:
        assert before == {
            v: r.get("/history", view=v)["snapshots"] for v in HISTORY[r.demo]
        }
        view = HISTORY[r.demo][0]
        old = before[view][-1]["snapshot_id"]
        assert r.get("/table/data", view=view, snapshot=old)["rows"]
    else:
        assert (
            r.get("/checks", view="scans:metrics")["states"][0]["state"] == "triggered"
        )
    storage = sum(
        p.stat().st_size for p in (r.directory / "store").rglob("*") if p.is_file()
    )
    assert storage < 100 * 1024**2


def test_browser_branding_reports_and_logs(receiver):
    playwright = pytest.importorskip("playwright.sync_api")
    r = receiver
    view = {
        "retail": "retail:guide",
        "live_import": "live:report",
        "scan_audit": "scans:changes",
    }[r.demo]
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(r.base + "/?" + urlencode({"view": view}))
            page.wait_for_selector('a[href="https://demo.plotsrv.com"] img.header-logo')
            if r.demo == "live_import":
                frame = page.frame_locator("iframe.plotsrv-html-iframe")
                frame.locator("h1").wait_for()
                assert "dependable records" in frame.locator("h1").inner_text()
                assert frame.locator("table").count() >= 2
            else:
                page.wait_for_selector(
                    ".artifact-markdown table, .markdown-body table, table"
                )
                assert page.locator("h1").count() >= 1
            page.locator(".ps-viewselect__btn").click()
            catalogue = {v["view_id"] for v in r.get("/views")}
            featured = [
                v
                for v in r.cfg["ui-settings"].get("featured_views", [])
                if v["view"] in catalogue
            ]
            thumbnails = page.locator(".ps-viewselect__feature-thumbnail")
            assert thumbnails.count() == len(featured)
            if featured:
                page.wait_for_function(
                    "Array.from(document.querySelectorAll('.ps-viewselect__feature-thumbnail')).every(e => e.complete && e.naturalWidth > 0)"
                )
            if r.demo == "retail":
                assert page.locator(".ps-viewselect__item--compact").count() == 2
            assert (
                "Demo source code"
                not in page.locator(".ps-viewselect__menu").inner_text()
            )
            page.keyboard.press("Escape")
            if r.demo == "scan_audit":
                page.goto(r.base + "/?" + urlencode({"view": "scans:metrics"}))
                page.locator("#header-status-button").click()
                page.locator("#status-modal").wait_for(state="visible")
                page.locator("#status-modal").get_by_text("Scans require review", exact=False).first.wait_for()
                page.locator("#status-modal-close-icon").click()
            page.screenshot(path=str(r.directory / "desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            if r.demo == "live_import":
                assert frame.locator("body").evaluate(
                    "e => e.scrollWidth <= window.innerWidth + 1"
                )
            page.screenshot(path=str(r.directory / "mobile.png"), full_page=True)
            if r.demo == "retail":
                page.goto(r.base + "/?" + urlencode({"view": "retail:log:orders"}))
                page.wait_for_selector(".ps-log-token--warn")
                page.goto(r.base + "/?" + urlencode({"view": "retail:log:fulfillment"}))
                page.wait_for_selector(".ps-log-token--method")
                assert page.locator("pre").inner_text().count("GET /warehouse") == 5
        finally:
            browser.close()
