"""Exercise packaging and installer transitions without touching host services."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'deploy'))
import manage
import package


def tar(path, entries):
    with tarfile.open(path, 'w:gz') as out:
        for name, content, kind in entries:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(content)
            if kind == tarfile.SYMTYPE:
                info.linkname = '/etc/shadow'
            out.addfile(info, io.BytesIO(content))


@pytest.mark.parametrize('name,kind', [('../escape', tarfile.REGTYPE), ('/escape', tarfile.REGTYPE),
    ('assets/link.png', tarfile.SYMTYPE), ('assets/device.png', tarfile.CHRTYPE),
    ('.env', tarfile.REGTYPE), ('assets/.env.png', tarfile.REGTYPE), ('scripts/private.py', tarfile.REGTYPE)])
def test_rejects_unsafe_archive_without_extracting(tmp_path, name, kind):
    path = tmp_path / 'bad.tar.gz'
    tar(path, [('index.html', b'hello', tarfile.REGTYPE), (name, b'', kind)])
    target = tmp_path / 'unpacked'
    target.mkdir()
    with pytest.raises(ValueError):
        manage.extract(path, target, 'website')
    assert not list(target.iterdir())


def test_packager_round_trip_and_exclusions(tmp_path):
    website = tmp_path / 'website'
    for name in package.WEBSITE_FILES + ('assets/logo.png', 'assets/screenshots/manifest.json', '.env', 'scripts/private.py', 'assets/.env.png'):
        p = website / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('test')
    target = tmp_path / 'website.tar.gz'
    package.archive(website, 'website', target)
    dest = tmp_path / 'unpacked'
    dest.mkdir()
    manage.extract(target, dest, 'website')
    assert (dest / 'assets/logo.png').exists()
    assert not (dest / 'assets/screenshots/manifest.json').exists()
    assert not (dest / 'assets/.env.png').exists()
    assert not (dest / 'scripts').exists()


@pytest.fixture
def installer(tmp_path, monkeypatch):
    for name, value in {'ETC': tmp_path/'etc', 'STATE': tmp_path/'etc/deployment.json',
                        'RELEASES': tmp_path/'releases', 'UNITS': tmp_path/'units',
                        'WEBSITE': tmp_path/'website', 'EXAMPLES': tmp_path/'examples'}.items():
        monkeypatch.setattr(manage, name, value)
    manage.ETC.mkdir(); manage.UNITS.mkdir()
    calls=[]
    def run(*args, **kwargs):
        calls.append(tuple(map(str,args)))
        return SimpleNamespace(stdout='', returncode=0)
    monkeypatch.setattr(manage, 'run', run)
    monkeypatch.setattr(manage, 'preflight', lambda args: None)
    monkeypatch.setattr(manage, 'ensure_user', lambda *args: None)
    monkeypatch.setattr(manage, 'validate_proxy', lambda *args: None)
    monkeypatch.setattr(manage, 'prepare_python', lambda *args: None)
    monkeypatch.setattr(manage, 'check_data', lambda name: None)
    monkeypatch.setattr(manage.subprocess, 'run', run)
    return calls


def website_archive(tmp_path):
    path = tmp_path / 'website.tar.gz'
    tar(path, [(name, b'test', tarfile.REGTYPE) for name in package.WEBSITE_FILES])
    return path


def args(kind, archive=None, profile=None):
    return SimpleNamespace(kind=kind, archive=archive, profile=profile, requirements=None)


def test_website_install_retains_demos_and_can_be_repeated(tmp_path, installer):
    manage.STATE.write_text(json.dumps({'website':False,'demos':['live_import']}))
    archive=website_archive(tmp_path)
    manage.deploy(args('website', archive))
    first=manage.WEBSITE.resolve()
    manage.deploy(args('website', archive))
    assert manage.load_state()=={'website':True,'demos':['live_import']}
    assert manage.WEBSITE.resolve()!=first
    assert manage.WEBSITE.with_name('website.previous').resolve()==first
    config=(manage.ETC/'Caddyfile').read_text()
    assert '\nplotsrv.com {' in config and '\nlive-demo.plotsrv.com {' in config
    assert not any('disable' in call for call in installer)


def test_all_to_retail_retains_website_tokens_and_state(tmp_path, installer):
    release=tmp_path/'old';release.mkdir();manage.EXAMPLES.symlink_to(release)
    manage.STATE.write_text(json.dumps({'website':True,'demos':manage.PROFILES['all']}))
    for name,key in manage.TOKENS.items():
        (manage.ETC/f'{name}.env').write_text(key+'=existing-token\n')
    manage.deploy(args('demos', profile='retail'))
    assert manage.load_state()=={'website':True,'demos':['retail']}
    assert manage.EXAMPLES.resolve()==release
    assert 'existing-token' in (manage.ETC/'retail.env').read_text()
    stopped=[c for c in installer if c[:3]==('systemctl','disable','--now')]
    assert len(stopped)==2
    assert not any('plotsrv-demo@retail.service' in c for c in stopped)
    assert not any('pip' in c for c in installer)


def test_bad_config_does_not_replace_existing_site(tmp_path, installer, monkeypatch):
    old=tmp_path/'old';old.mkdir();manage.WEBSITE.symlink_to(old)
    manage.STATE.write_text(json.dumps({'website':True,'demos':[]}))
    monkeypatch.setattr(manage,'validate_proxy',lambda p: (_ for _ in ()).throw(ValueError('bad config')))
    with pytest.raises(ValueError):manage.deploy(args('website',website_archive(tmp_path)))
    assert manage.WEBSITE.resolve()==old
    assert installer==[]


def test_failed_reload_restores_site_config_and_manifest(tmp_path, installer, monkeypatch):
    old=tmp_path/'old';old.mkdir();manage.WEBSITE.symlink_to(old)
    previous={'website':True,'demos':[]}
    manage.STATE.write_text(json.dumps(previous))
    (manage.ETC/'Caddyfile').write_text('old config')
    original=manage.run
    failed=False
    def fail_once(*a,**kw):
        nonlocal failed
        if a[:2]==('systemctl','reload') and not failed:
            failed=True
            raise RuntimeError('reload failed')
        return original(*a,**kw)
    monkeypatch.setattr(manage,'run',fail_once)
    with pytest.raises(RuntimeError):manage.deploy(args('website',website_archive(tmp_path)))
    assert manage.WEBSITE.resolve()==old
    assert (manage.ETC/'Caddyfile').read_text()=='old config'
    assert manage.load_state()==previous


@pytest.mark.parametrize('profile',['all','retail','live','scans'])
def test_fresh_demo_profile_and_pypi_preflight(tmp_path, installer, monkeypatch, profile):
    archive=tmp_path/'demos.tar.gz'
    package.archive(ROOT,'demos',archive)
    checked=[]
    monkeypatch.setattr(manage,'prepare_python',lambda *a:checked.append(a))
    manage.deploy(args('demos',archive,profile))
    assert checked
    assert manage.load_state()=={'website':False,'demos':manage.PROFILES[profile]}
    assert manage.EXAMPLES.is_symlink()
    assert any('configure-state.py' in ' '.join(call) for call in installer)
    probes = [call for call in installer if call[0] == 'systemd-run']
    assert len(probes) == len(manage.PROFILES[profile])
    for name in manage.PROFILES[profile]:
        probe = next(call for call in probes if call[-1] == f'/var/lib/plotsrv-demo/{name}')
        assert f'ReadWritePaths=/var/lib/plotsrv-demo/{name}' in probe
        assert f'Environment=MPLCONFIGDIR=/var/lib/plotsrv-demo/{name}/.cache/matplotlib' in probe
        assert any(f'/demos/{name}/plotsrv.yml' in arg for arg in probe)
    for name in manage.PROFILES[profile]:
        assert (manage.ETC/f'{name}.env').stat().st_mode & 0o777 == 0o600
    assert '\nplotsrv.com {' not in (manage.ETC/'Caddyfile').read_text()


def test_failed_demo_readiness_restores_previous_release_and_selection(tmp_path, installer, monkeypatch):
    old=tmp_path/'old';old.mkdir();manage.EXAMPLES.symlink_to(old)
    previous={'website':True,'demos':['retail']}
    manage.STATE.write_text(json.dumps(previous))
    (manage.ETC/'Caddyfile').write_text('previous routes')
    (manage.ETC/'retail.env').write_text('PLOTSRV_RETAIL_TOKEN=keep-this-token\n')
    archive=tmp_path/'demos.tar.gz';package.archive(ROOT,'demos',archive)
    monkeypatch.setattr(manage,'check_data',lambda name: (_ for _ in ()).throw(RuntimeError('no published view')))
    with pytest.raises(RuntimeError):manage.deploy(args('demos',archive,'all'))
    assert manage.EXAMPLES.resolve()==old
    assert manage.load_state()==previous
    assert (manage.ETC/'Caddyfile').read_text()=='previous routes'
    assert (manage.ETC/'retail.env').read_text()=='PLOTSRV_RETAIL_TOKEN=keep-this-token\n'
    assert ('systemctl','restart','plotsrv-demo@retail.service') in installer


def test_failed_package_checks_never_switch_live_services(tmp_path, installer, monkeypatch):
    old=tmp_path/'old';old.mkdir();manage.EXAMPLES.symlink_to(old)
    previous={'website':True,'demos':['retail']}
    manage.STATE.write_text(json.dumps(previous))
    archive=tmp_path/'demos.tar.gz';package.archive(ROOT,'demos',archive)
    monkeypatch.setattr(manage,'prepare_python',lambda *a: (_ for _ in ()).throw(RuntimeError('incompatible PyPI release')))
    with pytest.raises(RuntimeError):manage.deploy(args('demos',archive,'all'))
    assert manage.EXAMPLES.resolve()==old
    assert manage.load_state()==previous
    assert not installer
