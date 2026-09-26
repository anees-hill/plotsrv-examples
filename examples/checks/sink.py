"""Finite-memory loopback webhook fixture, owned and stopped by the scenario."""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    records = []

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(1)

        def do_GET(self):
            body = json.dumps({"view_id": "webhook-sink", "publish_queue": {},
                               "records": records}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192 or len(records) >= 16:
                    self.send_error(413)
                    return
                body = self.rfile.read(length)
                data = json.loads(body)
                identity = data["event_id"]
                if (self.headers.get("Idempotency-Key") != identity or
                        self.headers.get("X-Plotsrv-Event-Id") != identity):
                    self.send_error(400)
                    return
                records.append({"payload": data, "bytes": len(body), "identity_headers_match": True})
                self.send_response(204)
                self.end_headers()
            except (ValueError, KeyError, OSError):
                self.send_error(400)

        def log_message(self, *args):
            pass

    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
