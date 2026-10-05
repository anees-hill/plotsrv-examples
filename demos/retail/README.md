# Retail exploration

A deterministic fictional outdoor shop. The 1,680-row orders table is meant to be explored directly; four plots help with the same questions. There are intentionally discoverable patterns in returns, margins, fulfillment and seasonality.

From the examples checkout, with plotsrv installed in `.venv`:

```sh
export PLOTSRV_RETAIL_TOKEN="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uv run --no-sync python -B demos/retail/serve.py
```

In another terminal, with the **same** token:

```sh
PLOTSRV_DEBUG=1 uv run --no-sync python -B demos/retail/app.py
```

Open `http://127.0.0.1:8101/`. The receiver persists bounded history and a latest copy per content view for restart under `.plotsrv/retail` relative to its working directory. That directory is git-ignored. The deployment service uses a dedicated writable working directory. Do not commit tokens or generated state.

The public deployment binds the receiver to loopback and exposes read routes only through Caddy. `generate_data.py` can also print the synthetic CSV without a receiver. The dataset has no real orders or customer identifiers.

## Trading reports, history and freshness

The publisher seeds three **illustrative report editions** once: through December
2025, March 2026 and June 2026. Each edition contains complete reporting months.
These are fictional reporting periods, not backdated snapshot capture times.
Three snapshots are retained for the orders, four plots and trading report. The
small `.plotsrv/demo-publishing/retail-v1.json` journal makes setup resumable;
confirmed history is also inspected after interruption. Keep it with receiver state.

The dataset summary deliberately expects an update every five minutes,
warn after ten minutes and become overdue after fifteen. Other views do not use
these short thresholds. No recurring retail job is needed: the overdue status is
part of the demonstration and is explained in the report.

Northstar uses the existing homepage logo, bundled locally; clicking it opens
https://demo.plotsrv.com. Featured orders and trading-review entries have small local
screenshots and freshness checks disabled. Source-code views have been removed.
Republish with the command above after editing content; unchanged live/restored
views are reused.

View titles use plain business names. Earlier seeded snapshots identify their
reporting period; updating an older bundle publishes the clean current title once
without reseeding its history. Existing historical labels are left intact.
After an ordinary restart, unchanged prepared views can correctly show Restored
until they are published again; no recurring job runs just to clear that badge.

Dropdown descriptions are hidden with `ui-settings.show_view_descriptions: false`.
The **i / About this view** button retains the longer coworker explanations,
including on featured entries. The trading review uses a two-column category/sales
table that fits a narrow mobile screen.

## Operations logs

`serve.py` registers two static watched files in the receiver process: order
processing and fulfilment API access logs. They appear as compact entries in the
view selector. Text styling highlights timestamps/severity and HTTP requests.
Both use synthetic content, a 32 KiB read bound and memory materialisation; they
have no history/latest persistence. Only the existing file watcher polls for
changes. There is no log-writing process or report regeneration schedule.

The receiver restores all persisted published views before registering its logs.
SIGTERM/SIGINT shut down the receiver and watches together. A local health read
every 30 seconds detects a stopped background HTTP server so systemd can restart it.
