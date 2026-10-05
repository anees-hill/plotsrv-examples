#!/usr/bin/env python3
"""Recreate the local plotsrv upload bundle from current working files."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import tarfile

VERSION = '0.2.0'
BASE = Path('/home/samane')
PAYLOADS = ('plotsrv-examples-demos.tar.gz', 'plotsrv-homepage.tar.gz', 'caddy-plotsrv')


def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def parser():
    p = argparse.ArgumentParser(
        description=f'Build a fresh plotsrv deployment bundle (version {VERSION}).',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''Prerequisites:
  - Linux with Python 3.11+, and a build architecture matching the target VM.
  - Current plotsrv-examples and plotsrv-homepage working directories.
  - A patched Go toolchain >=1.25.1, Git, and network access for Caddy builds.
    Go is found via --go, PATH, or the previously installed local build cache.
    --caddy reuses a supplied binary and does not require Go or build downloads.
  - Several GB of free build space. Temporary build files use the output disk,
    avoiding a small /tmp filesystem. Go's own module/build caches also use space.
  - Run as your normal account; no sudo, VM access or Cloudflare token is needed.

Behaviour:
  Packages current files, including relevant uncommitted changes, using the
  examples repository's deploy/package.py. It excludes files according to that
  packager's rules (environments, credentials, Git data and generated state).
  Stop editing the source checkouts while packaging for a consistent snapshot.
  By default, rebuilds Caddy with the repository's pinned module versions.
  --caddy is faster for content-only updates, but does not rebuild its versions.
  Validates Caddy modules/config, includes the deployment guide and this script,
  ships deploy-plotsrv.sh plus ready-to-use tooling, and writes BUILD-INFO.json
  plus SHA256SUMS covering every delivered file.
  Builds in a staging directory. An existing recognised bundle is backed up
  beside the output only after success; failures retain the previous bundle.
  Old backups are retained until you remove them. Nothing is uploaded/deployed.
  plotsrv is NOT bundled: the VM installer obtains it from PyPI.

Examples:
  /home/samane/build-plotsrv-bundle
  /home/samane/build-plotsrv-bundle --version
  /home/samane/build-plotsrv-bundle --caddy /home/samane/Projects/plotsrv-homepage/plotsrv-upload/caddy-plotsrv
  /home/samane/build-plotsrv-bundle --go /path/to/go --output /home/samane/Projects/plotsrv-homepage/plotsrv-upload-next

Default checkouts:
  /home/samane/Projects/plotsrv-examples
  /home/samane/Projects/plotsrv-homepage
Default output:
  /home/samane/Projects/plotsrv-homepage/plotsrv-upload
''')
    p.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    p.add_argument('--examples', type=Path, default=BASE/'Projects/plotsrv-examples', help='Examples checkout')
    p.add_argument('--website', type=Path, default=BASE/'Projects/plotsrv-homepage', help='Homepage checkout')
    p.add_argument('--output', type=Path, default=BASE/'Projects/plotsrv-homepage/plotsrv-upload', help='Bundle directory; previous bundle is retained as a backup')
    choice = p.add_mutually_exclusive_group()
    choice.add_argument('--go', type=Path, help='Go executable for a fresh Caddy build')
    choice.add_argument('--caddy', type=Path, help='Reuse this Linux Caddy binary instead of rebuilding')
    return p


def build(args):
    if platform.system() != 'Linux':
        raise ValueError('Run this script on Linux matching the VM architecture')
    arch = {'x86_64':'amd64', 'aarch64':'arm64'}.get(platform.machine())
    if not arch:
        raise ValueError(f'Unsupported builder architecture: {platform.machine()}')
    examples, website = args.examples.resolve(), args.website.resolve()
    output = args.output.absolute()
    if output.is_symlink():
        raise ValueError('Output must not be a symlink')
    output = output.resolve()
    if output != website / 'plotsrv-upload' and (output == BASE or output == Path('/') or any(output == source or output in source.parents or source in output.parents for source in (examples, website))):
        raise ValueError('Choose plotsrv-homepage/plotsrv-upload or a directory outside both source checkouts')
    for path in (examples/'deploy/package.py', examples/'deploy/build-caddy.sh',
                 examples/'deploy/Caddyfile', examples/'deploy/DEPLOYMENT-GUIDE.md', website/'index.html'):
        if not path.is_file():
            raise ValueError(f'Missing required source file: {path}')
    supplied = args.caddy.resolve() if args.caddy else None
    go = None
    if supplied:
        if not supplied.is_file() or not os.access(supplied, os.X_OK):
            raise ValueError(f'Caddy binary is missing or not executable: {supplied}')
    else:
        go = args.go or shutil.which('go') or BASE/'.cache/plotsrv-deploy-build/go/bin/go'
        go = Path(go).resolve()
        if not go.is_file():
            raise ValueError('Go not found. Install patched Go >=1.25.1, use --go, or supply --caddy; see --help')
        for command in ('git', 'sh', 'install', 'grep', 'mktemp'):
            if not shutil.which(command):
                raise ValueError(f'Missing build prerequisite: {command}')
    output.parent.mkdir(parents=True, exist_ok=True)
    lock_path = output.parent / f'.{output.name}.build.lock'
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(f'Another bundle build is using {output}') from None
        if output.exists() and (not output.is_dir() or not all((output/name).is_file() for name in (*PAYLOADS, 'SHA256SUMS'))):
            raise ValueError(f'Refusing to replace an unrecognised directory: {output}')
        with tempfile.TemporaryDirectory(prefix=f'.{output.name}.build-', dir=output.parent) as scratch:
            scratch = Path(scratch)
            stage = scratch/'bundle'
            print(f'plotsrv bundle builder {VERSION} — Linux {arch}', flush=True)
            run(sys.executable, examples/'deploy/package.py', '--website', website, '--output', stage)
            binary = stage/'caddy-plotsrv'
            env = os.environ.copy()
            if supplied:
                print(f'Reusing Caddy: {supplied}', flush=True)
                shutil.copyfile(supplied, binary)
                binary.chmod(0o755)
            else:
                env.update(PATH=str(go.parent)+os.pathsep+env.get('PATH',''), TMPDIR=str(scratch),
                           GOOS='linux', GOARCH=arch, CGO_ENABLED='0')
                print(run(go, 'version', capture_output=True, text=True).stdout.strip(), flush=True)
                print('Building Caddy; the first build can take several minutes.', flush=True)
                run('sh', examples/'deploy/build-caddy.sh', binary, env=env)
            # Check the ELF architecture even when a different architecture is emulated.
            with binary.open('rb') as stream:
                elf = stream.read(20)
            machine = int.from_bytes(elf[18:20], 'little')
            if elf[:6] != b'\x7fELF\x02\x01' or machine != {'amd64':62,'arm64':183}[arch]:
                raise ValueError(f'Caddy must be a Linux {arch} ELF binary matching this builder/VM')
            modules = run(binary, 'list-modules', capture_output=True, text=True).stdout.splitlines()
            if not {'http.handlers.rate_limit', 'dns.providers.cloudflare'} <= set(modules):
                raise ValueError('Caddy is missing the rate-limit or Cloudflare DNS module')
            # A format-valid dummy token validates configuration without real credentials.
            env.update(CF_API_TOKEN='v'*40, XDG_DATA_HOME=str(scratch/'caddy-data'),
                       XDG_CONFIG_HOME=str(scratch/'caddy-config'))
            run(binary, 'validate', '--config', examples/'deploy/Caddyfile', '--adapter', 'caddyfile', env=env)
            caddy_version = run(binary, 'version', capture_output=True, text=True).stdout.strip()
            assemble_tooling(stage)
            guide = (stage/'tooling/deploy/DEPLOYMENT-GUIDE.md').read_text()
            guide = guide.replace('/home/samane/Projects/plotsrv-homepage/plotsrv-upload', str(output)).replace('Linux x86-64 bundle', f'Linux {platform.machine()} bundle').replace('prod1 is x86-64', f'prod1 is {platform.machine()}')
            (stage/'DEPLOYMENT-GUIDE.md').write_text(guide)
            shutil.copyfile(stage/'tooling/deploy/build-bundle.py', stage/'build-plotsrv-bundle')
            (stage/'build-plotsrv-bundle').chmod(0o755)
            (stage/'BUILD-INFO.json').write_text(json.dumps({
                'builder_version':VERSION, 'built_at':datetime.now(timezone.utc).isoformat(),
                'target':f'linux/{arch}', 'examples':str(examples), 'website':str(website),
                'caddy_version':caddy_version, 'caddy_reused':bool(supplied),
                'build_script_sha256':digest(examples/'deploy/build-caddy.sh'),
                'sources':'Current working files, including uncommitted changes',
            }, indent=2)+'\n')
            write_manifest(stage)
            backup = None
            if output.exists():
                backup = output.with_name(output.name+'.backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
                output.rename(backup)
            try:
                stage.rename(output)
            except BaseException:
                if backup:
                    backup.rename(output)
                raise
            print(f'\nBundle ready: {output}')
            if backup:
                print(f'Previous bundle retained: {backup}')
            print(f'Caddy: {caddy_version} (linux/{arch})')
            print(f'Guide: {output / "DEPLOYMENT-GUIDE.md"}')
            print(f'Verify with: cd {output} && sha256sum --check SHA256SUMS')



def assemble_tooling(stage):
    """Expose the exact tooling snapshot already present in the demo archive."""
    with tarfile.open(stage / 'plotsrv-examples-demos.tar.gz', 'r:gz') as source:
        for member in source.getmembers():
            relative = Path(member.name)
            if relative.parts[0] != 'deploy':
                continue
            if relative.is_absolute() or '..' in relative.parts or not member.isfile():
                raise ValueError(f'Invalid bundled tooling: {member.name}')
            target = stage / 'tooling' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(member) as inp, target.open('xb') as out:
                shutil.copyfileobj(inp, out)
            target.chmod(0o755 if target.suffix == '.sh' else 0o644)
    shutil.copyfile(stage / 'tooling/deploy/deploy-plotsrv.sh', stage / 'deploy-plotsrv.sh')
    (stage / 'deploy-plotsrv.sh').chmod(0o755)


def write_manifest(stage):
    delivered = sorted(p for p in stage.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
    (stage / 'SHA256SUMS').write_text(''.join(
        f'{digest(p)}  {p.relative_to(stage).as_posix()}\n' for p in delivered))

def main():
    if sys.version_info < (3,11):
        raise SystemExit('Python 3.11+ required')
    args = parser().parse_args()
    try:
        build(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f'ERROR: {exc}') from None


if __name__ == '__main__':
    main()
