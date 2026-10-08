"""Moving demos must retain their route boundaries and omit other origins."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'deploy/render-caddy.py'
spec = importlib.util.spec_from_file_location('demo_hosts', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('selected', [
    ['website', 'landing'], ['website', 'landing', 'retail'], ['live_import'], ['scan_audit'], list(module.HOSTS),
])
def test_profiles_keep_only_selected_sites_and_original_boundaries(selected):
    rendered = module.render(selected)
    source = (ROOT / 'deploy/Caddyfile').read_text()
    for name, host in module.HOSTS.items():
        marker = f'\n{host} {{'
        assert (marker in rendered) == (name in selected)
        if name in selected:
            start = source.index(marker)
            end = source.index('\n}', start) + len('\n}')
            assert source[start:end] in rendered
    assert rendered.startswith(source[:source.index('\nplotsrv.com {')])
    if 'landing' in selected:
        # The landing redirects still reach hosts now served on other VMs.
        for host in [module.HOSTS[n] for n in ("retail", "live_import", "scan_audit")]:
            assert f'https://{host}/' in rendered


def test_all_profile_preserves_full_template():
    result = subprocess.run([sys.executable, str(SCRIPT), 'all'], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == (ROOT / 'deploy/Caddyfile').read_text().strip()


@pytest.mark.parametrize('arguments', [[], ['unknown'], ['all', 'retail']])
def test_invalid_profiles_produce_no_config(arguments):
    result = subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True)
    assert result.returncode != 0
    assert not result.stdout
