#!/usr/bin/env bash
set -euo pipefail

HOST="${PLOTSRV_HOST:-0.0.0.0}"
PORT="${PLOTSRV_PORT:-8101}"
CONFIG_PATH="${PLOTSRV_CONFIG_PATH:-tmp/plotsrv-generated.yml}"
TARGET="${PLOTSRV_TARGET:-src/smoke-tests}"
PUBLISH_DELAY="${PLOTSRV_PUBLISH_DELAY:-4}"
KEEP_ALIVE="${PLOTSRV_KEEP_ALIVE:-1}"

require_repo_root() {
  if [[ ! -f "README.md" || ! -d "src/smoke-tests" ]]; then
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

echo "[INFO] Removing existing generated config: ${CONFIG_PATH}"
rm -f "${CONFIG_PATH}"

echo "[INFO] Creating config"
plotsrv config create --config "${CONFIG_PATH}"

echo "[INFO] Populating freshness"
plotsrv config populate freshness "${TARGET}" \
  --config "${CONFIG_PATH}" \
  --expected-every 30s \
  --warn-after 45s \
  --overdue-after 60s \
  --mode merge \
  --yes

echo "[INFO] Populating storage"
plotsrv config populate storage "${TARGET}" \
  --config "${CONFIG_PATH}" \
  --keep-last 3 \
  --min-store-interval 10s \
  --mode merge \
  --yes

echo "[INFO] Populating limits"
plotsrv config populate limits "${TARGET}" \
  --config "${CONFIG_PATH}" \
  --text 1000000 \
  --html off \
  --markdown off \
  --mode merge \
  --yes

echo
echo "[INFO] Generated config:"
echo "----------------------------------------"
cat "${CONFIG_PATH}"
echo "----------------------------------------"
echo

echo "[INFO] Starting plotsrv server"
plotsrv run "${TARGET}" \
  --config "${CONFIG_PATH}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --watch mock-files/long_text.txt --watch-label text-head --watch-section static-files --watch-head \
  --watch mock-files/long_text.txt --watch-label text-tail --watch-section static-files --watch-tail \
  --watch mock-files/uvicorn.log --watch-label long-log --watch-section static-files --watch-tail \
  --watch README.md --watch-label md --watch-section static-files \
  --watch mock-files/small_image.jpg --watch-label jpg --watch-section static-files \
  --watch pyproject.toml --watch-label toml --watch-section static-files \
  --watch plotsrv.yml --watch-label yml --watch-section static-files \
  --watch mock-files/yaml-1.yaml --watch-label yaml --watch-section static-files \
  --watch mock-files/json-1.json --watch-label json --watch-section static-files \
  --watch mock-files/html-simple-1.html --watch-label html-simple --watch-section static-files \
  --watch mock-files/html-complex-1.html --watch-label html-complex --watch-section static-files \
  --watch mock-files/6000_20.csv --watch-label csv-very-large --watch-section static-files \
  --watch mock-files/1000_20.csv --watch-label csv-large-head --watch-section static-files --watch-head \
  --watch mock-files/1000_20.csv --watch-label csv-large-tail --watch-section static-files --watch-tail \
  --watch mock-files/100_20.csv --watch-label csv-small --watch-section static-files \
  &
SERVER_PID="$!"

echo "[INFO] plotsrv PID: ${SERVER_PID}"
echo "[INFO] Open: http://${HOST}:${PORT}"
echo "[INFO] Waiting ${PUBLISH_DELAY}s before publishing Python objects..."
sleep "${PUBLISH_DELAY}"

echo "[INFO] Running Python publisher: smoke-tests.python_objs"
PLOTSRV_HOST="${HOST}" PLOTSRV_PORT="${PORT}" python -m smoke-tests.python_objs

echo "[INFO] Publisher completed."

if [[ "${KEEP_ALIVE}" == "1" || "${KEEP_ALIVE}" == "true" ]]; then
  echo "[INFO] Keeping server alive. Press Ctrl+C to stop."
  wait "${SERVER_PID}"
else
  cleanup
fi
