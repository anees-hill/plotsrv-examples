"""Wait a bounded time for a loopback plotsrv receiver to finish starting."""
import argparse
import json
import os
import time
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def wait_for_receiver(port, token, timeout=60):
    deadline = time.monotonic() + timeout
    # Bypass environment proxies; readiness must never contact a third party.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(f"http://127.0.0.1:{port}/capabilities",
                                     headers={"Authorization": f"Bearer {token}"})
    while time.monotonic() < deadline:
        try:
            remaining = deadline - time.monotonic()
            with opener.open(request, timeout=min(2, remaining)) as response:
                raw = response.read(65537)
                if len(raw) <= 65536:
                    data = json.loads(raw)
                    capabilities = data.get("capabilities") if isinstance(data, dict) else None
                    if isinstance(capabilities, list) and "publish" in capabilities:
                        return
        except (OSError, ValueError, urllib.error.URLError):
            pass
        time.sleep(min(.5, max(0, deadline - time.monotonic())))
    raise RuntimeError(f"receiver on loopback port {port} did not become ready in {timeout}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--token-env", required=True)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not 1 <= args.timeout <= 120:
        parser.error("invalid port or timeout")
    token = os.environ.get(args.token_env, "").strip()
    if not token:
        parser.error("publisher token environment variable is missing")
    wait_for_receiver(args.port, token, args.timeout)
