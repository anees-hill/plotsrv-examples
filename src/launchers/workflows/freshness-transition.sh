#!/usr/bin/env bash
set -euo pipefail
exec python -m plotsrv_examples run storage-history --inspect "$@"
