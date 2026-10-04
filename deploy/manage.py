#!/usr/bin/env python3
"""Root-only, independently repeatable website/demo deployment for bootstrapped VMs."""
import argparse
import contextlib
import fcntl
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

HERE = Path(__file__).resolve().parent
ETC = Path('/etc/plotsrv-demo')
RELEASES = Path('/opt/plotsrv-releases')
WEBSITE = Path('/opt/plotsrv-homepage')
EXAMPLES = Path('/opt/plotsrv-examples')
TOOLS = Path('/opt/plotsrv-tools')
CADDY = Path('/usr/local/bin/caddy-plotsrv')
STATE = ETC / 'deployment.json'
UNITS = Path('/etc/systemd/system')
PROXY = 'plotsrv-demo-proxy.service'
PROFILES = {'all': ['retail', 'live_import', 'scan_audit'], 'retail': ['retail'],
            'live': ['live_import'], 'scans': ['scan_audit']}
TOKENS = {'retail': 'PLOTSRV_RETAIL_TOKEN', 'live_import': 'PLOTSRV_LIVE_TOKEN',
          'scan_audit': 'PLOTSRV_SCANS_TOKEN'}
PORTS = {'retail': 8101, 'live_import': 8102, 'scan_audit': 8103}
JOBS = {'retail': ['plotsrv-demo-retail-publish.service'],
        'live_import': ['plotsrv-demo-live-writer.service', 'plotsrv-demo-live-follower.service'],
        'scan_audit': ['plotsrv-demo-scan-audit.timer', 'plotsrv-demo-scan-audit.service']}


def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def atomic(path, text, mode=0o644):
    temp = path.with_name(path.name + '.next')
    temp.write_text(text)
    temp.chmod(mode)
    os.replace(temp, path)


def load_state():
    if not STATE.exists():
        return {'website': False, 'demos': []}
    state = json.loads(STATE.read_text())
    if type(state.get('website')) is not bool or not isinstance(state.get('demos'), list):
        raise ValueError('Invalid deployment.json')
    if set(state['demos']) - set(TOKENS):
        raise ValueError('Unknown demo in deployment.json')
    return state


def selected_hosts(state):
    return (['website', 'landing'] if state['website'] else []) + state['demos']


def render(state):
    spec = importlib.util.spec_from_file_location('hosts', HERE / 'render-caddy.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.render(selected_hosts(state))


def extract(archive, destination, kind):
    """Validate the entire archive before writing; accept only ordinary source files."""
    from package import WEBSITE_FILES, SUFFIXES
    with tarfile.open(archive, 'r:gz') as source:
        members = source.getmembers()
        names = set()
        if sum(m.size for m in members) > 256 * 1024 * 1024:
            raise ValueError('Archive exceeds 256 MiB unpacked source limit')
        for member in members:
            p = PurePosixPath(member.name)
            if p.is_absolute() or '..' in p.parts or not p.parts or any(x.startswith('.') for x in p.parts):
                raise ValueError(f'Unsafe archive path: {member.name}')
            if not member.isfile() or str(p) in names:
                raise ValueError(f'Non-file or duplicate archive entry: {member.name}')
            names.add(str(p))
            if kind == 'website':
                allowed = str(p) in WEBSITE_FILES or (p.parts[0] == 'assets' and p.suffix.lower() in SUFFIXES)
            else:
                allowed = ((p.parts[0] == 'deploy' and len(p.parts) >= 2) or
                           (len(p.parts) >= 3 and p.parts[0] == 'demos' and p.parts[1] in TOKENS))
                prepared_asset = str(p) in {'demos/publishing.py', 'demos/restore.py', 'demos/retail/northstar.svg'}
                allowed = prepared_asset or (allowed and (p.suffix in {'.py', '.sh', '.yml', '.yaml', '.txt', '.md', '.service', '.timer'} or p.name == 'Caddyfile'))
            if not allowed:
                raise ValueError(f'Unexpected archive file: {member.name}')
        required = set(WEBSITE_FILES) if kind == 'website' else {
            'deploy/requirements.txt', 'deploy/check-install.py', 'deploy/wait-for-receiver.py',
            'deploy/systemd/plotsrv-demo@.service',
            'deploy/systemd/plotsrv-demo-content@.service', 'demos/retail/app.py',
            'demos/live_import/follow.py', 'demos/live_import/generate_events.py',
            'demos/scan_audit/run_audit.py', 'demos/live_import/reports.py', 'demos/publishing.py',
            'demos/restore.py', 'demos/retail/northstar.svg', *[f'demos/{d}/plotsrv.yml' for d in TOKENS]}
        if not required <= names:
            raise ValueError('Archive missing: ' + ', '.join(sorted(required - names)))
        for member in members:
            path = destination / member.name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            with source.extractfile(member) as inp, path.open('xb') as out:
                shutil.copyfileobj(inp, out)
            path.chmod(0o755 if path.suffix == '.sh' else 0o644)


def token_env():
    path = ETC / 'cloudflare.env'
    st = path.stat()
    if st.st_uid != 0 or st.st_mode & 0o077:
        raise ValueError(f'{path} must be root-owned, mode 0600')
    text = path.read_text().strip()
    if not re.fullmatch(r'CF_API_TOKEN=(?:[A-Za-z0-9_-]{35,50}|cf(?:ut|at)_[A-Za-z0-9_-]{32,256})', text):
        raise ValueError('cloudflare.env must contain only CF_API_TOKEN=your_token (no quotes)')
    return {'CF_API_TOKEN': text.split('=', 1)[1]}


def ensure_user(name, home):
    try:
        pwd.getpwnam(name)
    except KeyError:
        run('useradd', '--system', '--user-group', '--home-dir', home,
            '--no-create-home', '--shell', '/usr/sbin/nologin', name)
    run('install', '-d', '-o', name, '-g', name, '-m', '0700', home)


def preflight(args):
    if os.geteuid() != 0:
        raise ValueError('Run with sudo/root')
    if sys.version_info < (3, 11):
        raise ValueError('Python 3.11+ required')
    for command in ('systemctl', 'systemd-analyze', 'systemd-run', 'runuser', 'useradd', 'install'):
        if not shutil.which(command):
            raise ValueError(f'Missing {command}; run the VM bootstrap first')
    if not CADDY.is_file():
        raise ValueError(f'Install the supplied Caddy binary at {CADDY} first')
    modules = run(CADDY, 'list-modules', capture_output=True, text=True).stdout.splitlines()
    if not {'dns.providers.cloudflare', 'http.handlers.rate_limit'} <= set(modules):
        raise ValueError('Caddy requires Cloudflare DNS and rate-limit modules')
    token_env()
    if args.archive and not args.archive.is_file():
        raise ValueError(f'Archive not found: {args.archive}')
    for path in (WEBSITE, EXAMPLES):
        if path.exists() and not path.is_symlink():
            raise ValueError(f'{path} is an unmanaged installation; migrate it explicitly first')
    if not STATE.exists() and (ETC / 'Caddyfile').exists():
        raise ValueError('Existing unmanaged proxy configuration; migrate it explicitly first')


def validate_proxy(candidate):
    # No production credentials or certificate issuance during config validation.
    run('runuser', '-u', 'plotsrv-proxy', '--', str(CADDY), 'validate',
        '--config', candidate, '--adapter', 'caddyfile',
        env={**os.environ, 'CF_API_TOKEN': 'v' * 40,
             'XDG_DATA_HOME': '/var/lib/plotsrv-demo-proxy',
             'XDG_CONFIG_HOME': '/var/lib/plotsrv-demo-proxy'})


def switch_link(link, target):
    temporary = link.with_name(link.name + '.next')
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target, target_is_directory=True)
    os.replace(temporary, link)


def restore_link(link, target):
    if target is None:
        link.unlink(missing_ok=True)
    else:
        switch_link(link, target)


def prepare_python(release, requirements):
    if not (TOOLS / 'bin/uv').exists():
        if TOOLS.exists():
            raise ValueError(f'{TOOLS} exists without uv; repair it before retrying')
        run('/usr/bin/python3', '-m', 'venv', TOOLS)
        run(TOOLS / 'bin/pip', 'install', '--index-url', 'https://pypi.org/simple', 'uv')
    uv = TOOLS / 'bin/uv'
    run(uv, 'venv', '--python', '/usr/bin/python3', release / '.venv',
        env={**os.environ, 'UV_PYTHON_DOWNLOADS': 'never'})
    req = requirements or release / 'deploy/requirements.txt'
    if requirements:
        # Reproduction manifests must contain only pinned PyPI distributions.
        for line in req.read_text().splitlines():
            if line.strip() and not line.startswith('#') and not re.fullmatch(r'[A-Za-z0-9_.-]+==[A-Za-z0-9_.+!-]+', line):
                raise ValueError('Package manifest must contain only name==version entries')
    run(uv, 'pip', 'install', '--index-url', 'https://pypi.org/simple', '--python',
        release / '.venv/bin/python', '-r', req)
    run(release / '.venv/bin/python', '-B', release / 'deploy/check-install.py')
    run(release / '.venv/bin/plotsrv', 'serve', '--help', stdout=subprocess.DEVNULL)
    result = run(uv, 'pip', 'freeze', '--python', release / '.venv/bin/python', capture_output=True, text=True)
    (release / 'deployed-python-packages.txt').write_text(result.stdout)


def prepared_content_available():
    return ((EXAMPLES / 'demos/restore.py').is_file() and
            (UNITS / 'plotsrv-demo-content@.service').is_file())


def stop_demo(name):
    content = ([f'plotsrv-demo-content@{name}.service']
               if (UNITS / 'plotsrv-demo-content@.service').is_file() else [])
    run('systemctl', 'disable', '--now', *JOBS[name], *content, f'plotsrv-demo@{name}.service')


def start_demo(name, restart=False, publish=False):
    unit = f'plotsrv-demo@{name}.service'
    run('systemctl', 'enable', unit)
    run('systemctl', 'restart' if restart else 'start', unit)
    env = os.environ.copy()
    value = (ETC / f'{name}.env').read_text().strip().split('=', 1)[1]
    env[TOKENS[name]] = value
    run(EXAMPLES / '.venv/bin/python', '-B', EXAMPLES / 'deploy/wait-for-receiver.py',
        '--port', PORTS[name], '--token-env', TOKENS[name], env=env)
    prepared = prepared_content_available()
    if prepared:
        # Receiver startup wants this oneshot; start also waits for it to finish.
        run('systemctl', 'start', f'plotsrv-demo-content@{name}.service')
    if name == 'live_import':
        for job in reversed(JOBS[name]):
            run('systemctl', 'enable', job)
            run('systemctl', 'restart' if restart else 'start', job)
    elif (name == 'retail' and not prepared and (publish or restart)) or (publish and name != 'retail'):
        run('systemctl', 'start', JOBS[name][-1])
    if name == 'scan_audit':
        run('systemctl', 'enable', '--now', JOBS[name][0])


def check_data(name):
    paths = {'retail': ['/table/data?view=retail:orders'],
             'live_import': ['/stream/status?view=live:imports', '/artifact?view=live:report'],
             'scan_audit': ['/artifact?view=scans:example', '/checks?view=scans:metrics']}
    if not prepared_content_available():
        paths['live_import'] = ['/stream/status?view=live:imports']
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(60):
        try:
            for path in paths[name]:
                with opener.open(f'http://127.0.0.1:{PORTS[name]}{path}', timeout=2) as response:
                    if response.status != 200 or not response.read(1):
                        raise OSError('Demo content is not ready')
            return
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError(f'{name} did not serve its initial view')


def deploy(args):
    preflight(args)
    ETC.mkdir(exist_ok=True, mode=0o755)
    with (ETC / 'deployment.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous = load_state()
        desired = dict(previous)
        desired['website' if args.kind == 'website' else 'demos'] = True if args.kind == 'website' else PROFILES[args.profile]
        link = WEBSITE if args.kind == 'website' else EXAMPLES
        old_target = link.resolve() if link.is_symlink() else None
        if not args.archive and not old_target:
            raise ValueError('First demo deployment requires an archive')
        ensure_user('plotsrv-proxy', '/var/lib/plotsrv-demo-proxy')
        candidate = ETC / 'Caddyfile.candidate'
        atomic(candidate, render(desired))
        validate_proxy(candidate)
        release = None
        if args.archive:
            release = RELEASES / args.kind / (time.strftime('%Y%m%dT%H%M%S') + '-' + secrets.token_hex(3))
            release.mkdir(parents=True, mode=0o755)
            extract(args.archive, release, args.kind)
            if args.kind == 'demos':
                prepare_python(release, args.requirements)
                run(release / '.venv/bin/python', '-B', release / 'deploy/configure-state.py', release)
        if args.kind == 'demos':
            ensure_user('plotsrv-demo', '/var/lib/plotsrv-demo')
            for name in desired['demos']:
                run('install', '-d', '-o', 'plotsrv-demo', '-g', 'plotsrv-demo', '-m', '0700', f'/var/lib/plotsrv-demo/{name}')
                token = ETC / f'{name}.env'
                if not token.exists():
                    fd = os.open(token, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, 'w') as output:
                        output.write(f'{TOKENS[name]}={secrets.token_urlsafe(32)}\n')
        # A profile-only change must keep the installed release's service files.
        # New tooling may otherwise install jobs that older demo code cannot run.
        unit_source = (release or EXAMPLES) / 'deploy/systemd' if args.kind == 'demos' else HERE / 'systemd'
        units = {p.name: p.read_bytes() for p in unit_source.glob('*')
                 if args.kind == 'demos' or p.name == PROXY}
        old_units = {name: (UNITS / name).read_bytes()
                     if (UNITS / name).exists() else None for name in units}
        config = ETC / 'Caddyfile'
        old_config = config.read_text() if config.exists() else None
        proxy_was_active = subprocess.run(['systemctl', 'is-active', '--quiet', PROXY]).returncode == 0
        changed = False
        try:
            for name, data in units.items():
                atomic(UNITS / name, data.decode())
            run('systemctl', 'daemon-reload')
            # Executables must exist at their stable paths for systemd verification.
            if release:
                if args.kind == 'demos':
                    for name in previous['demos']:
                        stop_demo(name)
                switch_link(link, release)
                changed = True
            run('systemd-analyze', 'verify', *[UNITS / n for n in units])
            if args.kind == 'demos':
                for name in desired['demos']:
                    state_dir = f'/var/lib/plotsrv-demo/{name}'
                    run('systemd-run', '--wait', '--pipe', '--collect',
                        '-p', 'User=plotsrv-demo', '-p', 'Group=plotsrv-demo',
                        '-p', 'ProtectHome=true', '-p', 'ProtectSystem=strict',
                        '-p', 'PrivateTmp=true',
                        '-p', f'WorkingDirectory={state_dir}',
                        '-p', f'ReadWritePaths={state_dir}',
                        '-p', f'Environment=MPLCONFIGDIR={state_dir}/.cache/matplotlib',
                        '-p', f'Environment=PLOTSRV_CONFIG={EXAMPLES}/demos/{name}/plotsrv.yml',
                        EXAMPLES / '.venv/bin/python', '-B', EXAMPLES / 'deploy/check-install.py',
                        '--state-dir', state_dir)
                    start_demo(name, restart=bool(release), publish=bool(release) or name not in previous['demos'])
                    check_data(name)
            atomic(config, candidate.read_text())
            run('systemctl', 'enable', PROXY)
            run('systemctl', 'reload' if proxy_was_active else 'start', PROXY)
            if args.kind == 'demos':
                for name in set(previous['demos']) - set(desired['demos']):
                    stop_demo(name)
            if old_config is not None:
                atomic(ETC / 'Caddyfile.previous', old_config)
            atomic(ETC / 'deployment.previous.json', json.dumps(previous, indent=2) + '\n')
            if old_target:
                switch_link(link.with_name(link.name + '.previous'), old_target)
            atomic(STATE, json.dumps(desired, indent=2) + '\n')
        except Exception:
            print('Deployment failed; restoring previous code, configuration and service selection.', file=sys.stderr)
            if args.kind == 'demos':
                for name in set(previous['demos']) | set(desired['demos']):
                    with contextlib.suppress(Exception):
                        stop_demo(name)
            if changed:
                restore_link(link, old_target)
            if old_units.get(PROXY) is None:
                subprocess.run(['systemctl', 'disable', '--now', PROXY])
            for name, data in old_units.items():
                path = UNITS / name
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic(path, data.decode())
            run('systemctl', 'daemon-reload')
            if old_config is None:
                config.unlink(missing_ok=True)
                subprocess.run(['systemctl', 'stop', PROXY])
            else:
                atomic(config, old_config)
                run('systemctl', 'restart' if proxy_was_active else 'stop', PROXY)
            if args.kind == 'demos' and old_target:
                for name in previous['demos']:
                    start_demo(name, restart=True, publish=False)
            raise
        print('Deployment installed. Hosts: ' + ', '.join(selected_hosts(desired)))
        print('Caddy certificate issuance is asynchronous. Verify HTTPS before changing DNS.')
        print('State:', STATE)
        if args.kind == 'demos':
            print('Installed PyPI versions:', EXAMPLES / 'deployed-python-packages.txt')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='kind', required=True)
    website = sub.add_parser('website')
    website.add_argument('archive', type=Path)
    demos = sub.add_parser('demos')
    demos.add_argument('profile', choices=PROFILES)
    demos.add_argument('archive', nargs='?', type=Path)
    demos.add_argument('--requirements', type=Path, help='Reuse a recorded PyPI freeze on a fresh VM or update')
    args = parser.parse_args()
    if args.kind == 'demos' and args.requirements and not args.archive:
        parser.error('--requirements requires an archive')
    try:
        os.umask(0o022)
        deploy(args)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'ERROR: {exc}\n')


if __name__ == '__main__':
    main()
