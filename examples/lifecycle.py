"""Own an attached server with an explicit lifetime and joined cleanup.

uv run --no-sync python -B examples/lifecycle.py --config configs/current/minimal.yml
Use --mode show to demonstrate patched plt.show(), or --mode watch --watch FILE.
Run from a disposable working directory when using a storage-enabled config.
"""

import argparse
import math
from pathlib import Path
import time

import matplotlib.pyplot as plt
import plotsrv as ps


def run(config, port, seconds, mode, watch=None):
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("seconds must be finite and nonnegative")
    if mode == "watch" and (watch is None or not watch.is_file()):
        raise ValueError("watch mode requires an existing --watch file")
    if mode != "watch" and watch is not None:
        raise ValueError("--watch requires --mode watch")
    watches = ([{"path": str(watch.resolve()), "label": "Watched file"}]
               if mode == "watch" else None)
    figure = None
    try:
        ps.start_server(host="127.0.0.1", port=port, config=config.resolve(),
                        restore_latest=False, auto_on_show=(mode == "show"),
                        watches=watches, quiet=True)
        if mode == "publish":
            ps.publish_view({"lifecycle": "attached", "state": "ready"},
                            launch_server=True, host="127.0.0.1", port=port, async_=False,
                            view_id="example-lifecycle", label="Attached server")
        elif mode == "show":
            figure, ax = plt.subplots()
            ax.plot([1, 2, 3], [2, 5, 3])
            ax.set_title("Published by patched plt.show()")
            plt.show()
        print(f"Inspect http://127.0.0.1:{port} for {seconds:g} seconds", flush=True)
        time.sleep(seconds)
    finally:
        if figure is not None:
            plt.close(figure)
        ps.stop_server(join=True, timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--mode", choices=("publish", "show", "watch"), default="publish")
    parser.add_argument("--watch", type=Path)
    args = parser.parse_args()
    run(args.config, args.port, args.seconds, args.mode, args.watch)
