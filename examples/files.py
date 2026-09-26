"""Publish file contents (not a filename string) to an existing receiver.

uv run --no-sync python -B examples/files.py http://127.0.0.1:8000 mock-files/json-1.json
The receiver selects a renderer from the file type. No file watch is installed.
"""

import argparse
from pathlib import Path

import plotsrv as ps


def publish(destination, path):
    if not path.is_file():
        raise ValueError(f"Expected an existing file: {path}")
    ps.publish_view(path.resolve(), destination=destination, async_=False,
                    view_id="example-file", label=path.name, section="Files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", help="URL of an existing receiver")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    publish(args.destination, args.path)
