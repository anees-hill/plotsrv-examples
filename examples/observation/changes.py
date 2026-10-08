"""Keep one publisher session for healthy/failing/recovered observation changes.

Use --interactive to choose each state after inspecting the browser. Automated
runs use --control-file: each new state is requested only after receiver evidence.
"""

import argparse
import json
from pathlib import Path
import time

import plotsrv as ps


def publish(state, host, port, prefix):
    errors = 3 if state == "failing" else 0
    frame = {"amount": [float(10 + i) for i in range(12)]}
    if errors:
        frame["amount"][:3] = [None] * 3
    options = dict(host=host, port=port, observe=True, section="Smoke observation")
    ps.publish_view(frame, view_id=prefix + ":orders", **options)
    ps.publish_view({"errors": errors, "processed": 12}, view_id=prefix + ":metrics", **options)
    # Return the application result independently of telemetry.
    drained = ps.flush_views(timeout=5)
    print(json.dumps({"state": state, "application_result": 12, "errors": errors,
                      "drained": drained}), flush=True)


def run(args):
    if not 0 < args.seconds <= 1800:
        raise ValueError("seconds must be in (0, 1800]")
    deadline, revision, last = time.monotonic() + args.seconds, -1, 0.0
    while time.monotonic() < deadline:
        if args.interactive:
            print("Choose healthy, failing, recovered, or quit: ", end="", flush=True)
            try:
                state = input().strip()
            except EOFError:
                return
            if state == "quit":
                return
            if state not in ("healthy", "failing", "recovered"):
                continue
        else:
            try:
                control = json.loads(args.control_file.read_text())
            except (FileNotFoundError, ValueError):
                time.sleep(0.05)
                continue
            if control.get("stop") is True:
                return
            state = control.get("state")
            next_revision = control.get("revision")
            if (state not in ("healthy", "failing", "recovered")
                    or type(next_revision) is not int or next_revision <= revision):
                time.sleep(0.05)
                continue
            revision = next_revision
        # Keep captures outside the per-view and process admission cadence.
        time.sleep(max(0, 1.5 - (time.monotonic() - last)))
        publish(state, args.host, args.port, args.view_prefix)
        last = time.monotonic()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8101)
    parser.add_argument("--view-prefix", default="smoke-observe")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--interactive", action="store_true")
    mode.add_argument("--control-file", type=Path)
    parser.add_argument("--seconds", type=float, default=600)
    run(parser.parse_args())
