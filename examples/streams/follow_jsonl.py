"""Observe an independent JSONL file for a bounded duration; Ctrl+C drains it."""

import argparse
import json
import math
from pathlib import Path
import signal
import time

from plotsrv import stream_view


def main(*, format="jsonl"):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--view-id", default="example-" + format)
    parser.add_argument("--session-id")
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--stop-file", type=Path)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 300:
        parser.error("--seconds must be finite and between 0 and 300")
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    handle = None
    try:
        handle = stream_view(source=args.source, format=format,
                             destination=args.destination, view_id=args.view_id,
                             session_id=args.session_id)
        deadline = time.monotonic() + args.seconds
        ready = False
        while not stopping and time.monotonic() < deadline:
            if not handle.is_observing:
                raise RuntimeError("Source observer stopped unexpectedly")
            if not ready and handle.health["delivery"]["registered"]:
                print("Registered; append records now", flush=True)
                ready = True
            if args.stop_file and args.stop_file.exists():
                break
            time.sleep(0.02)
    finally:
        if handle is not None:
            handle.stop(timeout=3)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    health = handle.health
    print(json.dumps({"session_id": handle.session_id, "health": health}), flush=True)
    if (handle.is_observing or not health["delivery"]["registered"]
            or health["delivery"]["close_failures"]
            or handle.acknowledged_source_offset != args.source.stat().st_size):
        raise RuntimeError("Stream did not finish acknowledged delivery and close")


if __name__ == "__main__":
    main()
