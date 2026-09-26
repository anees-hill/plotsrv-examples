# Current representative configs

The limits profiles were first inspected against plotsrv 0.7.0 at
`c4c86d230955af9dff6a1c9c766eeb340859ae43`. The current 0.8.0
reconciliation is recorded in [the core review](../../assurance/current-core-review.md).
Current setting values are checked against the selected candidate by
`assurance/tests/test_current_configs.py`.

`minimal.yml` demonstrates bounded previews without persistence. `bounded.yml`
adds rendering, watched-file admission, storage retention settings (disabled),
and freshness. Use an absolute `--config` path to select one explicitly.
Both use preferred `limits.truncate_after`, `limits.published_objects`,
`limits.watched_files.max_mb`, and `freshness-settings.overdue_after` keys.
Superseded legacy profiles are retired. Root `plotsrv.yml` is a memory-only
compatibility default for external core smoke.

`keyed.yml` requires the synthetic example credential named by
`EXAMPLE_INGEST_KEY`. `catalogue.yml` additionally locks ingestion to the complete
configured allowlist `allowed:sample`. Neither profile stores credential values
or enables persistence. The receiver bind port can be overridden with `--port`.
Run `uv run --no-sync python -B -m plotsrv_examples run admission` for positive publication,
wrong-key rejection and unknown-ID rejection with independent receiver checks.
See [remote/config assurance](../../assurance/remote-config.md) for exact commands,
outage checks, and disposable AST/config workflows.

`demo-ui.yml` is a memory-only gallery profile with page/header text, two
Featured views, and two compact entries. Run the gallery's owned scenario to
see it with matching published view IDs. Browser pins, Grouped/A-Z navigation,
theme, saved presentations and other controls are user actions, so inspect
them in the browser rather than setting them through the config file.

Core YAML loading accepts unknown keys, so parsing alone is insufficient:
`assurance/tests/test_current_configs.py` also checks effective getter values.
Storage-enabled execution uses the owned `storage-history` scenario; these source
templates do not create state when inspected.
