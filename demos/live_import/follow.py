"""Attach plotsrv to the import worker's rotating JSONL file."""

import argparse
import os
from pathlib import Path
import signal
import time


def run(path):
    from plotsrv import stream_view

    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    handle = stream_view(source=path, format="jsonl", view_id="live:imports",
                         label="Live import log", section="Live imports")
    try:
        while not stopping:
            if not handle.is_observing:
                raise RuntimeError("JSONL follower stopped unexpectedly")
            time.sleep(0.5)
    finally:
        handle.stop(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=Path("import.jsonl"))
    args = parser.parse_args()
    os.environ.setdefault("PLOTSRV_CONFIG", str(Path(__file__).with_name("plotsrv.yml")))
    run(args.log)
