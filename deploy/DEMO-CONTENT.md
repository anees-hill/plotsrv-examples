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
latest content without repeating the history. A changed content hash permits an
explicit updated publication. Source-code views are no longer published or admitted;
the previous bundle disabled their persistence, so they disappear on restart.

On scan restart, the startup job republishes the latest successful metrics from
`.plotsrv/scans-output/state.json`. This restores the check's evidence without
running another image audit. On first setup there is no previous state; the normal
initial audit populates the content. Calibration image SHEET-01 is intentionally
dim, so the warning `Scans require review` is expected. The report explains it.

Northstar's dataset summary and the import manifest warn after ten minutes and
become overdue after fifteen. These are the only deliberate short freshness checks;
featured entries have freshness disabled. Capture/publication timestamps remain
genuine. The scan demo retains its daily freshness thresholds and visible failed
quality check, with all views shown as normal entries.

## Watched logs and packaged assets

Northstar uses `demos/retail/serve.py`, launched by the instance unit
`plotsrv-demo@retail.service`. It starts the receiver with two small static watched
logs in the same process, capped at 32 KiB each with history/latest persistence off.
The receiver restores all published views before registering these watches. The
other receivers still use the ordinary service template. Change both receiver
unit files when changing shared resource limits; all existing limits are retained.

The exact logo, two logs and five preview PNGs are listed in `package.DEMO_ASSETS`.
Archive extraction accepts this explicit asset list. Featured screenshots are
captured during development and served locally; the VM never runs a screenshot job.
Portable configs remain beside relocated VM configs for operator reference, but
are no longer published as dashboard content. No credentials are expanded into them.

Generated reports remain bounded to 128 KiB and plot images to 1 MiB. Selected
history retains three snapshots (seven for scans). Stream persistence stays off.
Public read routes remain available; publication and control remain private.

## Validation and rollout

The new plotsrv Python formatting, watched-file identity/authentication and UI fixes
must be released to PyPI separately. The demo bundle does not contain plotsrv.
The installer resolves the latest stable PyPI version; deploying before publishing
that release will fail the feature preflight before activating the new release. Check the installed version in the
installer output and `/status` after rollout.


- Run the focused demo, installer, browser and rehearsal tests before packaging.
- Keep the previous release and writable state; build a new archive from the
  examples checkout. Install only in an agreed deployment window.
- Verify content oneshots completed, all expected views exist, and every logo
  links to `https://demo.plotsrv.com`.
- Run the short production ptop smoke rehearsal before the longer conference
  rehearsal. A successful local test does not measure VM/Cloudflare performance.

Normal read/restart testing does not require clearing history. For a deliberately
fresh **local test**, use an empty temporary working directory and receiver store.
Do not clear production storage to reseed the examples.

### Presentation update verification (October 5)

The focused content, configuration, packaging, installer and rehearsal checks
passed, along with six real receiver/browser checks across all three demos.
They cover restart restoration without new snapshot IDs, local thumbnail loading,
compact watched logs with text highlighting, source-view absence, scan check
visibility, browser sizing and real freshness transitions. The authenticated local
watch regression also verifies that a receiver does not send its logs to an
independently configured outbound publisher destination.

A fresh local 6 → 20 → 6 visitor rehearsal, including an HTML report update during
the burst, completed **917 operations with zero failures**. Peak receiver RSS was
approximately **207 MiB retail, 193 MiB imports and 193 MiB scans**. Stored content
remained about **1.28 MiB, 0.53 MiB and 0.06 MiB**, respectively. Existing history
counts stayed at three. This short development-machine run does not measure
production capacity or long-term memory behaviour. Systemd unit verification
also passed using temporary copies with harmless executable placeholders.

Core tests passed 2,636 checks in the full run. Four assertions about the former
stream order were updated and passed their focused rerun. Two multi-tab browser
checks crash Chromium here; the same two crashes reproduce on the unchanged
starting commit (`86ffe8d`). Mobile Chromium TOC checks pass. WebKit could not run
because its required system libraries are absent; physical iOS Safari still needs
a manual TOC check. No production services were changed by these tests.

### Earlier rehearsal (before this presentation update)

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
trusted HTML iframe, logo links, the then-present source display and scan-check popover. Real
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
