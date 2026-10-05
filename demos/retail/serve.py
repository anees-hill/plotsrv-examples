"""Northstar receiver with two bounded, static watched logs in the same process."""

import os
import signal
import threading
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

import yaml

ROOT = Path(__file__).resolve().parent


def watches():
    from plotsrv import WatchConfig

    return [
        WatchConfig(
            path=ROOT / "logs" / filename,
            view_id=view,
            label=label,
            section="Operations logs",
            kind="text",
            read_mode="tail",
            max_bytes=32 * 1024,
            materialization="memory",
        )
        for filename, view, label in (
            ("orders.log", "retail:log:orders", "Order processing log"),
            (
                "fulfillment-access.log",
                "retail:log:fulfillment",
                "Fulfilment API access log",
            ),
        )
    ]


def main():
    import plotsrv as ps

    config = Path(os.environ.get("PLOTSRV_CONFIG", ROOT / "plotsrv.yml"))
    bind = yaml.safe_load(config.read_text())["server-settings"]["bind"]
    stopping = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopping.set())
    opener = build_opener(ProxyHandler({}))
    try:
        ps.start_server(
            config=config,
            host=bind["host"],
            port=bind["port"],
            auto_on_show=False,
            watches=watches(),
        )
        # Detect background receiver failure so systemd can restart the service.
        # This is a cheap local health read, not a content regeneration job.
        while not stopping.wait(30):
            with opener.open(
                f"http://127.0.0.1:{bind['port']}/status", timeout=5
            ) as response:
                response.read(1024)
    finally:
        ps.stop_server(join=True)


if __name__ == "__main__":
    main()
