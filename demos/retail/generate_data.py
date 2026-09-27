"""Reproducible fictional outdoor-shop orders; no external data or services."""

from datetime import date, timedelta
import random


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


def make_orders(count=1680, seed=20260927):
    rng = random.Random(seed)
    first_day = date(2025, 1, 1)
    rows = []
    for n in range(count):
        day = first_day + timedelta(days=(n * 540) // count)
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
        paid = round(unit_price * quantity * (0.8 if promoted else 1), 2)
        fulfillment = round(max(0.8, rng.gauss(2.3 + (1.8 if region == "West" else 0), 0.7)), 1)
        return_chance = 0.24 if product == "Summit Rain Shell" else 0.035
        returned = rng.random() < return_chance
        rows.append({
            "order_date": day.isoformat(), "order_id": f"ORD-{18001+n}",
            "product": product, "category": category, "region": region,
            "quantity": quantity, "unit_price_gbp": unit_price,
            "order_value_gbp": paid, "margin_gbp": round(paid * margin, 2),
            "fulfillment_days": fulfillment, "returned": returned,
            "return_reason": rng.choice(("fit", "changed mind", "damaged")) if returned else None,
        })
    return rows


if __name__ == "__main__":
    import csv
    import sys

    writer = csv.DictWriter(sys.stdout, fieldnames=list(make_orders(1)[0]))
    writer.writeheader()
    writer.writerows(make_orders())
