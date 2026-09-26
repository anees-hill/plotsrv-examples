# Current example API reconciliation

PHASE-01, 2026-09-10: source/doc/test inspection only. This is the migration
input for the focused examples and gallery, not evidence that they run yet.
Core reference: `/home/samane/Projects/plotsrv`, revision
`c4c86d230955af9dff6a1c9c766eeb340859ae43`; `PLOTSRV_CORE_DIR` was unset and
the sibling reference matches the existing lifecycle notes. Core Git status was
clean before and after inspection. No core imports, tests, or services were run.
Paths below are relative to that core checkout unless labelled legacy.

## Publication and lifecycle contracts

- `src/plotsrv/publisher.py:861`: `ps.publish_view` supports explicit
  `destination`, `launch_server`, `host`, `port`, `view_id`, `section`, `label`,
  `kind`, `artifact_kind`, and `async_`. For the external receiver use an explicit
  destination URL, `launch_server=False`, and `async_=False`. Destination and
  host/port cannot be combined. Avoid legacy `mode=local/remote/auto` aliases.
- `src/plotsrv/decorators.py:354`: `@ps.view` supports host/port and
  `launch_server`, but **does not accept destination**. Define active decorators
  where explicit runtime host/port are available. Metadata-only decorators do
  not publish on invocation. Functions retain their return values; decorated
  classes publish a JSON class/attributes description on construction.
  `tests/test_decorators.py` and `test_decorators_more.py:147` cover these
  distinctions. Do not use repeated decorated class construction merely to
  prepare data for another example: that produces extra publications.
- `docs/guides/python-api.md` identifies `publish_view` and `@view` as the
  primary APIs. `refresh_view` is an in-process compatibility helper; retain it
  only in an explicitly labelled local lifecycle demonstration.
- `src/plotsrv/server.py:811,890,945`: start uses a background thread;
  `auto_on_show=True` patches matplotlib show. Use explicit config and
  `restore_latest=False` for a fresh example. Put `stop_server(join=True,
  timeout=...)` in `finally`. `plot_session` is supported but exits with
  `stop_server(join=False)`, so it is not evidence of joined shutdown.
- Publication return/exit does not prove receipt. Publisher setup and transport
  exceptions can be swallowed outside debug mode (`publisher.py:861` and
  `tests/test_publisher.py:137`). Gallery verification must inspect receiver
  content. Keep the existing owned-process/provenance support for orchestration;
  keep actual plotsrv calls directly visible in example source.

## Renderer mapping

`docs/guides/renderers.md`, `publisher.py:125-205,342-433`, and
`tests/test_publisher.py:27-113` establish the public publication path:

| Representative input | Current publication result | Migration choice |
| --- | --- | --- |
| pandas / Polars DataFrame | table payload with columns, row records and counts | Keep both input libraries with small deterministic data. |
| matplotlib Figure / plotnine ggplot | plot PNG; plotnine is drawn to a Figure | Keep both constructors; close figures in cleanup. HTTP serialization also closes its rendered figure. |
| nested dict/list, heterogeneous list | JSON document artifact | Keep nested and heterogeneous shapes; builders receive dependencies explicitly. |
| NumPy array | JSON artifact through array conversion | Replace unseeded 5000-by-10 random output with a small deterministic array. |
| decorated class instance | JSON class/attribute description | Keep a distinct active class decorator demonstration. Ordinary objects otherwise fall back to Python representation. |
| text, markdown, HTML | artifact with explicit text/markdown/html subtype | Use `kind="artifact"` and `artifact_kind` when forcing a subtype; `kind="text"` is invalid. |
| Path | file content inferred by type | Use real `Path` values; a filename string publishes literal text. |

Do not infer HTTP publication behavior from private `render_any` probes:
`tests/test_renderers_default_registry_integration.py` shows raw registry string
selection can differ from the public publisher's text routing.

## Legacy purposes and supported modes

| Legacy source / purpose | Mapping for subsequent phases |
| --- | --- |
| `src/smoke-tests/python_objs.py` | Focused objects/tables/plots and explicit gallery composition. `get_mixed_objects_list` currently reads `planets`, `weather_observations`, `satellites` assigned only in `__main__`; replace those reads with arguments or local pure builders. |
| `src/launchers/python_api_smoke.sh` interactive | Extract direct HTTP publishing, active function/class decorators, and a separate attached lifecycle script. Set `auto_on_show=True` only for the actual patched-show demonstration (legacy interactive currently sets it false). |
| Same script passive / all | Passive watches are genuinely different from object publication. Preserve their purpose in watch/lifecycle coverage; `all` is only sequencing, not a distinct API mode. Do not add indefinite sequential waits to gallery. |
| `src/launchers/python-api/03-python-api-watch-limits.sh` | Extract Python lifecycle source and call object builders explicitly; eliminate its `runpy.run_module(..., run_name="__main__")` dependency. Detailed watch/limit assurance remains outside this phase. |
| `src/launchers/python-objs/00` through `05` | Same object scenario with different config/watch profiles, not six object implementations. Preserve minimal, limits, storage/freshness and security intentions in migration accounting without claiming those broader behaviors verified here. |
| `src/interactive_tests/manual_interactive_validation_1.py` | Replace network-fetched Titanic data with deterministic local data; retain explicit lifecycle/show and table input purposes. Private registry/store probes are not user-facing API examples. |
| `src/smoke-tests/python_objs_w_stream.py` | Its object portion currently executes the legacy gallery through runpy. Future reuse must call the explicit gallery entry point; stream assurance is deferred. |

Simple/rich are **still distinct**: `config.py:233,785` accepts both, and
`html.py:609` renders a read-only simple table or the rich explorer. Tests in
`test_config.py` and `test_table_plot_consolidation.py` document config and rich
explorer contracts. The setting is receiver-wide, not attached to each publish.
Publishing the same dataframe twice while switching only the external publisher's
setting cannot demonstrate two receiver modes. Remove that misleading variant;
if both presentations are retained, use explicitly separate receiver profiles.
Do not confuse these modes with rich explorer's browser Table / Plot + data tabs.

## Evidence to implement later

Use unique explicit view IDs and require all expected entries at `/views`.
For tables, `/table/data?view=ID` returns columns, row records, and counts
(`app.py:1021,1245`); assert recognizable values. For nested content inspect
`/artifact?view=ID` (`app.py:1809`) for expected rendered values. For plots,
`/plot?view=ID` (`app.py:932`) must return the expected image response, not merely
a catalogue entry. Browser interaction/appearance remains manual evidence.

PHASE-02/03 own implementation and behavioral validation, including
`uv run pytest -q assurance/tests`, the gallery inspection command, and compile
checks. None were run or claimed passed by this inspection unit. No legacy
paths were removed or wrappers changed in this phase; prior worktree changes
were preserved. This map addresses INV-02/INV-04 and informs CASE-04/CASE-05;
it does not establish integration acceptance.
