"""Publish one coherent, synthetic retail analysis to an existing plotsrv receiver."""

import argparse
from collections import Counter, defaultdict
from datetime import date
import os
from pathlib import Path

from generate_data import make_orders


def analyse(rows):
    by_month = defaultdict(float)
    by_category = defaultdict(float)
    by_product = defaultdict(lambda: [0, 0, 0])
    by_region = defaultdict(list)
    for row in rows:
        by_month[row["order_date"][:7]] += row["order_value_gbp"]
        by_category[row["category"]] += row["order_value_gbp"]
        by_product[row["product"]][0] += row["quantity"]
        by_product[row["product"]][1] += int(row["returned"])
        by_product[row["product"]][2] += 1
        by_region[row["region"]].append(row["fulfillment_days"])
    return by_month, by_category, by_product, by_region


def make_plots(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    by_month, by_category, by_product, by_region = analyse(rows)
    figures = []
    green = "#287a53"
    fig, ax = plt.subplots(figsize=(8.5, 3.6))
    months = sorted(by_month)
    ax.plot([date.fromisoformat(m + "-01") for m in months],
            [by_month[m] for m in months], color=green, linewidth=2.3)
    ax.set(title="Sales through time", ylabel="Revenue (£)")
    ax.grid(axis="y", alpha=0.2)
    fig.autofmt_xdate()
    fig.tight_layout()
    figures.append(("retail:sales", "Sales through time", fig))

    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    categories = sorted(by_category, key=by_category.get)
    ax.barh(categories, [by_category[c] for c in categories], color=green)
    ax.set(title="Revenue by category", xlabel="Revenue (£)")
    fig.tight_layout()
    figures.append(("retail:categories", "Category performance", fig))

    fig, ax = plt.subplots(figsize=(8, 4.4))
    for name, (units, returns, orders) in by_product.items():
        ax.scatter(units, 100 * returns / max(orders, 1), s=65, color=green)
        ax.annotate(name, (units, 100 * returns / max(orders, 1)),
                    xytext=(5, 4), textcoords="offset points", fontsize=7)
    ax.set(title="Popular products and returns", xlabel="Units sold", ylabel="Orders returned (%)")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    figures.append(("retail:returns", "Sales versus return rate", fig))

    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    regions = sorted(by_region)
    ax.boxplot([by_region[r] for r in regions], tick_labels=regions)
    ax.set(title="Fulfillment time by region", ylabel="Days")
    fig.tight_layout()
    figures.append(("retail:fulfillment", "Fulfillment by region", fig))
    return figures


def publish(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    import plotsrv as ps

    options = dict(launch_server=False, async_=False, section="Retail exploration")
    ps.publish_view(pd.DataFrame(rows), view_id="retail:orders", label="Explore orders", **options)
    for view_id, label, fig in make_plots(rows):
        try:
            ps.publish_view(fig, view_id=view_id, label=label, **options)
        finally:
            plt.close(fig)
    notes = ("# Northstar Outdoors\n\n"
             "A fictional retailer with 18 months of synthetic orders. Start with the orders "
             "table: sort by value, region or fulfillment time, then compare the plots. "
             "The figures are generated locally; no real customer data is used.\n")
    ps.publish_view(notes, view_id="retail:guide", label="About this analysis",
                    kind="artifact", artifact_kind="markdown", **options)
    ps.publish_view({"orders": len(rows), "period": "2025-01 to 2026-06",
                     "categories": dict(Counter(row["category"] for row in rows)),
                     "source": "deterministic synthetic data"},
                    view_id="retail:summary", label="Dataset summary", **options)
    if not ps.flush_views(timeout=10):
        raise RuntimeError("plotsrv publication did not drain")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1680)
    args = parser.parse_args()
    if not 1 <= args.count <= 1680:
        parser.error("--count must be between 1 and 1680")
    os.environ.setdefault("PLOTSRV_CONFIG", str(Path(__file__).with_name("plotsrv.yml")))
    publish(make_orders(args.count))
