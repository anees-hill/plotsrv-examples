"""Reproducible fictional outdoor-shop orders; no external data or services."""

import random
from datetime import date, timedelta

PRODUCTS = (
    ("Ridge 35 Backpack", "Packs", 84, 0.38),
    ("Trail 18 Daypack", "Packs", 48, 0.41),
    ("Summit Rain Shell", "Clothing", 115, 0.24),
    ("Merino Base Layer", "Clothing", 59, 0.43),
    ("Camp Lantern", "Camp", 32, 0.48),
    ("Alpine Tent", "Camp", 220, 0.31),
    ("Water Filter", "Essentials", 27, 0.44),
    ("Steel Bottle", "Essentials", 19, 0.47),
)
REGIONS = ("North", "Midlands", "South", "West")


def make_orders(count=1680, seed=20260927, revision=3):
    rng = random.Random(seed)
    first_day = date(2025, 1, 1)
    last_day = date(2026, 6, 30)
    days = (last_day - first_day).days + 1
    # September has more orders, but the discount comes out of gross profit.
    calendar = [first_day + timedelta(days=i) for i in range(days)]
    date_weights = [1.8 if d.year == 2025 and d.month == 9 else 1 for d in calendar]
    dates = sorted(rng.choices(calendar, weights=date_weights, k=count))
    if dates:
        dates[0] = first_day
        if len(dates) > 1:
            dates[-1] = last_day
    rows = []
    for n in range(count):
        day = dates[n]
        month = day.month
        weights = [2.0, 2.0, 1.3, 1.7, 1.3, 0.9, 1.4, 1.7]
        if month in (5, 6, 7, 8):
            weights[0] *= 1.7
            weights[5] *= 2.2
        if month in (11, 12):
            weights[3] *= 2
            weights[4] *= 2.2
        index = rng.choices(range(len(PRODUCTS)), weights=weights)[0]
        product, category, unit_price, margin = PRODUCTS[index]
        region = rng.choice(REGIONS)
        quantity = rng.choices((1, 2, 3), weights=(8, 2, 0.25))[0]
        if n in (89, 420, 1013, 1350):
            quantity = 9
        promoted = date(2025, 9, 1) <= day < date(2025, 10, 1)
        discount = 0.20 if promoted else 0
        paid = round(unit_price * quantity * (1 - discount), 2)
        unit_cost = round(unit_price * (1 - margin), 2)
        size = (
            rng.choice(("S", "M", "L", "XL")) if category == "Clothing" else "One size"
        )
        disrupted = region == "West" and date(2025, 3, 1) <= day < date(2025, 7, 1)
        fulfillment = round(
            max(0.8, rng.gauss(2.3 + (5.5 if disrupted else 0), 0.7)), 1
        )
        return_chance = (
            (0.7 if size == "M" else 0.10) if product == "Summit Rain Shell" else 0.035
        )
        returned = rng.random() < return_chance
        rows.append(
            {
                "order_date": day.isoformat(),
                "order_id": f"ORD-{18001 + n}",
                "product": product,
                "category": category,
                "region": region,
                "quantity": quantity,
                "unit_price_gbp": unit_price,
                "order_value_gbp": paid,
                "margin_gbp": round(paid - unit_cost * quantity, 2),
                "unit_cost_gbp": unit_cost,
                "discount_pct": int(discount * 100),
                "size": size,
                "fulfillment_days": fulfillment,
                "returned": returned,
                "return_reason": (
                    "fit"
                    if product == "Summit Rain Shell" and size == "M"
                    else rng.choice(("fit", "changed mind", "damaged"))
                )
                if returned
                else None,
                "report_revision": revision,
            }
        )
    # Revisions use the same stable source orders and successive complete quarters.
    cutoff = {1: "2025-12-31", 2: "2026-03-31", 3: "2026-06-30"}[revision]
    return [row for row in rows if row["order_date"] <= cutoff]


if __name__ == "__main__":
    import csv
    import sys

    writer = csv.DictWriter(sys.stdout, fieldnames=list(make_orders(1)[0]))
    writer.writeheader()
    writer.writerows(make_orders())
