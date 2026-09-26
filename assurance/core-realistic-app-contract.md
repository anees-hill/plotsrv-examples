# Realistic application publication contract

PHASE-01 inspection, 2026-09-10. Core reference is sibling
`/home/samane/Projects/plotsrv`, HEAD
`c4c86d230955af9dff6a1c9c766eeb340859ae43` (`PLOTSRV_CORE_DIR` unset).
Core status was clean before inspection. This is implementation guidance,
not runtime or integration acceptance. Existing worktree changes are preserved.

## Current APIs and receiver evidence

- Core `src/plotsrv/publisher.py:861` exposes `publish_view` with explicit
  `destination`, `launch_server`, `async_`, `view_id`, `kind` and
  `artifact_kind`. Use an explicit loopback receiver destination,
  `launch_server=False`, and `async_=False` for finite, verifiable publication.
  Do not combine destination with host/port. Reuse stable view IDs on updates.
- `publish_view` returns `None`; setup/transport failures may be swallowed.
  `tests/test_publisher.py` covers table, PNG, JSON, text and swallowed errors.
  Successful process exit is insufficient: check `/views`, exact expected
  table content at `/table/data?view=ID`, decoded PNG at `/plot?view=ID`, and
  status content at `/artifact?view=ID`. Existing `scenarios/gallery.py` and
  `assurance/tests/test_gallery.py` demonstrate receipt and negative evidence.
- Core `publisher.py:125-205,355-385`: pandas/Polars frames publish as tables;
  matplotlib figures (including seaborn-created figures) and plotnine objects
  publish as PNG plots. Plotnine is drawn to a figure. HTTP serialization closes
  figures after successful rendering; application `finally` cleanup is still
  needed for rendering/publication failures. Use an explicit Agg backend.
- Dictionaries publish as JSON artifacts; explicit text uses `kind="artifact"`
  and `artifact_kind="text"`. A filename string is text, whereas `Path` reads
  file content. Keep source status readable and separate from measurement data.
- Table truncation prepares the head of a frame; it does not bound application
  history. Bound history before constructing frames or plots.
- Core `html.py:609` and `tests/test_table_plot_consolidation.py` distinguish
  simple read-only tables from rich explorer tables. This is receiver config,
  not a per-publication mode. Duplicate publications do not demonstrate it.

## Resource monitor implementation assumptions for PHASE-02

Legacy implementation is `src/resource-monitor/main.py`; the target
`examples/resource_monitor/` does not yet exist. Real psutil snapshots and
representative tables/plots remain useful. `direct_publish` ignores `kind` and
`view_type`; every branch of `decorate_publisher` is identical. The advertised
infer/explicit distinction is therefore ineffective and should be removed.
The running frame grows with each iteration; finite iterations alone do not
bound prolonged inspection. Define history in samples, accounting for the four
long-form metric rows per sample, and retain only the configured rolling window.

Use stable view IDs, disable receiver persistence in owned scenario config,
and bound output, waits and inspection duration. Existing `support/lifecycle.py`
provides bounded child output (65,536 bytes by default), process ownership and
cleanup. `test_lifecycle.py` covers large output and timeout cleanup; those tests
were inspected, not executed here. Figure lifetime and retained sample counts
need monitor-specific checks. Assert plausible typed values, not exact host
measurements. Keep real plotsrv calls visible in example source.

## Weather implementation assumptions for PHASE-03

`demos/public_weather/` does not yet exist. The default source must be a
deterministic fixture served over owned loopback HTTP. Both sample and explicit
live selection must enter one fetch, validate, normalise, transform and publish
path (INV-04). Only source selection and truthful provenance differ. Define a
small documented example schema; the private application's schema is unavailable
and parity is not established.

Bound response bytes, request time, records and retries. Live HTTP/validation
failure must produce an explicit unavailable/error outcome, without sample
fallback or retained data being labelled current live success. Use placeholders
only in live configuration documentation; do not echo credentials or private
URLs into reports. Shut down and join the fixture server during cleanup.

Later verification must cover rolling history and cleanup, local HTTP content,
explicit live failure, and the full `uv run pytest -q assurance/tests` suite.
No application code or core files were changed and no core imports, services or
tests were run during this phase. INV-05/CASE-05 are checked by core Git status;
the remaining behavioral acceptance belongs to subsequent phases.

## Safe continuation recheck

The PHASE-01 retry preserved this existing record and re-read the current core
publisher implementation and publication/table-explorer tests at the same revision.
The table tests assert truncation metadata (`total_rows` versus `returned_rows`);
JSON publication tests assert the `plotsrv_json_document` envelope, so later
receiver checks must not assume a raw dictionary response. Synchronous publication
still returns no receipt. Asynchronous publication coalesces pending updates and
requires a finite `flush_views` wait if used; it is unnecessary for the planned
finite examples. Source/test inspection reconfirmed the assumptions above without
running core tests or importing core. Core Git status remained clean. This retry
changes only this record and does not implement PHASE-02 or PHASE-03.
