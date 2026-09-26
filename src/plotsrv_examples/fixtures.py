"""Bounded synthetic fixtures, streamed into a fresh owned run without downloads."""

import hashlib
import json
import os
from pathlib import Path

from .workspace import create, owned_directory


MAX_ROWS = 100_000
MAX_LINES = 10_000


def _integer(name, value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")


def _table(rows, seed):
    yield ",".join(f"column_{i:02d}" for i in range(20)) + "\n"
    for row in range(rows):
        yield ",".join(str((seed + row * 101 + col * 17) % 1_000_003)
                       for col in range(20)) + "\n"


def generate(repository: Path, *, seed=17, rows=MAX_ROWS, lines=4096) -> Path:
    """Return a new run containing reproducible data and a SHA-256 manifest.

    Fixed integer arithmetic and UTF-8/LF encoding are independent of platform,
    random-library versions, wall clock, and run path. Inputs are bounded before
    any directory is created. Generation failures leave an owned partial run.
    """
    _integer("seed", seed, 0, 2**32 - 1)
    _integer("rows", rows, 1, MAX_ROWS)
    _integer("lines", lines, 1, MAX_LINES)
    run = create(repository)
    with owned_directory(repository, run) as fd:
        entries = {}

        def write(name, chunks):
            digest = hashlib.sha256()
            size = 0
            handle = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(handle, "wb") as output:
                for chunk in chunks:
                    data = chunk.encode("utf-8")
                    output.write(data)
                    digest.update(data)
                    size += len(data)
            entries[name] = {"bytes": size, "sha256": digest.hexdigest()}

        for name, count in (("100_20.csv", 100), ("1000_20.csv", 1000),
                            ("6000_20.csv", rows)):
            write(name, _table(count, seed))
        write("long_text.txt", (f"fixture line {i:05d}: value={(seed + i * 31) % 10000:04d}\n"
                                for i in range(lines)))
        write("uvicorn.log", (f"INFO fixture request={i:05d} seed={seed} status=200\n"
                              for i in range(lines)))
        manifest = {"format": "plotsrv-examples/fixtures-v1", "seed": seed,
                    "large_rows": rows, "lines": lines, "columns": 20,
                    "files": dict(entries)}
        write("fixtures.json", [json.dumps(manifest, sort_keys=True, indent=2) + "\n"])
    return run
