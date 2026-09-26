# Current core lifecycle reference

PHASE-01 inspection (2026-09-10). This records source inspection and runtime
provenance, not integration acceptance. No receiver or publisher was launched.

## Compatibility

`PLOTSRV_CORE_DIR` was unset; the existing doctor selected sibling
`/home/samane/Projects/plotsrv`. Reference and editable runtime both resolve to
that checkout, revision `c4c86d230955af9dff6a1c9c766eeb340859ae43`, branch
`0-8-0-green-sprint-1`, clean working tree, declared/distribution version `0.7.0`.
`uv run python -m plotsrv_examples doctor` exited 0 with `readiness: ready` and
`relationship: matching source checkout`. Version alone is insufficient evidence:
future runs must repeat provenance checks before starting children and fail with
a useful diagnostic on a material mismatch or unavailable candidate/reference.

`uv run plotsrv serve --help` exited 0 and confirmed the options below. Core's
root help omits serve/publish, although its full parser implements them. There is
no `plotsrv/__main__.py`: do not assume `python -m plotsrv` works. The installed
console entry point is `plotsrv.cli_entry:main`; that module also supports
`python -m plotsrv.cli_entry`, allowing the runner to use its own interpreter.

## Receiver and publisher

- `src/plotsrv/cli_parser.py:112`, `cli.py:1231`, and `standalone.py:6`:
  `plotsrv serve --host 127.0.0.1 --port PORT --config ABSOLUTE_CONFIG --quiet`
  loads explicit runtime configuration and runs Uvicorn in the foreground,
  without application discovery/execution. Its printed waiting message precedes
  binding and is not readiness. Storage restore occurs before serving: use an
  owned working directory and explicit memory-only configuration (the existing
  `configs/current/minimal.yml` disables storage). Isolate publisher configuration
  too; `settings.py` recognizes `PLOTSRV_CONFIG` and `PLOTSRV_NAME`.
- `publisher.py:861`: public `plotsrv.publisher.publish_view` accepts an explicit
  `destination`, `launch_server=False`, `async_=False`, `view_id`, `section`,
  `label`, and `kind`. An explicit destination targets an existing receiver,
  never starts a fallback, and cannot be combined with host/port. A small text
  publication with a unique logical view ID and safe ASCII sentinel is suitable
  for the first scenario. Use synchronous publication to avoid background drain
  ambiguity. Ordinary API errors can be swallowed unless debug is enabled;
  application exit 0 and the API's `None` return do not prove delivery.
  PHASE-03 additionally inspected payload dispatch (`publisher.py:342`): text
  uses `kind="artifact", artifact_kind="text"`, not `kind="text"`. The latter
  produced exit 0 without a view and was rejected by the real evidence wait.
- `publisher_agent.py:312`: CLI `publish` registers a discovered/configured
  catalogue through `/catalogue/register` (or explicit bootstrap), then watches
  configured files. Without watches it returns 0 after registration. It does not
  execute a discovered callable or prove any artifact was published. The first
  scenario should run a separate Python publisher invoking the public API.

## Readiness and publication evidence

- `app.py:725`: GET `/status` returns a JSON object with `view_id`, service info,
  queue statistics and data activity. `?view=ID` selects a logical view. A 200
  status alone proves neither process ownership nor expected content.
- `app.py:1885`: GET `/views` returns a JSON list, with each entry containing
  `view_id`, `section`, `label`, `kind`, freshness and other metadata. Require the
  exact unique view identity, not merely a nonempty catalogue.
- `app.py:1809`: GET `/artifact?view=ID` returns rendered artifact JSON, including
  HTML; it returns 404 when no artifact exists. Require the scenario sentinel in
  the expected artifact content in addition to the matching logical view.
  These observations must be bounded by deadlines and checked alongside owned
  receiver liveness. Missing/malformed evidence must fail nonzero.

## Shutdown and ownership implications

`server.py:984` implements POST `/shutdown`, disabled by default (404), and
requires a direct local request when enabled. It schedules a service stop hook;
`standalone.py` connects that hook to Uvicorn's `should_exit` and runs
`stop_server(join=True)` in `finally`. HTTP shutdown is not a safe ownership
primitive: never send it to an unverified listener. Prefer signalling and reaping
the runner's own foreground child, with bounded escalation restricted to owned
processes. Never kill a PID discovered from a port. A busy-port preflight is only
a diagnostic because a bind race remains; readiness must also account for child
exit. Drain both output streams continuously with bounded retained logs.

Later phases must exercise real publication, missing evidence, startup failure,
busy unrelated ports, high output, and interruption cleanup. None of those
behavioral cases is claimed as passed by this inspection. Existing unrelated
working-tree changes were preserved; core was inspected without edits.
