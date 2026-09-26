"""Publish supplied check metrics and a small table for manual view inspection."""

import argparse
import json

import pandas as pd
from plotsrv import publish_view
from plotsrv.publishing import PublishTarget


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--state", choices=["healthy", "failing", "recovered"], required=True)
    parser.add_argument("--schema", type=int, choices=[1, 2], default=1)
    args = parser.parse_args()
    target = PublishTarget("remote", base_url=f"http://127.0.0.1:{args.port}", request_timeout_s=1)
    errors = 3 if args.state == "failing" else 0
    publish_view({"errors": errors}, destination=target, async_=False, launch_server=False,
                 view_id="checks:metrics", kind="artifact", artifact_kind="json")
    rows = {"job": ["import", "export"], "rows": [100, 200 + errors]}
    if args.schema == 2:
        rows["quality"] = ["review", "ok"]
    publish_view(pd.DataFrame(rows), destination=target, async_=False, launch_server=False,
                 view_id="checks:table", label="Schema inspection")
    print(json.dumps({"application_result": 20, "state": args.state, "errors": errors,
                      "schema": args.schema, "publication_returned": True}), flush=True)


if __name__ == "__main__":
    main()
