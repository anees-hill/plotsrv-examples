"""Repeatable tables, both plot backends, text and HTML for an existing receiver."""

import argparse
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import polars as pl
from plotnine import aes, geom_point, ggplot
import plotsrv as ps

from plotsrv_examples.smoke_inputs import table_rows


def publish(host, port, *, version=1, style="direct", async_=False):
    frame = pd.DataFrame(table_rows(1200, version))
    options = dict(host=host, port=port, async_=async_, section="Smoke", update_limit_s=0)
    for name, obj in (("pandas", frame), ("polars", pl.from_pandas(frame))):
        if style == "decorator":
            @ps.view(view_id="smoke-" + name, **options)
            def produce():
                return obj
            assert produce() is obj
        else:
            ps.publish_view(obj, view_id="smoke-" + name, **options)
    fig, ax = plt.subplots()
    try:
        ax.plot([1, 2, 3], [version, version + 2, version + 1])
        ax.set_title(f"Smoke version {version}")
        ps.publish_view(fig, view_id="smoke-matplotlib", **options)
        ps.publish_view(ggplot(frame.head(30), aes("id", "amount")) + geom_point(),
                        view_id="smoke-plotnine", **options)
        ps.publish_view(f"smoke-version-{version}\n" + "bounded text " * 50,
                        view_id="smoke-text", **options)
        ps.publish_view('<h1>html-smoke</h1><script>window.parent.smokeEscape=1</script>',
                        artifact_kind="html", view_id="smoke-html", **options)
        return {"version": version, "rows": len(frame), "style": style, "async": async_}
    finally:
        # Draining is a process boundary. The scenario separately checks receipt.
        drained = ps.flush_views(timeout=10)
        plt.close(fig)
        print(json.dumps({"drained": drained}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8101)
    parser.add_argument("--version", type=int, choices=range(1, 10), default=1)
    parser.add_argument("--style", choices=("direct", "decorator"), default="direct")
    parser.add_argument("--async", dest="async_", action="store_true")
    args = parser.parse_args()
    print(json.dumps(publish(**vars(args))), flush=True)
