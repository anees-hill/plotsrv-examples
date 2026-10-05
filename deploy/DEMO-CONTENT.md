# Prepared demo content and startup

This update adds **no recurring report job**. Existing live events still arrive
every three seconds and scan audits still run daily. Each receiver wants a
`plotsrv-demo-content@NAME.service` oneshot, which waits for readiness and runs
`demos/restore.py NAME`. It remains active after success and runs again when the
receiver restarts. Its separate 320 MiB memory bound and lower CPU priority keep
preparation distinct from the receiver; existing receiver limits are unchanged.
The installer waits for this content job and verifies the expected read routes.

Retail and file-import publishers seed three illustrative editions only once.
Snapshot timestamps are genuine, not the dates of the fictional reports. Publishers
inspect confirmed history and maintain small per-demo journals in the writable
working directory under `.plotsrv/demo-publishing`. Do not delete these journals
on upgrades. Interrupted setup fills missing editions; ordinary restart restores
latest content and republishes missing source views without repeating the history.
A changed source/content hash permits an explicit updated publication.

On scan restart, the startup job republishes the latest successful metrics from
`.plotsrv/scans-output/state.json`. This restores the check's evidence without
running another image audit. On first setup there is no previous state; the normal
initial audit populates the content. Calibration image SHEET-01 is intentionally
dim, so the warning `Scans require review` is expected. The report explains it.

Northstar's orders and trading report warn after ten minutes and become overdue
after fifteen. This is intentional; source-code views have freshness disabled.
The report explains the shortened thresholds. Stored content may display plotsrv's
normal restored-state indicator after restart until another live publication.

## Packaged assets and public code

The archive includes `demos/publishing.py`, `demos/restore.py` and the exact
`demos/retail/northstar.svg` asset. Extraction allows these explicit additions,
without accepting arbitrary assets or directories. Runtime storage is relocated to
writable VM state. Before rewriting each config, `configure-state.py` preserves
its portable source as `plotsrv.source.yml` for the public code view. It never
copies credentials or resolves the token environment variables into that file.

The shared code view exposes only a fixed list of demo scripts and the source
config. Source files are bounded to 64 KiB and have snapshot/latest persistence
disabled. The core code renderer itself has a 64 KiB limit. Generated reports are
bounded to 128 KiB and images to 1 MiB; selected history retains three snapshots.
Stream persistence remains explicitly disabled. Public history reads and the new
live-demo plot/table reads are allowed; publication and control remain private.

## Validation and rollout

- Run the focused demo, installer, browser and rehearsal tests before packaging.
- Keep the previous release and writable state; build a new archive from the
  examples checkout. Install only in an agreed deployment window.
- Verify content oneshots completed, all expected views exist, and every logo
  links to `https://plotsrv.com`.
- Run the short production ptop smoke rehearsal before the longer conference
  rehearsal. A successful local test does not measure VM/Cloudflare performance.

Normal read/restart testing does not require clearing history. For a deliberately
fresh **local test**, use an empty temporary working directory and receiver store.
Do not clear production storage to reseed the examples.

### Local verification of this change

A short loopback rehearsal exercised 6 → 20 → 6 simultaneous visitors, including
an HTML report republication during the burst: **930 recorded operations, zero
failures**. Peak receiver RSS was about **199 MiB retail, 193 MiB imports and
193 MiB scan audit**. Selected histories remained at three snapshots; total stored
content was approximately **1.24 MiB retail, 0.54 MiB imports and 0.09 MiB scans**.

These measurements used the development machine and its current plotsrv checkout,
with 0.3–0.6-second visitor pacing. Recorder process metrics were real; systemd
cgroup memory/limits were unavailable in the local fixture and are explicitly
marked unavailable in the report. This does not verify VM limits, Cloudflare,
production service orchestration or long-term memory stability. Run the production
smoke rehearsal after deployment.

Browser tests exercised Chromium at desktop and mobile sizes, including the
trusted HTML iframe, logo links, source display and scan-check popover. Real
receiver tests confirmed restart restoration and stable snapshot IDs across
unchanged republishing. A controlled-clock test checked retail freshness at
publication, ten minutes and fifteen minutes without changing stored timestamps.

Systemd unit syntax and dependency ordering also passed `systemd-analyze verify`
using temporary unit copies with `/usr/bin/true` as the executable. This checks the
receiver/content-job relationships without starting services. The optional real
Caddy acceptance test was skipped because no `CADDY_DEMO_BINARY` was supplied.

### Deployment review follow-up

The installer now selects service files from the release being installed (or the
already installed release for a profile-only change). Rollback recognises older
releases without the prepared-content job and restores the original retail
publisher. Regression tests inject a failed deployment and verify this old-release
recovery. Archives missing the new content service are rejected before extraction.

New bundles include `deploy-plotsrv.sh` and ready-to-use `tooling/deploy`. Transfer
the complete bundle and follow `deploy/DEPLOYMENT-GUIDE.md`. The guide also covers
older bundles that need manual tooling extraction. Never reuse an old installer
against a newer archive.

At the October 4 review, a clean PyPI environment resolved **plotsrv 0.8.0**. Real receiver tests
passed publication, retained snapshots and restart restoration for all three demos
using that released package. It does **not** include the recent table-response and
encoded-artifact caching changes in the local plotsrv checkout. A demo bundle does
not ship plotsrv itself: publish a plotsrv release containing those changes before
expecting the VM update to gain their performance benefits. The earlier load
numbers above used the local checkout and must not be attributed to PyPI 0.8.0.

Publisher peak RSS measured separately with the clean PyPI environment was about
161 MiB for retail, 135 MiB for imports and 115 MiB for scans during initial
preparation. Repeated startup used approximately 128, 111 and 108 MiB respectively.
These are process RSS measurements, not a test of the VM's 320 MiB cgroup limits.
The real bundled Caddy binary also passed local proxy tests for bounded SSE,
continued ordinary reads, blocked write routes and static-site restrictions.
