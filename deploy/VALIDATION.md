# Local validation record — 27 September 2026

This records what was actually checked on the development host. It is **not** a capacity certificate or evidence of an internet deployment.

## Functional and boundary checks

- The existing and new Python test suite passed: **152 tests** (`.venv/bin/python -B -m pytest -q`). New checks cover deterministic retail patterns, JSONL log-profile recognition and file rotation, generated JPEG defects, the landing page's checked-in assets, and loopback/catalogue-locked receiver settings.
- Local receiver runs accepted all seven retail views, five live-import records, and two daily scan reports. The live page displayed **Python application log** detection and **four suggested views**. The scan receiver served its table, JPEG artifact, observed summary and explicit previous-run comparison.
- Retail and scan receiver processes were restarted without rerunning their publishers. Both restored their table views from their bounded storage directories.
- The pinned Caddy v2.10.2 build included `http.handlers.rate_limit`; its Caddyfile adapted successfully. In a local HTTP-only version of that configuration, the static landing page and retail table returned 200, `/retail` returned a 302 to the dedicated hostname, and public `/publish`, `/docs` and retail `/history` returned 404. This was a harmless local route check with synthetic data, not a test of Cloudflare or a deployed origin.
- The three landing-page preview PNGs were captured in a local headless browser from those actual running demos. The static page was also opened in that browser.

## Limited local resource observations

With three populated receivers, a live follower and a continuous writer running together, their combined measured proportional set size was **436.2 MiB**: retail receiver 141.6, live receiver 133.6, scan receiver 136.3, follower 16.8 and writer 7.9 MiB. The short scan audit job's sampled peak was another **116.5 MiB PSS** before it exited. These figures exclude Caddy, the OS, Python installation files, filesystem cache, reverse-proxy connection buffers and visitor traffic. PSS from this development host must not be added directly to a 1 GB VM budget without a VM measurement.

Five sequential, direct local reads of the populated retail receiver had median response times of **3.2 ms** for `/`, **35.5 ms** for the 425 KB orders table payload, and **1.3 ms** for one 45 KB plot. This is a tiny, unloaded sample on different hardware; it says little about a one-core burst.

## Release gates still open

- No public hostname, Cloudflare zone, origin certificate, VM firewall or systemd service was changed. The Caddy template has not been exercised with Cloudflare's proxy, TLS, streaming behavior or real visitor IP headers.
- No multi-day soak, actual 1 GB VM measurement, 50-person conference rehearsal or internet-facing test was run. The earlier security constraint ruled out uncontrolled load testing, and no deployment target was provided. Complete these as bounded, explicitly scheduled staging checks before advertising capacity.
- The source links on the landing page point at `main` on GitHub. They will resolve to these new folders only after the local commits are published to that repository.
- The Caddy rate rules are initial values. They may reject legitimate attendees sharing a conference IP; adjust only from measured staging behavior. The 128 active-request ceiling protects each receiver but cannot prevent one source from occupying its stream slots.
