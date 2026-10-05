#!/usr/bin/env python3
"""Package current demo and website sources; no Git checkout or runtime state."""
import argparse
import hashlib
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
DEMOS = ('retail', 'live_import', 'scan_audit')
DEMO_ASSETS = (
    'demos/retail/northstar.svg',
    'demos/retail/logs/orders.log', 'demos/retail/logs/fulfillment-access.log',
    'demos/retail/previews/orders.png', 'demos/retail/previews/guide.png',
    'demos/live_import/previews/imports.png', 'demos/live_import/previews/report.png',
    'demos/live_import/previews/recent.png',
)
WEBSITE_FILES = ('index.html', 'styles.css', 'shared.css', 'app.js', 'navigation.js',
                 'demos/index.html', 'demos/styles.css')
SUFFIXES = {'.html', '.css', '.js', '.png', '.svg', '.webp', '.jpg', '.jpeg', '.ico', '.woff2'}


def files(root, kind):
    if kind == 'website':
        paths = [root / name for name in WEBSITE_FILES]
        paths += [p for p in (root / 'assets').rglob('*') if p.suffix.lower() in SUFFIXES]
    else:
        paths = [p for demo in DEMOS for p in (root / 'demos' / demo).rglob('*')
                 if p.suffix in {'.py', '.yml', '.yaml', '.md'}]
        paths += [root / 'demos/publishing.py', root / 'demos/restore.py']
        paths += [root / name for name in DEMO_ASSETS]
        paths += [p for p in (root / 'deploy').rglob('*')
                  if p.suffix in {'.py', '.sh', '.txt', '.md', '.service', '.timer'} or p.name == 'Caddyfile']
    for p in sorted(set(paths)):
        relative = p.relative_to(root)
        if any(part.startswith('.') or part == '__pycache__' for part in relative.parts):
            continue
        if p.is_symlink():
            raise ValueError(f'Refusing symlink: {p}')
        if not p.is_file():
            raise ValueError(f'Missing file: {p}')
        yield p, relative


def archive(root, kind, target):
    paths = list(files(root, kind))
    with tarfile.open(target, 'w:gz') as output:
        for p, relative in paths:
            info = output.gettarinfo(str(p), str(relative))
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            info.mode = 0o755 if p.suffix == '.sh' else 0o644
            with p.open('rb') as stream:
                output.addfile(info, stream)
    print(f'{target}: {len(paths)} files')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--website', type=Path, default=ROOT.parent / 'plotsrv-homepage')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    targets = [('demos', ROOT, 'plotsrv-examples-demos.tar.gz'),
               ('website', args.website.resolve(), 'plotsrv-homepage.tar.gz')]
    sums = []
    for kind, root, name in targets:
        target = args.output / name
        if target.exists():
            parser.error(f'{target} exists; use a new output directory')
        archive(root, kind, target)
        sums.append(f'{hashlib.sha256(target.read_bytes()).hexdigest()}  {name}\n')
    (args.output / 'SHA256SUMS').write_text(''.join(sums))


if __name__ == '__main__':
    main()
