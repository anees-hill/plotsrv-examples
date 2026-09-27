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

Open `http://127.0.0.1:8101/`. The receiver persists a single latest copy per view for restart under `.plotsrv/retail` relative to its working directory. That directory is git-ignored. The deployment service uses a dedicated writable working directory. Do not commit tokens or generated state.

The public deployment binds the receiver to loopback and exposes read routes only through Caddy. `generate_data.py` can also print the synthetic CSV without a receiver. The dataset has no real orders or customer identifiers.
