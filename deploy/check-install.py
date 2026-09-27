"""Fail early if the demo installation cannot survive ProtectHome=true."""
from importlib.util import find_spec
from pathlib import Path
import sys


def visible_path(value):
    path = Path(value).resolve()
    if any(path == root or root in path.parents for root in (Path('/home'), Path('/root'), Path('/run/user'))):
        raise RuntimeError(f"installation uses a path hidden by ProtectHome: {path}")
    return path


def main():
    interpreter = visible_path(sys.executable)
    for name in ('plotsrv', 'pandas', 'PIL', 'matplotlib'):
        spec = find_spec(name)
        if spec is None or not spec.origin:
            raise RuntimeError(f"missing required package: {name}")
        visible_path(spec.origin)
    from plotsrv.config import get_browser_update_limits
    get_browser_update_limits()
    print(f"Demo interpreter and packages are accessible: {interpreter}")


if __name__ == '__main__':
    main()
