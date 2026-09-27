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
