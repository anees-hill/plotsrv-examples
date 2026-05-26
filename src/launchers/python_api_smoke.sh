#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-interactive}"
HOST="${PLOTSRV_HOST:-0.0.0.0}"
PORT="${PLOTSRV_PORT:-8101}"
DELAY="${PLOTSRV_DELAY:-6}"
CONFIG_PATH="${PLOTSRV_CONFIG_PATH:-plotsrv.yml}"

usage() {
  cat <<EOF
Usage:
  bash src/launchers/python_api_smoke.sh passive
  bash src/launchers/python_api_smoke.sh interactive
  bash src/launchers/python_api_smoke.sh all

Environment overrides:
  PLOTSRV_HOST=0.0.0.0
  PLOTSRV_PORT=8101
  PLOTSRV_DELAY=6
  PLOTSRV_CONFIG_PATH=plotsrv.yml

Modes:
  passive      Start plotsrv using Python API with watched files.
  interactive  Simulate analyst-style Python work using refresh_view(), @view, publish_view().
  all          Run passive first, then interactive.
EOF
}

require_repo_root() {
  if [[ ! -f "README.md" || ! -d "mock-files" ]]; then
    echo "[ERROR] Run this from the plotsrv-examples repository root." >&2
    exit 2
  fi
}

run_passive() {
  echo "[INFO] Starting Python-side passive plotsrv smoke test"
  echo "[INFO] Open: http://${HOST}:${PORT}"
  echo "[INFO] Press Ctrl+C to stop"

  PLOTSRV_SMOKE_HOST="$HOST" \
  PLOTSRV_SMOKE_PORT="$PORT" \
  PLOTSRV_SMOKE_CONFIG="$CONFIG_PATH" \
  python - <<'PY'
from __future__ import annotations

import os
import time
import plotsrv as ps

host = os.environ.get("PLOTSRV_SMOKE_HOST", "0.0.0.0")
port = int(os.environ.get("PLOTSRV_SMOKE_PORT", "8101"))
config = os.environ.get("PLOTSRV_SMOKE_CONFIG", "plotsrv.yml")

watches = [
    {"path": "mock-files/long_text.txt", "label": "text-head", "section": "static-files", "read_mode": "head"},
    {"path": "mock-files/long_text.txt", "label": "text-tail", "section": "static-files", "read_mode": "tail"},
    {"path": "mock-files/uvicorn.log", "label": "long-log", "section": "static-files", "read_mode": "tail"},
    {"path": "README.md", "label": "md", "section": "static-files"},
    {"path": "mock-files/small_image.jpg", "label": "jpg", "section": "static-files"},
    {"path": "old_plotsrv.ini", "label": "ini", "section": "static-files"},
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
print("[INFO] Watching files via Python API.")
print("[INFO] Press Ctrl+C to stop.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[INFO] Stopping plotsrv")
    ps.stop_server(join=False)
PY
}

run_interactive() {
  echo "[INFO] Starting Python-side interactive plotsrv smoke test"
  echo "[INFO] Open: http://${HOST}:${PORT}"
  echo "[INFO] Delay between stages: ${DELAY}s"

  PLOTSRV_SMOKE_HOST="$HOST" \
  PLOTSRV_SMOKE_PORT="$PORT" \
  PLOTSRV_SMOKE_DELAY="$DELAY" \
  PLOTSRV_SMOKE_CONFIG="$CONFIG_PATH" \
  python - <<'PY'
from __future__ import annotations

import os
import time
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

import plotsrv as ps
from plotsrv.config import set_table_view_mode

host = os.environ.get("PLOTSRV_SMOKE_HOST", "0.0.0.0")
port = int(os.environ.get("PLOTSRV_SMOKE_PORT", "8101"))
delay = float(os.environ.get("PLOTSRV_SMOKE_DELAY", "6"))
config = os.environ.get("PLOTSRV_SMOKE_CONFIG", "plotsrv.yml")


def pause(msg: str) -> None:
    print(f"\n[STAGE] {msg}")
    print(f"[INFO] Inspect: http://{host}:{port}")
    time.sleep(delay)


def make_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": list(range(1, 11)),
            "group": ["A", "A", "B", "B", "C", "C", "A", "B", "C", "A"],
            "score": [10.5, 12.0, 9.5, 15.2, 8.1, 11.3, 14.8, 7.7, 13.4, 16.0],
            "flag": [True, False, True, False, True, False, True, True, False, True],
        }
    )


print("[INFO] Starting plotsrv via Python API")
ps.start_server(
    host=host,
    port=port,
    config=config,
    auto_on_show=False,
    quiet=True,
)

df = make_df()

# 1. Matplotlib via explicit refresh_view
fig = plt.figure()
ax = fig.add_subplot(111)
ax.scatter(df["id"], df["score"])
ax.set_title("Matplotlib scatter via ps.refresh_view()")
ax.set_xlabel("id")
ax.set_ylabel("score")
ps.refresh_view(fig, label="matplotlib-scatter", section="interactive")
pause("Matplotlib figure via ps.refresh_view(fig, label=...)")

# 2. Matplotlib via plt.show patch
fig2 = plt.figure()
ax2 = fig2.add_subplot(111)
ax2.plot(df["id"], df["score"], marker="o")
ax2.set_title("Matplotlib line via patched plt.show()")
plt.show()
pause("Matplotlib figure via patched plt.show()")

# 3. pandas table, simple mode
set_table_view_mode("simple")
ps.refresh_view(df, label="pandas-simple", section="interactive")
pause("Pandas DataFrame via ps.refresh_view(df) in simple mode")

# 4. pandas table, rich mode
set_table_view_mode("rich")
ps.refresh_view(df, label="pandas-rich", section="interactive")
pause("Pandas DataFrame via ps.refresh_view(df) in rich mode")

# 5. polars table if available
try:
    import polars as pl

    ps.refresh_view(pl.from_pandas(df), label="polars-rich", section="interactive")
    pause("Polars DataFrame via ps.refresh_view(pl_df)")
except Exception as e:
    print(f"[SKIP] Polars test skipped: {type(e).__name__}: {e}")

# 6. plotnine if available
try:
    from plotnine import aes, geom_point, ggplot

    p = ggplot(df, aes("id", "score", color="group")) + geom_point()
    ps.refresh_view(p, label="plotnine", section="interactive")
    pause("plotnine plot via ps.refresh_view(plotnine_plot)")
except Exception as e:
    print(f"[SKIP] plotnine test skipped: {type(e).__name__}: {e}")

# 7. JSON/dict artifact via generic refresh_view
ps.refresh_view(
    {
        "status": "ok",
        "metrics": {
            "rows": len(df),
            "mean_score": float(df["score"].mean()),
            "groups": sorted(df["group"].unique().tolist()),
        },
        "nested": {"a": {"b": [1, 2, 3]}},
    },
    label="json-dict",
    section="interactive",
)
pause("dict/JSON artifact via ps.refresh_view({...})")

# 8. text artifact via refresh_view
ps.refresh_view(
    "Hello from plotsrv\n\nThis is a text artifact published with ps.refresh_view().",
    label="text-message",
    section="interactive",
)
pause("text artifact via ps.refresh_view('...')")

# 9. file path artifact via refresh_view
readme = Path("README.md")
if readme.exists():
    ps.refresh_view(readme, label="readme-path", section="interactive")
    pause("Path-like file artifact via ps.refresh_view(Path('README.md'))")

# 10. image file via refresh_view
img = Path("mock-files/small_image.jpg")
if img.exists():
    ps.refresh_view(img, label="image-path", section="interactive")
    pause("Image file via ps.refresh_view(Path(...jpg))")

# 11. HTML file via refresh_view
html_file = Path("mock-files/html-simple-1.html")
if html_file.exists():
    ps.refresh_view(html_file, label="html-path", section="interactive")
    pause("HTML file via ps.refresh_view(Path(...html))")

# 12. Decorator-based generic view
@ps.view(label="decorated-dict", section="interactive", host=host, port=port)
def decorated_dict() -> dict[str, object]:
    return {
        "decorator": "@ps.view",
        "message": "This came from a decorated function.",
        "values": [1, 2, 3],
    }

decorated_dict()
pause("@ps.view-decorated function publishing dict")

# 13. publish_view over HTTP to same server
ps.publish_view(
    {
        "source": "publish_view",
        "transport": "HTTP",
        "message": "This was sent to the running server over HTTP.",
    },
    label="published-json",
    section="interactive",
    host="127.0.0.1",
    port=port,
)
pause("ps.publish_view({...}) over HTTP")

# 14. publish_view table over HTTP
ps.publish_view(
    df,
    label="published-table",
    section="interactive",
    host="127.0.0.1",
    port=port,
)
pause("ps.publish_view(df) over HTTP")

print("\n[INFO] Interactive smoke test complete.")
print("[INFO] Server will remain up. Press Ctrl+C to stop, or close this process.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[INFO] Stopping plotsrv")
    ps.stop_server(join=False)
PY
}

require_repo_root

case "$MODE" in
  passive)
    run_passive
    ;;
  interactive)
    run_interactive
    ;;
  all)
    echo "[INFO] Running passive mode first. Press Ctrl+C when done inspecting passive mode."
    run_passive
    echo "[INFO] Running interactive mode."
    run_interactive
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "[ERROR] Unknown mode: $MODE" >&2
    usage
    exit 2
    ;;
esac
