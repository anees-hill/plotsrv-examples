"""Real psutil measurements with a fixed-size rolling window."""

import argparse
from collections import deque
from datetime import datetime, timezone
import json
import math
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import polars as pl
import psutil
from plotsrv import publish_view


def snapshot(interval):
    cpu = psutil.cpu_percent(interval=interval)
    memory = psutil.virtual_memory()
    return {"time": datetime.now(timezone.utc).isoformat(),
            "cpu_percent": float(cpu), "memory_percent": float(memory.percent),
            "memory_used_gb": float(memory.used / 1024**3),
            "disk_percent": float(psutil.disk_usage("/").percent)}


def publish(history, destination):
    frame = pd.DataFrame(history)
    options = dict(destination=destination, launch_server=False, async_=False,
                   section="Resource monitor")
    publish_view(frame, view_id="resource-pandas", **options)
    publish_view(pl.from_pandas(frame), view_id="resource-polars", **options)
    for metric in ("cpu_percent", "memory_percent"):
        fig, ax = plt.subplots(figsize=(7, 3))
        try:
            ax.plot(pd.to_datetime(frame["time"]), frame[metric], marker=".")
            ax.set(title=metric.replace("_", " "), ylabel="percent", ylim=(0, 100))
            fig.autofmt_xdate()
            fig.tight_layout()
            publish_view(fig, view_id="resource-" + metric, **options)
        finally:
            plt.close(fig)


def run(destination, *, samples=3, history_size=60, interval=0.1, duration=None):
    if not 1 <= history_size <= 10000 or samples < 1:
        raise ValueError("history-size must be 1..10000 and samples positive")
    if not math.isfinite(interval) or not 0 < interval <= 10:
        raise ValueError("interval must be finite and in (0, 10]")
    if duration is not None and (not math.isfinite(duration) or duration < 0):
        raise ValueError("duration must be finite and nonnegative")
    history = deque(maxlen=history_size)
    deadline = None if duration is None else time.monotonic() + duration
    count = 0
    while count < samples or (deadline is not None and time.monotonic() < deadline):
        history.append(snapshot(interval))
        publish(history, destination)
        count += 1
    return {"samples": count, "retained": len(history), "history_size": history_size,
            "last": history[-1], "open_figures": len(plt.get_fignums())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--history-size", type=int, default=60)
    parser.add_argument("--interval", type=float, default=0.1)
    parser.add_argument("--duration", type=float)
    args = parser.parse_args()
    print(json.dumps(run(args.destination, samples=args.samples,
                         history_size=args.history_size, interval=args.interval,
                         duration=args.duration)))
