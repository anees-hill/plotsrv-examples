# Deploy and update plotsrv: website, demos and Python package

**Already running on prod1? Start here.** You do not need to repeat bootstrap,
Cloudflare-token, firewall or Caddy installation steps for an ordinary update.

- **Workstation**: your computer with the source projects.
- **VM**: an SSH terminal on prod1, prod2 or prod3, logged in as `samane`.
- Replace `PROD1_IP` (or `PROD2_IP` / `PROD3_IP`) with your SSH alias or VM address.
- The uploaded bundle belongs at `/home/samane/plotsrv-upload` on the VM.
- `deploy-plotsrv.sh` runs **on the VM**. `build-plotsrv-bundle` runs **on the workstation**.
- The website includes **both** `plotsrv.com` and the landing page at `demo.plotsrv.com`.
  The three running demo applications are installed separately. `docs.plotsrv.com`
  stays on its existing hosting.

## 1. Update an existing VM

### A. Put the new bundle on the VM

If you have already copied the **complete new directory**, go straight to B.
If you have uploaded `plotsrv-upload.tar.gz`, unpack it using the VM block below.
If your bundle has only `DEPLOY-DEMO-VM.md` and no `deploy-plotsrv.sh`, see
[Older bundles and missing tooling](#older-bundles-and-missing-tooling).

**Workstation — rebuild from current source, reuse the existing Caddy binary, upload:**

```bash
set -e
/home/samane/build-plotsrv-bundle --caddy /home/samane/Projects/plotsrv-homepage/plotsrv-upload/caddy-plotsrv
tar -C /home/samane/Projects/plotsrv-homepage -czf /home/samane/Projects/plotsrv-homepage/plotsrv-upload.tar.gz plotsrv-upload
scp /home/samane/Projects/plotsrv-homepage/plotsrv-upload.tar.gz samane@PROD1_IP:/home/samane/
ssh samane@PROD1_IP
```

**VM — unpack the uploaded archive into a fresh directory:**

```bash
set -e
cd /home/samane
if [ -e plotsrv-upload ]; then
    mv plotsrv-upload "plotsrv-upload.previous-$(date +%Y%m%dT%H%M%S)-$$"
fi
tar --no-same-owner -xzf plotsrv-upload.tar.gz
cd /home/samane/plotsrv-upload
sha256sum --check SHA256SUMS
```

All checksum lines must say **OK**. This moves only uploaded files; running
releases are under `/opt` and keep running. Keep the complete bundle together,
including `tooling`. Do not overlay new tooling onto an old directory or copy only
the archives. The deployment command also checks checksums automatically.

### B. Update just the demos and plotsrv (your current prod1 task)

**VM — these commands are complete; no earlier tooling-extraction step is needed:**

```bash
set -e
cd /home/samane/plotsrv-upload
sudo ./deploy-plotsrv.sh demos all
sudo ./deploy-plotsrv.sh status
```

This installs the new demo scripts/configs and the **latest stable, non-yanked
plotsrv release from PyPI**, then restarts all three demos. It prints the previous,
target and prepared plotsrv versions. It does **not** update website files or the
demo landing page. The shared proxy is reloaded to apply the selected demo routes.
Expect a brief demo interruption and browser reconnection.

The installer checks PyPI metadata afresh and pins that selected version for this
installation. If it cannot install that version on the VM, installation fails
before switching the active code; it does not silently install an older version.
Dependencies are freshly resolved too. Local plotsrv source changes reach the VM
only after you publish a package containing them to PyPI.

### C. Update the website later

Build and transfer a new complete bundle after editing the website. Then **on the VM**:

```bash
set -e
cd /home/samane/plotsrv-upload
sudo ./deploy-plotsrv.sh website
sudo ./deploy-plotsrv.sh status
```

This updates `plotsrv.com` and `demo.plotsrv.com` together. It preserves the active
demo selection and does not upgrade Python packages or restart demo receivers.
You can also run this against the current uploaded bundle if it already contains
the website version you want.

## 2. Choose exactly what to deploy

Run commands below **on the VM**, after `cd /home/samane/plotsrv-upload`.
`all` means all three demos; `retail`, `live`, and `scans` each mean **only that demo**.
A selection replaces the current selection on that VM; it is not an incremental addition.

| What you want | Command |
| --- | --- |
| Update all demos and PyPI plotsrv; keep website | `sudo ./deploy-plotsrv.sh demos all` |
| Update retail and PyPI plotsrv; run retail only; keep website | `sudo ./deploy-plotsrv.sh demos retail` |
| Update imports and PyPI plotsrv; run imports only; keep website | `sudo ./deploy-plotsrv.sh demos live` |
| Update scans and PyPI plotsrv; run scans only; keep website | `sudo ./deploy-plotsrv.sh demos scans` |
| Update website and landing page only | `sudo ./deploy-plotsrv.sh website` |
| Update website plus all demos and PyPI plotsrv | `sudo ./deploy-plotsrv.sh both all` |
| Update website plus only retail and PyPI plotsrv | `sudo ./deploy-plotsrv.sh both retail` |
| Update website plus only imports and PyPI plotsrv | `sudo ./deploy-plotsrv.sh both live` |
| Update website plus only scans and PyPI plotsrv | `sudo ./deploy-plotsrv.sh both scans` |
| Switch from all demos to retail only; no code/package update | `sudo ./deploy-plotsrv.sh select-demos retail` |
| Switch back from retail to all demos; no code/package update | `sudo ./deploy-plotsrv.sh select-demos all` |
| Switch to imports only or scans only; no code/package update | `sudo ./deploy-plotsrv.sh select-demos live` or `sudo ./deploy-plotsrv.sh select-demos scans` |
| Show installed version, selection and service health | `sudo ./deploy-plotsrv.sh status` |
| Show command help | `./deploy-plotsrv.sh --help` |

`both` performs **two separate transactions: demos first, then website**. If demos
fail, the website is not attempted. If the website fails afterward, the successful
demo update remains installed and the website installer attempts its own rollback.
Read the error, run `status`, then retry only the failed component.

`select-demos` uses the installed demo code, configs and environment. It does not
apply YAML/code changes from the bundle or contact PyPI. Disabled demo services and
routes stop, but their state and credentials remain. Re-enabling starts their jobs
and restores content. Website selection is preserved. If removed demos should stay
public on another VM, complete the migration below **before** disabling them here.

### Reproduce an existing package set instead of upgrading (advanced)

Normal updates always choose the latest stable PyPI plotsrv. Use this exception
only when you deliberately want the currently recorded package versions:

```bash
set -e
cd /home/samane/plotsrv-upload
cp /opt/plotsrv-examples/deployed-python-packages.txt /home/samane/prod1-packages.txt
sudo ./deploy-plotsrv.sh demos all --requirements /home/samane/prod1-packages.txt
```

`--requirements` also works with `both`. The manifest must contain only pinned
`name==version` entries and include plotsrv exactly once. It recreates a new
environment from PyPI using those pins; it does **not** select latest plotsrv.

## 3. Check the result and recover from failures

**VM:**

```bash
cd /home/samane/plotsrv-upload
sudo ./deploy-plotsrv.sh status
cat /opt/plotsrv-examples/deployed-python-packages.txt
sudo journalctl -u plotsrv-demo-proxy -n 60 --no-pager
```

For the demo that failed, substitute `retail`, `live_import` or `scan_audit`:

```bash
sudo journalctl -u plotsrv-demo@retail -u plotsrv-demo-content@retail -n 100 --no-pager
sudo systemctl show plotsrv-demo@retail -p MemoryCurrent -p MemoryPeak -p NRestarts
```

`status` returns a nonzero exit code if an expected service is inactive. It is a
local service check, not a public HTTPS or load test. Open the selected public demo
URLs and check tables/plots, source code, snapshots, live imports and scan reports.
Northstar freshness warnings and the dim scan's failed data check are intentional.

For an all-demo VM, verify local HTTPS through the real proxy:

```bash
curl --fail --resolve retail-demo.plotsrv.com:443:127.0.0.1 'https://retail-demo.plotsrv.com/table/data?view=retail:orders' -o /dev/null
curl --fail --resolve live-demo.plotsrv.com:443:127.0.0.1 'https://live-demo.plotsrv.com/artifact?view=live:report' -o /dev/null
curl --fail --resolve scans-demo.plotsrv.com:443:127.0.0.1 'https://scans-demo.plotsrv.com/checks?view=scans:metrics'
```

Run only the applicable checks on a one-demo VM. Check the website when installed:

```bash
curl --fail --resolve plotsrv.com:443:127.0.0.1 https://plotsrv.com/ -o /dev/null
curl --fail --resolve demo.plotsrv.com:443:127.0.0.1 https://demo.plotsrv.com/ -o /dev/null
```

Installers validate before activation and attempt to restore previous code, service
files, routes and selection if activation fails. Package-download/compatibility
failures leave the running installation unchanged. Read the first error, fix it,
and rerun the same command; do not delete runtime state or replace tokens.
Rollback is not a snapshot of data written by demo jobs. Retain backups if you need
to recover those writes too. Keep previous releases until verification succeeds:

| VM path | Purpose |
| --- | --- |
| `/opt/plotsrv-examples` and `.previous` | Current and previous demo releases/environments |
| `/opt/plotsrv-homepage` and `.previous` | Current and previous website releases |
| `/opt/plotsrv-releases` | Retained releases, including failed staging attempts |
| `/etc/plotsrv-demo` | Selection, proxy config and private credentials |
| `/var/lib/plotsrv-demo` | Demo data, snapshots and publisher journals |
| `/var/lib/plotsrv-demo-proxy` | Caddy certificates/account storage |

### Older bundles and missing tooling

An older bundle contains `DEPLOY-DEMO-VM.md` but no top-level launcher. Prefer to
rebuild and transfer the new complete bundle using section 1. The old server-side
shell script is not needed by the new launcher.

To recover the tools from an **already uploaded older bundle**, on the VM:

```bash
set -e
cd /home/samane/plotsrv-upload
sha256sum --check SHA256SUMS
if [ -e tooling ]; then
    mv tooling "tooling.previous-$(date +%Y%m%dT%H%M%S)-$$"
fi
mkdir tooling
tar --no-same-owner -xzf plotsrv-examples-demos.tar.gz -C tooling deploy
sudo sh tooling/deploy/deploy-demos.sh all "$PWD/plotsrv-examples-demos.tar.gz"
cat /opt/plotsrv-examples/deployed-python-packages.txt
```

This uses that older installer's package-resolution behaviour. It does not gain
the new launcher's explicit latest-version verification. Use the rebuilt bundle
for that guarantee. Do not run a previously copied installer from another release.

## 4. First installation on a new VM

Skip this section on an already configured prod1. Bootstrap Ubuntu with the bundled
`tooling/deploy/bootstrap-vm.sh` once (normally DigitalOcean user data). It creates
`samane` with SSH-key access. Use the same CPU architecture as the workstation's
Caddy build; Python 3.11+, systemd and outbound DNS/HTTPS are required.

Transfer the **whole** bundle as in section 1. **VM — install the supplied Caddy binary:**

```bash
set -e
cd /home/samane/plotsrv-upload
sha256sum --check SHA256SUMS
sudo install -o root -g root -m 0755 caddy-plotsrv /usr/local/bin/caddy-plotsrv
```

Routine content updates do not replace Caddy. Rebuild/reinstall it deliberately when
upgrading the proxy; validate and restart it in a maintenance window.

### Configure automatic HTTPS once per VM

**Cloudflare dashboard:**

1. Open your profile → **My Profile → API Tokens → Create Token**.
2. Choose **Edit zone DNS → Use template**. Name it `plotsrv Caddy prod1`.
3. Set these two permissions: **Zone / DNS / Edit** and **Zone / Zone / Read**.
4. Under **Zone Resources**, select **Include → Specific zone → plotsrv.com**.
5. Continue to the summary, create the token, and copy it. The secret is shown once.

See [Cloudflare's token instructions](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)
and the [Caddy Cloudflare module's required permissions](https://github.com/caddy-dns/cloudflare).
This token lets Caddy issue and renew HTTPS certificates. It does not create the
normal DNS records for your websites; you will set those after validating the installation below.

**prod1:** open a root-owned file in Nano. These commands preserve an existing file.

```bash
sudo install -d -o root -g root -m 0755 /etc/plotsrv-demo
sudo touch /etc/plotsrv-demo/cloudflare.env
sudo chown root:root /etc/plotsrv-demo/cloudflare.env
sudo chmod 0600 /etc/plotsrv-demo/cloudflare.env
sudo nano /etc/plotsrv-demo/cloudflare.env
```

If Nano is not installed, run `sudo apt-get install -y nano` and retry the last command.

Paste exactly one line, substituting your actual token. No quotes or spaces around `=`:

```text
CF_API_TOKEN=YOUR_ACTUAL_TOKEN
```

Save with **Ctrl+O**, press **Enter**, then exit with **Ctrl+X**. Do not paste the
token into shell commands or include it in the upload bundle. If changing a token
on an already running installation, run `sudo systemctl restart plotsrv-demo-proxy`.

### Configure ingress and Cloudflare

Use the DigitalOcean dashboard for the firewall rules below. If you already
configured UFW using the helper conversation, keep those rules: both firewalls
must allow SSH from you and web traffic from Cloudflare. You do not need to enable
UFW as an additional step here.

**DigitalOcean dashboard:**

1. Open **Networking → Firewalls**. Create a firewall named `plotsrv-prod1`, or
   edit the firewall already attached to prod1.
2. Add an inbound **SSH / TCP / 22** rule with your admin public IP/CIDR or VPN as
   its source. If SSH uses another port, use that port. Do this before restricting
   access. If your admin IP changes, update this rule in the dashboard.
3. Add inbound **HTTP / TCP / 80** and **HTTPS / TCP / 443** rules. For their
   sources, enter all the IPv4 and IPv6 ranges from
   [Cloudflare's current list](https://www.cloudflare.com/ips/). Do not select
   All IPv4 or All IPv6 for these web rules.
4. Remove any other broad rules allowing public access to 80/443. Do not add
   inbound rules for 8101, 8102, 8103 or 2019. Keep the default outbound rules
   allowing outgoing traffic (the installer needs DNS and HTTPS).
5. Apply the firewall to the **prod1 Droplet**. Check its **Networking** tab for
   rules from other attached firewalls that might still allow broad web access.
6. Keep your current SSH session open. In a second workstation terminal, run
   `ssh samane@PROD1_IP`. Confirm it works before closing the first session.

[DigitalOcean's firewall instructions](https://docs.digitalocean.com/products/networking/firewalls/how-to/configure-rules/)
explain the rule editor. Cloudflare IP ranges can change; use the linked list,
not a copied list from an old chat.

**Cloudflare dashboard, select plotsrv.com:**

- In **SSL/TLS → Overview**, open **Configure** if shown, choose the custom
  encryption setting **Full (strict)**, and save. See
  [Cloudflare’s Full (strict) instructions](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/).
- Open **Caching → Cache Rules → Create rule**. Name it `Live demos: bypass cache`.
  Choose **Custom filter expression → Edit expression** and paste:

  ```text
  (http.host in {"retail-demo.plotsrv.com" "live-demo.plotsrv.com" "scans-demo.plotsrv.com"})
  ```

  Set **Cache eligibility → Bypass cache**, place it **last**, and click **Deploy**.
  This keeps changing demo data fresh. See the
  [cache-rule editor instructions](https://developers.cloudflare.com/cache/how-to/cache-rules/create-dashboard/).
- Open **Speed → Settings → Content Optimization** and leave **Rocket Loader Off**
  for this setup. If you deliberately use it for other hosts, use a hostname-specific
  configuration rule instead. See
  [Rocket Loader settings](https://developers.cloudflare.com/speed/optimization/content/rocket-loader/enable/).
  Do not add extra bot/challenge rules for the demo hosts during initial setup.
- Leave existing DNS destinations in place until the validation and DNS steps below. Caddy uses DNS verification
  to obtain certificates, so it can prepare prod1 before you switch visitors over.

### Install, verify, then point DNS at the new VM

**VM — choose one command after token/firewall setup:**

```bash
cd /home/samane/plotsrv-upload
sudo ./deploy-plotsrv.sh both all
sudo ./deploy-plotsrv.sh status
```

Use `both retail` for website plus one demo, or `demos live` / `demos scans`
for a demo-only VM. Certificate issuance can take a few minutes. Run section 3's
HTTPS checks before moving visitors; investigate certificates instead of using `-k`.

**Cloudflare dashboard → plotsrv.com → DNS → Records:** search for each name
below. Click **Edit** on an existing matching record, or **Add record** if none
exists. For each, choose **Type A**, **IPv4 address = prod1's public IP**, **Proxy status =
Proxied** (orange cloud), and **TTL = Auto**, then click **Save**.
Use the VM address shown in DigitalOcean, not a Cloudflare proxy IP.
[Cloudflare’s DNS record instructions](https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-dns-records/)
show the editor.

| Name to enter | Website |
| --- | --- |
| `@` | plotsrv.com |
| `demo` | demo.plotsrv.com |
| `retail-demo` | retail-demo.plotsrv.com |
| `live-demo` | live-demo.plotsrv.com |
| `scans-demo` | scans-demo.plotsrv.com |

Edit existing records rather than creating duplicate/conflicting destinations.
Do not use the `stream` or `observe` example names from the helper conversation.
Leave `docs` unchanged. Do not create AAAA records unless IPv6 is configured and
protected; remove stale AAAA destinations for these five names if necessary.
Keep the old VM available until traffic has settled, and retain its old IP for
rollback. If the old landing page still appears, open **Caching → Configuration →
Purge Cache → Custom Purge**, choose URL purging, enter `https://demo.plotsrv.com/`
and `https://plotsrv.com/demos/`, then purge and reload the browser. See
[Cloudflare’s URL purge instructions](https://developers.cloudflare.com/cache/how-to/purge-cache/purge-by-single-file/).

Visit both website pages, retail table/plots, live streaming, and the scan report,
image, history and checks. Confirm there are no missing assets or failed API reads.
Use `systemd-cgtop`, `free -h`, `df -h` and service journals to measure real usage.
Per-service memory limits are not a promise that all services fit a 1 GB VM under
conference load. Rehearse with the expected browser count before the event.

## 5. Split demos across prod1, prod2 and prod3

Prepare prod2 and prod3 using section 4 (bootstrap, complete bundle, Caddy, token,
firewall). Keep prod1 serving traffic until their HTTPS checks pass. Use separate
zone-restricted Cloudflare tokens where practical.

To reproduce prod1's packages, **workstation**:

```bash
scp samane@PROD1_IP:/opt/plotsrv-examples/deployed-python-packages.txt /tmp/prod1-packages.txt
scp /tmp/prod1-packages.txt samane@PROD2_IP:/home/samane/prod1-packages.txt
scp /tmp/prod1-packages.txt samane@PROD3_IP:/home/samane/prod1-packages.txt
```

**prod2:**

```bash
cd /home/samane/plotsrv-upload
sudo ./deploy-plotsrv.sh demos live --requirements /home/samane/prod1-packages.txt
sudo ./deploy-plotsrv.sh status
```

**prod3:**

```bash
cd /home/samane/plotsrv-upload
sudo ./deploy-plotsrv.sh demos scans --requirements /home/samane/prod1-packages.txt
sudo ./deploy-plotsrv.sh status
```

Omit `--requirements` only if you deliberately want the latest PyPI packages on
the new VMs. Validate their selected hosts with section 3's local HTTPS checks.
Live imports can begin with fresh synthetic records. Its prepared report history
is illustrative and can be seeded independently. Existing scan history transfers
as follows; do not copy private receiver tokens between VMs.

### Transfer scan history while writers are stopped

On **both prod1 and prod3**, stop scans before copying:

```bash
sudo systemctl stop plotsrv-demo-scan-audit.timer
sudo systemctl stop plotsrv-demo-scan-audit.service plotsrv-demo@scan_audit.service
```

**prod1:**

```bash
sudo tar -C /var/lib/plotsrv-demo -czf /var/lib/plotsrv-demo/scan-transfer.tar.gz scan_audit
sudo install -o samane -g samane -m 0600 /var/lib/plotsrv-demo/scan-transfer.tar.gz /home/samane/plotsrv-upload/scan-transfer.tar.gz
sudo rm /var/lib/plotsrv-demo/scan-transfer.tar.gz
```

**Workstation:**

```bash
scp samane@PROD1_IP:/home/samane/plotsrv-upload/scan-transfer.tar.gz /home/samane/Projects/plotsrv-homepage/plotsrv-upload/
scp /home/samane/Projects/plotsrv-homepage/plotsrv-upload/scan-transfer.tar.gz samane@PROD3_IP:/home/samane/plotsrv-upload/
```

**prod3:** choose a fresh backup name if `scan_audit.before-move` already exists.

```bash
sudo bash -e <<'SH'
test ! -e /var/lib/plotsrv-demo/scan_audit.before-move
mv /var/lib/plotsrv-demo/scan_audit /var/lib/plotsrv-demo/scan_audit.before-move
tar --no-same-owner -xzf /home/samane/plotsrv-upload/scan-transfer.tar.gz -C /var/lib/plotsrv-demo
chown -R plotsrv-demo:plotsrv-demo /var/lib/plotsrv-demo/scan_audit
systemctl start plotsrv-demo@scan_audit.service
systemctl start plotsrv-demo-scan-audit.service
systemctl start plotsrv-demo-scan-audit.timer
SH
```

Restart **only the scan receiver on prod1** to serve old cached reads during DNS
propagation; leave its job and timer stopped:

```bash
sudo systemctl start plotsrv-demo@scan_audit.service
```

**Cloudflare dashboard → plotsrv.com → DNS → Records:**

1. Search for `live-demo`, click **Edit** on its A record, replace the IPv4 address
   with **prod2's public IPv4**, keep **Proxied** and **TTL Auto**, then **Save**.
2. Search for `scans-demo`, click **Edit** on its A record, replace the IPv4 address
   with **prod3's public IPv4**, keep **Proxied** and **TTL Auto**, then **Save**.
3. Leave `@`, `demo`, `retail-demo`, and `docs` unchanged. Do not change nameservers,
   add new hostnames, or alter the HTTPS encryption setting.
4. Wait for traffic to settle and visit `https://live-demo.plotsrv.com/` and
   `https://scans-demo.plotsrv.com/`. With proxying on, DNS lookups show Cloudflare
   addresses; inspect the record in the dashboard to confirm the origin IP.

Then, **prod1**:

```bash
cd /home/samane/plotsrv-upload
sudo ./deploy-plotsrv.sh select-demos retail
```

This keeps both websites and retail while stopping the other receivers/jobs and
removing only their public host blocks. The old demo data remains available for
rollback. Do not restart the old scan writer while prod3 owns the job.

## 6. Return from one demo on prod1 to all three

If no state moved to other VMs, this is the complete **prod1** command:

```bash
cd /home/samane/plotsrv-upload
sudo ./deploy-plotsrv.sh select-demos all
sudo ./deploy-plotsrv.sh status
```

If scans have been running on prod3, first bring their current state back.
**On both prod3 and prod1:**

```bash
sudo systemctl stop plotsrv-demo-scan-audit.timer
sudo systemctl stop plotsrv-demo-scan-audit.service plotsrv-demo@scan_audit.service
```

**prod3:**

```bash
set -e
sudo tar -C /var/lib/plotsrv-demo -czf /var/lib/plotsrv-demo/scan-return.tar.gz scan_audit
sudo install -o samane -g samane -m 0600 /var/lib/plotsrv-demo/scan-return.tar.gz /home/samane/scan-return.tar.gz
sudo rm /var/lib/plotsrv-demo/scan-return.tar.gz
```

**Workstation:**

```bash
scp samane@PROD3_IP:/home/samane/scan-return.tar.gz /tmp/scan-return.tar.gz
scp /tmp/scan-return.tar.gz samane@PROD1_IP:/home/samane/scan-return.tar.gz
```

**prod1:**

```bash
sudo bash -e <<'SH'
test ! -e /var/lib/plotsrv-demo/scan_audit.before-return
mv /var/lib/plotsrv-demo/scan_audit /var/lib/plotsrv-demo/scan_audit.before-return
tar --no-same-owner -xzf /home/samane/scan-return.tar.gz -C /var/lib/plotsrv-demo
chown -R plotsrv-demo:plotsrv-demo /var/lib/plotsrv-demo/scan_audit
SH
cd /home/samane/plotsrv-upload
sudo ./deploy-plotsrv.sh select-demos all
sudo ./deploy-plotsrv.sh status
```

Use a fresh backup name if `scan_audit.before-return` already exists. Validate the
live/scans HTTPS views locally. In Cloudflare DNS, change **live-demo** and
**scans-demo** A records back to prod1's public IP, keeping Proxied and TTL Auto.
Leave other records unchanged. Keep the old receivers available during propagation
(start only the scan receiver on prod3 if needed; keep its audit job/timer stopped).
After traffic settles, stop/disable their services and retire the event VMs.
Keep the transferred state and revoke retired VMs' separate tokens after checking
prod1's history and next daily audit. Switching profiles never moves DNS or data.

## 7. Change resource and visitor limits

Keep finite limits. A larger VM provides headroom, but does not automatically
raise the existing limits or make unlimited concurrent work safe. For a 4 GB VM,
**512 MiB per receiver is a starting point to test**, not a measured requirement.
The repository default is still 320 MiB. Leave room for the OS, Caddy and publisher
jobs; three receivers with 512 MiB ceilings can together use 1.5 GiB.

### Which setting controls what?

These source paths are relative to your workstation's
`/home/samane/Projects/plotsrv-examples` directory.

| Setting | Where to edit | Current value / meaning |
| --- | --- | --- |
| Receiver memory | `deploy/systemd/plotsrv-demo@.service`: `MemoryMax` | `320M` per receiver; `512M` is a suggested 4 GB VM test setting |
| Receiver tasks and open files | Same file: `TasksMax`, `LimitNOFILE` | `64` tasks (including threads), `1024` open files; keep initially |
| Publisher/job memory | Individual `.service` files in `deploy/systemd/` | Retail and scan jobs: `320M`; live follower: `160M`; live writer: `64M` |
| Live-update connections | Each demo's `plotsrv.yml`: `browser-update-settings` | `96` per receiver, `64` per client IP, `600` seconds per connection |
| Proxy request rates | `deploy/Caddyfile`: `rate_limit` zones | Dynamic reads: `900` per client IP and `1200` total per 10 seconds, separately for each demo |
| Static asset request rates | `deploy/Caddyfile`: zones ending `_static_client` / `_static_total` | `2400` per client IP and `4800` total per 10 seconds |
| Proxy active requests | `deploy/Caddyfile`: `unhealthy_request_count` | `128`; separate from requests per time window |
| Data size and retention | Each demo's `plotsrv.yml`: `limits`, `storage-settings`, `stream-settings` | Caps on published data, snapshots and retained logs; keep initially |

The three YAML files are `demos/retail/plotsrv.yml`,
`demos/live_import/plotsrv.yml`, and `demos/scan_audit/plotsrv.yml`.
There is no need to raise every limit together. Live-update connections are not
visitor counts: tabs and reconnects matter, and conference Wi-Fi may put many
visitors behind one client IP. The 600-second lifetime deliberately causes
periodic reconnections; do not remove it merely to keep a tab open longer.

### A. Change the source settings, then deploy them (recommended)

Use this procedure **before the first install or when demos are already running**.
It keeps future bundles consistent with your chosen settings.

1. **Workstation:** edit the relevant source files listed above. For example,
   change `MemoryMax=320M` to `MemoryMax=512M` in
   `deploy/systemd/plotsrv-demo@.service`. This affects all demo receiver instances
   installed from that template; it does not change the publisher job limits.
2. Rebuild the bundle:

   ```bash
   /home/samane/build-plotsrv-bundle --caddy /home/samane/Projects/plotsrv-homepage/plotsrv-upload/caddy-plotsrv
   ```

3. Follow **section 1A** to rebuild, upload, unpack and verify the complete bundle. Do this on every VM that needs the changed settings.
4. **On the target VM**, run the matching command below from
   `/home/samane/plotsrv-upload`. Run **one**, according to that VM's role:

   | VM role | Command |
   | --- | --- |
   | prod1, all three demos | `sudo ./deploy-plotsrv.sh demos all` |
   | prod1 during the event, retail only | `sudo ./deploy-plotsrv.sh demos retail` |
   | prod2, live imports only | `sudo ./deploy-plotsrv.sh demos live` |
   | prod3, scans only | `sudo ./deploy-plotsrv.sh demos scans` |

For a first install, complete token/firewall/Caddy setup in section 4 first.
The installer then starts the selected demos with the new settings. For an
existing install, it installs the updated units/configs, restarts the selected
receivers and live jobs, republishes demo data and reloads Caddy. Expect a brief
interruption and browser reconnection. It preserves the website selection.

`demos PROFILE` also creates a new Python environment from PyPI. To keep
exactly the currently installed package versions during a settings-only update,
first save the existing manifest **on that VM**:

```bash
cd /home/samane/plotsrv-upload
cp /opt/plotsrv-examples/deployed-python-packages.txt ./before-tuning-packages.txt
```

Append `--requirements "$PWD/before-tuning-packages.txt"` to your chosen installer
command. This option is for an existing successful install, not a first install.

**Use `demos PROFILE`, not `select-demos PROFILE`, when applying YAML changes.** A profile-only command
uses the existing deployed YAML. Do not edit `/opt/plotsrv-examples` or the
release directories directly: the installer prepares their storage paths, and a
later deployment would replace your edits. Likewise, change proxy settings in
`deploy/Caddyfile`, not the generated `/etc/plotsrv-demo/Caddyfile`.

### B. Change only this VM's receiver memory cap without rebuilding

Use a systemd override when prod1/prod2/prod3 need different memory budgets. It
survives deployments and reboots. You can create it **before the demos are first
installed**, or while they are running.

**On the target VM:** this sets a 512 MiB ceiling for each receiver on that VM.
It overwrites only the dedicated `90-conference-memory.conf` file below.

```bash
sudo install -d -m 0755 /etc/systemd/system/plotsrv-demo@.service.d
sudo tee /etc/systemd/system/plotsrv-demo@.service.d/90-conference-memory.conf >/dev/null <<'CONF'
[Service]
MemoryMax=512M
CONF
sudo systemctl daemon-reload
```

**Not installed yet:** stop here and follow the normal installation steps. The
first start uses the override; no service needs to exist when you create it.

**Already running:** apply it to active receivers only:

```bash
for demo in retail live_import scan_audit; do
    if sudo systemctl is-active --quiet "plotsrv-demo@$demo.service"; then
        sudo systemctl restart "plotsrv-demo@$demo.service" || break
    fi
done
```

This does not enable other demos on an event VM. Restarting briefly interrupts
browsers. Retail and scans restore stored views; live imports resumes as its
running follower publishes new records. Check readiness and the browser afterward.

To override **one receiver only**, use an instance directory such as
`/etc/systemd/system/plotsrv-demo@retail.service.d/` instead of the template
`plotsrv-demo@.service.d/`, with the same filename and contents. For the same
filename, the instance override takes precedence over the template override.

These overrides take precedence over `MemoryMax` in the packaged service file.
If a source change seems ineffective, inspect the overrides using the commands
below. To return to the packaged default, remove **only the override you created**:

```bash
sudo rm /etc/systemd/system/plotsrv-demo@.service.d/90-conference-memory.conf
sudo systemctl daemon-reload
```

If you used an instance directory, remove that file instead. Then repeat the
active-receiver restart loop above, or let the next first start use the default.
Lowering a cap below the workload's needs can cause an out-of-memory restart.

### C. Verify the effective settings and rehearse

**On a VM running retail** (substitute `live_import` or `scan_audit` as needed):

```bash
sudo systemctl cat plotsrv-demo@retail.service
sudo systemctl show plotsrv-demo@retail.service \
  -p MemoryMax -p MemoryCurrent -p MemoryPeak -p TasksCurrent -p TasksMax \
  -p LimitNOFILE -p NRestarts -p ActiveState -p SubState
sudo journalctl -u plotsrv-demo@retail.service -n 60 --no-pager
```

`MemoryMax=536870912` means 512 MiB. `MemoryPeak` availability depends on the
systemd/kernel version. Confirm the service remains active and inspect logs for
OOM kills or repeated restarts. Each demo and publisher has its own memory usage;
check the other units too. `free -h` shows whole-VM headroom.

For YAML settings, inspect just the relevant section in the deployed file:

```bash
sed -n '/^browser-update-settings:/,/^[^[:space:]]/p' /opt/plotsrv-examples/demos/retail/plotsrv.yml
```

For proxy settings, inspect `/etc/plotsrv-demo/Caddyfile` and check
`sudo journalctl -u plotsrv-demo-proxy -n 60 --no-pager` for reload failures.
None of these resource changes requires changing Cloudflare DNS records.

Before the conference, test 6 simultaneous browsers, then a burst of 20, with
cold page loads, the retail table, live logs, scan history and a scan publication.
Include clients sharing one IP. Record navigation latency, rejected requests
(429/503), live-update interruptions, memory peaks and restart counts. Increase
only a limit shown to obstruct normal use, keeping enough headroom for all jobs
on that VM. More RAM does not resolve CPU contention inside one receiver.
