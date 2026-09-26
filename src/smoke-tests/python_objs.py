"""Compatibility entry point: publish independent focused objects to an existing receiver."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "examples"))
from objects import publish

HOST = os.getenv("PLOTSRV_HOST", os.getenv("HOST", "127.0.0.1"))
PORT = int(os.getenv("PLOTSRV_PORT", os.getenv("PORT", "8101")))


def main():
    publish(f"http://{HOST}:{PORT}")


if __name__ == "__main__":
    main()
