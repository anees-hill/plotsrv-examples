# Daily document-scan audit

This job creates ten small synthetic JPEG documents, measures their pixels with Pillow, publishes a table and an actual JPEG, then exits. Its `observe=True` view describes the **current** run. A separate Markdown view compares with the prior successful date; plotsrv does not compare observation sessions across separate daily processes.

From the examples checkout, start the receiver:

```sh
export PLOTSRV_SCANS_TOKEN="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uv run --no-sync plotsrv serve --config demos/scan_audit/plotsrv.yml
```

Run the job in another terminal using the same token:

```sh
export PLOTSRV_SCANS_TOKEN=... # the same value
PLOTSRV_DEBUG=1 uv run --no-sync python -B demos/scan_audit/run_audit.py --date 2026-09-27
PLOTSRV_DEBUG=1 uv run --no-sync python -B demos/scan_audit/run_audit.py --date 2026-09-28
```

Open `http://127.0.0.1:8103/`. The generated files live under `.plotsrv/scans-output` in the working directory; the job retains the latest three image batches. The receiver keeps at most seven snapshots per view under `.plotsrv/scans-receiver`; production must additionally enforce a filesystem quota. The state file advances only after publishing succeeds. If a job fails, the prior published report remains visible until the next successful run.

The measurements are simple rules for demonstrating episodic work, not a real document-quality standard. No model, dataset or external image is downloaded.
