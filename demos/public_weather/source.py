"""Deterministic synthetic observations served over loopback HTTP."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from threading import Thread

SAMPLE = {"observations": [
    {"time": "2026-01-01T00:00:00Z", "temperature_c": 10.0, "humidity_percent": 70.0},
    {"time": "2026-01-01T01:00:00Z", "temperature_c": 12.0, "humidity_percent": 65.0},
    {"time": "2026-01-01T02:00:00Z", "temperature_c": 14.0, "humidity_percent": 60.0},
]}


@contextmanager
def sample_source():
    body = json.dumps(SAMPLE).encode()
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(1)

        def do_GET(self):
            if self.path != "/weather":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/weather"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if thread.is_alive():
            raise RuntimeError("Sample source did not stop")
