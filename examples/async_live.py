"""Queue latest-state updates and explicitly drain before this script exits.

uv run --no-sync python -B examples/async_live.py http://127.0.0.1:8000
Intermediate updates may coalesce: this is a live view, not an event log.
"""

import argparse

import plotsrv as ps


def publish(destination):
    for completed in range(1, 6):
        ps.publish_view({"completed": completed, "total": 5},
                        destination=destination, async_=True,
                        view_id="example-async", label="Latest progress", section="Focused")
    if not ps.flush_views(timeout=5):
        raise RuntimeError("Live publication queue did not drain within five seconds")
    # A drained queue is not proof of delivery; inspect the receiver for completed=5.


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", help="URL of an existing receiver")
    args = parser.parse_args()
    publish(args.destination)
