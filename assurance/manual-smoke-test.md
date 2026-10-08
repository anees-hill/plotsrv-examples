# Manual functional smoke testing — plotsrv 0.8.0

Work through this from **plotsrv-examples**, with two terminals (or two SSH
sessions) and a browser.

The usual pattern is **Terminal A: server**, **Terminal B: publisher**. A
publisher no longer needs to start the server. Attached Python use is tested
separately below. You can work through selected sections; record omitted checks
as not run rather than passed.

Allow roughly 45–60 minutes for a first complete pass. Repeat the automated
suite after fixing a failure. These commands target a trusted local source
candidate; the installed-wheel check is a separate step at the end.

Release record:

- Tester/date:
- OS/browser/version:
- Terminal/version:
- Core revision and dirty state (attach `doctor.json`):
- Examples revision and dirty state:
- Automated report:
- Sections omitted and why:
- Failures/notes:

## To begin

Open two terminals in the **plotsrv-examples project root**. Activate the existing
virtual environment in both, just as in the old guide:

```bash
source .venv/bin/activate
```

If this is a new environment, first run these from the project root, then activate
it. This assumes the plotsrv checkout is beside plotsrv-examples:

```bash
uv sync --locked
uv pip install --python .venv/bin/python --editable ../plotsrv
```

Remove any old `PLOTSRV_CONFIG` or `PLOTSRV_NAME` overrides from previous testing.
The publishers below read the ordinary `plotsrv.yml` in their working directory.
The server selects its config with `--config`.

**Terminal A**, prepare the sample files and configs:

```bash
python -m plotsrv_examples doctor
python -m plotsrv_examples smoke-prepare
```

Expect: doctor says `ready`, with the intended plotsrv 0.8.0 checkout.
The second command prints a new test directory under `.plotsrv-runs`.

In **both terminals**, change into that directory. Substitute the printed directory
name in this one command:

```bash
cd .plotsrv-runs/run-REPLACE-WITH-THE-PRINTED-ID
```

**All manual commands below run from this directory**, unless a step says otherwise.
The `../../examples/` paths lead back to the examples in the project root.

**Terminal A**, set the default publisher config and optionally save the automated
baseline:

```bash
cp memory.yml plotsrv.yml
python -m plotsrv_examples doctor > doctor.json
python -m plotsrv_examples check release > release.json
```

- [ ] Doctor identifies the intended candidate.
- [ ] Release command exits 0; all **19 required scenarios** report `passed`.
- [ ] Keep the report. `manual_status: pending` is expected before browser checks.

Use **http://127.0.0.1:8101** throughout the main walkthrough. Stop each server
with Ctrl+C before starting the next. Keep the same browser profile and address
for persistence checks. The generated configs and test store are separate from
any existing repository config or store.

If testing over SSH, open a tunnel from your own machine:

```bash
ssh -L 8101:127.0.0.1:8101 user@your-test-machine
```

## Tables, plots, objects and browser settings — storage off

**Terminal A**:

```bash
plotsrv serve --config memory.yml --host 127.0.0.1 --port 8101
```

**Terminal B**:

```bash
cp memory.yml plotsrv.yml
python ../../examples/smoke/publish.py --port 8101 --version 1
```

Open **http://127.0.0.1:8101**.

Expect two tables with **1,200 rows and 20 columns**, a matplotlib plot, a
plotnine plot, text and HTML. Tables have IDs `smoke-pandas` and `smoke-polars`.
The first row has `id=1`, `group=alpha`, `amount=100`; the last has `id=1200`.

- [ ] Both tables show the same data and counts.
- [ ] Search for `alpha`; clear search afterwards.
- [ ] Add `group = alpha` and `amount >= 110` filters. Visible rows satisfy both.
- [ ] Sort by group, then amount using the table's multi-sort control.
- [ ] Hide several columns. Selected columns and their order are sensible.
- [ ] Change to the other table and back. Filters/column settings remain.
- [ ] Refresh the browser page. Filters/column settings remain.
- [ ] Reset the view. Search, filters, sorting and column changes clear as the UI
      indicates. Add filters again for the restart check.
- [ ] Navigate through the table pages; the final row is reachable after reset.
      Page count depends on the selected page size, so do not assume the old 50.
- [ ] Export → Complete published table; open the download and check all 1,200
      rows, headers and data.
- [ ] Export → Current filtered view. Check only matching rows and the visible
      columns in their current order; this is distinct from the complete export.
- [ ] Export both plots; open the downloaded images and check labels/content.
- [ ] Try plot fit/size, fullscreen, and Table / Plot + data controls.
- [ ] HTML shows `html-smoke`. The synthetic script does not alter the dashboard.

**Terminal B**, publish a different version:

```bash
cp memory.yml plotsrv.yml
python ../../examples/smoke/publish.py --port 8101 --version 2
```

Expect first-row `amount=200`, text `smoke-version-2`, and updated plot values.

- [ ] Manual refresh / Update now reveals the new content.
- [ ] Enable auto-refresh and publish version 3; observe live updates.
- [ ] While filters or plot controls are active, check the pending-update/refresh
      behavior and the UI's option for applying updates during interaction.
- [ ] No snapshot history is recorded with storage off.

**Terminal A**: Ctrl+C, then restart using the same command. **Terminal B**:
republish version 1.

- [ ] The empty server does not claim old content was restored.
- [ ] After republishing the same IDs, table filters/columns survive the server
      restart at the same browser origin.
- [ ] Reset still works.

After stopping the server:

```bash
plotsrv store --config memory.yml stats
plotsrv store --config memory.yml list
```

- [ ] No stored snapshots/latest content from this storage-off section.

For the broader object gallery, stop the memory server and start this config in
**Terminal A**:

```bash
plotsrv serve --config ../../configs/current/demo-ui.yml --port 8101
```

**Terminal B**:

```bash
cp ../../configs/current/demo-ui.yml plotsrv.yml
python ../../examples/gallery.py --port 8101
```

- [ ] Nested objects expand; mixed objects/arrays look understandable.
- [ ] Markdown, HTML and the three traceback styles are readable.
- [ ] Featured/compact entries, Grouped/A–Z, view pins and theme work.
- [ ] Theme/pins survive a browser refresh.

Stop this server before returning to the memory config in the next section.

## Direct/decorated publishing — synchronous and asynchronous

Restart Terminal A with `memory.yml` on 8101. In **Terminal B**, run each command
and inspect both tables afterwards:

```bash
cp memory.yml plotsrv.yml
python ../../examples/smoke/publish.py --port 8101 --version 1 --style direct

python ../../examples/smoke/publish.py --port 8101 --version 2 --style decorator

python ../../examples/smoke/publish.py --port 8101 --version 3 --style direct --async

python ../../examples/smoke/publish.py --port 8101 --version 4 --style decorator --async
```

- [ ] First-row amount changes to 100, 200, 300 and 400 respectively.
- [ ] Each publisher reports `drained: true`; independently verify the browser
      receives the corresponding version.
- [ ] Both plot backends and text remain usable.
- [ ] There is one view per stable ID, rather than duplicate views per run.

Async is bounded latest-state delivery; a successful drain does not promise
receipt of every intermediate publish. These finite commands test the final
received versions. Queue congestion/performance thresholds remain core tests.

## Continuous resource monitor

With the memory server running, **Terminal B**:

```bash
cp memory.yml plotsrv.yml
python ../../examples/resource_monitor/main.py \
  --destination http://127.0.0.1:8101 --samples 3 --history-size 60 \
  --interval 1 --duration 60
```

- [ ] Run for at least 60 seconds; pandas/Polars tables and CPU/memory plots update.
- [ ] Manual refresh and auto-refresh both work.
- [ ] Tables/plots describe the same measurements.
- [ ] No snapshot history with the memory config.

The old `--kind infer/explicit` and resource-monitor publishing-style flags are
retired. Use the dedicated publishing variants above for decorator/async checks.

## Storage, alternative root, history, restart and freshness

Stop Terminal A. Start the same server with **`storage.yml`** instead:

```bash
plotsrv serve --config storage.yml --host 127.0.0.1 --port 8101
```

The storage root is explicitly **`store/`**, rather than the repository's
`.plotsrv/store`. It retains the last **three snapshots per view**.

**Terminal B**: run these **one at a time**, waiting for the received version
before publishing the next:

```bash
cp storage.yml plotsrv.yml
python ../../examples/smoke/publish.py --port 8101 --version 1
python ../../examples/smoke/publish.py --port 8101 --version 2
python ../../examples/smoke/publish.py --port 8101 --version 3
python ../../examples/smoke/publish.py --port 8101 --version 4
```

- [ ] History contains up to three snapshots per published view; version 1 is
      eventually evicted after four successful distinct publications.
- [ ] Navigate old snapshots. Tables, text and plots match the selected version.
- [ ] Compare versions where supported; both sides identify their source/version.
- [ ] Return to latest and confirm version 4.
- [ ] After the last publication, freshness progresses through fresh, warning
      (about 10 seconds), and overdue (about 20 seconds).
- [ ] Restart the server **without publishing again**. Latest and snapshots return.
- [ ] Restored stale content does not become fresh merely because of restart.
- [ ] Publish again; freshness recovers and history updates.

Stop the server before inspecting/clearing storage:

```bash
plotsrv store --config storage.yml stats
plotsrv store --config storage.yml list
ls -la store

# Only this generated test store is selected by storage.yml.
plotsrv store --config storage.yml clear --all --yes
plotsrv store --config storage.yml stats
```

- [ ] Stats/list show stored content before clear and no stored content afterwards.
- [ ] Physical files are under the configured test root.
- [ ] Restart after clear: cleared views do not reappear.

Optional config variants (stop/restart between each):

- [ ] Use `no-freshness.yml`; publish and wait beyond 20 seconds. Freshness does
      not produce the enabled profile's stale transitions.

Optional timing check: snapshot **retention is count-based** in the current API.
`default_min_store_interval` controls how often snapshots may be written; it is
not an expiry timer. To test it, create a separate profile/store:

```bash
cp storage.yml interval.yml
```

Open `interval.yml` in your editor. In `storage-settings`, change:

```yaml
root_dir: interval-store
# Minimum time between snapshots of a view:
default_min_store_interval: 30s
```

Restart Terminal A with `interval.yml`. Publish versions 1 and 2 with the same
publisher profile, within 30 seconds, then publish version 3 after 30 seconds.

- [ ] Live content updates on each publish; snapshot count does not increase
      for the update inside the interval, then increases for the later update.
- [ ] Latest-state persistence is separate from snapshot history; do not assume
      snapshot cadence limits latest-state writes.

Age limits exist for retained stream records/raw blocks and are a separate
optional longer check, outside this deterministic smoke suite.

## Tracebacks — enabled and disabled at each end

Start Terminal A with `memory.yml`, then **Terminal B**:

```bash
cp memory.yml plotsrv.yml
python ../../examples/exceptions.py --port 8101
```

- [ ] Three traceback views: explicit, captured and decorated failures.
- [ ] Expand frames/context; content is readable and controls work.
- [ ] The synthetic messages correspond to the three publication styles.

Restart a **fresh** receiver with `no-tracebacks.yml` and repeat the command above
(publisher still enabled).

- [ ] No traceback body is displayed. An admitted/error entry may exist; that
      is not permission to display the blocked traceback.

Restart a fresh receiver with `memory.yml`, then publish with:

```bash
cp no-tracebacks.yml plotsrv.yml
python ../../examples/exceptions.py --port 8101
```

- [ ] No traceback views are sent by the disabled publisher.

Both sides matter. Old instructions that changed one shared config obscured
these two separate policies. To test traceback snapshots, use the storage
receiver and repeat the enabled publisher; inspect retained history.

## Watched files — formats, limits, head/tail and updates

Stop the receiver. **Terminal A**:

```bash
plotsrv run discovery --config memory.yml --port 8101 \
  --watch large.csv --watch-label large --watch-head \
  --watch small.csv --watch-label small --watch-head \
  --watch sample.json --watch-label json --watch-head \
  --watch sample.yml --watch-label yaml --watch-head \
  --watch sample.md --watch-label markdown --watch-head \
  --watch sample.html --watch-label html --watch-head \
  --watch-materialization memory --watch-every 0.5
```

Expect `watch:large` (1,200 rows), `watch:small` (99 rows), and four artifact views.
The empty discovery directory keeps this a focused file test.

- [ ] Both CSVs load, paginate, sort, filter, hide columns and reset.
- [ ] Raw CSV download matches the generated source; presentation exports match
      the selected browser presentation.
- [ ] JSON/YAML contain their fixture labels; markdown formats correctly.
- [ ] HTML displays `html-smoke`; its script cannot change the parent page.
- [ ] Add two filters to the small CSV, change views and return; filters persist.

For an explicit **trusted local HTML iframe sandbox** check, stop the server and
create a profile with sandbox tokens. This differs from the script-stripping
remote publication checked earlier:

```bash
cp memory.yml sandbox.yml
```

Open `sandbox.yml` in your editor. In `render-settings`, change:

```yaml
html_sanitize: false
html_sandbox: allow-scripts
```

Then start the watch:

```bash
plotsrv run discovery --config sandbox.yml --port 8101 \
  --watch sample.html --watch-label html --watch-head \
  --watch-materialization memory
```

- [ ] The local report uses an iframe with `sandbox="allow-scripts"` (inspect in
      browser developer tools). It can display HTML without gaining parent-page
      origin access; the synthetic `window.parent.smokeEscape` assignment fails.

Stop it, then restart the multi-file memory watch command above before continuing.

**Terminal B**: open `small.csv` in your editor. Change the first data row's
`amount` from **100 to 200**, then save the file.

- [ ] Small table updates to first-row amount 200; refresh behavior is clear.

Restart the same watch command with **`--watch-materialization file`**:

- [ ] CSV previews and downloads still work. Large-file metadata communicates
      any unknown count rather than claiming every row was scanned.

For byte-window checks, stop the multi-file server. **Terminal A**, head first:

```bash
plotsrv watch window.txt --config memory.yml \
  --port 8101 --label window --head --max-mb 0.0005 --materialization memory
```

- [ ] Shows `HEAD-SENTINEL`; excludes `TAIL-SENTINEL`.

Restart with **`--tail`** replacing `--head`:

- [ ] Shows `TAIL-SENTINEL`; excludes `HEAD-SENTINEL`.
- [ ] Limited source coverage is communicated.

For rendering limits, start the standalone server with **`bounded.yml`**, then
publish version 1 in Terminal B:

```bash
cp bounded.yml plotsrv.yml
python ../../examples/smoke/publish.py --port 8101 --version 1
```

- [ ] Table preview is bounded to 10 rows / 5 columns; text is truncated at the
      configured limit (80 characters). The UI explains the limitation.
- [ ] Limit-recovery controls work where offered and do not silently imply that
      a partial export includes omitted data.
- [ ] Restart with `simple.yml`: simple table presentation works; rich search,
      filters and browser plotting are unavailable as indicated by the UI.

## Stream views — watch records arrive, pause/resume and saved presentations

Restart Terminal A with `memory.yml` on 8101. Use a third terminal for the writer
while Terminal B follows a log (or run the writer after temporarily returning to
Terminal A's shell with an additional SSH session).

**Terminal B**:

```bash
cp memory.yml plotsrv.yml
python ../../examples/streams/follow_jsonl.py events.jsonl \
  --destination http://127.0.0.1:8101 --seconds 300
```

Wait for **`Registered; append records now`**, then **writer terminal**:

```bash
python ../../examples/streams/write_jsonl.py \
  events.jsonl --records 6
```

- [ ] Records appear while the follower is running.
- [ ] Pause the browser display; write another batch; resume and check behavior.
- [ ] Filter/search, column controls and saved presentations work.
- [ ] Raw records and interpreted views remain distinguishable.
- [ ] Stop the follower after the writer exits; session status becomes ended.

Repeat with `follow_http.py` and `write_http.py` on `http.log`, then
`follow_text.py` and `write_python_logs.py` on `python.log`.
The followers accept the same destination/seconds arguments; these two writers
take just the file path. Start each follower before its writer.

- [ ] HTTP batch has 200/500/404 requests, ordinary text and a traceback.
- [ ] Suggested request/error/latency presentations use appropriate records.
- [ ] Ordinary text and the unattributed traceback remain available in Raw stream.
- [ ] Python logs offer Recent log events, Warnings and errors, Events by level
      over time and Busiest loggers; unknown lines remain in Raw stream.
- [ ] Save a modified presentation, refresh, and check it remains available.

Existing bytes are skipped at attachment. Reuse a file only when deliberately
testing new appended content; a new filename gives a clean run. The finite
`run stream-* --inspect` scenarios are useful for static inspection, but their
writers have finished by the inspection window.

## Observed views — baseline, bad data, recovery and Changes

With the memory receiver running, **Terminal B**:

```bash
cp memory.yml plotsrv.yml
python ../../examples/observation/changes.py --port 8101 --interactive
```

At the prompt, enter **`healthy`**. Keep this publisher process running throughout
the section so it retains one publisher session.

- [ ] Open `smoke-observe:orders`: 12 supplied amounts, no observed missing values.
- [ ] Open `smoke-observe:metrics`: supplied errors=0 and processed=12.
- [ ] First observation has no comparable earlier Changes.
- [ ] Overview, Fields, Evidence, help and suggested presentations are usable.
- [ ] Evidence explains inspected coverage; source examples are off by default.

Enter **`failing`** in Terminal B and refresh/update:

- [ ] Metrics show errors=3. Changes show the supplied errors value changed 0 → 3.
- [ ] Orders show three observed missing amounts and the captured change.
- [ ] The application result remains 12; telemetry does not replace its result.

Enter **`recovered`**:

- [ ] Errors return to 0; Changes show 3 → 0.
- [ ] Observed missing amounts return to 0.
- [ ] Recent scalar history/suggestions communicate irregular receipt times.

Enter **`quit`**. Restart the script and enter healthy again:

- [ ] A new publisher session starts a new comparison boundary rather than
      presenting the old session as directly comparable.

For the ETL example with field/path selection and a separate exact aggregation,
keep the memory receiver running and use **Terminal B**:

```bash
python ../../examples/observation/etl.py --port 8101
python ../../examples/observation/custom.py --port 8101
```

- [ ] Sampled order evidence and application-supplied totals are clearly labelled.
- [ ] Selected batch metrics and the custom regional report are understandable.
- [ ] Sampled ranges/missingness are not presented as whole-dataset guarantees.

## Checks, attention and webhooks

Stop the previous server. Copy the storage profile:

```bash
cp storage.yml checks.yml
```

Open `checks.yml` in your editor and add these top-level settings:

```yaml
checks-settings:
  enabled: true
  rules:
    - id: errors
      name: Pipeline errors
      source: checks:metrics
      kind: state
      path: [errors]
      op: gt
      value: 0
      severity: critical
      notify: [local-sink]
webhook-settings:
  destinations:
    local-sink:
      url: http://127.0.0.1:8102/hook
```

**Terminal A**:

```bash
plotsrv serve --config checks.yml --port 8101
```

In a **third terminal**, activate the same environment, change into the same test
directory, and start the local webhook receiver:

```bash
python ../../examples/checks/sink.py --port 8102
```

**Terminal B**, publish the healthy baseline:

```bash
cp memory.yml plotsrv.yml
python ../../examples/checks/publish.py --port 8101 --state healthy
```

- [ ] Errors=0; the check is healthy.

Then publish a failure and an added table column:

```bash
python ../../examples/checks/publish.py --port 8101 --state failing --schema 2
```

- [ ] Critical attention appears; check details explain errors=3.
- [ ] Table has the added quality column; saved selections react sensibly to drift.
- [ ] History/Compare, snapshot arrows, focus and attention controls work.

Recover:

```bash
python ../../examples/checks/publish.py --port 8101 --state recovered
```

- [ ] Attention recovers; table schema returns; check history retains transitions.

Inspect the webhook receiver's recorded messages:

```bash
curl http://127.0.0.1:8102/status
```

- [ ] It received a triggered event and a recovered event. Local webhook delivery
      is separate from the dashboard's check state.

Stop both the plotsrv server and webhook receiver with Ctrl+C.

## Split publisher/server — file publication and remote watching

**Terminal A**:

```bash
plotsrv serve --config memory.yml --host 127.0.0.1 --port 8101
```

**Terminal B**, publish a file's content:

```bash
cp memory.yml plotsrv.yml
python ../../examples/watch/publish_file.py sample.md \
  --destination http://127.0.0.1:8101 --view-id remote:file
```

- [ ] `remote:file` shows the file's content on the receiver.

Follow changes in a file beside the publisher:

```bash
cp sample.md remote-sample.md
plotsrv watch remote-sample.md --destination http://127.0.0.1:8101 \
  --view-id remote:sample --head --every 0.5
```

Edit `remote-sample.md` in your editor, save, and inspect `remote:sample`.
Then delete just this copied file in your editor/file manager while the watcher
is still running.

- [ ] Changes arrive at the receiver.
- [ ] Missing-source status appears; the last received content remains available.
- [ ] The receiver keeps serving after the publisher is stopped with Ctrl+C.

For a two-machine check, bind the receiver to the intended network address and
replace `127.0.0.1` in the publisher destination with that machine's address.
Record this separately from the local test.

## Publisher keys and allowed view IDs

Stop the memory receiver. These example configs reference a synthetic key through
an environment variable, as an ordinary keyed plotsrv setup does.

**Terminal A**:

```bash
env EXAMPLE_INGEST_KEY=example-only-key plotsrv serve \
  --config ../../configs/current/keyed.yml --port 8101
```

**Terminal B**:

```bash
env EXAMPLE_PUBLISH_KEY=example-only-key python ../../examples/watch/admission_publish.py \
  --destination http://127.0.0.1:8101 --bearer-token-env EXAMPLE_PUBLISH_KEY \
  --view-id allowed:sample --text received-with-correct-key --report correct-key.json
```

- [ ] `allowed:sample` shows the received text.

Try the wrong key:

```bash
env EXAMPLE_PUBLISH_KEY=wrong-key python ../../examples/watch/admission_publish.py \
  --destination http://127.0.0.1:8101 --bearer-token-env EXAMPLE_PUBLISH_KEY \
  --view-id denied:sample --text must-not-arrive --report wrong-key.json --probe-rejection
```

- [ ] `wrong-key.json` reports HTTP 401; denied content is absent from the browser.
      A normal publisher exit alone is not proof of receipt.

Restart Terminal A with `catalogue.yml` replacing `keyed.yml`, using the same key.
Repeat the correct-key publication; then try an ID outside the configured allowlist:

```bash
env EXAMPLE_PUBLISH_KEY=example-only-key python ../../examples/watch/admission_publish.py \
  --destination http://127.0.0.1:8101 --bearer-token-env EXAMPLE_PUBLISH_KEY \
  --view-id unknown:sample --text must-not-arrive --report unknown-id.json --probe-rejection
```

- [ ] Allowed content arrives. `unknown-id.json` reports HTTP 403; unknown content
      is not admitted.

## Config creation, population and passive discovery

Stop the server. Create a separate config using the normal CLI:

```bash
plotsrv config create --config discovery.yml
plotsrv config populate limits ../../examples/decorated.py --config discovery.yml --mode merge
```

- [ ] The generated config is readable; population finds the literal
      `example-function` and `example-class` IDs. Review the prompt before writing.

**Terminal A**:

```bash
plotsrv run ../../examples/decorated.py --config discovery.yml --no-watch --port 8101
```

- [ ] Discovered entries appear before the publisher runs; scanning does not
      execute the decorated functions or create their content.

**Terminal B**:

```bash
cp memory.yml plotsrv.yml
python ../../examples/decorated.py --port 8101
```

- [ ] The function and class content now arrives.
- [ ] Explicit config selection works even though `plotsrv.yml` also exists.

## Receiver outage and recovery

Start the memory receiver on 8101. Publish version 1, stop the receiver, then
publish version 2 with the same command. Restart the receiver and publish version 3.

**Terminal B**, change only `--version` between runs:

```bash
cp memory.yml plotsrv.yml
python ../../examples/smoke/publish.py --port 8101 --version 1
```

- [ ] Unavailable publishing returns without crashing the application or starting
      a fallback server. While the receiver is stopped, the browser cannot connect.
- [ ] Restart alone does not promise an automatic retry of version 2.
- [ ] Version 3 arrives after a fresh explicit publish.

## Attached Python / patched show / local watch

Stop any server on 8101. Each command below starts and stops its **own attached
server**. Run one at a time, inspecting the browser during its 120-second lifetime:

```bash
python ../../examples/lifecycle.py \
  --config memory.yml --port 8101 --seconds 120 --mode publish

python ../../examples/lifecycle.py \
  --config memory.yml --port 8101 --seconds 120 --mode show

python ../../examples/lifecycle.py \
  --config memory.yml --port 8101 --seconds 120 --mode watch \
  --watch small.csv
```

- [ ] Publish mode displays the attached object.
- [ ] Show mode publishes the matplotlib figure through patched `plt.show()`.
- [ ] Watch mode displays the CSV and notices a change made from another terminal.
- [ ] Each server stops after the script exits; another command can reuse the port.
- [ ] Loopback-bound instances are available through your tunnel, without requiring
      public binding.

For your original interactive Python check, stop the attached script first:

```bash
cp memory.yml plotsrv.yml
python
```

At the Python prompt:

```python
import plotsrv as ps
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
ps.publish_view(df, view_id="manual-repl", launch_server=True,
                host="127.0.0.1", port=8101, async_=False)
# Inspect the browser, then publish an update:
ps.publish_view(pd.DataFrame({"a": [4, 5, 6]}), view_id="manual-repl",
                host="127.0.0.1", port=8101, async_=False)
ps.stop_server(join=True, timeout=5)
```

- [ ] The REPL remains usable, both versions arrive, and explicit stop releases
      the listener. Restarting with the memory profile does not restore data from
      the separate storage profile.

## Check the actual release wheel

Return to the **plotsrv-examples project root** for this section:

```bash
cd ../..
uv build --wheel --out-dir wheels ../plotsrv
python -m plotsrv_examples check wheel \
  --wheel-path wheels/plotsrv-0.8.0-py3-none-any.whl \
  > .plotsrv-runs/wheel-report.json
```

Adjust the wheel filename if the candidate version changes.

- [ ] Wheel check exits 0; report records artifact SHA-256 and installed version.
- [ ] Import comes from the fresh test environment, rather than the editable core.
- [ ] Received text/table/plot and packaged local JS/CSS all pass.

This command creates a separate environment, installs the wheel and its
dependencies, and checks a fresh receiver. Dependency installation may use the
network. It does not claim to run the full source assurance suite against a wheel;
the source identity gate remains explicit. The temporary installed environment
is removed after the check; the diagnostic workspace remains and can be cleaned
with `workspace-clean` from the project root. Retain the installed dependency
versions in the report alongside the wheel hash.

## Finish

- [ ] Required manual rows above passed, or omitted rows have a recorded reason.
- [ ] Record browser failures independently of automated results.
- [ ] Retain doctor, release and wheel reports with the tested candidate identity.
- [ ] Stop servers/followers before cleanup; keep diagnostics needed for failures.

Optional cleanup, from the examples project root: replace the path below with
the absolute test directory printed at the beginning.

```bash
python -m plotsrv_examples workspace-clean /absolute/path/to/the/printed/test-directory
```

Copy useful reports elsewhere first; cleanup removes the generated contents.
Core regression tests and performance benchmarks remain separate release checks.
