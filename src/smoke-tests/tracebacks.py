"""Compatibility publisher for the three public exception styles."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "examples"))
from exceptions import publish

if __name__ == "__main__":
    publish(os.getenv("PLOTSRV_HOST", "127.0.0.1"), int(os.getenv("PLOTSRV_PORT", "8101")))
