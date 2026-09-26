"""One fetch/validate/normalise/transform/publish path for sample and live input."""
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys

from source import sample_source


class Unavailable(ValueError):
    pass


def fetch(url):
    env = dict(os.environ, WEATHER_FETCH_URL=url)
    worker = None
    try:
        # Register the worker before honouring interruption, including signals
        # arriving inside Popen's constructor. Handlers reset on child exec.
        pending = []
        previous = {}
        try:
            for number in (signal.SIGINT, signal.SIGTERM):
                previous[number] = signal.signal(number, lambda number, frame: pending.append(number))
            worker = subprocess.Popen(
                [sys.executable, str(Path(__file__).with_name("fetch.py"))],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)
        if pending:
            raise KeyboardInterrupt()
        output, _ = worker.communicate(timeout=5)
        if worker.returncode:
            raise Unavailable("Weather input unavailable")
        return json.loads(output)
    except (subprocess.TimeoutExpired, ValueError, OSError, RecursionError):
        raise Unavailable("Weather input unavailable") from None
    finally:
        if worker is not None:
            if worker.poll() is None:
                worker.kill()
            worker.communicate()


def normalise(payload):
    if not isinstance(payload, dict) or set(payload) != {"observations"}:
        raise Unavailable("Weather input invalid")
    records = payload["observations"]
    if not isinstance(records, list) or not 1 <= len(records) <= 1000:
        raise Unavailable("Weather input invalid")
    rows = []
    seen = set()
    for record in records:
        try:
            if set(record) != {"time", "temperature_c", "humidity_percent"}:
                raise ValueError()
            stamp = datetime.fromisoformat(record["time"].replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError()
            stamp = stamp.astimezone(timezone.utc).isoformat()
            temperature, humidity = record["temperature_c"], record["humidity_percent"]
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in (temperature, humidity)):
                raise ValueError()
            if not -100 <= temperature <= 70 or not 0 <= humidity <= 100 or stamp in seen:
                raise ValueError()
            seen.add(stamp)
            rows.append({"time": stamp, "temperature_c": float(temperature),
                         "humidity_percent": float(humidity)})
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            raise Unavailable("Weather input invalid") from None
    return sorted(rows, key=lambda row: row["time"])


def transform(rows, source):
    return [dict(row, temperature_f=round(row["temperature_c"] * 1.8 + 32, 2),
                 source=source) for row in rows]


def publish(rows, destination, status):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    from plotsrv import publish_view
    options = dict(destination=destination, launch_server=False, async_=False,
                   section="Weather demo")
    publish_view(status, view_id="weather-status", kind="artifact", artifact_kind="text", **options)
    if rows is None:
        return
    frame = pd.DataFrame(rows)
    publish_view(frame, view_id="weather-observations", **options)
    fig, ax = plt.subplots(figsize=(7, 3))
    try:
        ax.plot(pd.to_datetime(frame["time"]), frame["temperature_c"], marker="o")
        ax.set(title=status, ylabel="Temperature (C)")
        fig.autofmt_xdate()
        fig.tight_layout()
        publish_view(fig, view_id="weather-temperature", **options)
    finally:
        plt.close(fig)


def run(destination, mode="sample"):
    source = "synthetic sample" if mode == "sample" else "configured live input"
    try:
        if mode not in ("sample", "live"):
            raise Unavailable("Weather mode invalid")
        url = os.environ.get("WEATHER_LIVE_URL", "")
        if mode == "live" and not url:
            raise Unavailable("Weather live configuration missing")
        with sample_source() if mode == "sample" else nullcontext(url) as endpoint:
            rows = transform(normalise(fetch(endpoint)), source)
        publish(rows, destination, source + " available")
        return {"success": True, "mode": mode, "count": len(rows)}
    except Unavailable as exc:
        publish(None, destination, source + " unavailable")
        return {"success": False, "mode": mode, "error": str(exc)}


if __name__ == "__main__":
    # Unwind fetch's owned-worker cleanup on shutdown.
    def interrupt(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupt)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--mode", choices=("sample", "live"), default="sample")
    args = parser.parse_args()
    try:
        result = run(args.destination, args.mode)
        print(json.dumps(result))
        raise SystemExit(0 if result["success"] else 1)
    except KeyboardInterrupt:
        raise SystemExit(130)
