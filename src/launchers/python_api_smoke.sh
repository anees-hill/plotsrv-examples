#!/usr/bin/env bash
set -euo pipefail
# Python is now readable in examples/lifecycle.py. publish/show/watch are distinct.
exec python examples/lifecycle.py --config "${PLOTSRV_CONFIG_PATH:-configs/current/minimal.yml}" --port "${PLOTSRV_PORT:-8101}" "$@"
