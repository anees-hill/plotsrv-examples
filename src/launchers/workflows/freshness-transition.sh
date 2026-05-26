#!/usr/bin/env bash
set -euo pipefail

HOST="${PLOTSRV_HOST:-0.0.0.0}"
PORT="${PLOTSRV_PORT:-8101}"
CONFIG_PATH="${PLOTSRV_CONFIG_PATH:-tmp/plotsrv-freshness-transition.yml}"
VIEW_ID="freshness-demo:one-shot"

require_repo_root() {
  if [[ ! -f "README.md" ]]; then
    echo "[ERROR] Run this from the plotsrv-examples repository root." >&2
    exit 2
  fi
}

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    echo "[INFO] Stopping plotsrv server PID ${SERVER_PID}"
    kill "${SERVER_PID}" 2>/dev/null || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

require_repo_root

mkdir -p "$(dirname "${CONFIG_PATH}")"

cat > "${CONFIG_PATH}" <<'YAML'
limits:
  watched_files:
    max_bytes: 5000000
  render:
    text: 1000000
    html: off
    markdown: off
  tables:
    max_rows: 10000
    max_columns: 200

table-settings:
  table_view_mode: rich

storage-settings:
  enabled: true
  root_dir: .plotsrv/store
  default_keep_last: 5
  max_snapshot_size_mb: 20

freshness-settings:
  enabled: true
  expected_every: 5s
  warn_after: 8s
  overdue_after: 12s
  views:
    freshness-demo:one-shot:
      expected_every: 5s
      warn_after: 8s
      overdue_after: 12s
YAML

echo "[INFO] Freshness demo config written to: ${CONFIG_PATH}"

plotsrv run . \
  --config "${CONFIG_PATH}" \
  --host "${HOST}" \
  --port "${PORT}" \
  &
SERVER_PID="$!"

echo "[INFO] plotsrv PID: ${SERVER_PID}"
echo "[INFO] Waiting for server..."
sleep 3

echo "[INFO] Publishing one-shot view"
PLOTSRV_HOST="${HOST}" PLOTSRV_PORT="${PORT}" python - <<'PY'
import os
import plotsrv as ps

host = os.environ.get("PLOTSRV_HOST", "127.0.0.1")
port = int(os.environ.get("PLOTSRV_PORT", "8101"))

ps.publish_view(
    {"status": "published once", "note": "watch freshness change over time"},
    label="one-shot",
    section="freshness-demo",
    host="127.0.0.1",
    port=port,
)
PY

echo
echo "[INFO] Open: http://${HOST}:${PORT}/?view=${VIEW_ID}"
echo "[INFO] Expected freshness transitions:"
echo "  0-7s: fresh/ok"
echo "  8-11s: warn/stale"
echo "  12s+: overdue/error"
echo
echo "[INFO] Polling /status for 20 seconds..."
for i in $(seq 1 20); do
  echo "[${i}s]"
  curl -fsS "http://127.0.0.1:${PORT}/status?view=${VIEW_ID}" || true
  echo
  sleep 1
done

echo "[INFO] Keeping server alive for manual inspection. Press Ctrl+C to stop."
wait "${SERVER_PID}"
