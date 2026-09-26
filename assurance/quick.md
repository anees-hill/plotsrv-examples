# Basic publication assurance

Run `uv run --no-sync python -B -m plotsrv_examples check quick` from this checkout after
installing a matching current plotsrv candidate. The command checks provenance,
starts a foreground receiver and separate synchronous Python publisher, and
requires a unique logical view and sentinel in the receiver's rendered artifact.
Exit 0 requires publication evidence and completed owned-child cleanup.
The JSON keeps `manual_status: pending` and `release_signoff: withheld` separate.
Quick is the basic-publication subset of the [release suite](release.md); use
`uv run --no-sync python -B -m plotsrv_examples list` for the stable scenario registry and
the [manual checklist](manual-checklist.md) for human sign-off.

The current reference defaults to sibling `plotsrv`; `PLOTSRV_CORE_DIR` selects
another reference explicitly. A missing or mismatched imported candidate fails
before launch. The validated source candidate is explicitly selected for both
children, using the runner's interpreter. This check does not certify a different
wheel against the reference source.

Each run creates an owned `.plotsrv-runs/run-*` workspace with memory-only
configuration and isolated caches. It retains that workspace for inspection;
the JSON result reports its path, provenance, view/sentinel, child exit statuses,
and bounded output tails. No existing configuration is overwritten. After the
run, `uv run --no-sync python -B -m plotsrv_examples workspace-clean ABSOLUTE_RUN_PATH` can
clear the owned workspace contents while preserving its ownership marker.

Deliberate drills:

- `uv run --no-sync python -B -m plotsrv_examples check quick --fault missing-evidence`
  runs a publisher that exits 0 without publishing; the check must exit 1.
- `uv run --no-sync python -B -m plotsrv_examples check quick --fault startup`
  selects an absent receiver configuration inside the owned workspace; it must
  fail promptly, exit 1 and reap the receiver.
- `uv run --no-sync python -B -m plotsrv_examples check quick --fault high-output`
  writes 4 MiB across publisher stdout/stderr before real publication. It must
  pass with no more than 64 KiB retained per child.
- `--port PORT` selects a port for a busy-listener drill. An unrelated listener
  is rejected without receiving publication, shutdown or a process signal.
- Interrupt after the receiver-ready message. SIGINT/SIGTERM must return 130
  and leave no owned listener. Automated tests verify both signals.

`uv run --no-sync python -B -m pytest -q assurance/tests` includes real CLI tests for these cases and
candidate mismatch. It requires an installed matching candidate and fails rather
than skipping when that prerequisite is missing. Primitive tests additionally
exercise forced cleanup and HTTP trickle deadlines. These are worker-run checks;
they do not constitute independent review or browser verification.
