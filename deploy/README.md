# Website and demo deployment

Start with [the prod1/prod2/prod3 walkthrough](DEPLOYMENT-GUIDE.md).
The website remains in the separate `plotsrv-homepage` repository; only its
static deployment archive is needed here.

- `bootstrap-vm.sh`: the supplied DigitalOcean bootstrap, creating `samane` with
  SSH-key access. Run once on fresh VMs (already done on prod1).
- `deploy-plotsrv.sh`: the top-level **VM** command in the bundle. Supports `demos`,
  `website`, `both`, `select-demos`, and read-only `status`; all tooling is supplied.
- `bundle.py`: validates bundle checksums and dispatches explicit deployment commands.
- `build-bundle.py`: canonical **workstation** bundle builder; the existing
  `/home/samane/build-plotsrv-bundle` command points here.
- `package.py`: creates two source archives from current working files, plus checksums.
- `build-caddy.sh OUTPUT`: builds Linux Caddy with rate limiting and Cloudflare DNS.
  Build on the same architecture as the VM; the builder needs patched Go >=1.25.1.
- `deploy-website.sh ARCHIVE`: internal/legacy website installer wrapper.
- `deploy-demos.sh all|retail|live|scans [ARCHIVE] [--requirements FREEZE]`:
  installs/updates demo code and PyPI packages, or changes the active profile when
  no archive is supplied. Internal/legacy interface; use `select-demos` in the bundle.
- `configure-state.py`: assigns absolute storage paths in staged VM configs while
  leaving the source examples portable.
- `manage.py`: shared transactional deployment, release directories, safe archive
  extraction, proxy validation and rollback on activation failure.
- `render-caddy.py`: selects hosts from the shared Caddy template. `website landing`
  serves just the two static sites; `all` includes both sites and three receivers.

The installers require root, systemd, Python 3.11+, the custom Caddy binary, and
`/etc/plotsrv-demo/cloudflare.env`. They do not configure provider firewalls, change
DNS, or contact other VMs. Cloudflare DNS credentials are used by Caddy only for
certificate verification. DNS verification does not depend on the new VM already
receiving website traffic.

Website files and demo environments use separate releases behind stable symlinks.
The last successful release is retained through a `.previous` symlink; older
releases are retained for deliberate cleanup. Tokens, certificate storage and
runtime state are outside releases. Profile changes preserve them. Do not delete
Caddy storage or copy live scan state. The walkthrough covers moving scans safely.

Demo updates select and pin the latest stable, non-yanked PyPI `plotsrv`, refresh
package metadata, and check the installed version before activation. Incompatible
latest releases fail rather than silently falling back. Use
`--requirements` with prod1's recorded `deployed-python-packages.txt` to reproduce
that installation on event VMs. This is a package-version manifest, not a source
commit requirement. The installers refuse unmanaged directories left by the old
one-shot installer; follow an explicit migration instead of overwriting them.

Local checks:

```bash
python3 -m py_compile deploy/manage.py deploy/package.py deploy/render-caddy.py deploy/bundle.py deploy/build-bundle.py
sh -n deploy/deploy-plotsrv.sh deploy/deploy-website.sh deploy/deploy-demos.sh deploy/build-caddy.sh
bash -n deploy/bootstrap-vm.sh
.venv/bin/python -m pytest assurance/tests/test_deployment_bundle.py assurance/tests/test_deploy_installers.py assurance/tests/test_demo_host_profiles.py assurance/tests/test_demo_deployment_config.py -q
CADDY_DEMO_BINARY=/absolute/path/to/caddy-plotsrv .venv/bin/python -m pytest assurance/tests/test_demo_proxy_runtime.py -q
```

`VALIDATION.md` retains historical validation notes. The current deployment uses
Caddy-managed DNS-verified certificates, not manually uploaded Origin CA files.
