"""Separate synchronous publisher; readable public API example."""

import argparse
import os

from plotsrv.publisher import publish_view


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("destination")
    parser.add_argument("view_id")
    parser.add_argument("sentinel")
    parser.add_argument("--skip", action="store_true")
    parser.add_argument("--high-output", action="store_true")
    args = parser.parse_args()
    if args.high_output:
        for _ in range(512):
            os.write(1, b"o" * 4096)
            os.write(2, b"e" * 4096)
    if not args.skip:
        publish_view(args.sentinel, destination=args.destination, launch_server=False,
                     async_=False, view_id=args.view_id, section="assurance",
                     label="Basic publication", kind="artifact", artifact_kind="text")


if __name__ == "__main__":
    main()
