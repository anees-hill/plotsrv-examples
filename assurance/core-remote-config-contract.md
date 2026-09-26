# Remote, watch, admission and config contracts

PHASE-01 inspection, 2026-09-10. Reference: `/home/samane/Projects/plotsrv`,
HEAD `c4c86d230955af9dff6a1c9c766eeb340859ae43`. `PLOTSRV_CORE_DIR` was unset;
the sibling reference is the reference specified by the retained plan and prior
assurance notes. Core Git status was clean before and after inspection. Only
source/docs/tests were read: no core imports, tests, services or writes occurred.
Existing examples worktree changes were preserved. All source paths below are
relative to core. This is implementation input, not runtime acceptance evidence.

## Invocation and ownership

| Public invocation | Current behavior |
| --- | --- |
| `plotsrv serve --config receiver.yml --host 127.0.0.1 --port PORT` | Foreground receiver only; no target, AST scan, application import or publisher watch startup. Each explicit bind option overrides its config field; defaults are loopback:8000. |
| `ps.publish_view(value, view_id="remote:sample", destination=URL, launch_server=False, async_=False)` | Direct synchronous HTTP publication to an existing receiver. Returns no delivery acknowledgement. For keyed explicit routing use public `PublishTarget(kind="remote", base_url=URL, bearer_token_env="EXAMPLE_PUBLISH_KEY")`. |
| `plotsrv watch ./sample.txt --port PORT --view-id local:sample --tail` | Local watch/server workflow. Explicit legacy host/port overrides configured remote routing and credentials. |
| `plotsrv watch ./sample.txt --destination URL --view-id remote:sample --tail --every 0.1` | Foreground publisher-side capture, no receiver launch. For keyed explicit URL add `--bearer-token-env EXAMPLE_PUBLISH_KEY`. |
| `plotsrv publish --config publisher.yml --no-discovery` | Register configured watch/additional IDs, then run configured remote watches in foreground. Never executes application code or starts a server. |
| `plotsrv publish ./src --config publisher.yml --no-watch` | Static catalogue registration, then exits. Without explicit/configured target, publish does not scan cwd; `publish .` opts in. |
| `plotsrv publish ./src --config publisher.yml --seal-catalogue --add-id runtime:sample` | Explicit complete-union bootstrap. Normal registration never seals. `--reviewed` acknowledges unresolved/skipped scan issues, but cannot override cancellation/resource limits or duplicate IDs. |
| `plotsrv run ./src --config local.yml --mode passive --no-watch` | Static discovery and local serving; passive is the default. `--mode callable` explicitly executes application code and is unsuitable for the passive side-effect test. |
| `plotsrv config create --config generated.yml` | Creates config; existing file requires `--force`. Optional `--expanded`. |
| `plotsrv config populate limits ./src --config generated.yml --mode merge` | AST-derived view settings; merge preserves existing entries, replace replaces the relevant views mapping. Also supports `freshness` and `storage`. Run only in a disposable example project. |

Sources: `cli_parser.py:96,308,452`, `cli.py:1231`, `standalone.py:6`,
`publisher.py:861,945`, `publisher_agent.py:289,312`, `config_writer.py:217,282,314`.
`@ps.view` has no destination parameter: use configured routing or host/port.
Metadata-only decorators remain passive unless publishing options/configured
remote routing activate them at decorator evaluation.

## Precedence and path resolution

`settings.py:32-182`, `connection_config.py:32-193`, `source_setup.py:40-105`:

1. Explicit runtime/CLI config path wins over an existing-file `PLOTSRV_CONFIG`,
   then cwd `plotsrv.yml`, then cwd `plotsrv.yaml`. An invalid environment path
   is ignored by the resolver, so isolate environment and use explicit config in
   assurance. Config is cached per path in-process; use fresh subprocesses for
   precedence cases rather than assuming file edits reload settings.
2. Explicit runtime/CLI name wins over `PLOTSRV_NAME`. Selected instance mappings
   recursively overlay the section's `default` mapping (or flat global keys if
   no default mapping). An unknown name resolves globals; it does not fail merely
   because the instance is absent. `instances` and legacy `instance` are supported.
3. Explicit destination replaces configured destination **and credential**.
   A bare URL has no inherited key. Destination conflicts with explicit host/port
   or local launch. Explicit host/port or local-launch intent replaces configured
   routing; otherwise configured destination is remote, including with
   `launch_server=False`. Without routing, ordinary `publish_view` can launch an
   attached local server; therefore outage examples must specify remote intent.
4. Configured discovery filesystem paths and watch paths resolve beside selected
   config. Explicit CLI filesystem paths resolve from cwd. Module targets retain
   module identity and resolve statically from the appropriate lookup context.
5. `run` explicit target overrides only discovery target; explicit watch set
   replaces, not extends, configured watches. `--no-watch` disables them and is
   mutually exclusive with `--watch`. No target falls back to project discovery
   for `run`, but not `publish`. `serve` ignores publisher sources entirely.
6. `exact_selection`, when present, matches IDs only; empty means skip discovery.
   Otherwise legacy selection matches ID/label/section, with empty meaning all.
   Explicit `run --include` replaces configured selection; exclusions win.
   Selection does not filter watches or restrict active writes on a dynamic server.
   `additional_ids` adds reviewed logical IDs. Population respects destination
   config discovery selection and retains literal IDs even when labels differ.

## Routes, authentication and admission

`ingestion.py:106,210,240,445`, `app.py:1375,1885`, `remote_watch.py:383`:

- Shared transport negotiates authenticated `GET /capabilities` before payload
  capture; ordinary publication uses `POST /publish`. Catalogue routes are
  `POST /catalogue/register` and `POST /catalogue/bootstrap`. Watch routes are
  `POST /watch/register`, `/watch/update`, `/watch/close`; hosted bytes use
  `GET /watch/source?view=ID`. Reads for assurance are `/views`,
  `/artifact?view=ID`, `/table/data?view=ID`, and `/plot?view=ID` as appropriate.
- Server config uses `server-settings.ingestion.bearer_token_env`; publisher
  config uses `publisher-settings.destination.{url,bearer_token_env}`. Named
  environment variables contain synthetic matching values. Missing configured
  credentials fail closed. Wrong/missing key yields 401 `unauthorised_publisher`
  / `publisher_key_required` before parsing or mutation. Sending a key to an
  unkeyed server is also rejected, not downgraded to anonymous access.
- Anonymous ingestion is loopback-only unless `allow_remote_without_key` is
  explicitly enabled. Browser Origin mutation requests are denied. A publisher
  key does not protect dashboard reads or grant administration rights.
- `server-settings.admission.mode: catalogue-locked` with `allowed_ids` supplies
  the complete allowlist. Without that list, writes await explicit bootstrap:
  403 `catalogue_awaiting_bootstrap`. Unknown IDs after sealing yield 403
  `view_not_admitted`. Identical complete bootstrap is idempotent; different
  sealed manifests conflict (409). Discovery selection is not write admission.
- Explicit bearer destinations require HTTPS except loopback. Redirects are
  refused. Ordinary remote failure has no local fallback or anonymous downgrade;
  normal publication is best effort, debug mode may raise. A successful process
  exit or flush is not evidence of receipt. Inspect actual content for success,
  and rejection diagnostics plus absent denied IDs for rejection.

## Watch and discovery boundaries

`publisher_agent.py:58-267`, `remote_watch.py:60-358`, `discovery.py:284-437`:

Remote watchers require `watch-v2`, negotiate before capture, and upload bounded
content plus basename/provenance. Receiver requests cannot install a publisher
path as a local watch; path/policy fields are rejected. Remote `materialization:
file` still means publisher capture, unlike local lazy file-backed previews.
Use explicit logical IDs. Capture normally waits two admitted polls, minimum
poll cadence 0.1s; update limits also gate capture. Intermediate states may
coalesce. Missing/stopped sources retain last good content with changed status.
Status changes do not imply fresh data arrival. Full-source downloads exist
only for complete hosted bounded content, never arbitrary publisher files.

Relevant bounds: 256 KiB capture, 384 KiB watch request, 200 CSV rows/64 columns,
64 watched IDs, one active capture/transport job. A 60s ownership lease renews
every 20s; restart requires re-registration. Use bounded polling of recognizable
content, not fixed sleep or registration alone, as later scenario evidence.

Static discovery reads Python source and parses AST; module resolution does not
import parent packages or use import hooks. Literal supported declarations and
aliases are discoverable; dynamic metadata is unresolved, not executed. A
synthetic module/package side effect must remain absent during passive run,
publish catalogue scanning, and config population. Wizard internals are outside
this task; use existing noninteractive create/populate commands.

## Inspected core test evidence and later assurance requirements

Tests were read, not run:

- `test_connection_contracts.py:63,115,455`: routing/config precedence and remote
  failure with forbidden local startup, including redacted debug errors.
- `test_publisher_agent.py:32,70,126,171`: no-execution catalogue scan, explicit
  sealing, local versus remote watch dispatch, disjoint cwd restart/watch flow.
- `test_remote_watch.py:207,238,393`: filesystem-instruction rejection without
  file reads, auth/unknown-ID rejection, unavailable receiver before capture.
- `test_ingestion.py:108,126`: auth before body/mutation and exposure modes.
- `test_source_setup.py:50,142,258`: source precedence, module resolution without
  import hooks/application execution, selected literal IDs in population.
- `test_discovery.py` and `test_cli_config_cmds.py`: discovery and config command
  coverage inspected alongside scanner/writer implementation.

PHASE-02/03 own executable scenarios/tests. For CASE-01/02, different cwd alone
does not prove filesystem isolation: verify received content after making the
publisher source unavailable and inspect remote metadata; explicitly describe
loopback as split-process testing, not two-machine network testing. CASE-03/04
need rejection plus absence and a valid positive control. CASE-05 needs the
application result and evidence no unexpected listener/process was created.
CASE-06 needs discovered IDs and absence of synthetic side effects. CASE-07 and
INV-05 require unchanged core Git state. This phase informs INV-01 through INV-04
and CASE-01 through CASE-06 without claiming their behavioral acceptance.

No runtime candidate was executed/reconciled in this inspection unit. Later
runtime assurance must use existing candidate provenance checks. The requested
pytest suite, scenario runs and listener checks remain for implementation phases.
