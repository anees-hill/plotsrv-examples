"""Set storage locations in staged VM configs; source examples stay portable."""
import argparse
from pathlib import Path
import yaml

STORES = {'retail': '.plotsrv/retail', 'live_import': '.plotsrv/store',
          'scan_audit': '.plotsrv/scans-receiver'}


def configure(release, state_root):
    for name, relative in STORES.items():
        path = release / 'demos' / name / 'plotsrv.yml'
        source = path.with_name('plotsrv.source.yml')
        if not source.exists():
            source.write_bytes(path.read_bytes())
        data = yaml.safe_load(path.read_text())
        data.setdefault('storage-settings', {})['root_dir'] = str(
            (state_root / name / relative).resolve())
        path.write_text(yaml.safe_dump(data, sort_keys=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release', type=Path)
    parser.add_argument('--state-root', type=Path, default=Path('/var/lib/plotsrv-demo'))
    args = parser.parse_args()
    configure(args.release, args.state_root)
