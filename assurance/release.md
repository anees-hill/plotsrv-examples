# Automated release suite

After explicit candidate setup, run:

```sh
uv run --no-sync python -B -m plotsrv_examples doctor
uv run --no-sync python -B -m plotsrv_examples list
uv run --no-sync python -B -m plotsrv_examples check quick
uv run --no-sync python -B -m plotsrv_examples check release
```

Quick checks one real publication. Release requires all 19 named scenarios in
`coverage.md`, sequentially, using ephemeral loopback ports and owned workspaces.
Weather uses the local deterministic sample; no external weather service is used.
Each scenario must return zero, report success and nonempty asserted evidence,
and confirm owned children were reaped. Reports include per-scenario evidence,
candidate provenance, timestamps, and required scenarios not run after a failure.
The suite compares each scenario and the final core/candidate state with its
initial provenance. A mismatch blocks automated success.

Exit 0 means **automated evidence passed**, while `manual_status: pending` and
`release_signoff: withheld` remain explicit. Missing dependencies, exceptions,
failed assertions, invalid reports, incomplete cleanup and timeouts return nonzero.
SIGINT/SIGTERM returns 130. The suite stops on the first failed requirement;
remaining scenarios are `not_run`, never passed or silently skipped.

The release runner uses POSIX signal deadlines (120 seconds per scenario,
overridable with `--scenario-timeout`). Timeout exceptions unwind scenario-owned
process cleanup. This is a Linux/POSIX workflow; it does not certify Windows.
`--port` and `--evidence-timeout` are quick-only options. Fault drills on release
target the required basic publication scenario:

```sh
uv run --no-sync python -B -m plotsrv_examples check release --fault missing-evidence
uv run --no-sync python -B -m plotsrv_examples check release --scenario-timeout 0.01
```

Both must fail. The first deliberately runs a zero-exit publisher without the
required received sentinel. Suite tests additionally inject missing dependencies,
assertion failures, interruption, invalid evidence and changed provenance.

Use [the manual checklist](manual-checklist.md) to record human observations
separately. Repository tests, compilation, privacy/migration review and final
independent review are additional obligations; this suite does not replace them.
The [manual smoke guide](manual-smoke-test.md) supplies two-terminal commands and
expected results. New source scenarios cover publishing variants and exports,
traceback policy, render limits, attached lifecycle, mixed watched-file formats,
head/tail windows, and compatible observation changes. Browser persistence,
filtered exports, live controls and reset remain human checks.

`check wheel --wheel-path /absolute/candidate.whl` is a separate packaged smoke
check, not a waiver of the source provenance gate. It creates an owned virtual
environment, installs that artifact, verifies import/direct-URL identity and
checks received text/table/plot plus local page assets. Its report includes the
wheel SHA-256 and installation diagnostics. It requires `uv`; installation can
use the network. It leaves manual status pending and retains its workspace.
Generated workspaces are retained locally for diagnostics and can be cleaned
with the documented `workspace-clean` command. Do not commit runtime reports.

## PHASE-02 worker verification

On 2026-09-10, quick passed and the release run from 15:44:08 to 15:45:56 UTC
passed all 15 required scenarios. Both retained pending manual status and withheld
sign-off. Core and imported editable candidate matched clean revision
`c4c86d230955af9dff6a1c9c766eeb340859ae43` before and after release execution.
The missing-evidence release drill exited 1, identified basic-publication failure
and marked the other 14 requirements `not_run`.

The suite/quick regression run passed 17 tests. After adding timeout diagnostic
retention and a live timeout cleanup check, the suite-specific run passed 11
tests, including verification that timed-out owned children were reaped. These
are implementation-phase worker observations; final repository integration and
independent review remain separate obligations.
