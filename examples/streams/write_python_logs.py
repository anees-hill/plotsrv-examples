"""Append a small, repeatable Python application log batch."""

import argparse
from pathlib import Path


LOG = """INFO:worker.tasks:Job started
WARNING:worker.tasks:Retrying one task
ERROR:worker.db:Connection failed
worker-note: this line stays in the raw stream
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    with args.source.open("a", encoding="utf-8") as output:
        output.write(LOG)
        output.flush()


if __name__ == "__main__":
    main()
