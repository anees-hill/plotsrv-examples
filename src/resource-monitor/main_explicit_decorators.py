from __future__ import annotations

import argparse
import time
from datetime import datetime

import psutil
import polars as pl
import pandas as pd

from plotnine import (
    aes,
    geom_line,
    geom_point,
    ggplot,
    labs,
    scale_colour_manual,
    scale_x_datetime,
    scale_y_continuous,
    theme_bw,
)

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import seaborn as sns

from plotsrv import table, plot


@table(label="Tabular view", section="polars", host="127.0.0.1", port=8000)
def system_snapshot_polars(interval: float = 1) -> pl.DataFrame:
    mem = psutil.virtual_memory()
    now = datetime.now()

    cpu_percent = psutil.cpu_percent(interval=interval)
    memory_percent = mem.percent
    memory_used_gb = round(mem.used / 1024**3, 2)
    disk_percent = psutil.disk_usage("/").percent

    row = pl.DataFrame(
        {
            "datetime": [now],
            "cpu_percent": [cpu_percent],
            "memory_percent": [memory_percent],
            "memory_used_gb": [memory_used_gb],
            "disk_percent": [disk_percent],
        }
    ).cast({"datetime": pl.Datetime("ms")})

    row = row.unpivot(
        ["cpu_percent", "memory_percent", "memory_used_gb", "disk_percent"],
        index="datetime",
    )

    return row


@table(label="Tabular view", section="pandas", host="127.0.0.1", port=8000)
def system_snapshot_pandas(interval: float = 1):
    # Reuse the polars implementation, then convert.
    df = system_snapshot_polars(interval=interval)
    return df.to_pandas(use_pyarrow_extension_array=False)


def x_scale_picker(observation_count: int) -> tuple[str, str]:
    if observation_count < 360:
        date_breaks_selection = "1 minute"
        date_labels_selection = "%H:%M"
    elif observation_count < 1080:
        date_breaks_selection = "10 minutes"
        date_labels_selection = "%H:%M"
    else:
        date_breaks_selection = "1 hour"
        date_labels_selection = "%D-%M %H:%M"

    return date_breaks_selection, date_labels_selection


def _to_plot_df(data: pl.DataFrame, variable: str) -> pl.DataFrame:
    return data.filter(pl.col("variable") == variable)


def _to_pandas_for_timeplot(df: pl.DataFrame):
    pdf = df.select(["datetime", "value"]).to_pandas(use_pyarrow_extension_array=False)
    # Ensure datetime is actually datetime for matplotlib/seaborn
    if "datetime" in pdf.columns:
        pdf["datetime"] = pd.to_datetime(pdf["datetime"])
    return pdf


@plot(label="CPU%", section="plotnine", host="127.0.0.1", port=8000)
def plot_cpu_percent_plotnine(data: pl.DataFrame):
    cpu_percent = _to_plot_df(data, "cpu_percent").with_columns(
        pl.when(pl.col("value") > 90).then(True).otherwise(False).alias("high_usage")
    )

    date_breaks_selection, date_labels_selection = x_scale_picker(cpu_percent.height)

    p = (
        ggplot(cpu_percent, aes("datetime", "value"))
        + geom_line()
        + geom_point(aes(colour="high_usage"), show_legend=False)
        + scale_y_continuous(limits=[0, 100])
        + theme_bw()
        + scale_colour_manual(values={True: "#b82525", False: "#000000"})
        + scale_x_datetime(
            date_breaks=date_breaks_selection, date_labels=date_labels_selection
        )
        + labs(title="CPU%", x="Date/Time", y="CPU usage % (1s average)")
    )
    return p


@plot(label="CPU%", section="matplotlib", host="127.0.0.1", port=8000)
def plot_cpu_percent_matplotlib(data: pl.DataFrame):
    cpu = _to_plot_df(data, "cpu_percent").with_columns(
        pl.when(pl.col("value") > 90).then(True).otherwise(False).alias("high_usage")
    )

    pdf = cpu.select(["datetime", "value", "high_usage"]).to_pandas(
        use_pyarrow_extension_array=False
    )
    pdf["datetime"] = pd.to_datetime(pdf["datetime"])

    fig, ax = plt.subplots()
    ax.plot(pdf["datetime"], pdf["value"])

    hi = pdf[pdf["high_usage"] == True]
    if len(hi) > 0:
        ax.scatter(hi["datetime"], hi["value"])

    ax.set_ylim(0, 100)
    ax.set_title("CPU%")
    ax.set_xlabel("Date/Time")
    ax.set_ylabel("CPU usage % (1s average)")

    loc = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    fig.autofmt_xdate()

    return fig


@plot(label="CPU%", section="seaborn", host="127.0.0.1", port=8000)
def plot_cpu_percent_seaborn(data: pl.DataFrame):
    cpu = _to_plot_df(data, "cpu_percent").with_columns(
        pl.when(pl.col("value") > 90).then(True).otherwise(False).alias("high_usage")
    )

    pdf = cpu.select(["datetime", "value", "high_usage"]).to_pandas(
        use_pyarrow_extension_array=False
    )
    pdf["datetime"] = pd.to_datetime(pdf["datetime"])

    fig, ax = plt.subplots()
    sns.lineplot(data=pdf, x="datetime", y="value", ax=ax)

    hi = pdf[pdf["high_usage"] == True]
    if len(hi) > 0:
        sns.scatterplot(data=hi, x="datetime", y="value", ax=ax)

    ax.set_ylim(0, 100)
    ax.set_title("CPU%")
    ax.set_xlabel("Date/Time")
    ax.set_ylabel("CPU usage % (1s average)")

    loc = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    fig.autofmt_xdate()

    return fig


@plot(label="MEM-USED", section="plotnine", host="127.0.0.1", port=8000)
def plot_mem_used_plotnine(data: pl.DataFrame):
    mem_used = _to_plot_df(data, "memory_used_gb")
    date_breaks_selection, date_labels_selection = x_scale_picker(mem_used.height)

    p = (
        ggplot(mem_used, aes("datetime", "value"))
        + geom_line()
        + geom_point()
        + theme_bw()
        + scale_x_datetime(
            date_breaks=date_breaks_selection, date_labels=date_labels_selection
        )
        + labs(title="Memory in use (actual)", x="Date/Time", y="gb")
    )
    return p


@plot(label="MEM-USED", section="matplotlib", host="127.0.0.1", port=8000)
def plot_mem_used_matplotlib(data: pl.DataFrame):
    mem_used = _to_plot_df(data, "memory_used_gb")
    pdf = mem_used.select(["datetime", "value"]).to_pandas(
        use_pyarrow_extension_array=False
    )
    pdf["datetime"] = pd.to_datetime(pdf["datetime"])

    fig, ax = plt.subplots()
    ax.plot(pdf["datetime"], pdf["value"])
    ax.scatter(pdf["datetime"], pdf["value"])

    ax.set_title("Memory in use (actual)")
    ax.set_xlabel("Date/Time")
    ax.set_ylabel("gb")

    loc = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    fig.autofmt_xdate()

    return fig


@plot(label="MEM-USED", section="seaborn", host="127.0.0.1", port=8000)
def plot_mem_used_seaborn(data: pl.DataFrame):
    mem_used = _to_plot_df(data, "memory_used_gb")
    pdf = mem_used.select(["datetime", "value"]).to_pandas(
        use_pyarrow_extension_array=False
    )
    pdf["datetime"] = pd.to_datetime(pdf["datetime"])

    fig, ax = plt.subplots()
    sns.lineplot(data=pdf, x="datetime", y="value", ax=ax)
    sns.scatterplot(data=pdf, x="datetime", y="value", ax=ax)

    ax.set_title("Memory in use (actual)")
    ax.set_xlabel("Date/Time")
    ax.set_ylabel("gb")

    loc = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    fig.autofmt_xdate()

    return fig


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fetch-interval",
        help="How often to fetch system resource usage",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--sample-interval",
        help="Interval passed to psutil.cpu_percent(interval=...)",
        type=float,
        default=1.0,
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    running_data = pl.DataFrame(
        schema={
            "datetime": pl.Datetime(time_unit="ms"),
            "variable": pl.String,
            "value": pl.Float64,
        }
    )

    i = 0
    while i >= 0:
        res = system_snapshot_polars(interval=args.sample_interval)
        _ = system_snapshot_pandas(interval=args.sample_interval)

        running_data = running_data.vstack(res)

        _ = plot_cpu_percent_plotnine(running_data)
        _ = plot_cpu_percent_matplotlib(running_data)
        _ = plot_cpu_percent_seaborn(running_data)

        _ = plot_mem_used_plotnine(running_data)
        _ = plot_mem_used_matplotlib(running_data)
        _ = plot_mem_used_seaborn(running_data)

        i += 1
        time.sleep(args.fetch_interval)
