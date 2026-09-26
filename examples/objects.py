"""Small deterministic objects, tables and plots sent to an existing receiver.

uv run --no-sync python -B examples/objects.py http://127.0.0.1:8000
Each builder can be called independently; importing this module publishes nothing.
"""

import argparse
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
from plotnine import aes, geom_col, ggplot, labs, theme_minimal
import plotsrv as ps


@dataclass
class Satellite:
    name: str
    altitude_km: int


def nested_objects():
    return {"Earth": {"moons": ["Moon"], "atmosphere": {"nitrogen": 78.08}},
            "Mars": {"moons": ["Phobos", "Deimos"], "inhabited": False}}


def mixed_objects():
    return [nested_objects()["Earth"], Satellite("Hubble", 547),
            {"note": "heterogeneous example"}, [1, None, True]]


def planet_table():
    return pd.DataFrame({"planet": ["Earth", "Mars", "Jupiter"],
                         "gravity": [9.81, 3.71, 24.79],
                         "temperature": [15, -63, -110]})


def gravity_plot():
    data = planet_table()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(data["planet"], data["gravity"])
    ax.set(title="Surface gravity", ylabel="Gravity (m/s²)")
    fig.tight_layout()
    return fig


def temperature_plot():
    return (ggplot(planet_table(), aes("planet", "temperature")) + geom_col()
            + labs(title="Mean temperature", y="Temperature (°C)") + theme_minimal())


def publish(destination):
    # Transport options are explicit at each call; no examples client is needed.
    ps.publish_view(nested_objects(), destination=destination, async_=False,
                    view_id="example-nested", label="Planets", section="Objects")
    ps.publish_view(mixed_objects(), destination=destination, async_=False,
                    view_id="example-mixed", label="Mixed objects", section="Objects")
    ps.publish_view(np.arange(12).reshape(4, 3), destination=destination, async_=False,
                    view_id="example-array", label="NumPy array", section="Objects")
    ps.publish_view(planet_table(), destination=destination, async_=False,
                    view_id="example-pandas", label="pandas table", section="Tables")
    ps.publish_view(pl.from_pandas(planet_table()), destination=destination, async_=False,
                    view_id="example-polars", label="Polars table", section="Tables")
    figure = gravity_plot()
    try:
        ps.publish_view(figure, destination=destination, async_=False,
                        view_id="example-matplotlib", label="Gravity", section="Plots")
        ps.publish_view(temperature_plot(), destination=destination, async_=False,
                        view_id="example-plotnine", label="Temperature", section="Plots")
    finally:
        plt.close(figure)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", help="URL of an existing receiver")
    args = parser.parse_args()
    publish(args.destination)
