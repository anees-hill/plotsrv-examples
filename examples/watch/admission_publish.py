"""Best-effort application publication plus optional HTTP rejection diagnostics."""

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

import psutil
from plotsrv import publish_view
from plotsrv.publishing import PublishTarget


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", required=True)
    parser.add_argument("--view-id", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--bearer-token-env")
    parser.add_argument("--probe-rejection", action="store_true")
    args = parser.parse_args()
    target = PublishTarget("remote", base_url=args.destination,
                           bearer_token_env=args.bearer_token_env, request_timeout_s=0.5)
    # The application result is independent of best-effort visualization delivery.
    application_result = sum([4, 7, 9])
    publish_view(args.text, destination=target, launch_server=False, async_=False,
                 view_id=args.view_id, kind="artifact", artifact_kind="text")
    process = psutil.Process()
    descendants = process.children(recursive=True)
    listeners = [c.laddr.port for p in [process, *descendants]
                 for c in p.net_connections(kind="tcp") if c.status == psutil.CONN_LISTEN]
    result = {"application_result": application_result, "publication_returned": True,
              "listeners_after_call": listeners, "descendants_after_call": [p.pid for p in descendants]}
    if args.probe_rejection:
        # This diagnostic separately checks the public wire rejection. A normal
        # Python call returning is deliberately not classified as delivery.
        headers = {"Content-Type": "application/json"}
        if args.bearer_token_env:
            headers["Authorization"] = "Bearer " + os.environ[args.bearer_token_env]
        body = {"view_id": args.view_id, "kind": "artifact", "artifact_kind": "text",
                "artifact": args.text}
        request = Request(args.destination.rstrip("/") + "/publish",
                          data=json.dumps(body).encode(), headers=headers)
        try:
            with build_opener(ProxyHandler({})).open(request, timeout=2) as response:
                result["http_status"] = response.status
        except HTTPError as error:
            with error:
                result["http_status"] = error.code
                result["detail"] = json.loads(error.read(65536))["detail"]
    args.report.write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__":
    main()
