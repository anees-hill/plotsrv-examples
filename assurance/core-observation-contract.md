# Current observation contract

PHASE-01 source/doc/test inspection, 2026-09-10. `PLOTSRV_CORE_DIR` was unset;
the documented sibling fallback is `/home/samane/Projects/plotsrv`, HEAD
`c4c86d230955af9dff6a1c9c766eeb340859ae43`. Core Git status was clean before
and after inspection. No core imports, tests, services or mutations were run.
Existing examples worktree changes were preserved. Paths below refer to core.

## Supported public invocation forms

- `ps.publish_view(value, observe=True, view_id="etl:rows", host=..., port=...)`
  submits bounded evidence and returns `None`, not a delivery acknowledgement.
  Inline publication also accepts `destination` (URL or `PublishTarget`), configured
  routing, or attached local startup. Do not combine destination with host/port.
- `@ps.view(observe=True, view_id="etl:rows", host=..., port=...)` wraps a
  synchronous function synchronously or awaits an async function once. It returns
  the identical application result; original exceptions/cancellation propagate
  without automatic error publication. Classes cannot use this observation form.
  The decorator has no `destination` argument: use host/port or configuration.
- Both forms accept `observe=ps.ObservationOptions(fields=("rows", "net_cents"),
  path=("import",), include_examples=False)`. Fields and path must be tuples;
  fields use all names or all nonnegative positions. There are at most 32 field
  selectors and 6 path components; strings are nonempty and at most 128 characters.
  Table integer selectors are positions. Dict name/path lookup is bounded to an
  inspected prefix; unmatched does not prove absent. Field selection on sequences,
  arrays or scalars fails closed. Path traversal supports builtin dict/list/tuple.
- Omit `async_` or use `async_=True`. Observation always uses background delivery,
  independent of ordinary async defaults. `async_=False` is a setup error.
  Observation requires decorator `on_error="raise"`; inline `kind` and
  `artifact_kind` overrides are rejected. Invalid static options can raise;
  nonfatal runtime failures are not a promise that arbitrary invalid setup succeeds.
- `observe=False` is ordinary publication. Compute a domain aggregate explicitly
  in application code and publish its small dictionary normally as the separate
  custom example. Observation does not accept custom aggregation callbacks.

Sources: `publisher.py:861`, `decorators.py:216,354`,
`observations/runtime.py:22`, `observations/models.py:99` and
`docs/guides/observation-capture.md`. Pipeline tests at lines 63, 128 and 175
exercise public entrypoints, identity/errors/cancellation and sync incompatibility;
line 558 checks ordinary custom reports. Tests were read, not executed.

## Types, bounds and meaning

`observations/capture.py:310` and `observations/adapters.py` dispatch on exact
types. Supported bounded storage includes CPython dict, list/tuple, builtin
scalar metrics, safe eager NumPy arrays, and checked pandas DataFrame storage.
NumPy foreign owners/memmaps and unsafe dtypes are restricted. Pandas supports
NumPy-backed and selected nullable/string/temporal blocks; unknown layouts,
categorical/Arrow/custom extensions can be omitted. Polars capture is disabled:
even an exact eager DataFrame gets `polars_capture_unavailable` without native
shape/value access. Generators, lazy frames, subclasses and arbitrary objects do
not trigger conversion, property traversal or repr fallback. Prefer modest
builtin metric dictionaries and ordinary numeric pandas columns for the ETL.

Defaults from `observations/models.py:12` apply together:

| Limit | Default |
| --- | ---: |
| Base positions / fields | 32 / 16 |
| Element allowance / nodes / depth | 1,024 / 1,024 / 6 |
| Value bytes / category prefixes | 256 / 16 |
| Charged capture bytes / envelope bytes | 256 KiB / 64 KiB |
| Additional exploratory positions | 4 |
| Dimensions / pandas blocks | 8 / 32 |
| Soft capture deadline | 10 ms |
| Process refill / minimum view interval | 0.25 s / 1 s |
| Reservations / reserved bytes / view identities | 8 / 512 KiB / 128 |

Budgets live under `publish-settings.observe`, initialized once per process.
They are work/evidence bounds, not RSS or latency guarantees; native work cannot
be preempted. A 32-by-16 selection need not capture every cell. Keep the default
fixture small (for example 48 deterministic rows and a few numeric columns),
large enough to illustrate sampling without becoming a benchmark.

Positional samples are deterministic distributed positions including endpoints,
not random samples. Exploratory probes are separate from base statistics.
`observations/summary.py` exports explicit `supplied_value`, `base_sample`,
`complete_small_inspection` or `captured_structure` field scope. Even complete
positional coverage is not atomic or proof omitted cells were inspected.
Use coverage, omission reasons, selection, recipe/version, capture time, source
type and publisher session as provenance. Means/ranges/missingness describe
captured evidence; exact business totals must come from application aggregation.
No claim of whole-data correctness or absence of rare failures follows from a
sample. Examples default off, but metrics/names/category prefixes still export;
selection is not redaction. Capture owns detached bytes but concurrent writes
are only best effort; keep source storage stable during the synchronous call.

Read tests: `test_observation_capture.py` covers unknown objects, detachment,
budgets, pandas restrictions, probes and disabled Polars; pipeline test at 617
checks mutation after handoff cannot change retained delivery.

## Admission, delivery and errors

`observations/admission.py` reserves capture, pending and in-flight work against
one process engine. Rejected admission does not inspect the source. The process
token bucket permits up to four starts and refills at the configured interval;
per-view cadence still applies. Public pending work coalesces per destination/view
after cadence admission. In-flight work for that identity is skipped. Replacement
capture failure also loses the old pending sample. There is no guarantee of one
observation per call or delivery of the final call, and no event ledger.

Only admission and bounded detached capture run in the caller. Setup may also
occur on the first inline invocation; decorators prepare routing/worker at setup.
The consumer summarizes and performs local startup/HTTP. Runtime capture/delivery
exceptions are nonfatal (also under debug); application/control exceptions retain
their normal semantics. Remote capability negotiation requires `observation-v1`
and has no raw-object fallback. Delivery failure introduces target cooldown
(normally 5 seconds, 30 for auth/admission/protocol failures), with no automatic
resend or retained retry backlog. Later calls may try again after cooldown.

`ps.flush_views(timeout=...)` shares a finite deadline across ordinary and
observation queues. True means accepted work drained, including failed delivery;
it does not certify reception. `ps.get_observation_stats()` is process-wide,
best-effort diagnostics, not proof for a particular ETL run. Server receipt can
also return `ignored=True` for throttling (`observations/receiver.py:15`).
Shutdown drains briefly then closes admission/drops pending work; a finite wait
cannot guarantee termination of stuck native work.

Read pipeline tests at 231 (coalescing/in-flight rejection), 283 (nonfatal failure
despite successful flush), 599 (failed replacement), and 641 (shared flush deadline).

## Requirements for subsequent phases

Use public APIs with stable explicit IDs and an independent receiver. Assert the
deterministic application result separately from received exported summary content
and provenance. Flush while the receiver remains alive, check actual receiver
content with bounded waits, then clean up owned processes in `finally`. Do not
assert private envelopes/counters as acceptance, every rapid call surviving, or
fixed sleep as proof of delivery. Verify the executing candidate matches this
reference before runtime assurance.

This phase records the contract only. ETL/custom example implementation belongs
to PHASE-02; finite assurance and the requested `uv run pytest -q assurance/tests`
and `uv run python -m plotsrv_examples run observe-etl` belong to later work.
INV-01/02 and CASE-01/02/03 are informed by inspection, not behaviorally accepted.
INV-04/CASE-05 have limited self-reported evidence from read-only access and
unchanged clean core Git status. Fixture size remains a later implementation check.
