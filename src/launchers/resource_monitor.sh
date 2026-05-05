#!/usr/bin/env bash

set -euo pipefail

HOST="127.0.0.1"
PORT="8000"
CONFIG_PATH=""

SERVER_TARGET=""
SERVER_MODE="passive"
CALL_EVERY=""

PUBLISHER_SCRIPT="src/resource-monitor/main.py"
PUBLISH_STYLE="decorator"
KIND="infer"
FETCH_INTERVAL="10"
SAMPLE_INTERVAL="1"
PLOT_LIBS="all"

STARTUP_WAIT="10"
WAIT_SECONDS="60"

usage() {
  cat <<'EOF'
Usage:
  bash src/launchers/resource_monitor.sh [options]

Server options:
  --server-target TARGET       Target passed to `plotsrv run`
  --server-mode MODE           passive or callable. Default: passive
  --call-every SECONDS         Passed when --server-mode callable
  --config PATH                Config passed to `plotsrv run --config`

Publisher options:
  --publisher-script PATH      Default: src/resource-monitor/main.py
  --publish-style STYLE        decorator or direct. Default: decorator
  --kind KIND                  infer or explicit. Default: infer
  --fetch-interval SECONDS     Default: 10
  --sample-interval SECONDS    Default: 1
  --plot-libs LIBS             all, or comma-separated: plotnine,matplotlib,seaborn

Shared options:
  --host HOST                  Default: 127.0.0.1
  --port PORT                  Default: 8000
  --startup-wait SECONDS       Default: 10
  --wait SECONDS               Default: 60

Examples:
  bash src/launchers/resource_monitor.sh \
    --server-target resource-monitor \
    --config plotsrv.yml \
    --publish-style decorator \
    --kind infer \
    --wait 120

  bash src/launchers/resource_monitor.sh \
    --server-target resource-monitor \
    --config plotsrv_smoketests.yml \
    --publish-style direct \
    --kind explicit \
    --wait 60
EOF
}

SERVER_PID=""
PUBLISHER_PID=""

cleanup() {
  echo
  echo "[resource-monitor] Cleaning up..."

  if [[ -n "${PUBLISHER_PID}" ]] && kill -0 "${PUBLISHER_PID}" 2>/dev/null; then
    echo "[resource-monitor] Stopping publisher process ${PUBLISHER_PID}"
    kill "${PUBLISHER_PID}" 2>/dev/null || true
  fi

  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    echo "[resource-monitor] Stopping plotsrv process ${SERVER_PID}"
    kill "${SERVER_PID}" 2>/dev/null || true
  fi

  wait "${PUBLISHER_PID}" 2>/dev/null || true
  wait "${SERVER_PID}" 2>/dev/null || true

  echo "[resource-monitor] Done."
}

trap cleanup EXIT INT TERM

while [[ $# -gt 0 ]]; do
  case "$1" in
    --server-target)
      SERVER_TARGET="$2"
      shift 2
      ;;
    --server-mode)
      SERVER_MODE="$2"
      shift 2
      ;;
    --call-every)
      CALL_EVERY="$2"
      shift 2
      ;;
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --publisher-script)
      PUBLISHER_SCRIPT="$2"
      shift 2
      ;;
    --publish-style)
      PUBLISH_STYLE="$2"
      shift 2
      ;;
    --kind)
      KIND="$2"
      shift 2
      ;;
    --fetch-interval)
      FETCH_INTERVAL="$2"
      shift 2
      ;;
    --sample-interval)
      SAMPLE_INTERVAL="$2"
      shift 2
      ;;
    --plot-libs)
      PLOT_LIBS="$2"
      shift 2
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --startup-wait)
      STARTUP_WAIT="$2"
      shift 2
      ;;
    --wait)
      WAIT_SECONDS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      echo
      usage
      exit 1
      ;;
  esac
done

if [[ "${SERVER_MODE}" != "passive" && "${SERVER_MODE}" != "callable" ]]; then
  echo "--server-mode must be one of: passive, callable"
  exit 1
fi

if [[ "${PUBLISH_STYLE}" != "decorator" && "${PUBLISH_STYLE}" != "direct" ]]; then
  echo "--publish-style must be one of: decorator, direct"
  exit 1
fi

if [[ "${KIND}" != "infer" && "${KIND}" != "explicit" ]]; then
  echo "--kind must be one of: infer, explicit"
  exit 1
fi

SERVER_CMD=(plotsrv run)

if [[ -n "${SERVER_TARGET}" ]]; then
  SERVER_CMD+=("${SERVER_TARGET}")
fi

if [[ "${SERVER_MODE}" == "callable" ]]; then
  SERVER_CMD+=(--mode callable)

  if [[ -n "${CALL_EVERY}" ]]; then
    SERVER_CMD+=(--call-every "${CALL_EVERY}")
  fi
fi

SERVER_CMD+=(--host "${HOST}" --port "${PORT}")

if [[ -n "${CONFIG_PATH}" ]]; then
  SERVER_CMD+=(--config "${CONFIG_PATH}")
fi

PUBLISHER_CMD=(
  python "${PUBLISHER_SCRIPT}"
  --publish-style "${PUBLISH_STYLE}"
  --kind "${KIND}"
  --host "${HOST}"
  --port "${PORT}"
  --fetch-interval "${FETCH_INTERVAL}"
  --sample-interval "${SAMPLE_INTERVAL}"
  --plot-libs "${PLOT_LIBS}"
)

echo "[resource-monitor] Starting plotsrv server:"
printf '  %q' "${SERVER_CMD[@]}"
echo

"${SERVER_CMD[@]}" &
SERVER_PID="$!"

echo "[resource-monitor] plotsrv PID: ${SERVER_PID}"
echo "[resource-monitor] Waiting ${STARTUP_WAIT}s before starting publisher..."
sleep "${STARTUP_WAIT}"

if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
  echo "[resource-monitor] plotsrv exited before publisher started."
  exit 1
fi

echo "[resource-monitor] Starting publisher:"
printf '  %q' "${PUBLISHER_CMD[@]}"
echo

"${PUBLISHER_CMD[@]}" &
PUBLISHER_PID="$!"

echo "[resource-monitor] publisher PID: ${PUBLISHER_PID}"
echo "[resource-monitor] Running for ${WAIT_SECONDS}s..."
sleep "${WAIT_SECONDS}"

echo "[resource-monitor] Wait complete."
