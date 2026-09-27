"""Optional bounded loopback acceptance test using the actual custom Caddy binary.

Run with CADDY_DEMO_BINARY=/absolute/path/to/caddy. Two streams and sequential
requests exercise admission/reconnection; this is not a load test.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_proxy_preserves_reads_when_sse_is_full_and_releases_expired_clients(tmp_path):
    binary = os.environ.get("CADDY_DEMO_BINARY")
    if not binary:
        pytest.skip("set CADDY_DEMO_BINARY to the built custom Caddy")
    port, proxy_port = free_port(), free_port()
    config = yaml.safe_load((ROOT / "demos/retail/plotsrv.yml").read_text())
    config["server-settings"]["bind"]["port"] = port
    config["publisher-settings"]["destination"]["url"] = f"http://127.0.0.1:{port}"
    config["browser-update-settings"] = dict(max_connections=2,
        max_connections_per_client=1, max_connection_seconds=2)
    config_path = tmp_path / "plotsrv.yml"
    config_path.write_text(yaml.safe_dump(config))
    env = {**os.environ, "PLOTSRV_RETAIL_TOKEN": "local-acceptance-only",
           "PLOTSRV_CONFIG": str(config_path), "PLOTSRV_DEBUG": "1",
           "MPLCONFIGDIR": str(tmp_path / "mpl")}
    # Keep the production retail allowlist, rates and upstream directives.
    production = (ROOT / "deploy/Caddyfile").read_text()
    retail = production.split("\nretail-demo.plotsrv.com {", 1)[1].split("\nlive-demo.plotsrv.com {", 1)[0]
    retail = retail.replace("\ttls /etc/plotsrv-demo/origin.crt /etc/plotsrv-demo/origin.key\n", "")
    retail = retail.replace("\timport demo_headers\n", "").replace("127.0.0.1:8101", f"127.0.0.1:{port}")
    # Shrink only the static budget to prove it is separate without load.
    retail = retail.replace("events 2400", "events 1")
    caddy_path = tmp_path / "Caddyfile"
    caddy_path.write_text("{\n admin off\n auto_https off\n}\n" + f"http://127.0.0.1:{proxy_port} {{" + retail)
    processes = []
    streams = []
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(path, ip="192.0.2.1", method="GET"):
        return opener.open(urllib.request.Request(f"http://127.0.0.1:{proxy_port}{path}",
            headers={"CF-Connecting-IP": ip}, method=method), timeout=5)

    def ready():
        for _ in range(150):
            try:
                with request("/") as response:
                    if response.status == 200:
                        return
            except (OSError, urllib.error.URLError):
                time.sleep(.1)
        raise AssertionError("local proxy/receiver did not become ready")

    with (tmp_path / "processes.log").open("w") as log:
        try:
            processes.append(subprocess.Popen([str(Path(sys.executable).with_name("plotsrv")), "serve", "--config", str(config_path)],
                env=env, cwd=tmp_path, stdout=log, stderr=log))
            processes.append(subprocess.Popen([binary, "run", "--config", str(caddy_path), "--adapter", "caddyfile"],
                cwd=tmp_path, stdout=log, stderr=log))
            ready()
            subprocess.run([sys.executable, "-B", str(ROOT / "demos/retail/app.py")],
                env=env, cwd=tmp_path, stdout=log, stderr=log, check=True, timeout=60)
            with request("/static/logo_plot.png") as asset:
                assert asset.status == 200
            with pytest.raises(urllib.error.HTTPError) as static_limited:
                request("/static/logo_plot.png")
            assert static_limited.value.code == 429
            first = request("/updates?view=retail:orders")
            streams.append(first)
            assert first.readline().startswith(b"retry:")
            with pytest.raises(urllib.error.HTTPError) as busy:
                request("/updates?view=retail:sales")
            assert busy.value.code == 503
            second = request("/updates?view=retail:orders", ip="192.0.2.2")
            streams.append(second)
            assert second.readline().startswith(b"retry:")
            with pytest.raises(urllib.error.HTTPError) as full:
                request("/updates?view=retail:orders", ip="192.0.2.3")
            assert full.value.code == 503
            with request("/table/data?view=retail:orders") as response:
                assert response.status == 200
                assert json.load(response)
            with request("/status?view=retail:orders") as response:
                assert response.status == 200
            for path, method in (("/publish", "POST"), ("/docs", "GET"), ("/history", "GET")):
                with pytest.raises(urllib.error.HTTPError) as blocked:
                    request(path, method=method)
                assert blocked.value.code == 404
            # Read through clean EOF, then reuse the released IP and global slots.
            first.read()
            second.read()
            with request("/updates?view=retail:orders") as reconnected:
                assert reconnected.readline().startswith(b"retry:")
                reconnected.read()
        finally:
            for stream in streams:
                stream.close()
            for process in reversed(processes):
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
