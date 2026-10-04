# Rehearse the public demos

This directory contains a **standalone, read-only visitor script** and two ptop
load descriptions. No plotsrv code changes or server publishing credentials are
required. Visitors run on your laptop; ptop records selected VM services over SSH.
One offline `report.html` combines both sides.

## First run

1. Build the recovered ptop checkout at `~/Projects/ptools/projects/ptop-nu` with
   `uv build`. Install that wheel into `~/.venvs/ptop-rehearsal` on the laptop and
   each monitored VM (see ptop's `LOAD-TESTING.md`). This can coexist with installed
   ptop 0.5.0; there is no need to replace it.
2. Copy this directory somewhere convenient. Edit **both TOMLs**: set the existing
   SSH alias and absolute remote ptop executable path. The supplied service list
   describes all three demos and Caddy on one VM. If they run on separate VMs,
   split services into separate `[monitors.NAME]` sections with each VM's SSH alias.
   Every selected service must be running. Continuous live writer/follower services
   can also be added; omit completed oneshot publisher jobs.
3. Validate without sending traffic:

   ```sh
   ~/.venvs/ptop-rehearsal/bin/ptop load plan smoke.toml
   ```

4. Run the **37-second smoke rehearsal** first:

   ```sh
   ~/.venvs/ptop-rehearsal/bin/ptop load run smoke.toml --output results/smoke-1
   ```

   Open `results/smoke-1/report.html`. Check all demos have measurements, services
   are visible, and there are no missing-metric warnings or proxy failures.

5. Run the **26-minute conference rehearsal**:

   ```sh
   ~/.venvs/ptop-rehearsal/bin/ptop load run conference.toml --output results/conference-1
   ```

   | Phase | Visitors | Duration |
   | --- | ---: | ---: |
   | Idle before | 0 | 1 minute |
   | One visitor | 1 | 2 minutes |
   | Normal | 6 | 5 minutes |
   | Burst | 20 | 1 minute |
   | Recovery | 6 | 12 minutes |
   | Idle after | 0 | 5 minutes |

   Visitors already present keep their connections across phases. The recovery
   phase spans the demos' normal ten-minute SSE connection lifetime. Final idle
   time lets you see whether memory settles after connections close.

Ctrl-C stops the rehearsal and preserves a partial report. ptop stops its visitors
and recorders; it does not restart or signal demo services. Its memory guard uses
existing systemd limits and does not introduce a new plotsrv memory limit.

## What each visitor does

Visitors are spread evenly across retail, live imports and scan audit using their
stable worker number. Each loads a demo page plus up to 40 same-origin static assets,
holds one `/updates` connection, and repeatedly reads demo content with a random
2–5 second pause between operations:

- **Retail:** table, PNG plot, Markdown guide and JSON summary.
- **Live:** stream data, status and summary.
- **Scans:** table, image artifact, observation, change note and bounded history.

Each visitor owns separate HTTP/SSE connections. SSE update and heartbeat events
are recorded; expected connection expiry reconnects with the last revision.
Unexpected disconnect, receiver identity change, invalid content, rate limiting,
Cloudflare challenge or HTTP error fails the visitor. The default ptop policy stops
the run on the first error and keeps the evidence. Dynamic content requests are
paced independently of SSE; this tests persistent subscriptions plus repeated
render reads without replaying the browser's exact refresh logic.

This is an **HTTP rehearsal**, not a browser test. It does not execute JavaScript,
measure rendering speed, simulate table interactions performed entirely in the
browser, or warm a browser cache. It starts at the individual demo origins, not the
static landing page. Public traffic goes through the ordinary Cloudflare route;
no random cache-busting parameters or relaxed protections are used. Cache response
headers, HTTP status and challenge errors remain visible in the report. All
visitors on one laptop share a public IP, so per-IP protection may affect results.

## Adjusting or debugging

Add `"--demo", "retail"` (or `live` / `scans`) to the TOML command to concentrate all
visitors on one demo. Edit phase durations/concurrency to try a smaller rehearsal.
For a longer memory check, extend `recovery` within ptop's four-hour run limit.
The default does not manufacture publications: normal demo jobs must be running
for the test to include changing content. A quiet demo exercises repeated reads
and open connections but says less about rebuilding after updates.

The script has no ptop dependency and uses Python's standard library:

```sh
python3 visitor.py --demo retail --duration 30
```

That command **does send real demo traffic**, for one visitor. `--help` does not.
For local fixtures, override `--retail-url`, `--live-url` or `--scans-url` and pass
`--allow-http`. Timeouts, pacing and expected SSE lifetime are configurable;
production defaults match the demo configuration. JSONL measurements go to stdout.

Rebuild a report from saved evidence with `ptop load report results/conference-1`.
Compare failure counts and p95 timings with CPU and memory across phases. A high
final memory value alone does not prove a leak: look for continued growth and
whether repeated rehearsals settle. A successful run supports this workload only;
it does not establish the VM's maximum capacity.

## Local verification

`python -m pytest assurance/tests/test_rehearsal.py` exercises all three journeys,
proxy failures, receiver restart, disconnect and SSE expiry against local fixtures.
No public demo is contacted by these tests. ptop has separate runner/recorder and
report tests. Real VM SSH permissions and production service names still need the
smoke rehearsal above.
