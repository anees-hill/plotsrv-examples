"""Compatibility entry point for the bounded resource monitor."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[2] /
                       "examples/resource_monitor/main.py"), run_name="__main__")
