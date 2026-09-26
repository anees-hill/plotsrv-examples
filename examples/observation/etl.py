"""Observe a finite order import; use an already running receiver."""

import argparse
import json

import plotsrv as ps

from plotsrv_examples.etl import order_fixture, regional_totals, transform_orders


def publish(host, port, *, view_prefix="etl"):
    # Decoration prepares observation outside the application function call.
    # This synchronous function still returns its normal columns. Delivery is
    # always background; observe=True cannot be combined with async_=False.
    @ps.view(observe=True, host=host, port=port, view_id=f"{view_prefix}:orders",
             label="Paid orders — bounded evidence", section="Observation")
    def transform(orders):
        return transform_orders(orders)

    source = order_fixture()
    columns = transform(source)
    ledger = regional_totals(columns)
    # Scalar values are computed by the application over this whole tiny batch.
    # Their supplied_value scope differs from the observed column samples.
    metrics = {"batch": {
        "input_orders": len(source),
        "paid_orders": ledger["paid_orders"],
        "cancelled_orders": len(source) - ledger["paid_orders"],
        "net_cents": ledger["net_cents"],
    }}
    ps.publish_view(
        metrics, host=host, port=port, view_id=f"{view_prefix}:metrics",
        label="Batch metrics — supplied values", section="Observation",
        observe=ps.ObservationOptions(path=("batch",), fields=(
            "input_orders", "paid_orders", "cancelled_orders", "net_cents")),
    )
    # Observation has not replaced the useful application result.
    return ledger


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--view-prefix", default="etl")
    args = parser.parse_args()
    try:
        result = publish(args.host, args.port, view_prefix=args.view_prefix)
        print(json.dumps({"application_result": result}), flush=True)
    finally:
        # A script boundary, not a hot-loop cadence mechanism. Drained does not
        # mean delivered: inspect the independent receiver for actual evidence.
        drained = ps.flush_views(timeout=3)
        print(json.dumps({"accepted_work_drained": drained,
                          "observation_stats": ps.get_observation_stats()}), flush=True)
