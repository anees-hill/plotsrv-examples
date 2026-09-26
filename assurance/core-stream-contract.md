# Current stream contract

PHASE-01 inspection, 2026-09-10. Source/test inspection only; no stream scenario
or integration acceptance is claimed. `PLOTSRV_CORE_DIR` is unset; the repository's
documented sibling fallback is `/home/samane/Projects/plotsrv`, HEAD
`c4c86d230955af9dff6a1c9c766eeb340859ae43`. Core Git status was clean before and
after inspection. No core imports, tests, services, or Git mutations were run.
Existing examples worktree changes were preserved.

All core paths below are relative to that checkout.

## Attachment and delivery

- `src/plotsrv/streams/api.py:187` exposes `stream_view(source=..., format=...,
  destination=..., view_id=..., client_id=..., session_id=...)`. It always uses
  background observation and an existing receiver, independent of snapshot async
  settings. It does not launch a receiver. Keep the follower process alive.
- `streams/file_source.py:304` captures an existing file's EOF synchronously in
  follower construction, before worker scheduling or HTTP registration completes.
  Missing files retain offset zero until created. There is no historical import.
  Default JSONL requires `.jsonl`/`.ndjson`, complete finite JSON objects per line;
  malformed/oversized records are accounted as rejected, not delivered records.
- `streams/client.py` registers asynchronously and retains one batch until an
  acknowledgement, reusing batch identity and sequence on retries. Pending data
  remains in the source file beyond that bounded batch. Receiver restart can
  change the session; this is not a global exactly-once guarantee.
- The public handle exposes `initial_offset`, `is_observing`, `session_id`, and
  `health["delivery"]["registered"]`. Observer liveness alone is not HTTP readiness.
  Later scenarios should create the file, start the independent follower, wait
  for acknowledged registration of the expected unique view/session, then release
  the writer through an explicit readiness barrier. Use bounded waits and check
  owned child liveness; do not use a fixed sleep as readiness evidence.
- Read `GET /stream/data?view=ID`; actual input values are in `records[*].data`.
  Compare deterministic values/order and absence of a pre-attach sentinel, not
  merely a catalogue entry or child exit code. The finite batch must fit retention.
  `streams/server_state.py:744` defines `after` as a server record sequence, not a
  source byte offset or user JSON sequence. Carry session identity with incremental
  reads; session mismatch, aged-out or ahead-of-window cursors require explicit
  reset handling. Full bounded reads suffice for the small finite scenarios.
- `acknowledged_source_offset` measures accepted source progress;
  `candidate_source_offset` can include an unacknowledged batch, and
  `accounted_source_offset` also includes rejected input. Neither candidate nor
  accounted progress substitutes for receiver content assertions.

Inspected tests: `tests/test_streams.py:2221` (existing EOF), `:2301` (missing
file), `:2886` (retained batch and acknowledged offsets), and `:4220` (real
receiver data and ended lifecycle). These tests were read, not executed here.

## HTTP framing and suggested views

`streams/text_framing.py`, `text_source.py`, `http_adapter.py`, `http_profile.py`
and `docs/guides/http-log-streams.md` define two distinct layers:

- `format="uvicorn"` conservatively adapts access lines and frames mixed text;
  `text` disables access recognition. `auto` selects strict JSONL by suffix and
  Uvicorn adaptation otherwise; it is not arbitrary parser inference.
- Adapted JSON has `log_schema_version: 1`, `event`, and `raw`. Recognized access
  lines add `http.method/path/status`; a supplied unit-bearing duration can add
  `duration_ms`. Unknown text and traceback frames have no `http` object.
  Tracebacks remain ambiguous/unattributed, with no nearby-500 association,
  invented request ID, route template, or duration.
- Source timestamps exist only when valid and supplied. Publisher observation
  time and outer server receipt time are different clocks. `raw.text` is a
  sanitized bounded excerpt with explicit transformations, not archival bytes.
  JSONL input is caller-controlled and does not receive this text sanitization.
- Framing caps are 4 KiB per physical line, 8 KiB/32 lines per frame, and
  64 KiB/128 reads per turn. Partial frames get a one-second grace then finalize
  on a scheduled poll; oversized suffixes are discarded through newline.
  Pending batches are bounded to 100 records/512 KiB, with one text lookahead;
  records have a 64 KiB wire ceiling. These bounds do not bound the producer file.
- Server HTTP suggestions validate request semantics independently: the version-1
  Uvicorn envelope or one unambiguous complete flat/nested structured request.
  Supported methods and integer statuses 100–599 are validated. Invalid requests,
  text, tracebacks and ambiguous shapes stay raw and outside request denominators.
  Partial/truncated/ambiguous adapted events cannot contribute request recipes.
- The first recognized request fixes clock/template mapping. Missing later values
  remain missing. Latency recipes need actual durations. Suggestions use at most
  the newest 512 accepted records still retained (default raw retention 200),
  with browser loaded-window/filter restrictions. Counts represent retained
  evidence, not service rates or availability; historical compact summaries do
  not support these HTTP recipes. Suggested/saved views reuse the admitted source
  ID; Raw stream retains fallback visibility.

Inspected tests: `tests/test_text_streams.py:42,57,74,88` exercise mixed fallback,
supplied duration/time, and unattributed chains; `tests/test_http_profile.py:137`
checks raw rows versus request counts and `:164` excludes partial/ambiguous frames.
Later mixed assurance should assert recognized values, fallback text and traceback
presence, absent fabricated HTTP fields, and receiver profile request counts.
Browser presentation remains separate manual evidence.

## Lifecycle and subsequent implementation requirements

`streams/api.py:75` makes `handle.stop(timeout=...)` idempotent with a finite
join/drain/close budget. Successful drain can report `ended`; incomplete work
reports `incomplete` if close succeeds. Failed close relies on heartbeat expiry;
returning from stop does not prove ended delivery. Core installs no signal handlers
and only offers bounded best-effort atexit cleanup.

Stop and reap the owned writer first, then drain/stop the follower while the
receiver is alive, verify content and close outcome, and finally stop the receiver.
Use `finally` for explicit handle cleanup and existing `Processes` /
`interruption_cleanup` support for owned foreground children. Reconcile runtime
provenance with `require_candidate()` before launching. Bound writer record count,
record size and total output even during inspection; a finished finite writer can
leave the receiver open for inspection without continuing to grow a log. Stop all
owned processes before workspace cleanup. Do not truncate an active log just to
bound it: truncation/rotation introduce continuity semantics and cannot guarantee
recovery of removed unread bytes.

This phase adds only this reference. PHASE-02/03 own example/scenario changes,
`uv run pytest -q assurance/tests`, `stream-structured`, `stream-http`, and real
interruption verification. INV-01/02/03 and CASE-01/02/03/04 are informed by this
inspection, not accepted as behaviorally passed. INV-04/CASE-05 have the limited
self-reported evidence of read-only core access and unchanged clean Git status.
