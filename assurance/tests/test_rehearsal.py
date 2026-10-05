"""Exercise public visitor journeys against a local HTTP/SSE fixture only."""

import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "rehearsal/visitor.py"


@pytest.fixture
def origin():
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        paths = []  # noqa: RUF012 - shared request log scoped to this fixture
        status = 200
        challenge = False
        epoch_change = False
        early_close = False

        def log_message(self, *args):
            pass

        def do_GET(self):
            self.paths.append(self.path)
            route = urlsplit(self.path).path
            self.send_response(self.status)
            self.send_header("CF-Cache-Status", "DYNAMIC")
            if self.challenge:
                self.send_header("cf-mitigated", "challenge")
            if route == "/updates" and self.status == 200 and not self.challenge:
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                try:
                    for i in range(8 if not self.early_close else 1):
                        payload = {
                            "revision": i,
                            "server_instance_id": "changed"
                            if i and self.epoch_change
                            else "test",
                        }
                        self.wfile.write(
                            (
                                "event: update\ndata: " + json.dumps(payload) + "\n\n"
                            ).encode()
                        )
                        self.wfile.flush()
                        time.sleep(0.05)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            if route == "/":
                body = b'<html>plotsrv<script src="/static/app.js"></script><img src="https://unrelated.invalid/assets/a.png"></html>'
                kind = "text/html"
            elif route == "/plot":
                body = b"\x89PNG\r\n\x1a\nfixture"
                kind = "image/png"
            elif route.startswith("/static/"):
                body = b"/* fixture */"
                kind = "text/javascript"
            else:
                body = json.dumps(
                    {
                        "records": [],
                        "data": [],
                        "snapshots": [{"snapshot_id": "fixture-1"}]
                        if route == "/history"
                        else [],
                        "count": 0,
                    }
                ).encode()
                kind = "application/json"
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:" + str(server.server_port), Handler
    server.shutdown()
    server.server_close()
    thread.join()


def visitor(origin, demo="retail", *extra):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--demo",
            demo,
            "--" + demo + "-url",
            origin,
            "--allow-http",
            "--duration",
            ".7",
            "--sse-lifetime",
            ".4",
            "--pause-min",
            ".01",
            "--pause-max",
            ".01",
            *extra,
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


@pytest.mark.parametrize(
    "demo,expected",
    [
        ("retail", {"table", "plot", "markdown", "summary", "operations_log"}),
        (
            "live",
            {
                "stream",
                "stream_status",
                "stream_summary",
                "recent",
                "exceptions",
                "manifest",
                "outcomes",
                "durations",
                "report",
                "history",
            },
        ),
        ("scans", {"table", "image", "observation", "changes", "history"}),
    ],
)
def test_read_only_journeys_and_persistent_updates(origin, demo, expected):
    url, handler = origin
    result = visitor(url, demo)
    assert result.returncode == 0, result.stderr + result.stdout
    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert all(row["ok"] for row in events)
    names = {row["name"].removeprefix(demo + ".") for row in events}
    assert names >= expected | {"page", "asset", "sse_connect", "sse_update"}
    assert "/static/app.js" in handler.paths
    assert all("unrelated" not in path for path in handler.paths)
    assert all(
        row["attributes"]["cf_cache_status"] == "DYNAMIC"
        for row in events
        if row["type"] == "operation"
    )


@pytest.mark.parametrize(
    "status,challenge,error",
    [(429, False, "rate_limited"), (403, True, "cloudflare_challenge")],
)
def test_proxy_failures_are_distinguishable(origin, status, challenge, error):
    url, handler = origin
    handler.status, handler.challenge = status, challenge
    result = visitor(url)
    assert result.returncode == 1
    row = json.loads(result.stdout.splitlines()[0])
    assert not row["ok"] and row["attributes"]["error"] == error
    assert row["attributes"]["status_code"] == status


def test_sse_restart_is_a_failure(origin):
    url, handler = origin
    handler.epoch_change = True
    result = visitor(url)
    assert result.returncode == 1
    assert "receiver_restarted" in result.stdout


def test_unexpected_sse_disconnect_is_a_failure(origin):
    url, handler = origin
    handler.early_close = True
    result = visitor(url)
    assert result.returncode == 1
    assert "sse_disconnected_early" in result.stdout


def test_sse_expected_expiry_reconnects_with_cursor(origin):
    url, handler = origin
    result = visitor(url, "live", "--duration", "2.7", "--sse-lifetime", ".4")
    assert result.returncode == 0, result.stdout
    paths = [p for p in handler.paths if p.startswith("/updates?")]
    assert len(paths) == 2
    assert int(parse_qs(urlsplit(paths[1]).query)["since"][0]) > 0
    assert "sse_reconnect" in result.stdout
