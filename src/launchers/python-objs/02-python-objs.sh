#!/usr/bin/env bash
set -euo pipefail
echo 'Legacy profile launcher retired. Use python -m plotsrv_examples run gallery --inspect for the memory-only gallery. Profile-specific watch/storage/security work is separate; see assurance/gallery.md.' >&2
exit 2
