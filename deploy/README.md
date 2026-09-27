# Public demo deployment template

This directory is an implementation template, **not a deployed service**. It assumes one Ubuntu-like VM with 1 vCPU and 1 GB RAM, Cloudflare Free with all four DNS records proxied, and `demo.plotsrv.com`, `retail-demo.plotsrv.com`, `live-demo.plotsrv.com` and `scans-demo.plotsrv.com` on one Cloudflare Origin CA certificate. These are all first-level subdomains: [Cloudflare Free Universal SSL does not cover deeper subdomains on a full zone setup](https://developers.cloudflare.com/ssl/edge-certificates/universal-ssl/limitations/). The landing-page paths remain short redirects. Run a measured staging rehearsal before opening it publicly. The three demo origins remain stable when one receiver moves to another VM.

## Prepare the VM

1. Install the tested plotsrv core and this examples checkout at `/opt/plotsrv-examples`; pin both Git revisions. Use a system Python outside home directories: `UV_PYTHON_DOWNLOADS=never uv sync --locked --no-dev --python /usr/bin/python3` in the examples checkout, then `uv pip install --python .venv/bin/python /opt/plotsrv` from a separately pinned core checkout. Install core as a wheel (no `-e`). The chosen core must include `browser-update-settings` admission and lifetime support. Do not reuse a virtual environment pointing into `/home` or `/root`: `ProtectHome=true` deliberately hides those paths. Run `.venv/bin/python -B deploy/check-install.py` before enabling services. Keep `/opt/plotsrv-examples` owned by an administrator and read-only to the demo service account.
2. Create an unprivileged `plotsrv-demo` account and `/var/lib/plotsrv-demo/{retail,live_import,scan_audit}` owned by it, mode `0700`. Each service uses its own working directory. Apply a hard filesystem/project quota: start at 256 MiB for retail and scan receiver state together, and 16 MiB for live source logs. App retention is not a quota. Rotate journald/Caddy logs too.
3. Create three independent root-owned `0600` environment files at `/etc/plotsrv-demo/{retail,live_import,scan_audit}.env`. Each has exactly one randomly generated `PLOTSRV_RETAIL_TOKEN`, `PLOTSRV_LIVE_TOKEN`, or `PLOTSRV_SCANS_TOKEN` variable. Never commit the values, use the same file for that demo's receiver and publisher, and do not add credentials to the site or Cloudflare rules.
4. Install the files from `systemd/` under `/etc/systemd/system/`, reload systemd, then enable the receivers. Start the retail publisher once; enable the live follower and writer; start the scan audit once and enable its timer. The scan job runs at 03:00 UTC, then exits. Disable that timer during a conference presentation if the scheduled or catch-up run might overlap it.
5. Build Caddy with `deploy/build-caddy.sh /tmp/caddy-demo` using a currently patched Go toolchain (minimum 1.25.1). It pins Caddy and the third-party rate-limit module to specific source versions and checks that the module is present and the Caddyfile adapts. Review the plugin on upgrades. Install the binary into your Caddy service and copy `Caddyfile` to its configured path. On the VM, provision the Cloudflare Origin CA certificate and private key at the paths in the Caddyfile; the Caddy service account must be able to read the key, while other unprivileged users must not. Then run `caddy validate` and restart Caddy. Keep Caddy's admin API loopback-only.

The included systemd memory ceilings are initial safeguards, not proof that all processes fit in 1 GB. Check `systemd-analyze verify` against the installed unit files and test them on the target distribution. If the quota, memory ceiling or CPU budget causes legitimate requests to fail, measure and adjust before public launch. Do not grant either demo process access to production data, SSH keys, cloud credentials, a container socket or an observed production process.

## Cloudflare and network edge

- Proxy the four hostnames through Cloudflare and use **Full (strict)** TLS. The origin firewall must allow HTTPS only from [Cloudflare's current IP ranges](https://www.cloudflare.com/ips/); deny direct public access to ports 8101–8103, SSH except from an administrative network, and all other inbound ports. Update the allowlist when Cloudflare publishes changes. Cloudflare's [origin protection guide](https://developers.cloudflare.com/fundamentals/security/protect-your-origin-server/) explains why proxied DNS alone is insufficient.
- The Caddyfile uses `CF-Connecting-IP` for per-client limits and forwarded provenance. That header must be treated as trusted **only** while origin ingress is limited to Cloudflare. For stronger origin authentication, set up [per-hostname Authenticated Origin Pulls](https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/) with your own certificate and enforce client-certificate verification at Caddy. A shared global AOP certificate proves only that traffic came from Cloudflare, not your zone.
- The Free plan has one rate rule with a 10-second counting window. Start with an emergency rule on `/updates` at a high threshold, for example 300 starts per client IP per 10 seconds, and use sampled security events to tune it. Free-tier rule expressions can match path but not hostname, so verify this zone-wide path rule does not affect another application under `plotsrv.com`. The Caddyfile independently limits ordinary reads to 900 per client and 1,200 per receiver per 10 seconds for dynamic reads; static assets have separate allowances of 2,400 per client and 4,800 per receiver per 10 seconds. Each receiver also has a shared limit of 128 simultaneous upstream requests. These are starting controls, not measured capacity. plotsrv admits at most 96 SSE subscriptions per receiver, including at most 64 per client address, leaving headroom within Caddy's shared 128-request allowance for other reads. The 64-client allowance accommodates 50 browsers behind conference NAT; it is not a per-person identity or a fairness guarantee.
- Keep Bot Fight Mode off initially because it cannot be skipped for a particular stream/API path. Enable it only after confirming that normal browser visits and live updates continue working. Bypass Cloudflare caching for HTML reports, APIs and `/updates`; cache only tested static assets. Confirm that Cloudflare and Caddy pass SSE heartbeats promptly and that the application closes SSE at ten minutes and browsers reconnect normally.
- The public proxy accepts only GET/HEAD on named view routes. It blocks publishing, ingestion, settings, watch mutation, admin and docs routes, strips browser-supplied authorization/cookies, and does not inject publisher credentials. The scan receiver alone exposes finite snapshot history. Do not apply a script-blocking CSP or HTML sandbox to a future developer-authored report on these receiver origins; the separate static landing page has its own strict CSP.

## Rehearsal and operation

Before launch, check local Caddy routing with correct hostnames and a synthetic `CF-Connecting-IP`: the landing page, all demo views, image, table, history and live stream must work. Direct `POST /publish`, `GET /docs`, unknown paths and unexpected hosts must fail through the public listener. Verify IPv4 and IPv6, that no receiver port is reachable externally, and that the origin certificate fails direct browser trust. Inspect the actual Caddy/Cloudflare responses, not only the application endpoints.

Run all services on the **actual 1 GB VM** for several days, including repeated scan jobs and log rotation. Record idle/peak RSS or PSS, CPU, swap/OOM events, disk, receiver restarts, stream freshness and representative endpoint latency. Then run a controlled staging rehearsal of about 50 people opening the landing page, switching retail plots/table, reading scan images and using the stream. Include a case where many visitors share one source IP; raise conference-time per-IP thresholds only if the measurements support it. Cloudflare rate rules and Caddy bounds can reject requests during bursts even when the VM has spare capacity.

If the 1 GB gate fails, move a whole demo to a second temporary VM or resize for the conference. Keep the same public hostname and route it to the moved instance. Do not put replicas behind one demo URL until their local stream sessions, snapshot stores and return-visit semantics have been tested. After the conference, route each hostname back to the original VM and retire the temporary host. Keep the origin firewall and DNS configuration synchronized during the move.

The most important residual availability risk is an adversary occupying stream slots until the application expires them (and then reconnecting). Rate rules count request starts, not open-connection time. The application bounds SSE separately, preserving capacity for ordinary reads, but an adversary can still deny live updates to some clients. Treat sustained 429/503 responses or high active-request counts as a signal to intervene, rather than assuming a rate-limit plugin solves this alone.


## Installation and recovery acceptance

The interpreter and installed core must remain visible with `ProtectHome=true`.
After the unprivileged account and working directories exist, exercise the checker
under the actual sandbox (run as an administrator):

```sh
systemd-run --wait --pipe --collect -p User=plotsrv-demo -p Group=plotsrv-demo \
  -p ProtectHome=true -p ProtectSystem=strict -p PrivateTmp=true \
  -p WorkingDirectory=/var/lib/plotsrv-demo/retail \
  /opt/plotsrv-examples/.venv/bin/python -B /opt/plotsrv-examples/deploy/check-install.py
```

Use a currently patched Go toolchain to build the pinned Caddy release. Build on
a separate machine if temporary compiler memory/disk would pressure the 1 GB VM.
Pinning source versions is reproducibility, not an automatic security-update policy.

The scan job waits up to 60 seconds for an authenticated, loopback-only
capability response, with proxy environment variables and redirects disabled.
It retries every five minutes, at most four starts within two hours; permanent
failures therefore do not create an endless publishing loop. Investigate
`systemctl --failed`, `journalctl -u plotsrv-demo-scan-audit`, and
`/var/lib/plotsrv-demo/scan_audit/.plotsrv/scans-output/job-status.json`.
After fixing an exhausted retry budget, use `systemctl reset-failed plotsrv-demo-scan-audit` and start it again. Configure external alerting on failed
units or a completed-audit view older than 26 hours. Dashboard freshness warnings
are useful to visitors but are not an operator notification service.

Rehearse boot with empty storage, receiver restart, an unavailable receiver during
a scheduled job, same-date retry after partial publication, and source rotation.
The stream follower already retries transport failures; its process being alive
alone is not evidence that records are arriving. Check `/stream/status` freshness.
Keep the conference timer disabled during the talk if a catch-up job could run.


The optional local proxy regression can be rerun without an external target:

```sh
CADDY_DEMO_BINARY=/absolute/path/to/caddy-demo .venv/bin/python -m pytest \
  assurance/tests/test_demo_proxy_runtime.py -q
```

It uses two loopback SSE connections with deliberately tiny test limits, checks
that ordinary reads still work at the SSE limit, observes expiry/reconnection,
and checks blocked routes. It does not simulate conference load or contact
Cloudflare. The ordinary examples test suite skips this check without the binary.
