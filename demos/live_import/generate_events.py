"""Small synthetic import worker; validates each record and writes bounded JSONL logs."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import time


def candidate(index, rng):
    row = {"record_id": f"IMP-{index:07d}", "sku": rng.choice(("PACK", "SHELL", "LAMP")),
           "quantity": rng.randint(1, 5), "price_gbp": rng.choice((19, 32, 48, 84, 115))}
    if index % 23 == 0:
        row["quantity"] = -1
    if index % 47 == 0:
        row["sku"] = "UNKNOWN"
    return row


def validate(row):
    if row["sku"] not in {"PACK", "SHELL", "LAMP"}:
        return "unknown_sku"
    if not 1 <= row["quantity"] <= 20:
        return "invalid_quantity"
    return None


def event(index, rng, *, now=None):
    row = candidate(index, rng)
    issue = validate(row)
    duration = round(35 + 0.7 * (index % 90) + rng.random() * 16, 1)
    return {
        "timestamp": (now or datetime.now(timezone.utc)).isoformat(),
        "level": "WARNING" if issue else "INFO",
        "logger": "importer.validation" if issue else "importer.records",
        "message": f"Rejected {row['record_id']}: {issue}" if issue else f"Imported {row['record_id']}",
        "record_id": row["record_id"], "sku": row["sku"],
        "quantity": row["quantity"], "duration_ms": duration,
        "validation_issue": issue,
    }


def append_rotating(path, record, *, max_bytes=1_048_576, backups=2):
    line = (json.dumps(record, separators=(",", ":")) + "\n").encode()
    if len(line) > max_bytes:
        raise ValueError("one record exceeds the configured file limit")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size + len(line) > max_bytes:
        oldest = path.with_name(path.name + f".{backups}")
        oldest.unlink(missing_ok=True)
        for n in range(backups - 1, 0, -1):
            earlier = path.with_name(path.name + f".{n}")
            if earlier.exists():
                os.replace(earlier, path.with_name(path.name + f".{n+1}"))
        os.replace(path, path.with_name(path.name + ".1"))
    with path.open("ab") as output:
        output.write(line)


def run(path, count=None, interval=3.0, seed=2026, max_bytes=1_048_576):
    rng = random.Random(seed)
    index = 1
    while count is None or index <= count:
        append_rotating(path, event(index, rng), max_bytes=max_bytes)
        index += 1
        if count is None or index <= count:
            time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=Path("import.jsonl"))
    parser.add_argument("--count", type=int)
    parser.add_argument("--interval", type=float, default=3.0)
    parser.add_argument("--max-bytes", type=int, default=1_048_576)
    args = parser.parse_args()
    if args.count is not None and not 1 <= args.count <= 100_000:
        parser.error("--count must be between 1 and 100000")
    if not 0 <= args.interval <= 60 or not 1024 <= args.max_bytes <= 1_048_576:
        parser.error("interval or file size outside supported bounds")
    run(args.log, args.count, args.interval, max_bytes=args.max_bytes)
