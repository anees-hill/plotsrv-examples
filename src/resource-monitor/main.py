from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import polars as pl
import psutil
import seaborn as sns
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

from plotsrv import plot, plot_launch, plotsrv, publish_artifact, publish_view, table

PublishStyle = Literal["decorator", "direct"]
KindMode = Literal["explicit", "infer"]
PlotLib = Literal["plotnine", "matplotlib", "seaborn"]


@dataclass(frozen=True)
class ResourceMonitorConfig:
    publish_style: PublishStyle
    kind: KindMode
    host: str
    port: int
    fetch_interval: float
    sample_interval: float
    max_iterations: int | None
    plot_libs: tuple[PlotLib, ...]


def system_snapshot_polars(interval: float = 1.0) -> pl.DataFrame:
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

    return row.unpivot(
        ["cpu_percent", "memory_percent", "memory_used_gb", "disk_percent"],
        index="datetime",
    )


def system_snapshot_pandas(row: pl.DataFrame) -> pd.DataFrame:
    return row.to_pandas(use_pyarrow_extension_array=False)


def empty_running_data() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "datetime": pl.Datetime(time_unit="ms"),
            "variable": pl.String,
            "value": pl.Float64,
        }
    )


def x_scale_picker(observation_count: int) -> tuple[str, str]:
    if observation_count < 360:
        return "1 minute", "%H:%M"

    if observation_count < 1080:
        return "10 minutes", "%H:%M"

    return "1 hour", "%D-%M %H:%M"


def _to_plot_df(data: pl.DataFrame, variable: str) -> pl.DataFrame:
    return data.filter(pl.col("variable") == variable)


def _to_pandas_for_timeplot(df: pl.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    pdf = df.select(list(columns)).to_pandas(use_pyarrow_extension_array=False)

    if "datetime" in pdf.columns:
        pdf["datetime"] = pd.to_datetime(pdf["datetime"])

    return pdf


def plot_cpu_percent_plotnine(data: pl.DataFrame):
    cpu_percent = _to_plot_df(data, "cpu_percent").with_columns(
        pl.when(pl.col("value") > 90).then(True).otherwise(False).alias("high_usage")
    )

    date_breaks_selection, date_labels_selection = x_scale_picker(cpu_percent.height)

    return (
        ggplot(cpu_percent, aes("datetime", "value"))
        + geom_line()
        + geom_point(aes(colour="high_usage"), show_legend=False)
        + scale_y_continuous(limits=[0, 100])
        + theme_bw()
        + scale_colour_manual(values={True: "#b82525", False: "#000000"})
        + scale_x_datetime(
            date_breaks=date_breaks_selection,
            date_labels=date_labels_selection,
        )
        + labs(title="CPU%", x="Date/Time", y="CPU usage % (1s average)")
    )


def plot_cpu_percent_matplotlib(data: pl.DataFrame):
    cpu = _to_plot_df(data, "cpu_percent").with_columns(
        pl.when(pl.col("value") > 90).then(True).otherwise(False).alias("high_usage")
    )

    pdf = _to_pandas_for_timeplot(cpu, ["datetime", "value", "high_usage"])

    fig, ax = plt.subplots()
    ax.plot(pdf["datetime"], pdf["value"])

    hi = pdf[pdf["high_usage"]]
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


def plot_cpu_percent_seaborn(data: pl.DataFrame):
    cpu = _to_plot_df(data, "cpu_percent").with_columns(
        pl.when(pl.col("value") > 90).then(True).otherwise(False).alias("high_usage")
    )

    pdf = _to_pandas_for_timeplot(cpu, ["datetime", "value", "high_usage"])

    fig, ax = plt.subplots()
    sns.lineplot(data=pdf, x="datetime", y="value", ax=ax)

    hi = pdf[pdf["high_usage"]]
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


def plot_mem_used_plotnine(data: pl.DataFrame):
    mem_used = _to_plot_df(data, "memory_used_gb")
    date_breaks_selection, date_labels_selection = x_scale_picker(mem_used.height)

    return (
        ggplot(mem_used, aes("datetime", "value"))
        + geom_line()
        + geom_point()
        + theme_bw()
        + scale_x_datetime(
            date_breaks=date_breaks_selection,
            date_labels=date_labels_selection,
        )
        + labs(title="Memory in use (actual)", x="Date/Time", y="gb")
    )


def plot_mem_used_matplotlib(data: pl.DataFrame):
    mem_used = _to_plot_df(data, "memory_used_gb")
    pdf = _to_pandas_for_timeplot(mem_used, ["datetime", "value"])

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


def plot_mem_used_seaborn(data: pl.DataFrame):
    mem_used = _to_plot_df(data, "memory_used_gb")
    pdf = _to_pandas_for_timeplot(mem_used, ["datetime", "value"])

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


def direct_publish(
    obj,
    *,
    label: str,
    section: str,
    kind: KindMode,
    view_type: Literal["table", "plot"],
    host: str,
    port: int,
) -> None:
    if kind == "infer":
        publish_artifact(obj, label=label, section=section, host=host, port=port)
        return

    if view_type == "table":
        publish_view(obj, label=label, section=section, host=host, port=port)
        return

    plot_launch(obj, label=label, section=section, host=host, port=port)


def decorate_publisher(
    fn: Callable,
    *,
    label: str,
    section: str,
    kind: KindMode,
    view_type: Literal["table", "plot"],
    host: str,
    port: int,
) -> Callable:
    if kind == "infer":
        return plotsrv(label=label, section=section, host=host, port=port)(fn)

    if view_type == "table":
        return table(label=label, section=section, host=host, port=port)(fn)

    return plot(label=label, section=section, host=host, port=port)(fn)


def publish_tables(
    row: pl.DataFrame,
    *,
    config: ResourceMonitorConfig,
    decorated_publishers: dict[str, Callable] | None = None,
) -> None:
    pandas_row = system_snapshot_pandas(row)

    if config.publish_style == "decorator":
        if decorated_publishers is None:
            raise RuntimeError(
                "decorated_publishers must be supplied in decorator mode"
            )

        decorated_publishers["polars_table"](row)
        decorated_publishers["pandas_table"](pandas_row)
        return

    direct_publish(
        row,
        label="Tabular view",
        section="polars",
        kind=config.kind,
        view_type="table",
        host=config.host,
        port=config.port,
    )
    direct_publish(
        pandas_row,
        label="Tabular view",
        section="pandas",
        kind=config.kind,
        view_type="table",
        host=config.host,
        port=config.port,
    )


def publish_plot(
    obj,
    *,
    label: str,
    section: str,
    config: ResourceMonitorConfig,
    decorated_publishers: dict[str, Callable] | None = None,
    publisher_key: str,
) -> None:
    if config.publish_style == "decorator":
        if decorated_publishers is None:
            raise RuntimeError(
                "decorated_publishers must be supplied in decorator mode"
            )

        decorated_publishers[publisher_key](obj)
        return

    direct_publish(
        obj,
        label=label,
        section=section,
        kind=config.kind,
        view_type="plot",
        host=config.host,
        port=config.port,
    )


def identity(obj):
    return obj


def make_decorated_publishers(config: ResourceMonitorConfig) -> dict[str, Callable]:
    return {
        "polars_table": decorate_publisher(
            identity,
            label="Tabular view",
            section="polars",
            kind=config.kind,
            view_type="table",
            host=config.host,
            port=config.port,
        ),
        "pandas_table": decorate_publisher(
            identity,
            label="Tabular view",
            section="pandas",
            kind=config.kind,
            view_type="table",
            host=config.host,
            port=config.port,
        ),
        "cpu_plotnine": decorate_publisher(
            identity,
            label="CPU%",
            section="plotnine",
            kind=config.kind,
            view_type="plot",
            host=config.host,
            port=config.port,
        ),
        "cpu_matplotlib": decorate_publisher(
            identity,
            label="CPU%",
            section="matplotlib",
            kind=config.kind,
            view_type="plot",
            host=config.host,
            port=config.port,
        ),
        "cpu_seaborn": decorate_publisher(
            identity,
            label="CPU%",
            section="seaborn",
            kind=config.kind,
            view_type="plot",
            host=config.host,
            port=config.port,
        ),
        "mem_plotnine": decorate_publisher(
            identity,
            label="MEM-USED",
            section="plotnine",
            kind=config.kind,
            view_type="plot",
            host=config.host,
            port=config.port,
        ),
        "mem_matplotlib": decorate_publisher(
            identity,
            label="MEM-USED",
            section="matplotlib",
            kind=config.kind,
            view_type="plot",
            host=config.host,
            port=config.port,
        ),
        "mem_seaborn": decorate_publisher(
            identity,
            label="MEM-USED",
            section="seaborn",
            kind=config.kind,
            view_type="plot",
            host=config.host,
            port=config.port,
        ),
    }


def publish_all_plots(
    running_data: pl.DataFrame,
    *,
    config: ResourceMonitorConfig,
    decorated_publishers: dict[str, Callable] | None = None,
) -> None:
    if "plotnine" in config.plot_libs:
        publish_plot(
            plot_cpu_percent_plotnine(running_data),
            label="CPU%",
            section="plotnine",
            config=config,
            decorated_publishers=decorated_publishers,
            publisher_key="cpu_plotnine",
        )
        publish_plot(
            plot_mem_used_plotnine(running_data),
            label="MEM-USED",
            section="plotnine",
            config=config,
            decorated_publishers=decorated_publishers,
            publisher_key="mem_plotnine",
        )

    if "matplotlib" in config.plot_libs:
        publish_plot(
            plot_cpu_percent_matplotlib(running_data),
            label="CPU%",
            section="matplotlib",
            config=config,
            decorated_publishers=decorated_publishers,
            publisher_key="cpu_matplotlib",
        )
        publish_plot(
            plot_mem_used_matplotlib(running_data),
            label="MEM-USED",
            section="matplotlib",
            config=config,
            decorated_publishers=decorated_publishers,
            publisher_key="mem_matplotlib",
        )

    if "seaborn" in config.plot_libs:
        publish_plot(
            plot_cpu_percent_seaborn(running_data),
            label="CPU%",
            section="seaborn",
            config=config,
            decorated_publishers=decorated_publishers,
            publisher_key="cpu_seaborn",
        )
        publish_plot(
            plot_mem_used_seaborn(running_data),
            label="MEM-USED",
            section="seaborn",
            config=config,
            decorated_publishers=decorated_publishers,
            publisher_key="mem_seaborn",
        )


def parse_plot_libs(value: str) -> tuple[PlotLib, ...]:
    if value == "all":
        return ("plotnine", "matplotlib", "seaborn")

    allowed = {"plotnine", "matplotlib", "seaborn"}
    selected = tuple(part.strip() for part in value.split(",") if part.strip())

    unknown = set(selected) - allowed
    if unknown:
        unknown_text = ", ".join(sorted(unknown))
        raise argparse.ArgumentTypeError(f"Unknown plot lib(s): {unknown_text}")

    if not selected:
        raise argparse.ArgumentTypeError("At least one plot lib must be selected")

    return selected  # type: ignore[return-value]


def parse_args() -> ResourceMonitorConfig:
    parser = argparse.ArgumentParser(
        description="Publish live system resource examples to plotsrv."
    )

    parser.add_argument(
        "--publish-style",
        choices=["decorator", "direct"],
        default="decorator",
        help="Use plotsrv decorators, or call publish functions directly.",
    )
    parser.add_argument(
        "--kind",
        choices=["explicit", "infer"],
        default="infer",
        help="Use explicit table/plot publishing, or let plotsrv infer the view kind.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="plotsrv host.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="plotsrv port.",
    )
    parser.add_argument(
        "--fetch-interval",
        type=float,
        default=10.0,
        help="How often to fetch system resource usage.",
    )
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=1.0,
        help="Interval passed to psutil.cpu_percent(interval=...).",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of publish cycles. Omit for endless running.",
    )
    parser.add_argument(
        "--plot-libs",
        type=parse_plot_libs,
        default=("plotnine", "matplotlib", "seaborn"),
        help="Comma-separated plot libraries to publish, or 'all'. Example: matplotlib,plotnine",
    )

    args = parser.parse_args()

    return ResourceMonitorConfig(
        publish_style=args.publish_style,
        kind=args.kind,
        host=args.host,
        port=args.port,
        fetch_interval=args.fetch_interval,
        sample_interval=args.sample_interval,
        max_iterations=args.max_iterations,
        plot_libs=args.plot_libs,
    )


def main() -> None:
    config = parse_args()

    decorated_publishers = (
        make_decorated_publishers(config)
        if config.publish_style == "decorator"
        else None
    )

    running_data = empty_running_data()

    iteration = 0
    while config.max_iterations is None or iteration < config.max_iterations:
        row = system_snapshot_polars(interval=config.sample_interval)
        running_data = running_data.vstack(row)

        publish_tables(
            row,
            config=config,
            decorated_publishers=decorated_publishers,
        )
        publish_all_plots(
            running_data,
            config=config,
            decorated_publishers=decorated_publishers,
        )

        iteration += 1
        time.sleep(config.fetch_interval)


if __name__ == "__main__":
    main()
