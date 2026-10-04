"""Read-only demo visitor. Standard library only; stdout is versioned JSONL."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import random
import signal
import socket
import threading
import time
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlsplit

MAX_BODY = 16 * 1024**2
PRINT_LOCK = threading.Lock()


def emit(name, ok=True, duration=None, **attributes):
    row = {
        "version": 1,
        "type": "event" if duration is None else "operation",
        "name": name,
        "ok": ok,
        "attributes": attributes,
    }
    if duration is not None:
        row["duration_s"] = duration
    with PRINT_LOCK:
        print(json.dumps(row, allow_nan=False), flush=True)


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("src", "href") and value and len(self.paths) < 40:
                self.paths.add(value)


def endpoint(path, view, **query):
    return path + "?" + urlencode(dict(view=view, **query))


def response_attributes(response):
    return {
        "status_code": response.status,
        "cf_cache_status": response.getheader("CF-Cache-Status", "not reported"),
        "cf_challenge": response.getheader("cf-mitigated") == "challenge",
    }


class Visitor:
    def __init__(self, args):
        self.args = args
        self.demo = (
            ("retail", "live", "scans")[args.visitor_id % 3]
            if args.demo == "mixed"
            else args.demo
        )
        self.base = getattr(args, self.demo + "_url").rstrip("/") + "/"
        self.url = urlsplit(self.base)
        if (
            self.url.scheme not in ("http", "https")
            or not self.url.hostname
            or self.url.username
            or self.url.query
            or self.url.fragment
            or self.url.path != "/"
        ):
            raise ValueError(
                "demo URLs must be bare HTTP(S) origins, without credentials"
            )
        if self.url.scheme == "http" and not args.allow_http:
            raise ValueError("HTTP requires --allow-http (for local fixtures)")
        self.stop = threading.Event()
        self.random = random.Random(args.visitor_id)
        self.connection = self.connect(args.timeout)
        self.sse_connection = None
        self.thread = None
        self.failed = False
        self.view = {
            "retail": "retail:orders",
            "live": "live:imports",
            "scans": "scans:results",
        }[self.demo]
        self.instance = None
        self.revision = 0

    def connect(self, timeout):
        cls = (
            http.client.HTTPSConnection
            if self.url.scheme == "https"
            else http.client.HTTPConnection
        )
        return cls(self.url.hostname, self.url.port, timeout=timeout)

    def request(self, name, path, kind="json"):
        started = time.monotonic()
        attributes = {}
        try:
            self.connection.request(
                "GET",
                path,
                headers={
                    "User-Agent": "plotsrv-rehearsal/1",
                    "Accept-Encoding": "identity",
                },
            )
            response = self.connection.getresponse()
            attributes = response_attributes(response)
            body = response.read(MAX_BODY + 1)
            attributes["response_bytes"] = len(body)
            if len(body) > MAX_BODY:
                raise ValueError("response_too_large")
            if attributes["cf_challenge"]:
                raise ValueError("cloudflare_challenge")
            if response.status != 200:
                raise ValueError(
                    "rate_limited" if response.status == 429 else "http_status"
                )
            content_type = response.getheader("Content-Type", "")
            if kind == "json":
                if "application/json" not in content_type:
                    raise ValueError("unexpected_content_type")
                value = json.loads(body)
                if not isinstance(value, dict):
                    raise ValueError("invalid_json_shape")
            elif kind == "page":
                if "text/html" not in content_type or b"plotsrv" not in body.lower():
                    raise ValueError("unexpected_page")
                value = body.decode("utf-8")
            elif kind == "png":
                if not body.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("invalid_png")
                value = None
            else:
                value = None
            emit(
                self.demo + "." + name,
                duration=time.monotonic() - started,
                **attributes,
            )
            return value
        except (OSError, ValueError, http.client.HTTPException) as exc:
            if not self.stop.is_set():
                emit(
                    self.demo + "." + name,
                    False,
                    time.monotonic() - started,
                    error=str(exc)[:200],
                    **attributes,
                )
                self.failed = True
                self.stop.set()
            return None

    def initial_page(self):
        page = self.request("page", endpoint("/", self.view), "page")
        if page is None:
            return
        assets = Assets()
        assets.feed(page)
        for path in sorted(assets.paths):
            target = urlsplit(urljoin(self.base, path))
            if (target.scheme, target.netloc) != (self.url.scheme, self.url.netloc):
                continue
            if not target.path.startswith(("/static/", "/assets/")):
                continue
            if self.stop.is_set():
                break
            self.request(
                "asset",
                target.path + ("?" + target.query if target.query else ""),
                "asset",
            )

    def updates(self):
        while not self.stop.is_set():
            started = time.monotonic()
            connection = self.connect(self.args.sse_timeout)
            self.sse_connection = connection
            attributes = {}
            try:
                connection.request(
                    "GET",
                    endpoint("/updates", self.view, since=self.revision),
                    headers={
                        "Accept": "text/event-stream",
                        "Last-Event-ID": str(self.revision),
                        "User-Agent": "plotsrv-rehearsal/1",
                    },
                )
                response = connection.getresponse()
                attributes = response_attributes(response)
                if attributes["cf_challenge"]:
                    raise ValueError("cloudflare_challenge")
                if (
                    response.status != 200
                    or "text/event-stream" not in response.getheader("Content-Type", "")
                ):
                    raise ValueError(
                        "sse_rate_limited" if response.status == 429 else "sse_rejected"
                    )
                emit(
                    self.demo + ".sse_connect",
                    duration=time.monotonic() - started,
                    **attributes,
                )
                event, data, size = "", [], 0
                while not self.stop.is_set():
                    line = response.readline(65537)
                    if not line:
                        if time.monotonic() - started < self.args.sse_lifetime * 0.9:
                            raise ValueError("sse_disconnected_early")
                        emit(self.demo + ".sse_reconnect")
                        break
                    size += len(line)
                    if size > 65536:
                        raise ValueError("sse_event_too_large")
                    text = line.decode("utf-8").rstrip("\r\n")
                    if not text:
                        if event in ("update", "keepalive"):
                            payload = json.loads("\n".join(data))
                            if not isinstance(payload, dict):
                                raise ValueError("invalid_sse_payload")
                            if event == "update":
                                instance = payload.get("server_instance_id")
                                revision = payload.get("revision")
                                if not isinstance(instance, str) or not isinstance(
                                    revision, int
                                ):
                                    raise ValueError("invalid_sse_identity")
                                if (
                                    self.instance is not None
                                    and instance != self.instance
                                ):
                                    raise ValueError("receiver_restarted")
                                self.instance, self.revision = (
                                    instance,
                                    max(self.revision, revision),
                                )
                            emit(self.demo + ".sse_" + event)
                        event, data, size = "", [], 0
                    elif text.startswith("event:"):
                        event = text[6:].strip()
                    elif text.startswith("data:"):
                        data.append(text[5:].lstrip())
            except (OSError, ValueError, http.client.HTTPException) as exc:
                if not self.stop.is_set():
                    emit(
                        self.demo + ".sse_failure",
                        False,
                        error=str(exc)[:200],
                        **attributes,
                    )
                    self.failed = True
                    self.stop.set()
            finally:
                connection.close()
                self.sse_connection = None
            self.stop.wait(2)

    def actions(self):
        if self.demo == "retail":
            return [
                ("table", endpoint("/table/data", self.view), "json"),
                ("plot", endpoint("/plot", "retail:sales"), "png"),
                ("markdown", endpoint("/artifact", "retail:guide"), "json"),
                ("summary", endpoint("/artifact", "retail:summary"), "json"),
            ]
        if self.demo == "live":
            return [
                ("stream", endpoint("/stream/data", self.view, limit=100), "json"),
                ("stream_status", endpoint("/stream/status", self.view), "json"),
                ("stream_summary", endpoint("/stream/summary", self.view), "json"),
            ]
        return [
            ("table", endpoint("/table/data", self.view), "json"),
            ("image", endpoint("/artifact", "scans:example"), "json"),
            ("observation", endpoint("/artifact", "scans:observed"), "json"),
            ("changes", endpoint("/artifact", "scans:changes"), "json"),
            ("history", endpoint("/history", self.view, limit=5), "json"),
        ]

    def close(self):
        self.stop.set()
        # Interrupt a blocked SSE read so downscaling releases its subscription.
        connection = self.sse_connection
        if connection and connection.sock:
            try:
                connection.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if self.thread:
            self.thread.join(timeout=2)
        self.connection.close()

    def run(self):
        deadline = time.monotonic() + self.args.duration
        try:
            self.initial_page()
            if self.stop.is_set():
                return 1
            self.thread = threading.Thread(target=self.updates, daemon=True)
            self.thread.start()
            actions = self.actions()
            index = 0
            while not self.stop.is_set() and time.monotonic() < deadline:
                name, path, kind = actions[index % len(actions)]
                self.request(name, path, kind)
                # Each visitor remains paced even if the receiver publishes rapidly.
                self.stop.wait(
                    min(
                        self.random.uniform(self.args.pause_min, self.args.pause_max),
                        max(0, deadline - time.monotonic()),
                    )
                )
                index += 1
            return int(self.failed)
        finally:
            self.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--demo", choices=("mixed", "retail", "live", "scans"), default="mixed"
    )
    parser.add_argument(
        "--visitor-id", type=int, default=int(os.environ.get("PTOP_WORKER_ID", "0"))
    )
    for demo in ("retail", "live", "scans"):
        parser.add_argument(
            "--" + demo + "-url", default="https://" + demo + "-demo.plotsrv.com"
        )
    parser.add_argument(
        "--duration", type=float, default=14520 if "PTOP_RUN_ID" in os.environ else 60
    )
    parser.add_argument("--pause-min", type=float, default=2)
    parser.add_argument("--pause-max", type=float, default=5)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--sse-timeout", type=float, default=45)
    parser.add_argument("--sse-lifetime", type=float, default=600)
    parser.add_argument("--allow-http", action="store_true")
    args = parser.parse_args(argv)
    if not (
        0 < args.duration <= 14520
        and 0.01 <= args.pause_min <= args.pause_max <= 60
        and 0 < args.timeout <= 60
        and 0 < args.sse_timeout <= 120
        and 0 < args.sse_lifetime <= 3600
    ):
        parser.error("durations/timeouts and pacing are outside the supported bounds")
    try:
        visitor = Visitor(args)
    except ValueError as exc:
        parser.error(str(exc))
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: visitor.stop.set())
    return visitor.run()


if __name__ == "__main__":
    raise SystemExit(main())
