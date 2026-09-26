"""Read a publisher-owned file and send its content to an existing receiver."""

import argparse
from pathlib import Path

from plotsrv import publish_view


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--view-id", default="remote:file")
    parser.add_argument("--remove-after-read", action="store_true",
                        help="Assurance drill: remove the disposable input before sending")
    args = parser.parse_args()
    content = args.source.read_text(encoding="utf-8")
    if args.remove_after_read:
        args.source.unlink()
    publish_view(content, destination=args.destination, launch_server=False,
                 async_=False, view_id=args.view_id, kind="artifact", artifact_kind="text")


if __name__ == "__main__":
    main()
