# Check/webhook and browser inspection states

```bash
uv run --no-sync python -B -m plotsrv_examples run checks-webhook
uv run --no-sync python -B -m plotsrv_examples run checks-webhook --inspect --inspect-seconds 120
uv run --no-sync python -B -m pytest -q assurance/tests
```

The automated report covers live baseline/trigger/recovery, an event occurrence,
real loopback POST payloads, finite unavailable-endpoint failures and application
result independence. `--fault missing-evidence` deliberately returns nonzero and
still cleans up owned processes. See the [core contract](core-storage-check-contract.md)
for the current semantics. No HTTP destination is selected by published data.

The inspection run prints a receiver URL and an owned `control.json` path after
the automated assertions pass. Open the URL during the inspection period. Start
with `checks:table` (columns `job`, `rows`) and `checks:metrics` (recovered state).
Edit the control file in an editor, incrementing `revision` for each action:

```json
{"revision": 1, "state": "failing", "schema": 2}
```

Allowed states are `healthy`, `failing`, `recovered`; schema 2 adds `quality`.
Use schema 1 to return to the original columns. Revisions must increase from 0
through 6; invalid/partial JSON is ignored without publication. Edits cannot
change URLs, configs or store roots. Each accepted edit runs a finite publisher
against the verified owned listener. The final report records applied controls
separately from the automated transition evidence.

All rows below remain **manual-pending**, even when preparation succeeds. Record
tester, date, browser, core revision, observations and explicit pass/fail separately.

| Browser behavior | Prepared state and manual action |
| --- | --- |
| My Views schema drift | Save a view using schema 1; change the control to schema 2, then inspect how the saved view handles the extra column. |
| Check attention | Read existing activity, change recovered to failing, and check unseen attention. Reading it must not resolve failure. Change to recovered with a new revision and inspect recovery. |
| Focus | Enter focus on the table, change a control, and inspect focus/navigation stability. |
| Snapshot arrows | Two table snapshots are retained; browse older/newer while publishing another schema version. |
| Compare | Select the retained versions and inspect the existing Compare UI and day selection. No Compare/diff feature is implemented or automatically certified. |

The receiver and sink stop at the deadline or Ctrl+C. URLs are available only
during inspection, and generated owned history remains afterward. A prepared
report does not imply that the browser was opened or any checklist row passed.
Use [storage-history](storage-history.md) separately for restart and freshness.

## PHASE-03 worker verification (2026-09-10)

- `uv run python -m plotsrv_examples run checks-webhook`: passed, including the
  final receipt-context refinement. Healthy baseline emitted no event, unchanged
  failure stayed silent, trigger/recovery and one match reached the sink with
  matching identities. The unavailable destination reported six failed attempts
  (three per state event), zero queued/delivered, and a recovered check.
- `uv run pytest -q assurance/tests`: 101 passed in 270.91 seconds. This includes
  storage-history restart/retention, unowned-clear rejection, deliberate failures
  and manual-control preparation. The earlier phase's lifecycle diagnostic failure
  did not recur in this run.
- `uv run pytest -q assurance/tests/test_checks_webhook.py`: 9 passed in 37.55
  seconds on the final code, after the receipt-context and evidence refinements.
  The inspection test changed a control to failing/schema 2 and checked preparation
  and process cleanup; it did not inspect a browser.
- `git diff --check` passed; core Git status and diff remained clean at
  `c4c86d230955af9dff6a1c9c766eeb340859ae43`.

These are worker-reported observations, not independent acceptance. All browser
checklist items remain manual-pending. No core changes or durable webhook delivery
guarantee were introduced.
