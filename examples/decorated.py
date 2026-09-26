"""Publish function results and class construction through active decorators.

uv run --no-sync python -B examples/decorated.py --port 8000
"""

import argparse

import plotsrv as ps


def publish(host, port):
    # Active decorators take host/port, not a destination URL.
    @ps.view(host=host, port=port, async_=False, view_id="example-function",
             label="Function result", section="Focused")
    def summary():
        return {"planet": "Earth", "moons": ["Moon"]}

    @ps.view(host=host, port=port, async_=False, view_id="example-class",
             label="Satellite instance", section="Focused")
    class Satellite:
        def __init__(self, name, altitude_km):
            self.name = name
            self.altitude_km = altitude_km

    result = summary()
    satellite = Satellite("Hubble", 547)
    # Decorated calls still return useful Python values.
    assert result["planet"] == "Earth"
    assert satellite.name == "Hubble"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    publish(args.host, args.port)
