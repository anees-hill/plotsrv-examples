# Retail exploration

A deterministic fictional outdoor shop. The 1,680-row orders table is meant to be explored directly; four plots help with the same questions. There are intentionally discoverable patterns in returns, margins, fulfillment and seasonality.

From the examples checkout, with plotsrv installed in `.venv`:

```sh
export PLOTSRV_RETAIL_TOKEN="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uv run --no-sync plotsrv serve --config demos/retail/plotsrv.yml
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

Orders and the trading report deliberately expect an update every five minutes,
warn after ten minutes and become overdue after fifteen. Other views do not use
these short thresholds. No recurring retail job is needed: the overdue status is
part of the demonstration and is explained in the report.

Northstar uses the existing homepage logo, bundled locally; clicking it opens
https://plotsrv.com. The **Demo source code** section displays the publishing files
and portable config without resolving token environment variables. Source views
have no snapshot history. Republish with the command above after editing content;
unchanged live/restored views are reused.
