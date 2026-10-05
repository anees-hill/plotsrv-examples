"""One startup publication per receiver; no periodic report-generation schedule."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOKENS = {
    "retail": "PLOTSRV_RETAIL_TOKEN",
    "live_import": "PLOTSRV_LIVE_TOKEN",
    "scan_audit": "PLOTSRV_SCANS_TOKEN",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo", choices=TOKENS)
    args = parser.parse_args()
    os.environ.setdefault("PLOTSRV_CONFIG", str(ROOT / args.demo / "plotsrv.yml"))
    os.environ["PLOTSRV_DEBUG"] = "1"
    # Reuse the bounded, authenticated readiness check; no public network access.
    import importlib.util

    import yaml

    config = yaml.safe_load(Path(os.environ["PLOTSRV_CONFIG"]).read_text())
    spec = importlib.util.spec_from_file_location(
        "readiness", ROOT.parent / "deploy/wait-for-receiver.py"
    )
    readiness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(readiness)
    readiness.wait_for_receiver(
        config["server-settings"]["bind"]["port"], os.environ[TOKENS[args.demo]]
    )
    if args.demo in ("retail", "live_import"):
        script = (
            ROOT / args.demo / ("app.py" if args.demo == "retail" else "reports.py")
        )
        os.execv(sys.executable, [sys.executable, "-B", str(script)])
    import plotsrv as ps
    from publishing import Publisher

    with Publisher("scan_audit").locked():
        state = Path(".plotsrv/scans-output/state.json")
        if state.exists():
            if state.stat().st_size > 16384:
                raise ValueError("Previous scan state exceeds its bound")
            metrics = json.loads(state.read_text())["current"]
            # Restored snapshots deliberately do not act as new check evidence.
            # Re-submit the actual latest successful metrics, without redoing scans.
            ps.publish_view(
                metrics,
                view_id="scans:metrics",
                label=f"Audit metrics · {metrics['run_date']}",
                section="Document scan audit",
                kind="artifact",
                artifact_kind="json",
                launch_server=False,
                async_=False,
            )
            if not ps.flush_views(timeout=15):
                raise RuntimeError("Check evidence publication did not drain")


if __name__ == "__main__":
    main()
