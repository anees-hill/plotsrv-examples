"""Local transport, shared transforms, explicit live failure and cleanup."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil
import pytest

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demos/public_weather"


@pytest.fixture
def weather(monkeypatch):
    monkeypatch.syspath_prepend(str(DEMO))
    spec = importlib.util.spec_from_file_location("weather_example", DEMO / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_actual_http_and_transform(weather):
    with weather.sample_source() as url:
        rows = weather.normalise(weather.fetch(url))
    assert [r["temperature_f"] for r in weather.transform(rows, "synthetic sample")] == [50, 53.6, 57.2]
    assert weather.transform(rows, "configured live input")[0]["temperature_f"] == 50
    with pytest.raises(weather.Unavailable):
        weather.fetch(url)


@pytest.mark.parametrize("payload", [None, {}, {"observations": []},
    {"observations": [None]}, {"observations": [{"time": "no date"}]},
    {"observations": [{"time": "2026-01-01T00:00:00Z", "temperature_c": True,
                       "humidity_percent": 60}]},
    {"observations": [{"time": "2026-01-01T00:00:00Z", "temperature_c": float("nan"),
                       "humidity_percent": 60}]}])
def test_invalid_input_is_explicit(weather, payload):
    with pytest.raises(weather.Unavailable):
        weather.normalise(payload)


@pytest.mark.parametrize("mode", ["sample", "live", "failure"])
def test_receiver_and_no_fallback(weather, mode):
    with weather.sample_source() as url:
        env = dict(os.environ, WEATHER_LIVE_URL=url if mode == "live" else url + "?secret=placeholder")
        command = [sys.executable, "-m", "plotsrv_examples", "run", "weather-demo",
                   "--inspect", "--inspect-seconds", "0",
                   "--weather-mode", "sample" if mode == "sample" else "live"]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=45)
    report = json.loads(result.stdout)
    assert result.returncode == (1 if mode == "failure" else 0), result.stdout + result.stderr
    assert "secret" not in result.stdout + result.stderr
    assert report["owned_children_reaped"]
    assert all(not psutil.pid_exists(c["pid"]) for c in report["children"])
    if mode == "failure":
        assert report["evidence"]["views"] == ["weather-status"]
        assert report["evidence"]["status"] == "configured live input unavailable"
    else:
        assert report["evidence"]["count"] == 3


def test_live_missing_configuration_never_starts_sample(weather, monkeypatch):
    monkeypatch.delenv("WEATHER_LIVE_URL", raising=False)
    monkeypatch.setattr(weather, "sample_source", lambda: pytest.fail("sample fallback"))
    published = []
    monkeypatch.setattr(weather, "publish", lambda *args: published.append(args))
    assert not weather.run("http://127.0.0.1:1", "live")["success"]
    assert published[0][0] is None
    assert published[0][2] == "configured live input unavailable"


def test_http_size_and_total_deadline(weather):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Event, Thread
    stop = Event()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            try:
                if self.path == "/large":
                    self.wfile.write(b"x" * 65537)
                else:
                    while not stop.wait(0.1):
                        self.wfile.write(b" ")
                        self.wfile.flush()
            except OSError:
                pass
        def log_message(self, *args):
            pass
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever)
    thread.start()
    before = {c.pid for c in psutil.Process().children()}
    try:
        for path in ("large", "slow"):
            start = time.monotonic()
            with pytest.raises(weather.Unavailable):
                weather.fetch(f"http://127.0.0.1:{server.server_port}/{path}")
            assert time.monotonic() - start < 8
        assert {c.pid for c in psutil.Process().children()} == before
        # Terminating the publisher must also interrupt and reap its HTTP worker.
        env = dict(os.environ, WEATHER_LIVE_URL=f"http://127.0.0.1:{server.server_port}/slow")
        parent = subprocess.Popen(
            [sys.executable, str(DEMO / "main.py"), "--mode", "live",
             "--destination", "http://127.0.0.1:1"], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        descendants = []
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                descendants = psutil.Process(parent.pid).children()
                if descendants:
                    break
                time.sleep(0.01)
            assert descendants, "HTTP worker was not started"
            parent.terminate()
            parent.communicate(timeout=5)
            assert parent.returncode == 130
            assert all(not psutil.pid_exists(c.pid) for c in descendants)
        finally:
            if parent.poll() is None:
                parent.terminate()
                parent.communicate(timeout=5)
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert not thread.is_alive()


def test_interruption_during_worker_registration_is_reaped(weather, monkeypatch):
    import signal
    original = subprocess.Popen
    workers = []
    def interrupt_after_spawn(*args, **kwargs):
        child = original(*args, **kwargs)
        workers.append(child)
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler), "Worker creation must defer termination"
        handler(signal.SIGTERM, None)
        return child
    monkeypatch.setattr(subprocess, "Popen", interrupt_after_spawn)
    with pytest.raises(KeyboardInterrupt):
        weather.fetch("http://127.0.0.1:1")
    assert workers and all(child.poll() is not None for child in workers)
