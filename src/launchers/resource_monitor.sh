#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
exec uv run python -m plotsrv_examples run resource-monitor "$@"
