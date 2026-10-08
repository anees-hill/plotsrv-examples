# Local validation record — 27 September 2026

This records what was actually checked on the development host. It is **not** a capacity certificate or evidence of an internet deployment.

## Functional and boundary checks

- The existing and new Python test suite passed: **152 tests** (`.venv/bin/python -B -m pytest -q`). New checks cover deterministic retail patterns, JSONL log-profile recognition and file rotation, generated JPEG defects, the landing page's checked-in assets, and loopback/catalogue-locked receiver settings.
- Local receiver runs accepted all seven retail views, five live-import records, and two daily scan reports. The live page displayed **Python application log** detection and **four suggested views**. The scan receiver served its table, JPEG artifact, observed summary and explicit previous-run comparison.
- Retail and scan receiver processes were restarted without rerunning their publishers. Both restored their table views from their bounded storage directories.
- The pinned Caddy v2.10.2 build included `http.handlers.rate_limit`; its Caddyfile adapted successfully. In a local HTTP-only version of that configuration, the static landing page and retail table returned 200, `/retail` returned a 302 to a dedicated hostname, and public `/publish`, `/docs` and retail `/history` returned 404. After changing the dedicated hostnames to first-level `*-demo.plotsrv.com` names, the rebuilt Caddyfile again served the landing page, redirected `/retail` to `retail-demo.plotsrv.com`, and blocked public `/publish`. These were harmless local route checks with synthetic data, not tests of Cloudflare or a deployed origin.
- The three landing-page preview PNGs were captured in a local headless browser from those actual running demos. The static page was also opened in that browser.

## Limited local resource observations

With three populated receivers, a live follower and a continuous writer running together, their combined measured proportional set size was **436.2 MiB**: retail receiver 141.6, live receiver 133.6, scan receiver 136.3, follower 16.8 and writer 7.9 MiB. The short scan audit job's sampled peak was another **116.5 MiB PSS** before it exited. These figures exclude Caddy, the OS, Python installation files, filesystem cache, reverse-proxy connection buffers and visitor traffic. PSS from this development host must not be added directly to a 1 GB VM budget without a VM measurement.

Five sequential, direct local reads of the populated retail receiver had median response times of **3.2 ms** for `/`, **35.5 ms** for the 425 KB orders table payload, and **1.3 ms** for one 45 KB plot. This is a tiny, unloaded sample on different hardware; it says little about a one-core burst.

## Release gates still open

- No public hostname, Cloudflare zone, origin certificate, VM firewall or systemd service was changed. The Caddy template has not been exercised with Cloudflare's proxy, TLS, streaming behavior or real visitor IP headers.
- No multi-day soak, actual 1 GB VM measurement, 50-person conference rehearsal or internet-facing test was run. The earlier security constraint ruled out uncontrolled load testing, and no deployment target was provided. Complete these as bounded, explicitly scheduled staging checks before advertising capacity.
- The source links on the landing page point at `main` on GitHub. They will resolve to these new folders only after the local commits are published to that repository.
- The Caddy rate rules are initial values. They may reject legitimate attendees sharing a conference IP; adjust only from measured staging behavior. The 128 active-request ceiling protects each receiver but cannot prevent one source from occupying its stream slots.

## Reliability follow-up — 27 September 2026

The following supersedes the earlier proxy limits and Caddy version above:

- Caddy **v2.11.4**, built with Go **1.27.1** and the pinned rate-limit module,
  built successfully and adapted the full production Caddyfile.
- The committed optional proxy regression passed against that binary. It uses
  two loopback SSE connections with reduced test limits: per-client/global
  admission rejects additional streams, ordinary table/status reads still work,
  expiry releases slots and reconnection succeeds. A reduced static budget also
  returns 429 without blocking dynamic reads. Publishing, docs and retail history
  remain blocked. This is a bounded functional test, not a load test.
- All three demo YAML files now limit SSE to 96 total, 64 per client and 600
  seconds. Caddy retains the shared 128-request allowance. Static assets and
  dynamic reads use separate rate budgets. Lifetime enforcement belongs to
  plotsrv; the ineffective Caddy SSE `stream_timeout` was removed.
- A fresh scan receiver accepted two daily runs and a same-date retry. All four
  outputs returned 200; state kept the original previous-day comparison and the
  completion view reported the configured freshness thresholds. Failure tests
  verify bounded failed batches, unchanged successful state, and withholding the
  completion view when observation delivery fails.
- Synthetic scan tests check rotation measurements across 14 days; a separate
  retail test distinguishes order return rate from quantities sold.
- Readiness tests cover temporary HTTP failure, malformed capability data,
  token forwarding and redirect refusal, using only a local synthetic server.
- `systemd-analyze verify` found the expected absent `/opt/plotsrv-examples`
  executables on this development host; the real service sandbox has not been
  executed here. The installation checker and documented transient-unit check
  must still run on the actual VM.

Source links still require publishing the commits. Cloudflare/TLS, actual 1 GB
capacity, multi-day soak, operator alert delivery and the conference shared-IP
rehearsal remain deployment gates. No external service was tested or changed.

Final test results: **157 passed, 1 skipped** in the complete examples suite;
that optional proxy test then **passed separately** with the built Caddy binary.
The affected core configuration, SSE and response-cleanup suite passed **79 tests**.


## Deployment workflow update — 2 October 2026

- Hosted scope remains retail, live imports and scans; Markdown and weather remain
  source examples. The guide now covers all three plus the landing page on one VM,
  then retail/landing plus two temporary single-demo VMs for the conference, and
  moving back afterwards. The scans transfer preserves both receiver history and
  audit output/state while writers are stopped.
- `render-caddy.py` selects complete site blocks from the existing Caddyfile,
  retaining the global options, shared headers, public read restrictions and
  landing redirects. Tests cover all four deployment profiles, byte preservation
  of selected site blocks, and rejection of invalid/empty CLI selections.
- The dedicated demo environment installs unpinned plotsrv from PyPI and the small
  direct demo dependency set. No core checkout or specific Git revision is needed.
  A clean isolated PyPI install resolved **0.7.0**. Its CLI lacks `serve` and its
  config module lacks browser-update admission/lifetime support. The installation
  checker correctly rejected it and reported both missing features and its version.
  The feature check passed against the existing local **0.8.0** environment; that
  does not establish that a compatible version is available on PyPI.
- The focused deployment, host-profile, landing-page, readiness, retail, live and
  scan tests passed: **18 passed**. `git diff --check` passed. This update did not
  run Caddy adaptation/runtime checks: neither Go nor the custom Caddy binary was
  available. Selected proxy blocks are unchanged from the shared template.
- No VM, DNS, Cloudflare, certificate or public service was changed. Real systemd
  sandbox, origin TLS, DNS moves, reboot, capacity and shared-IP visitor checks
  remain deployment acceptance work.

## Website and event-VM installers — 3 October 2026

This supersedes the 2 October PyPI availability and manual-origin-TLS notes above.

- Built Caddy 2.11.4 with the existing rate-limit module and Cloudflare DNS v0.2.4.
  The full five-host configuration validated with a syntactically valid dummy
  token, without requesting certificates or changing DNS.
- A clean PyPI installation resolved plotsrv **0.8.0** and passed the required
  capability checks. Bounded retail publishing, live JSONL following and scan
  audit publishing all ran successfully against real loopback receivers from
  that wheel; no plotsrv source checkout supplied the runtime.
- Installer tests exercise safe archive extraction, packaging exclusions, all
  profiles, independent website/demo selections, repeated website updates,
  preserving tokens, profile-only changes, failed package preflight, failed
  readiness and failed proxy reload rollback. System commands are mocked in
  these tests: no local system services are installed or changed.
- The custom Caddy passed the real read-only/SSE proxy test, including `/checks`,
  static rate limits, bounded SSE admission/reconnection and rejected publishing.
  Both website host blocks passed HTTP asset and private-path rejection checks.
- Chromium checked both websites through those Caddy blocks and their CSP at
  desktop and mobile sizes, including images, installation toggle and navigation.
  No JavaScript, CSP or HTTP errors occurred. These local website checks used HTTP
  loopback listeners, not production certificates.
- Prepared the two upload archives, checksums and a **Linux x86-64** Caddy binary.
  The archives exclude secrets, virtual environments, Git metadata, runtime state
  and unrelated files from the examples checkout.

Real root/systemd installation, DNS challenge issuance/renewal with the operator's
API token, provider firewall enforcement, DNS cutover, reboot, measured VM capacity
and multi-day operation still require the VM acceptance steps in the walkthrough.
No DigitalOcean VM, Cloudflare setting, DNS record or existing live site was changed.

## 3 October 2026: receiver storage failure correction

The first prod1 install exposed a gap in the earlier runtime check: its config
was in the writable working directory. plotsrv 0.8.0 actually resolves relative
storage paths against the config directory. In deployment that directory is in
a read-only release, so retail could not start.

- Staged release configs now use explicit storage paths under each demo's
  `/var/lib/plotsrv-demo` directory; source example YAML stays portable.
- Receiver and publisher units set a per-demo writable Matplotlib cache.
- The installer checks each deployed config's actual resolved storage path and
  ability to write under the service's ProtectSystem/ProtectHome restrictions.
- Regression tests exercise plotsrv's real storage backend with read-only configs
  outside the writable state directory, and reject release-relative storage.
- All three demos again published against PyPI 0.8.0 loopback receivers, now with
  their config directory read-only and separate from their working directory.

Local tests cannot substitute for rerunning the corrected installer on prod1;
root/systemd sandbox execution and real Cloudflare issuance remain VM checks.
