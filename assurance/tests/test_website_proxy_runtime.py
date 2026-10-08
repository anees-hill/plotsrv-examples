"""Validate static-site routes using the actual production Caddy blocks."""
from pathlib import Path
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[2]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@pytest.fixture
def website_proxy(tmp_path):
    binary = os.environ.get('CADDY_DEMO_BINARY')
    website = Path(os.environ.get('PLOTSRV_HOMEPAGE', str(ROOT.parent/'plotsrv-homepage')))
    if not binary or not (website/'index.html').exists():
        pytest.skip('requires CADDY_DEMO_BINARY and a plotsrv-homepage checkout')
    ports = [free_port(), free_port()]
    source = subprocess.check_output([sys.executable, str(ROOT/'deploy/render-caddy.py'), 'website', 'landing'], text=True)
    source = source.replace('import managed_tls', '').replace('/opt/plotsrv-homepage', str(website))
    source = source.replace('plotsrv.com {', f'http://127.0.0.1:{ports[0]} {{', 1)
    source = source.replace('demo.plotsrv.com {', f'http://127.0.0.1:{ports[1]} {{', 1)
    source = source.replace('{\n\tservers', '{\n\tadmin off\n\tauto_https off\n\tservers', 1)
    cfg = tmp_path/'Caddyfile'
    cfg.write_text(source)
    with (tmp_path/'proxy.log').open('w') as log:
        proc = subprocess.Popen([binary, 'run', '--config', str(cfg), '--adapter', 'caddyfile'], stdout=log, stderr=log)
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen(f'http://127.0.0.1:{ports[0]}/', timeout=1).close()
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise AssertionError((tmp_path/'proxy.log').read_text())
            yield [f'http://127.0.0.1:{port}' for port in ports]
        finally:
            proc.terminate()
            proc.wait(timeout=10)


def test_static_hosts_serve_only_public_assets(website_proxy):
    home, demos = website_proxy
    expected = {home: ['/', '/demos/', '/app.js', '/shared.css', '/assets/screenshots/scatter.png'],
                demos: ['/', '/demos/', '/demos/styles.css', '/navigation.js', '/assets/demos/retail.png']}
    for base, routes in expected.items():
        for route in routes:
            with urllib.request.urlopen(base+route) as response:
                assert response.status == 200
                assert response.read(1)
                assert 'Content-Security-Policy' in response.headers
        for route, method in [('/scripts/capture_source.py','GET'),('/demos/README.md','GET'),('/.git/config','GET'),('/','POST')]:
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(urllib.request.Request(base+route, method=method))
            assert exc.value.code == 404
    with urllib.request.urlopen(home+'/') as response:
        assert b'Your outputs.' in response.read()
    with urllib.request.urlopen(demos+'/') as response:
        assert b'Live demos' in response.read()
