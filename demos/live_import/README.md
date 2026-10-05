# Live file imports

This is a small, continuously running file-validation task. It generates synthetic input rows, actually validates them, and writes ordinary structured JSONL application logs. The standard plotsrv log suggestions should show recent events, warnings, levels over time and busiest loggers. There is no REST integration or demo-specific plotsrv feature.

From the examples checkout, run these commands in separate terminals. Share the same token between receiver and follower:

```sh
export PLOTSRV_LIVE_TOKEN="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uv run --no-sync plotsrv serve --config demos/live_import/plotsrv.yml
```

```sh
export PLOTSRV_LIVE_TOKEN=... # the same value
uv run --no-sync python -B demos/live_import/follow.py --log .plotsrv/live/import.jsonl
```

```sh
uv run --no-sync python -B demos/live_import/generate_events.py --log .plotsrv/live/import.jsonl
```

Open `http://127.0.0.1:8102/`. Start the follower before the writer if you want the first records: plotsrv begins at the current end of an existing file. A new visitor may wait up to three seconds for the next event. `Since Last` needs a previous visit from that same browser.

The active log rotates at 1 MiB and keeps two older files, so disk use stays below about 3 MiB plus metadata. plotsrv follows the active pathname and can report uncertain continuity at rotation; old rotated files are not replayed. Stream persistence is disabled; the live log remains short-lived. Snapshot storage is enabled only for the prepared report views described below. The `--count`, `--interval` and `--max-bytes` options support finite local checks.

## Prepared import operations workspace

Run once, with the same receiver token:

```sh
PLOTSRV_DEBUG=1 uv run --no-sync python -B demos/live_import/reports.py
```

This publishes recent-import and exception tables, a nested manifest, two plots and
a colourful HTML operations report. It seeds three reproducible **illustrative
batches**: initial issues, partial improvement and the current example. They are
separate from the live log; report labels and provenance explain this. Processing
durations are simulated, not measurements of plotsrv or the VM.

The six report views each retain three snapshots with genuine capture timestamps.
Seeding is resumable, using confirmed receiver history and a small publisher journal
under `.plotsrv/demo-publishing`. Repeat the command after editing reports; unchanged
content is reused. There is **no recurring report job** and no growing archive.

The HTML report uses trusted rendering with bundled styles, no external fonts or
scripts, and escaped data values. The default plotsrv header logo links to
https://demo.plotsrv.com. The three featured entries use small local screenshots.
Source-code views have been removed. Only the manifest deliberately expects a
refresh every five minutes, warns after ten and becomes overdue after fifteen.
The featured views have freshness checks disabled. The fixed manifest is left
unchanged to demonstrate freshness; no extra recurring work is introduced.

Dropdown descriptions are hidden while the **i / About this view** explanations
remain available. Current titles omit revision suffixes; earlier seeded snapshots
use batch-stage labels. An update from older labels publishes the clean current
title once, retaining the existing history bound and earlier snapshot metadata.
Prepared reports may show Restored after a restart; the independent live stream
updates as new events arrive. The outcomes legend sits above the data bars.
