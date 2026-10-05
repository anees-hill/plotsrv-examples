"""Fail early if the demo installation cannot survive ProtectHome=true."""
from importlib.metadata import version
from importlib.util import find_spec
from pathlib import Path
import sys
import argparse
import tempfile


def visible_path(value):
    path = Path(value).resolve()
    if any(path == root or root in path.parents for root in (Path('/home'), Path('/root'), Path('/run/user'))):
        raise RuntimeError(f"installation uses a path hidden by ProtectHome: {path}")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path)
    args = parser.parse_args()
    interpreter = visible_path(sys.executable)
    for name in ('plotsrv', 'pandas', 'PIL', 'matplotlib'):
        spec = find_spec(name)
        if spec is None or not spec.origin:
            raise RuntimeError(f"missing required package: {name}")
        visible_path(spec.origin)
    check_core_features()
    if args.state_dir:
        check_storage(args.state_dir)
    print(f"Demo interpreter and packages are accessible: {interpreter}")


def check_storage(state_dir):
    import plotsrv.config as config
    root = config.get_storage_root_dir().resolve()
    if not root.is_relative_to(state_dir.resolve()):
        raise RuntimeError(f'Demo storage {root} is outside writable state directory {state_dir}')
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=root) as probe:
        probe.write(b'storage preflight')
        probe.flush()
    print(f'Demo storage is writable: {root}')


def check_core_features():
    import inspect
    import plotsrv
    import plotsrv.config as config
    import plotsrv.runtime as runtime
    missing = []
    for name in ('publish_view', 'stream_view', 'flush_views'):
        if not callable(getattr(plotsrv, name, None)):
            missing.append(name)
    if not callable(getattr(config, 'get_browser_update_limits', None)):
        missing.append('browser-update-settings admission/lifetime support')
    if find_spec('plotsrv.standalone') is None:
        missing.append('plotsrv serve')
    if not {'destination', 'view_id'} <= set(inspect.signature(runtime.publish_watch_payload).parameters):
        missing.append('authenticated local watches with explicit view IDs')
    if missing:
        raise RuntimeError(
            f"Installed PyPI plotsrv {version('plotsrv')} lacks required demo features: "
            + ', '.join(missing)
            + '. Install a PyPI release containing these features before starting services.'
        )
    config.get_browser_update_limits()
    print(f"Installed plotsrv: {version('plotsrv')}")


if __name__ == '__main__':
    main()
