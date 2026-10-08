"""Storage must be writable even when config/code live in an immutable release."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('configure_state', ROOT/'deploy/configure-state.py')
state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state)


@pytest.mark.parametrize('name', state.STORES)
def test_resolved_storage_outside_readonly_release(tmp_path, name):
    release = tmp_path/'release'
    writable = tmp_path/'state'
    for demo in state.STORES:
        dest = release/'demos'/demo
        dest.mkdir(parents=True)
        shutil.copyfile(ROOT/'demos'/demo/'plotsrv.yml', dest/'plotsrv.yml')
    state.configure(release, writable)
    config = release/'demos'/name/'plotsrv.yml'
    content = config.read_bytes()
    cwd = writable/name
    cwd.mkdir(parents=True)
    config.chmod(0o444)
    config.parent.chmod(0o555)
    env = {**os.environ, 'PLOTSRV_CONFIG': str(config), 'MPLCONFIGDIR': str(cwd/'.cache/matplotlib')}
    try:
        # Use plotsrv's real resolution and backend, not a YAML-only assertion.
        subprocess.run([sys.executable, '-c', '''
import importlib.util, sys
from pathlib import Path
import plotsrv.config as config
from plotsrv.storage.latest import FileLatestStateBackend
spec = importlib.util.spec_from_file_location('check_install', sys.argv[1])
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
check.check_storage(Path(sys.argv[2]))
FileLatestStateBackend(root_dir=config.get_storage_root_dir())
import matplotlib
assert Path(matplotlib.get_configdir()).is_relative_to(Path(sys.argv[2]))
''', str(ROOT/'deploy/check-install.py'), str(cwd)], cwd=cwd, env=env, check=True)
        assert (cwd/state.STORES[name]).is_dir()
        assert not (config.parent/'.plotsrv').exists()
        assert config.read_bytes() == content
        source = yaml.safe_load((ROOT/'demos'/name/'plotsrv.yml').read_text())
        assert not Path(source['storage-settings'].get('root_dir', '.plotsrv/store')).is_absolute()
    finally:
        config.parent.chmod(0o755)
        config.chmod(0o644)


def test_preflight_rejects_original_config_relative_storage(tmp_path):
    spec = importlib.util.spec_from_file_location('check_install', ROOT/'deploy/check-install.py')
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    import plotsrv.config as config
    from unittest.mock import patch
    with patch.object(config, 'get_storage_root_dir', return_value=tmp_path/'release/.plotsrv'):
        with pytest.raises(RuntimeError, match='outside writable state'):
            check.check_storage(tmp_path/'state')
