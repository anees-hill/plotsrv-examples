#!/usr/bin/env bash
set -euo pipefail

HOST="${PLOTSRV_HOST:-0.0.0.0}"
PORT="${PLOTSRV_PORT:-8101}"
CONFIG_PATH="${PLOTSRV_CONFIG_PATH:-configs/python-objs/03-watch-limits.yml}"
PUBLISH_DELAY="${PLOTSRV_PUBLISH_DELAY:-3}"
KEEP_ALIVE="${PLOTSRV_KEEP_ALIVE:-1}"

require_repo_root() {
  if [[ ! -f "README.md" || ! -d "mock-files" || ! -d "src/smoke-tests" ]]; then
    echo "[ERROR] Run this from the plotsrv-examples repository root." >&2
    exit 2
  fi
}

require_repo_root

echo "[INFO] Starting plotsrv via Python API"
echo "[INFO] Host: ${HOST}"
echo "[INFO] Port: ${PORT}"
echo "[INFO] Config: ${CONFIG_PATH}"
echo "[INFO] Open: http://${HOST}:${PORT}"
echo

PLOTSRV_SMOKE_HOST="${HOST}" \
PLOTSRV_SMOKE_PORT="${PORT}" \
PLOTSRV_SMOKE_CONFIG="${CONFIG_PATH}" \
PLOTSRV_PUBLISH_DELAY="${PUBLISH_DELAY}" \
PLOTSRV_KEEP_ALIVE="${KEEP_ALIVE}" \
python - <<'PY'
from __future__ import annotations

import os
import runpy
import time

import plotsrv as ps

host = os.environ.get("PLOTSRV_SMOKE_HOST", "0.0.0.0")
port = int(os.environ.get("PLOTSRV_SMOKE_PORT", "8101"))
config = os.environ.get("PLOTSRV_SMOKE_CONFIG", "configs/python-objs/03-watch-limits.yml")
publish_delay = float(os.environ.get("PLOTSRV_PUBLISH_DELAY", "3"))
keep_alive = os.environ.get("PLOTSRV_KEEP_ALIVE", "1").strip().lower() in {"1", "true", "yes", "y"}

watches = [
    {"path": "mock-files/long_text.txt", "label": "text-head", "section": "static-files", "read_mode": "head"},
    {"path": "mock-files/long_text.txt", "label": "text-tail", "section": "static-files", "read_mode": "tail"},
    {"path": "mock-files/uvicorn.log", "label": "long-log", "section": "static-files", "read_mode": "tail"},
    {"path": "README.md", "label": "md", "section": "static-files"},
    {"path": "mock-files/small_image.jpg", "label": "jpg", "section": "static-files"},
    {"path": "configs/old_plotsrv.ini", "label": "ini", "section": "static-files"},
    {"path": "pyproject.toml", "label": "toml", "section": "static-files"},
    {"path": "plotsrv.yml", "label": "yml", "section": "static-files"},
    {"path": "mock-files/yaml-1.yaml", "label": "yaml", "section": "static-files"},
    {"path": "mock-files/json-1.json", "label": "json", "section": "static-files"},
    {"path": "mock-files/html-simple-1.html", "label": "html-simple", "section": "static-files"},
    {"path": "mock-files/html-complex-1.html", "label": "html-complex", "section": "static-files"},
    {"path": "mock-files/6000_20.csv", "label": "csv-very-large", "section": "static-files"},
    {"path": "mock-files/1000_20.csv", "label": "csv-large-head", "section": "static-files", "read_mode": "head"},
    {"path": "mock-files/1000_20.csv", "label": "csv-large-tail", "section": "static-files", "read_mode": "tail"},
    {"path": "mock-files/100_20.csv", "label": "csv-small", "section": "static-files"},
]

ps.start_server(
    host=host,
    port=port,
    config=config,
    watches=watches,
    auto_on_show=False,
    quiet=True,
)

print(f"[INFO] plotsrv running at http://{host}:{port}")
print("[INFO] Watched files are being published via Python API start_server(watches=...).")
print(f"[INFO] Waiting {publish_delay}s before publishing Python objects...")
time.sleep(publish_delay)

print("[INFO] Running smoke-tests.python_objs via runpy")
runpy.run_module("smoke-tests.python_objs", run_name="__main__")
print("[INFO] Python object publisher completed.")

if keep_alive:
    print("[INFO] Keeping server alive. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Stopping plotsrv")
        ps.stop_server(join=False)
else:
    ps.stop_server(join=False)
PY
