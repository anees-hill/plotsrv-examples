"""A tiny loopback server checks authentication, retries and redirect refusal."""
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading

import pytest


def test_readiness_retries_and_never_follows_redirects():
    path = Path(__file__).resolve().parents[2] / "deploy/wait-for-receiver.py"
    spec = importlib.util.spec_from_file_location("readiness", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seen = []
    redirect = False

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            seen.append(self.path)
            assert self.headers.get("Authorization") == "Bearer test-only"
            if redirect:
                self.send_response(302)
                self.send_header("Location", "/must-not-follow")
                self.end_headers()
            elif len(seen) == 1:
                self.send_response(503)
                self.end_headers()
            elif len(seen) == 2:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"capabilities":null}')
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"capabilities":["publish"]}')

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        module.wait_for_receiver(server.server_port, "test-only", timeout=2)
        assert len(seen) == 3
        redirect = True
        with pytest.raises(RuntimeError):
            module.wait_for_receiver(server.server_port, "test-only", timeout=.1)
        assert set(seen) == {"/capabilities"}
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
