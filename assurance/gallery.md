# Focused examples and gallery

Run after the candidate setup and doctor described in the root README:

```bash
uv run --no-sync python -B -m plotsrv_examples run gallery
uv run --no-sync python -B -m plotsrv_examples run gallery --inspect
uv run --no-sync python -B -m plotsrv_examples run gallery --inspect --inspect-seconds 300
```

The source-checkout gallery runs `examples/gallery.py` in a separate publisher
process against a new owned loopback receiver. It uses an explicit memory-only
config with traceback rendering enabled, isolated cache directories and no core
bytecode writes. The JSON report records runtime/reference provenance, receiver
content checks, child exits, and `manual_status: pending`. There is no automatic
browser launch. Inspection defaults to 30 seconds, with Ctrl+C returning 130
after owned-child cleanup. Generated state is retained under `.plotsrv-runs/`
for the existing workspace-clean command. This command requires the repository's
`examples/` and fixtures; they are not included in the distribution wheel.

The 18 expected views include nested/mixed objects, an array, pandas and Polars
tables, matplotlib and plotnine plots, function/class decorators, direct and async
updates, three exception styles, JSON file content, text, markdown and HTML.
Checks require view IDs/kinds, rendered artifact sentinels, exact table rows and
valid decoded PNGs. A fresh receiver with storage disabled prevents old content
from satisfying these stable example IDs. Plot appearance and browser controls
are not certified by PNG decoding. Async publication remains latest-state,
best-effort behavior; it does not assure delivery of every intermediate update.
The owned receiver uses `configs/current/demo-ui.yml`, so the published planet
table and plot appear as Featured views and the text/HTML views are compact.
The scenario also checks that the resulting page contains the configured title
and view-browser entries.

An intentional zero-exit publisher with no content must fail:

```bash
uv run --no-sync python -B -m plotsrv_examples run gallery --fault missing-evidence
uv run --no-sync python -B -m pytest -q assurance/tests
uv run --no-sync python -B -m compileall examples src
```

## Standalone usage

In one terminal start an existing receiver:

```bash
uv run --no-sync plotsrv serve --host 127.0.0.1 --port 8000 --config configs/current/minimal.yml
```

Then select a focused script in another terminal:

```bash
uv run --no-sync python -B examples/direct.py http://127.0.0.1:8000
uv run --no-sync python -B examples/decorated.py --port 8000
uv run --no-sync python -B examples/objects.py http://127.0.0.1:8000
uv run --no-sync python -B examples/async_live.py http://127.0.0.1:8000
uv run --no-sync python -B examples/files.py http://127.0.0.1:8000 mock-files/json-1.json
```

`examples/exceptions.py --port 8000` additionally requires
`security-settings.tracebacks_enabled: true` in both receiver and publisher
configs; select the latter with `PLOTSRV_CONFIG`. Normal core publication may
swallow delivery errors, so standalone exit zero alone does not prove receipt.

The lifecycle script owns its server; choose an unused port:

```bash
uv run --no-sync python -B examples/lifecycle.py --config configs/current/minimal.yml --port 8101
uv run --no-sync python -B examples/lifecycle.py --config configs/current/minimal.yml --port 8101 --mode show
uv run --no-sync python -B examples/lifecycle.py --config configs/current/bounded.yml --port 8101 --mode watch --watch mock-files/table-small.csv
```

These modes publish an attached object, invoke patched `plt.show`, or watch a
file. They are distinct behaviors. Simple/rich are receiver-wide table settings,
not per-publication variants; the bounded config selects simple and minimal
defaults to rich. No script toggles publisher settings and mislabels duplicate
remote tables as different modes.

## Legacy decisions

| Old entry | Current behavior / replacement |
| --- | --- |
| `src/smoke-tests/python_objs.py` | Small adapter to `examples/objects.py`; preserves HOST/PORT environment choices, publishes to an existing receiver. |
| `python_objs_w_stream.py` | Calls that adapter explicitly; no runpy dictionary or __main__ state. Stream behavior otherwise unchanged and not assured in this slice. |
| `src/launchers/python-objs/00-python-objs.sh` | Thin bounded gallery inspection launcher; accepts gallery flags. Old watch profiles are not implied. |
| `01` through `05` object launchers | Exit 2 with migration guidance. Their watch/limits/storage/freshness/security profile intentions remain recorded in legacy-map.md for their respective assurance work. |
| `src/launchers/python_api_smoke.sh` | Thin lifecycle launcher; use `--mode publish/show/watch`, not legacy positional passive/interactive/all. Direct/decorated/async steps are focused scripts above. |
| `src/launchers/python-api/03-python-api-watch-limits.sh` | Exit 2 with separate lifecycle watch and object-publisher commands. No heredoc/runpy execution. |
| `src/interactive_tests/manual_interactive_validation_1.py` | Gallery inspection adapter with deterministic data; downloaded Titanic data and duplicate remote table-mode stages removed. |
| Legacy traceback scripts | Focused replacement is `examples/exceptions.py`; old scripts retained pending broader security/watch-launcher reconciliation. |

## Manual inspection checklist

Run the inspection command above. Record tester, date, browser and the report's
core revision with the observations. All items start pending:

- Check nested expansion, heterogeneous object representation and array layout.
- Check table search/filter/sort and Table / Plot + data controls in rich mode.
- Check matplotlib/plotnine labels, fit/size controls and fullscreen behavior.
- Check markdown/HTML rendering and exception presentation.
- Check Featured cards, compact entries, Grouped/A–Z navigation, pins and theme.

This is a reconstructed checklist, not the unavailable historical manual release
checklist. Core reference for this implementation: revision
`c4c86d230955af9dff6a1c9c766eeb340859ae43`; use live doctor/report provenance for
each new run. No stream, observe, storage/restart or resource/weather assurance
is claimed here.
