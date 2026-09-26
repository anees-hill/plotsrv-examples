#!/usr/bin/env bash
set -euo pipefail
exec python -m plotsrv_examples run gallery --inspect "$@"
