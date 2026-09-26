# plotsrv-examples 2.0.0

Public examples and release assurance for [plotsrv](https://github.com/anees-hill/plotsrv).
Focused scripts show public API calls; scenarios check received evidence through
owned local receivers. Automated passes do not certify browser/TUI behavior or
authorize a release.

## Setup and candidate identity

From this checkout on Linux/POSIX with Python 3.11 or newer:

```bash
export PLOTSRV_CORE_DIR=/absolute/path/to/plotsrv
uv sync --locked
uv pip install --python .venv/bin/python --editable "$PLOTSRV_CORE_DIR"
uv run --no-sync python -B -m plotsrv_examples doctor
uv run --no-sync python -B -m plotsrv_examples list
uv run --no-sync python -B -m plotsrv_examples check quick
uv run --no-sync python -B -m plotsrv_examples check release
```

The package is `plotsrv-examples` version 2.0.0, imported as `plotsrv_examples`.
The core has its own version. `uv.lock` locks examples dependencies, without a
machine-specific core path. Install core explicitly after syncing: `uv sync`
can remove the separately installed candidate. Use `--no-sync` for execution.
Core dependencies are not locked here; reproducibility also requires recording
the candidate revision and its dependency environment.

`PLOTSRV_CORE_DIR` selects the read-only reference, not the installation. Doctor
reports imported module, distribution/direct URL and reference revision/dirty
state separately. It blocks missing or mismatched candidates. A sibling fallback
exists, but explicit selection is recommended. Separately installed wheels are
currently rejected by the source-identity gate; they are not silently certified.
See [the inspected candidate baseline](assurance/final-core-candidate.md).
The [current core review](assurance/current-core-review.md) records the fresh
0.8.0 integration result.

## Workflows and coverage

Quick requires a real received view and sentinel. Release requires all 16
deterministic scenarios; failed assertions, absent dependencies, timeouts and
interruption cannot pass. Exit 0 means automated success while manual status stays
pending and full sign-off stays withheld. See [release semantics](assurance/release.md),
[coverage matrix](assurance/coverage.md), and the reconstructed
[manual checklist](assurance/manual-checklist.md).

```bash
uv run --no-sync python -B -m plotsrv_examples run gallery --inspect
uv run --no-sync python -B -m pytest -q
uv run --no-sync python -B -m plotsrv_examples check release --fault missing-evidence
```

The last command deliberately fails and must return nonzero. Gallery inspection
prints a local URL and stays available for 30 seconds; extend with
`--inspect-seconds 300`. Ctrl+C cleans up and returns 130, not a pass.

| Examples / scenario | Guide |
| --- | --- |
| Direct/decorated/async objects, files, exceptions and lifecycle | [Gallery and focused examples](assurance/gallery.md) |
| JSONL, mixed HTTP/text/traceback, and Python application logs | [Stream examples](examples/streams/README.md) |
| Observed ETL, application result and capture provenance | [Observation](examples/observation/README.md) |
| Local/remote watches, admission and config discovery | [Watch examples](examples/watch/README.md) |
| Storage restart, history, retention and freshness | [Storage assurance](assurance/storage-history.md) |
| Checks and bounded local webhook delivery | [Checks/webhooks](assurance/checks-webhook.md) |
| Finite real psutil monitor | [Resource monitor](examples/resource_monitor/README.md) |
| Weather shared pipeline, local synthetic sample by default | [Weather demo](demos/public_weather/README.md) |

Live weather is explicit and never falls back to sample data. Two-machine
networking, live external sources, browser/TUI checks and prolonged monitor
sessions remain separate manual obligations. No browser automation, benchmark
thresholds, deployment or publication is provided.

## Configuration, fixtures and retained compatibility

Use [current representative configs](configs/current/README.md). Root
`plotsrv.yml` is a memory-only compatibility default for external core smoke.
Older dated assurance reports describe their original 0.7.0 candidate. The
[final migration map](assurance/legacy-map.md) accounts for all legacy
purposes and removed paths, including profile-specific limitations.
The external `src/smoke-tests/basic-smoke-test.py` path is retained; it is a
long-running compatibility service, not the release suite.

Small synthetic mixed-format fixtures stay tracked.
[Large fixtures](mock-files/README.md) are generated locally. The retained object
stream companion can be run against an explicitly started receiver with
`PYTHONPATH=src python -B -m smoke-tests.python_objs_w_stream`; its default
destination is loopback port 8101. See its `--help` for finite record bounds.

## Owned local state

Scenarios retain diagnostics in ignored `.plotsrv-runs/run-*` directories:

```bash
uv run --no-sync python -B -m plotsrv_examples workspace-create
uv run --no-sync python -B -m plotsrv_examples workspace-clean /absolute/owned/run/path
```

Stop producers before cleanup. Cleanup removes contents irreversibly while
retaining the ownership marker. Foreign directories, symlinks, copied markers,
special files and cross-device contents are rejected. Do not alter markers to
adopt existing data. POSIX descriptor support is required; concurrent moves or
writers during cleanup are unsupported. Historical tmp/store copies remain
ignored locally. Do not commit generated reports, caches, credentials or local
configuration. No command here modifies, tags, pushes or deploys core.
