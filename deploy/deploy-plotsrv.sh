#!/bin/sh
# Production entrypoint. Always use the tooling delivered beside this script.
set -eu
bundle_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ ! -f "$bundle_dir/tooling/deploy/bundle.py" ]; then
    echo 'ERROR: bundle tooling is missing. Transfer the complete new plotsrv-upload directory; see DEPLOYMENT-GUIDE.md.' >&2
    exit 1
fi
exec python3 -B "$bundle_dir/tooling/deploy/bundle.py" "$bundle_dir" "$@"
