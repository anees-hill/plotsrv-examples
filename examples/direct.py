"""Publish an existing value to a running receiver.

uv run --no-sync python -B examples/direct.py http://127.0.0.1:8000
"""

import argparse

import plotsrv as ps


def publish(destination):
    ps.publish_view(
        {"status": "ready", "rows_processed": 3},
        destination=destination, launch_server=False, async_=False,
        view_id="example-direct", label="Pipeline status", section="Focused",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", help="URL of an existing receiver")
    args = parser.parse_args()
    publish(args.destination)
