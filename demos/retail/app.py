"""Publish one coherent, synthetic retail analysis to an existing plotsrv receiver."""

import argparse
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generate_data import make_orders
from publishing import Publisher


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


GREEN, BLUE, AMBER = "#23634f", "#397e97", "#c98032"


def make_plots(rows):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.ticker import FuncFormatter

    monthly, categories, products, regions = analyse(rows)
    months = sorted(monthly)
    money = FuncFormatter(lambda x, _: f"£{x / 1000:.0f}k")
    with plt.rc_context(
        {
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titleweight": "bold",
            "figure.facecolor": "#f7faf8",
            "axes.facecolor": "#f7faf8",
            "text.color": "#234d40",
            "axes.labelcolor": "#234d40",
        }
    ):
        fig, ax = plt.subplots(figsize=(9, 4.8), layout="constrained")
        dates = [date.fromisoformat(m + "-01") for m in months]
        profits = [
            sum(r["margin_gbp"] for r in rows if r["order_date"].startswith(m))
            for m in months
        ]
        ax.fill_between(dates, [monthly[m] for m in months], alpha=0.12, color=GREEN)
        ax.plot(
            dates,
            [monthly[m] for m in months],
            color=GREEN,
            lw=2.5,
            marker="o",
            ms=4,
            label="Booked sales",
        )
        ax.plot(
            dates,
            profits,
            color=AMBER,
            lw=2.5,
            marker="o",
            ms=4,
            label="Gross profit before returns",
        )
        ax.set(title="A year on the trail", ylabel="Monthly total")
        ax.yaxis.set_major_formatter(money)
        ax.grid(axis="y", alpha=0.15)
        ax.legend(frameon=False)
        fig.autofmt_xdate()
        yield "retail:sales", "Sales & gross profit", fig

        fig, ax = plt.subplots(figsize=(9, 4.2), layout="constrained")
        names = sorted(categories)
        values = np.array(
            [
                [
                    sum(
                        r["order_value_gbp"]
                        for r in rows
                        if r["category"] == c and r["order_date"].startswith(m)
                    )
                    for m in months
                ]
                for c in names
            ]
        )
        image = ax.imshow(values, aspect="auto", cmap="YlGnBu")
        ax.set_yticks(range(len(names)), labels=names)
        ax.set_xticks(
            range(len(months)),
            labels=[date.fromisoformat(m + "-01").strftime("%b %y") for m in months],
            rotation=60,
            ha="right",
        )
        ax.set_title("Every season has its essentials", pad=16)
        fig.colorbar(image, ax=ax, shrink=0.8, label="Booked sales (£)")
        yield "retail:categories", "Seasonal demand", fig

        fig, ax = plt.subplots(figsize=(9, 5.2), layout="constrained")
        colours = dict(zip(names, [GREEN, BLUE, AMBER, "#876496"]))
        for index, (name, (units, returns, orders)) in enumerate(
            sorted(products.items())
        ):
            category = next(r["category"] for r in rows if r["product"] == name)
            x, y = units, 100 * returns / max(orders, 1)
            ax.scatter(
                x,
                y,
                s=160,
                color=colours[category],
                alpha=0.85,
                edgecolor="white",
                linewidth=1.5,
            )
            ax.annotate(
                name,
                (x, y),
                xytext=(6, 8 if index % 2 else -13),
                textcoords="offset points",
                fontsize=8,
            )
        ax.set(
            title="Popular does not always mean trouble-free",
            xlabel="Units ordered",
            ylabel="Orders returned (%)",
        )
        ax.margins(x=0.3, y=0.25)
        ax.grid(alpha=0.15)
        yield "retail:returns", "Popularity & returns", fig

        fig, ax = plt.subplots(figsize=(9, 4.5), layout="constrained")
        names = sorted(regions)
        boxes = ax.boxplot(
            [regions[r] for r in names],
            tick_labels=names,
            patch_artist=True,
            medianprops={"color": "#234d40", "linewidth": 2},
            flierprops={"marker": ".", "markersize": 3, "alpha": 0.4},
        )
        for patch, colour in zip(boxes["boxes"], [GREEN, BLUE, GREEN, AMBER]):
            patch.set_facecolor(colour)
            patch.set_alpha(0.45)
        ax.axhline(3, color=AMBER, linestyle="--", lw=1, label="3-day service target")
        ax.set(title="The journey after checkout", ylabel="Fulfilment time (days)")
        ax.grid(axis="y", alpha=0.15)
        ax.legend(frameon=False)
        yield "retail:fulfillment", "Delivery experience", fig


def trading_report(rows):
    import statistics

    sales = sum(r["order_value_gbp"] for r in rows)
    profit = sum(r["margin_gbp"] for r in rows)
    returns = sum(r["returned"] for r in rows)
    categories = []
    for name in sorted({r["category"] for r in rows}):
        group = [r for r in rows if r["category"] == name]
        revenue = sum(r["order_value_gbp"] for r in group)
        categories.append(
            f"| {name} | {len(group):,} | £{revenue:,.2f} | £{sum(r['margin_gbp'] for r in group):,.2f} | {100 * sum(r['returned'] for r in group) / len(group):.1f}% |"
        )
    revision = rows[0]["report_revision"] if rows else 3
    period = {1: "December 2025", 2: "March 2026", 3: "June 2026"}[revision]
    median = statistics.median(r["fulfillment_days"] for r in rows)
    return f"""# Northstar Outdoors
## Trading review · through {period}

**Prepared for the trading and operations team** · Illustrative report edition {revision}/3

> Build equipment people trust, and an experience that brings them back.

### Executive summary

The reporting window contains **{len(rows):,} orders**, **£{sales:,.2f} in booked sales**
and **£{profit:,.2f} in gross profit before returns**. The range spans everyday
accessories, technical clothing and equipment for longer trips. These categories
serve different customer needs, so the mix matters as much as the headline total.

### Category scorecard

| Category | Orders | Booked sales | Gross profit¹ | Returned orders |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(categories)}

¹ Revenue less product cost; before refunds, shipping, overheads and tax.

### Commercial observations

Demand changes with the season. Buyers preparing for summer trips do not build the
same basket as winter gift shoppers. Merchandising should consider **availability,
product mix and contribution**, rather than order count alone.

The September campaign offered a 20% price reduction. Product costs did not fall
with the selling price. Review both the sales and profit series before deciding
whether a similar campaign should be repeated.

### Customer experience

**{returns:,} orders were returned**. Product and size belong in the same conversation:
a popular line can perform well commercially while still creating avoidable work
for the support team. Review reasons remain attached to individual orders.

Median fulfilment was **{median:.1f} days**, against a three-day service target.
Regional distributions show the range of experiences behind the average. The
operations team should consider when a delay occurred as well as where it occurred.

### Priorities for the next review

1. Review the balance of discounted volume and gross profit.
2. Follow up product feedback with the buying team.
3. Check that service improvements persist beyond the next reporting period.

#### Working definitions

- **Booked sales:** quantity × list price, less promotional discount.
- **Gross profit:** booked sales less quantity × unit cost.
- **Return rate:** returned orders ÷ orders; not returned units ÷ units.
- **Reporting periods:** complete months, beginning January 2025.

### Notes on this report

All customers, transactions and report editions are **fictional, deterministic
examples**. The history selector contains three illustrative editions; snapshot
capture timestamps are genuine and are not the dates of the fictional reports.

The orders and trading-report views deliberately expect a refresh every five
minutes, warn after ten, and become overdue after fifteen. They are left unchanged
to demonstrate freshness. An overdue badge here illustrates the feature; it does
not indicate a broken demo server.
"""


HISTORY_VIEWS = (
    "retail:orders",
    "retail:sales",
    "retail:categories",
    "retail:returns",
    "retail:fulfillment",
    "retail:guide",
)


def content(rows):
    import pandas as pd

    yield "retail:orders", "Explore orders", pd.DataFrame(rows), "table"
    for view, label, figure in make_plots(rows):
        yield view, label, figure, "plot"
    yield "retail:guide", "Trading review", trading_report(rows), "markdown"


def publish(rows):
    """Explicit republish of current content; unchanged restored views are reused."""
    with Publisher("retail").locked() as publisher:
        publisher.seeded(
            HISTORY_VIEWS,
            lambda revision: content(make_orders(len(rows), revision=revision)),
        )
        publisher.current(lambda _: content(rows))
        publisher.publish(
            "retail:summary",
            "Dataset summary",
            {
                "orders": len(rows),
                "period": "2025-01 to 2026-06",
                "categories": dict(Counter(row["category"] for row in rows)),
                "source": "deterministic synthetic data",
                "gross_profit_basis": "before returns and overheads",
            },
            "json",
        )
        publisher.sources()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1680)
    args = parser.parse_args()
    if not 1 <= args.count <= 1680:
        parser.error("--count must be between 1 and 1680")
    os.environ.setdefault(
        "PLOTSRV_CONFIG", str(Path(__file__).with_name("plotsrv.yml"))
    )
    os.environ["PLOTSRV_DEBUG"] = "1"
    publish(make_orders(args.count))
