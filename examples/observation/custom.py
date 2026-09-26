"""Publish explicit business aggregation with ordinary publication."""

import argparse
import json

import plotsrv as ps

from plotsrv_examples.etl import order_fixture, regional_totals, transform_orders


def publish(host, port, *, view_prefix="etl"):
    columns = transform_orders(order_fixture())
    report = regional_totals(columns)
    # This is our full-batch business calculation, not a capture-engine callback
    # or an inference from sampled values. Ordinary JSON publishing suffices.
    ps.publish_view(report, host=host, port=port, async_=False,
                    view_id=f"{view_prefix}:regional-totals",
                    label="Regional sales — explicit full-batch totals",
                    section="Custom observation", kind="artifact", artifact_kind="json")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--view-prefix", default="etl")
    args = parser.parse_args()
    print(json.dumps({"application_result": publish(
        args.host, args.port, view_prefix=args.view_prefix)}), flush=True)
