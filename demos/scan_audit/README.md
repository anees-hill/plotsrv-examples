# Daily document-scan audit

This job creates ten small synthetic JPEG documents, measures their pixels with Pillow, publishes a table and an actual JPEG, then exits. Its `observe=True` view describes the **current** run. A separate Markdown view compares with the prior successful date; plotsrv does not compare observation sessions across separate daily processes.

From the examples checkout, start the receiver:

```sh
export PLOTSRV_SCANS_TOKEN="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uv run --no-sync plotsrv serve --config demos/scan_audit/plotsrv.yml
```

Run the job in another terminal using the same token. For a fresh local output directory, these two runs seed yesterday and today so the comparison is immediately visible:

```sh
export PLOTSRV_SCANS_TOKEN=... # the same value
audit_yesterday=$(uv run --no-sync python -c "from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) - timedelta(days=1)).date())")
uv run --no-sync python -B demos/scan_audit/run_audit.py --date "$audit_yesterday"
uv run --no-sync python -B demos/scan_audit/run_audit.py
```

For subsequent runs, omit `--date` to use today in UTC. Do not seed yesterday into a directory already containing a successful run from today; older dates are deliberately rejected. The scheduled service always uses the current UTC date.

Open `http://127.0.0.1:8103/`. The generated files live under `.plotsrv/scans-output` in the working directory; the job retains the latest three image batches. The receiver keeps at most seven snapshots per view under `.plotsrv/scans-receiver`; production must additionally enforce a filesystem quota. The state file advances only after publishing succeeds. Views publish independently: a failed job can leave mixed dates. Each view identifies its run, and the completion Markdown updates last, after observation delivery succeeds. Retrying the same date republishes the complete batch without changing its prior-run comparison. Failed batches count towards the three-directory bound too; unrelated directories are preserved. Do not run this job concurrently against the same output directory.

`job-status.json` records running, succeeded or failed locally. The systemd job waits for receiver readiness and retries failures at five-minute intervals (at most four starts in two hours). Check `systemctl status plotsrv-demo-scan-audit` and its journal after a failure. The dashboard marks results stale after 26 hours and overdue after 48 hours; inspect the completed-audit view because a partly published table may have a newer timestamp.

The measurements are simple rules for demonstrating episodic work, not a real document-quality standard. No model, dataset or external image is downloaded.

## Visible quality check

SHEET-01 is an intentionally dim calibration image. The real pixel audit detects
it, and the `Scans require review` state check evaluates `review_count > 0` in the
published `scans:metrics` JSON view. The warning is intentional; successful job
completion means all scans were inspected, not that every image passed.

The completed report contains scan/flag and comparison tables, review priorities
and measurement thresholds. The first report remains useful before a previous run
exists. The daily schedule and seven-snapshot retention are unchanged.

All scan views are normal entries, with no featured or source-code section.
The plotsrv logo links to https://demo.plotsrv.com. On receiver restart,
`demos/restore.py scan_audit` resubmits the last successful metrics so the check can
re-evaluate actual evidence; restored snapshots alone do not trigger checks.
