# Current storage, freshness, checks and webhook contract

PHASE-01 inspection, 2026-09-10. `PLOTSRV_CORE_DIR` was unset; inspected the
documented sibling fallback `/home/samane/Projects/plotsrv` at HEAD
`c4c86d230955af9dff6a1c9c766eeb340859ae43`. Paths below are relative to core.
Core source, guides and tests were read, not executed or imported. This is a
worker-reported implementation contract, not scenario acceptance evidence.
Existing examples changes were preserved. No later-phase scenarios are added here.

## Storage and restart

- Storage is opt-in. Snapshot history and latest live persistence are separate.
  `storage/worker.py:202` writes latest before applying snapshot admission, so a
  skipped snapshot does not imply latest was skipped. File-backed watched views
  bypass both. Queued persistence can be rejected or fail; publication success
  alone does not establish a durable snapshot.
- `storage/policy.py:66` checks view/source admission, payload size and minimum
  interval. Retention keeps the newest N snapshot IDs; `None` means unlimited.
  Use explicit finite retention, modest payloads and an explicit interval policy
  in the future owned scenario. Wait for externally visible stored versions
  between publications rather than relying on a fixed sleep or publisher exit.
- `/history?view=...` returns `count`, `snapshots`, `capability`, and `result`
  (`available`, `empty`, `unavailable`). Distinguish disabled storage from enabled
  but empty history. Snapshot summaries include identity, creation time, kind,
  payload availability, extras, `is_latest`, and `is_live_equivalent`.
  Latest snapshot does not necessarily equal current live content; matching
  timestamps/content alone are not durable revision proof.
- `/history/navigation` provides bounded navigation; invalid queries return 400,
  unavailable/over-budget metadata returns 503. `/history/month?view=...&month=YYYY-MM`
  returns UTC day metadata. This can verify prepared calendar data, but cannot
  establish that Compare selection or browser arrows work. No Compare/diff work
  belongs in this slice.
- `server.py:236,305` restores directly into the store with arrival recording
  disabled, bypassing publication/persistence. `discovered` restores only already
  registered IDs (none when none are registered); `all` loads all latest records
  under the root; `none` or disabled startup restore loads nothing. Use explicit
  discovery or `all` only inside the verified owned root for a receiver-only run.
- `store.py:766` restores the persisted latest timestamp as `last_updated` and artifact content time,
  sets `restored_from_storage`, `restored_at`, and `restore_source=latest`.
  A subsequent live update clears restored status. Restart must preserve the
  retained snapshot identities/content without adding a restart snapshot or
  arrival. Do not compare process-local revision counters as durable identities.
  PHASE-02 runtime reconciliation: `storage/latest.py:109` timestamps the latest
  write itself, so this timestamp can differ from the preceding live status time.
  Compare restored time to the pre-restart `store list` latest timestamp, not to
  the live receipt timestamp. It remains a pre-restart time, not startup time.

Read evidence: guides `storage-and-history.md`, `freshness.md`;
`tests/test_app_storage_and_snapshots.py:43-182` (summary, latest and equivalence),
`tests/test_server_unit.py:651-696` (original timestamp and restored markers),
`tests/test_checks_integration.py:30-120` (read-only snapshot/restore and generation).

## Freshness

`store.py:817` computes age from original `last_updated`, clamps negative age to
zero and uses integer seconds. API states are `disabled`, `unknown`, `ok`, `warn`,
`error`; UI labels are Fresh, Stale and Overdue for the last three. Thresholds
are inclusive (`age_s >= threshold`), overdue takes priority. Missing warning
defaults to expected interval; missing overdue defaults to twice warning.
Missing/unparseable update time is unknown. Global freshness applies to ordinary
Python publishes; watch sources need an explicit per-view freshness entry.
Restoration never resets age to zero. Future assertions must poll these API
states within a deadline and leave rendered indicators manual-pending.

## Store CLI and ownership boundary

`cli.py:550-740` reads the selected config's storage root for `store stats`,
`store list [--view ID]`, and `store clear (--view ID | --all) [--yes]`.
Stats account separately for snapshots, latest and streams; list is human-readable
text, not a promised JSON interface. Clear deletes all three storage categories
for its selected scope. Missing/conflicting targets return 2; declining a prompt
returns 0 with `Aborted.`, so zero exit alone is not evidence of deletion.

Core clear has no examples ownership marker validation. `--yes` only skips its
confirmation. The examples support layer must verify ownership before launching
any mutating core process, pin the effective config/root to that owned run, and
reject unowned roots before invoking the CLI. Existing examples
`workspace.owned_directory` verifies repository/run identity using descriptor
traversal and a marker; it is not by itself a guard on arbitrary storage paths
or changed config contents. Root/config substitution and symlink checks need
explicit treatment in PHASE-02. Stop owned writers before clear or restart.

Read evidence: `tests/test_cli_store_cmds.py:105-180` covers target rejection,
abort and deletion output. No destructive command was run during this phase.

## Check baselines, transitions and evidence

`checks.py:322` and `docs/guides/checks.md` define predicates as **triggers when**,
not healthy conditions. Plain JSON rules select bounded scalar paths; tables or
missing/wrong-type values are unknown. Use a small supplied metric dictionary
for deterministic state evidence. Rules belong to server config, not publications.

The first processed state result initializes the rule without an event, even if
triggered or unknown. Unknown is not a healthy baseline; subsequent unknown-to-OK
is `available`. Known OK-to-failure emits `triggered`; uninterrupted known
failure-to-OK emits `recovered`; unchanged failure emits nothing. Missing evidence
or coverage loss prevents a fabricated recovery. Pending state work can coalesce:
wait for each expected latest state before publishing the next transition.

Event rules inspect accepted structured records, emit `match` occurrences, and
leave latest state OK/unknown rather than a persistent failure. Retry deduplication
precedes evaluation. Heartbeats, history browsing and restoration do not evaluate
live rules. Restart yields a new generation, unknown states and no startup events;
the next live state initializes the new baseline.

`/checks?view=...&after=...&generation=...` has exclusive cursors, bounded events,
generation and `history_gap`. `/status` includes latest checks without event history.
Track generation plus cursor and reject unexplained gaps in deterministic evidence.
History is capped at 256 events/256 KiB; overload can lose coverage. These checks
are observational, not a delivery ledger. Initial failing baseline does not create
browser unseen attention. Reading attention does not resolve an active failure.

Read evidence: `tests/test_checks_integration.py:30-120` exercises live receipt,
snapshot reads, unsupported evidence, deduplication and restart; implementation
`checks.py:322-382` establishes the exact initialized/unknown behavior.

## Generic webhook delivery

Server-configured `notify` destinations receive only check events; no initial
baseline alert or restore replay. State transitions notify independently of event
match cooldown (default 60 seconds, configurable 1–86400). Suppressed matches are
reported on the next eligible match, with no scheduled trailing summary.

`webhooks.py:17-25,310-348` and `docs/guides/webhooks.md` specify one worker,
64 items/256 KiB including in-flight work, 8 KiB payloads, 200 ms minimum spacing,
two-second socket exchange deadline, at most three attempts and 60-second expiry.
Network failures, 408/425/429/5xx retry after one then two seconds; Retry-After can
extend delays to 30 seconds. Other HTTP errors, redirects, TLS/response-limit
failures pause a destination for 300 seconds and drop its backlog. No recovery
probe runs. DNS cannot be forcibly cancelled; these are bounded-resource policies,
not hard wall-clock guarantees. Use numeric loopback and bounded external waits.

Any 2xx is success; response bodies are discarded. Retries preserve payload and
event identity (`Idempotency-Key`, `X-Plotsrv-Event-Id`). FIFO applies per
check/destination; receivers should deduplicate and use generation/cursor order.
Delivery is best effort and process-local, never durable/exactly-once. Failure
diagnostics do not alter check state, create check events, or redefine application
success. A future failure scenario should observe finite attempts/queue completion
and continuing trigger/recovery through `/checks`, separately from sink delivery.

Read evidence: `tests/test_webhooks.py:403-426` asserts exactly three failed
attempts before recovery delivery; lines 625-696 exercise real HTTP trigger/recovery
and notification failure preserving the check state/event sequence.

## Phase boundary and remaining evidence

INV-01/CASE-02 ownership enforcement remains an implementation/test obligation;
INV-02/CASE-01 restart and INV-03/CASE-03/CASE-04 transition/delivery scenarios remain
unexecuted. INV-04/CASE-05 browser Compare, My Views, focus, snapshot arrows and
check-attention remain manual-pending, including after API preparation succeeds.
INV-05/CASE-06: inspection made no core edits; core Git status was clean before
and after this phase. That observation is worker-reported, not independent proof.
The full assurance suite and storage-history/checks-webhook runs belong to the
implementation/integration evidence, not this documentation-only phase.
