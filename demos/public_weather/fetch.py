"""Bounded HTTP worker; parent enforces a five-second wall-clock deadline."""
import os
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

MAX_BYTES = 65536


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main():
    try:
        url = os.environ["WEATHER_FETCH_URL"]
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
            return 1
        opener = build_opener(ProxyHandler({}), NoRedirect())
        with opener.open(url, timeout=2) as response:
            if response.status != 200:
                return 1
            body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            return 1
        sys.stdout.buffer.write(body)
        return 0
    except Exception:
        # Never emit the configured URL, response body, or credentials in errors.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
