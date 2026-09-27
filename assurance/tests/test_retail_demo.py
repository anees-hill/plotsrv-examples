"""The retail example must keep its discoverable patterns reproducible."""

import importlib.util
from pathlib import Path


def _orders():
    path = Path(__file__).resolve().parents[2] / "demos/retail/generate_data.py"
    spec = importlib.util.spec_from_file_location("retail_data", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.make_orders()


def test_retail_data_is_reproducible_and_has_explorable_patterns():
    rows = _orders()
    assert rows == _orders()
    assert len(rows) == 1680
    assert len({row["order_id"] for row in rows}) == len(rows)
    shells = [row for row in rows if row["product"] == "Summit Rain Shell"]
    others = [row for row in rows if row["product"] != "Summit Rain Shell"]
    assert sum(row["returned"] for row in shells) / len(shells) > 3 * (
        sum(row["returned"] for row in others) / len(others)
    )
    west = [row["fulfillment_days"] for row in rows if row["region"] == "West"]
    other = [row["fulfillment_days"] for row in rows if row["region"] != "West"]
    assert sum(west) / len(west) > sum(other) / len(other) + 1


def test_return_rate_counts_orders_independently_of_quantity(monkeypatch):
    import sys
    directory = Path(__file__).resolve().parents[2] / "demos/retail"
    monkeypatch.syspath_prepend(str(directory))
    spec = importlib.util.spec_from_file_location("retail_app", directory / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = _orders()[:2]
    for row, quantity, returned in zip(rows, [9, 1], [True, False]):
        row.update(product="Test product", quantity=quantity, returned=returned)
    _, _, products, _ = module.analyse(rows)
    units, returns, orders = products["Test product"]
    assert units == 10
    assert 100 * returns / orders == 50
