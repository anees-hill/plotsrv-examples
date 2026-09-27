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

The active log rotates at 1 MiB and keeps two older files, so disk use stays below about 3 MiB plus metadata. plotsrv follows the active pathname and can report uncertain continuity at rotation; old rotated files are not replayed. Receiver storage is disabled; stream history is deliberately short-lived. The `--count`, `--interval` and `--max-bytes` options support finite local checks.
