"""Compose focused examples for an existing receiver; importing has no side effects.

uv run --no-sync python -B examples/gallery.py --port 8000
For an owned receiver use: uv run --no-sync python -B -m plotsrv_examples run gallery --inspect
"""

import argparse
from pathlib import Path

import plotsrv as ps
import direct
import decorated
import objects
import async_live
import exceptions
import files


def publish(host, port):
    destination = f"http://{host}:{port}"
    direct.publish(destination)
    decorated.publish(host, port)
    objects.publish(destination)
    async_live.publish(destination)
    exceptions.publish(host, port)
    files.publish(destination, Path(__file__).resolve().parents[1] / "mock-files/json-1.json")
    ps.publish_view("Gallery text sentinel", destination=destination, async_=False,
                    view_id="gallery-text", label="Text", section="Documents")
    ps.publish_view("# Gallery markdown sentinel", destination=destination, async_=False,
                    artifact_kind="markdown", view_id="gallery-markdown",
                    label="Markdown", section="Documents")
    ps.publish_view("<p>Gallery HTML sentinel</p>", destination=destination, async_=False,
                    artifact_kind="html", view_id="gallery-html",
                    label="HTML", section="Documents")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    publish(args.host, args.port)
