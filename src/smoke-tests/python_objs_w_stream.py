"""Run the Python-object smoke test, then publish a live structured log."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory
import time

from plotsrv import stream_view


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=60, help="log records to emit (default: 60)")
    parser.add_argument("--interval", type=float, default=0.5, help="seconds between records (default: 0.5)")
    args = parser.parse_args()
    if args.records < 1:
        parser.error("--records must be at least 1")
    if not 0 <= args.interval < float("inf"):
        parser.error("--interval must be finite and non-negative")

    # Execute the original entry point so its views and shared globals stay intact.
    objects = runpy.run_module("smoke-tests.python_objs", run_name="__main__")

    with TemporaryDirectory(prefix="plotsrv-smoke-stream-") as directory:
        source = Path(directory) / "python-objs.jsonl"
        handle = stream_view(
            source=source,
            label="python objects log",
            section="streams",
            host=objects["HOST"],
            port=objects["PORT"],
        )
        print(f"Streaming {args.records} log records to {objects['HOST']}:{objects['PORT']} (streams / python objects log)", flush=True)
        try:
            # Missing sources are observed from byte zero when they appear.
            with source.open("w", encoding="utf-8") as log:
                for index in range(1, args.records + 1):
                    level = "ERROR" if index % 15 == 0 else "WARNING" if index % 5 == 0 else "INFO"
                    record = {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": level,
                        "message": {
                            "INFO": "Processed satellite telemetry",
                            "WARNING": "Telemetry delayed; retry scheduled",
                            "ERROR": "Telemetry unavailable for this sample",
                        }[level],
                        "sequence": index,
                        "satellite": ["Hubble", "Mars Recon Orbiter"][(index - 1) % 2],
                        "metrics": {"latency_ms": 20 + (index * 17) % 200, "samples": index * 10},
                    }
                    log.write(json.dumps(record) + "\n")
                    log.flush()
                    if index < args.records:
                        time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopping stream observation.", flush=True)
        finally:
            # Drain the final records and close the session before deleting its source.
            handle.stop()
        health = handle.health
        if (
            handle.acknowledged_source_offset != source.stat().st_size
            or health["delivery"]["close_failures"]
        ):
            raise RuntimeError(f"Stream delivery was incomplete: {health}")
        print("Stream observation stopped; inspect the log in plotsrv.", flush=True)


if __name__ == "__main__":
    main()
