"""Small deterministic order import; application logic has no plotsrv dependency."""


def order_fixture():
    """Extract one fixed synthetic batch: 48 orders, six cancelled."""
    return [
        {
            "order_id": i + 1,
            "region": ("north", "south", "west")[i % 3],
            "quantity": 1 + i % 4,
            "unit_cents": 500 + 25 * (i % 5),
            "discount_cents": 50 if i % 3 == 0 else 0,
            "status": "cancelled" if i % 8 == 0 else "paid",
        }
        for i in range(48)
    ]


def transform_orders(orders):
    """Validate paid orders and build detached columns without changing input.

    Bad paid-order amounts raise ValueError; callers decide how to handle it.
    Cancelled orders do not enter the sales ledger.
    """
    columns = {name: [] for name in
               ("order_id", "region", "gross_cents", "discount_cents", "net_cents")}
    for order in orders:
        if order["status"] == "cancelled":
            continue
        if order["status"] != "paid":
            raise ValueError("unknown order status")
        quantity, unit, discount = (order[key] for key in
                                    ("quantity", "unit_cents", "discount_cents"))
        if (any(type(value) is not int for value in (quantity, unit, discount))
                or quantity <= 0 or unit < 0 or not 0 <= discount <= quantity * unit):
            raise ValueError("invalid paid-order amounts")
        gross = quantity * unit
        for key, value in zip(columns, (order["order_id"], order["region"], gross,
                                        discount, gross - discount)):
            columns[key].append(value)
    return columns


def regional_totals(columns):
    """Load an exact in-memory sales ledger from every transformed order.

    These are explicit domain calculations, independent of captured samples.
    Amounts are integer cents; no floating-point currency rounding is involved.
    """
    regions = {}
    for region, gross, discount, net in zip(
        columns["region"], columns["gross_cents"], columns["discount_cents"],
        columns["net_cents"], strict=True,
    ):
        totals = regions.setdefault(region, {
            "orders": 0, "gross_cents": 0, "discount_cents": 0, "net_cents": 0,
        })
        totals["orders"] += 1
        totals["gross_cents"] += gross
        totals["discount_cents"] += discount
        totals["net_cents"] += net
    return {
        "scope": "all transformed paid orders in this synthetic batch",
        "currency_unit": "cents",
        "paid_orders": len(columns["order_id"]),
        "net_cents": sum(item["net_cents"] for item in regions.values()),
        "regions": regions,
    }
