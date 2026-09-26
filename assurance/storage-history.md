# Owned storage and restart

Run `uv run --no-sync python -B -m plotsrv_examples run storage-history`.
The command creates a fresh owned run, checks storage disabled, publishes three
recognisable text versions with retention two, reads both historical payloads,
and observes fresh/stale/overdue API states. It stops the first receiver before
restarting against the same store. Restored content must retain its persisted
timestamp and snapshot IDs and have no new process-lifetime publication arrivals.
The persisted timestamp comes from `store list`; core writes it separately from
the live receipt timestamp.

After stopping writers, the scenario runs owned `store stats`, `store list`, and
per-view `store clear`, verifies empty storage, and reports those commands' output.
Only that run's generated history/latest data is removed; the run directory and
publisher reports remain. Clear is irreversible; the same data can be regenerated
by rerunning the scenario. No arbitrary config or external root is accepted by the
support layer, and an unrelated-root rejection is demonstrated before launch.
Store identity, run marker and existing tree symlinks are checked before use.
These private run directories must not be concurrently edited by other processes.

`--inspect --inspect-seconds 30` holds the restored receiver open before clear.
Browser history arrows, freshness rendering and Compare remain manual-pending;
UTC calendar API metadata is preparation evidence only. Checks/webhooks and their
manual controls belong to PHASE-03.

`--fault missing-evidence` deliberately fails before success and still reaps
owned children. Run `uv run --no-sync python -B -m pytest -q assurance/tests/test_storage_history.py`
for target substitution rejection, sentinel preservation and public restart tests.

## PHASE-02 worker verification (2026-09-10)

- `run storage-history`: passed against core
  `c4c86d230955af9dff6a1c9c766eeb340859ae43`; two retained versions, preserved
  persisted timestamp, zero restart arrivals, owned clear and unowned rejection.
  An initial run failed the overly strict live-receipt timestamp comparison;
  inspecting `storage/latest.py:109` established the persistence timestamp rule
  documented above. Core was not changed.
- `uv run pytest -q assurance/tests/test_storage_history.py`: 11 passed, including
  a deliberate missing-evidence failure and substitution/symlink/hardlink rejection.
- `uv run pytest -q assurance/tests`: 90 passed, 1 failed. This run collected
  before the additional hardlink parameter was added. The failure was the existing
  `test_failed_child_diagnostic_is_prompt`: expected startup stderr, but received
  a listener-ownership inspection error. Its isolated rerun passed (1 passed).
  The full-suite result remains failed; no unrelated lifecycle code was changed.
- `git diff --check` passed; core Git status and diff remained clean.

These are worker-reported checks, not independent acceptance. Browser-only
behavior remains manual-pending, and checks-webhook was not run in PHASE-02.
