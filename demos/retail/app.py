"""Publish one coherent, synthetic retail analysis to an existing plotsrv receiver."""

import argparse
import os
import sys
from collections import defaultdict
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
            "figure.facecolor": "white",
            "axes.facecolor": "white",
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
        ax.set(title="Monthly sales and gross profit", ylabel="Monthly total")
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
        ax.set_title("Monthly sales by category", pad=16)
        fig.colorbar(image, ax=ax, shrink=0.8, label="Booked sales (£)")
        yield "retail:categories", "Sales by category", fig

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
            title="Return rate by product",
            xlabel="Units ordered",
            ylabel="Orders returned (%)",
        )
        ax.margins(x=0.3, y=0.25)
        ax.grid(alpha=0.15)
        yield "retail:returns", "Product return rates", fig

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
        ax.set(title="Fulfilment time by region", ylabel="Fulfilment time (days)")
        ax.grid(axis="y", alpha=0.15)
        ax.legend(frameon=False)
        yield "retail:fulfillment", "Regional fulfilment times", fig


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
            f"| {name} | £{revenue:,.2f} |"
        )
    revision = rows[0]["report_revision"] if rows else 3
    period = {1: "December 2025", 2: "March 2026", 3: "June 2026"}[revision]
    median = statistics.median(r["fulfillment_days"] for r in rows)
    return f"""# Northstar Outdoors
## Trading review · through {period}

**Prepared for the trading and operations team**

> Build equipment people trust, and an experience that brings them back.

### Executive summary

The reporting window contains **{len(rows):,} orders**, **£{sales:,.2f} in booked sales**
and **£{profit:,.2f} in gross profit before returns**. The range spans everyday
accessories, technical clothing and equipment for longer trips. These categories
serve different customer needs, so the mix matters as much as the headline total.

### Category scorecard

| Category | Sales (£) |
| --- | ---: |
{chr(10).join(categories)}

Booked sales are before returns. Use the orders register for category-level
order counts, gross profit and returns.

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

The dataset summary deliberately expects a refresh every five
minutes, warn after ten, and become overdue after fifteen. It is left unchanged
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


def dataset_summary(rows):
    """Reconcile the register without introducing a second source of figures."""
    from statistics import median

    def totals(group):
        sales = sum(r["order_value_gbp"] for r in group)
        profit = sum(r["margin_gbp"] for r in group)
        returned = sum(r["returned"] for r in group)
        return {
            "orders": len(group),
            "units": sum(r["quantity"] for r in group),
            "booked_sales_gbp": round(sales, 2),
            "gross_profit_before_returns_gbp": round(profit, 2),
            "gross_margin_pct": round(100 * profit / sales, 2) if sales else None,
            "average_order_value_gbp": round(sales / len(group), 2) if group else None,
            "returned_orders": returned,
            "returned_order_pct": round(100 * returned / len(group), 2)
            if group
            else None,
            "median_fulfillment_days": median(r["fulfillment_days"] for r in group)
            if group
            else None,
            "within_3_day_target_pct": round(
                100 * sum(r["fulfillment_days"] <= 3 for r in group) / len(group), 2
            )
            if group
            else None,
        }

    fields = list(rows[0]) if rows else []
    dates = [r["order_date"] for r in rows]
    return {
        "source": "Northstar Outdoors order register · deterministic fictional data",
        "reporting_period": {
            "from": min(dates) if dates else None,
            "through": max(dates) if dates else None,
            "months": len({d[:7] for d in dates}),
        },
        "coverage": {
            "rows": len(rows),
            "fields": len(fields),
            "field_names": {
                "order": "order_date, order_id, product, category, region, quantity, size",
                "financial": "unit_price_gbp, order_value_gbp, margin_gbp, unit_cost_gbp, discount_pct",
                "service": "fulfillment_days, returned, return_reason",
                "report": "report_revision",
            },
            "products": len({r["product"] for r in rows}),
            "regions": len({r["region"] for r in rows}),
        },
        "totals": totals(rows),
        "by_category": {
            name: {
                k: v
                for k, v in totals([r for r in rows if r["category"] == name]).items()
                if k
                in {"orders", "booked_sales_gbp", "gross_profit_before_returns_gbp"}
            }
            for name in sorted({r["category"] for r in rows})
        },
        "by_region": {
            name: {
                k: v
                for k, v in totals([r for r in rows if r["region"] == name]).items()
                if k in {"orders", "booked_sales_gbp", "median_fulfillment_days"}
            }
            for name in sorted({r["region"] for r in rows})
        },
        "returns": {
            "by_reason": {
                reason: sum(r["return_reason"] == reason for r in rows)
                for reason in sorted(
                    {r["return_reason"] for r in rows if r["return_reason"]}
                )
            }
        },
        "data_quality": {
            "duplicate_order_ids": len(rows) - len({r["order_id"] for r in rows}),
            "missing_values_by_field": {
                field: sum(r.get(field) is None for r in rows)
                for field in fields
                if any(r.get(field) is None for r in rows)
            },
            "return_reason_missing_on_returned_orders": sum(
                r["returned"] and not r["return_reason"] for r in rows
            ),
            "financial_reconciliation_errors": sum(
                abs(
                    r["order_value_gbp"]
                    - round(
                        r["unit_price_gbp"]
                        * r["quantity"]
                        * (1 - r["discount_pct"] / 100),
                        2,
                    )
                )
                > 0.005
                or abs(
                    r["margin_gbp"]
                    - round(
                        r["order_value_gbp"] - r["unit_cost_gbp"] * r["quantity"], 2
                    )
                )
                > 0.005
                for r in rows
            ),
            "nullable_field_note": "return_reason is intentionally null for orders that were not returned",
        },
        "definitions": {
            "booked_sales_gbp": "Quantity × list price, less discount; before refunds",
            "gross_profit_before_returns_gbp": "Booked sales less product cost; excludes refunds, shipping, overheads and tax",
            "returned_order_pct": "Returned orders / all orders × 100; not a unit-based return rate",
            "fulfillment_days": "Elapsed days from order placement to fulfilment",
            "within_3_day_target_pct": "Orders fulfilled in at most three days / all orders × 100",
            "report_revision": "Illustrative reporting edition 1, 2 or 3; snapshot timestamps are actual capture times",
        },
    }


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
            dataset_summary(rows),
            "json",
        )


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
