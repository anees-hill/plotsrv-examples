"""Append one deterministic synthetic batch of requests, text and a traceback."""

import argparse
from pathlib import Path


MIXED_LOG = '''INFO: 127.0.0.1:54321 - "GET /health HTTP/1.1" 200
INFO: 127.0.0.1:54321 - "POST /work HTTP/1.1" 500 duration=12.5ms
Traceback (most recent call last):
  File "/tmp/synthetic/app.py", line 7, in work
    raise ValueError("synthetic failure")
ValueError: synthetic failure
worker-note: unexpected orbit wobble
{"incomplete":
INFO: 127.0.0.1:54321 - "GET /missing HTTP/1.1" 404
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    with args.source.open("a", encoding="utf-8") as output:
        output.write(MIXED_LOG)
        output.flush()


if __name__ == "__main__":
    main()
