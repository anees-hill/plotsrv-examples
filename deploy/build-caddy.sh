#!/bin/sh
# Reproducible source inputs; build in an isolated builder and verify the binary.
set -eu
: "${1:?usage: build-caddy.sh /path/to/output-binary}"

CADDY_VERSION=v2.10.2
RATELIMIT_COMMIT=5625512f24f6f59d6f64fb3aafe5eecff0b286db
XCADDY_VERSION=v0.4.5

command -v go >/dev/null || { echo 'Go 1.25 or newer is required' >&2; exit 1; }
builder_dir=$(mktemp -d)
trap 'rm -rf "$builder_dir"' EXIT
GOBIN="$builder_dir/bin" go install "github.com/caddyserver/xcaddy/cmd/xcaddy@$XCADDY_VERSION"
"$builder_dir/bin/xcaddy" build "$CADDY_VERSION" \
    --with "github.com/mholt/caddy-ratelimit@$RATELIMIT_COMMIT" \
    --output "$builder_dir/caddy"
"$builder_dir/caddy" list-modules | grep -Fx 'http.handlers.rate_limit'
"$builder_dir/caddy" adapt --config "$(dirname "$0")/Caddyfile" --adapter caddyfile >/dev/null
install -m 0755 "$builder_dir/caddy" "$1"
