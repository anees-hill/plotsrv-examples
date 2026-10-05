"""Production bundle entrypoint, version selection and update failure boundaries."""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "deploy"))
import bundle
import manage
import package
from test_demo_content_deploy import legacy_installation

spec = importlib.util.spec_from_file_location(
    "build_bundle", ROOT / "deploy/build-bundle.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.fixture
def upload(tmp_path):
    stage = tmp_path / "upload with spaces"
    stage.mkdir()
    website = tmp_path / "website"
    for name in package.WEBSITE_FILES:
        path = website / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("website fixture")
    package.archive(ROOT, "demos", stage / "plotsrv-examples-demos.tar.gz")
    package.archive(website, "website", stage / "plotsrv-homepage.tar.gz")
    builder.assemble_tooling(stage)
    (stage / "DEPLOYMENT-GUIDE.md").write_bytes(
        (ROOT / "deploy/DEPLOYMENT-GUIDE.md").read_bytes()
    )
    (stage / "build-plotsrv-bundle").write_bytes(
        (ROOT / "deploy/build-bundle.py").read_bytes()
    )
    (stage / "BUILD-INFO.json").write_text("{}")
    (stage / "caddy-plotsrv").write_text("fixture only")
    builder.write_manifest(stage)
    return stage


def test_complete_bundle_works_without_extraction_from_another_directory(
    upload, tmp_path
):
    bundle.verify_bundle(upload)
    result = subprocess.run(
        ["sh", str(upload / "deploy-plotsrv.sh"), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "select-demos" in result.stdout and "website" in result.stdout
    subprocess.run(
        ["sha256sum", "--check", "SHA256SUMS"],
        cwd=upload,
        check=True,
        capture_output=True,
    )
    assert not list((upload / "tooling").rglob("__pycache__"))


@pytest.mark.parametrize(
    "command,profile,kinds",
    [
        ("website", None, ["website"]),
        ("demos", "all", ["demos"]),
        ("demos", "retail", ["demos"]),
        ("demos", "live", ["demos"]),
        ("demos", "scans", ["demos"]),
        ("both", "all", ["demos", "website"]),
        ("both", "retail", ["demos", "website"]),
        ("select-demos", "all", ["demos"]),
        ("select-demos", "retail", ["demos"]),
    ],
)
def test_commands_dispatch_exact_archives_and_profiles(
    upload, monkeypatch, command, profile, kinds
):
    calls = []
    monkeypatch.setattr(bundle.os, "geteuid", lambda: 0)
    monkeypatch.setattr(bundle.subprocess, "run", lambda args, **kw: calls.append(args))
    argv = [command] + ([profile] if profile else [])
    assert bundle.execute(upload, bundle.parser().parse_args(argv)) == 0
    assert [args[3] for args in calls] == kinds
    for args in calls:
        assert args[2] == str(upload / "tooling/deploy/manage.py")
        if args[3] == "demos":
            assert args[4] == profile
            assert len(args) == (5 if command == "select-demos" else 6)
        else:
            assert args[4] == str(upload / "plotsrv-homepage.tar.gz")


@pytest.mark.parametrize(
    "damage", ["changed", "missing", "extra", "symlink", "manifest"]
)
def test_damaged_or_overlaid_bundles_never_start_deployment(
    upload, monkeypatch, damage
):
    target = upload / "tooling/deploy/manage.py"
    if damage == "changed":
        target.write_text("changed")
    elif damage == "missing":
        target.unlink()
    elif damage == "extra":
        (upload / "tooling/deploy/stale.py").write_text("old installer")
    elif damage == "symlink":
        data = target.read_bytes()
        target.unlink()
        outside = upload.parent / "outside.py"
        outside.write_bytes(data)
        target.symlink_to(outside)
    else:
        (upload / "SHA256SUMS").write_text("")
    monkeypatch.setattr(bundle.os, "geteuid", lambda: 0)
    calls = []
    monkeypatch.setattr(bundle.subprocess, "run", lambda *a, **kw: calls.append(a))
    with pytest.raises((ValueError, OSError)):
        bundle.execute(upload, bundle.parser().parse_args(["both", "all"]))
    assert calls == []


@pytest.mark.parametrize(
    "failed_kind,expected", [("demos", ["demos"]), ("website", ["demos", "website"])]
)
def test_combined_updates_stop_and_report_partial_success(
    upload, monkeypatch, capsys, failed_kind, expected
):
    calls = []
    monkeypatch.setattr(bundle.os, "geteuid", lambda: 0)

    def run(args, **kwargs):
        calls.append(args[3])
        if args[3] == failed_kind:
            raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(bundle.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        bundle.execute(upload, bundle.parser().parse_args(["both", "all"]))
    assert calls == expected
    assert ("Demos updated successfully" in capsys.readouterr().err) == (
        failed_kind == "website"
    )


def test_requirements_are_explicit_and_not_accepted_for_selection(
    upload, tmp_path, monkeypatch
):
    req = tmp_path / "saved packages.txt"
    req.write_text("plotsrv==0.8.0\n")
    calls = []
    monkeypatch.setattr(bundle.os, "geteuid", lambda: 0)
    monkeypatch.setattr(bundle.subprocess, "run", lambda args, **kw: calls.append(args))
    args = bundle.parser().parse_args(["demos", "live", "--requirements", str(req)])
    bundle.execute(upload, args)
    assert calls[0][-2:] == ["--requirements", str(req)]
    with pytest.raises(SystemExit):
        bundle.parser().parse_args(["select-demos", "all", "--requirements", str(req)])


def test_latest_release_ignores_prereleases_yanked_and_empty_versions(monkeypatch):
    releases = {
        v: [{"yanked": False}]
        for v in (
            "0.8.9",
            "0.8.10",
            "0.8.10.post1",
            "0.9.0rc1",
            "1.0.dev1",
            "1.0+local",
        )
    }
    releases["0.9.0"] = [{"yanked": True}]
    releases["9.0"] = []

    def metadata(request, timeout):
        assert request.full_url == "https://pypi.org/pypi/plotsrv/json"
        assert request.get_header("Cache-control") == "no-cache"
        return io.BytesIO(json.dumps({"releases": releases}).encode())

    monkeypatch.setattr(manage.urllib.request, "urlopen", metadata)
    assert manage.latest_plotsrv() == "0.8.10.post1"
    releases["1.0.0"] = [{"yanked": False}]
    releases["1.0.post1"] = [{"yanked": False}]
    assert manage.latest_plotsrv() == "1.0.post1"
    releases.clear()
    with pytest.raises(ValueError, match="no stable"):
        manage.latest_plotsrv()


@pytest.fixture
def python_install(tmp_path, monkeypatch):
    release = tmp_path / "candidate"
    (release / "deploy").mkdir(parents=True)
    (release / "deploy/requirements.txt").write_text(
        "plotsrv\npandas\nmatplotlib>=3.9\npillow\n"
    )
    tools = tmp_path / "tools"
    (tools / "bin").mkdir(parents=True)
    (tools / "bin/uv").touch()
    monkeypatch.setattr(manage, "TOOLS", tools)
    monkeypatch.setattr(manage, "EXAMPLES", tmp_path / "old")
    monkeypatch.setattr(
        manage,
        "installed_version",
        lambda p: "0.8.0" if p == manage.EXAMPLES else "0.9.0",
    )
    monkeypatch.setattr(manage, "latest_plotsrv", lambda: "0.9.0")
    calls = []

    def run(*args, **kwargs):
        calls.append((list(map(str, args)), kwargs))
        return SimpleNamespace(stdout="plotsrv==0.9.0\n")

    monkeypatch.setattr(manage, "run", run)
    return release, calls


def test_package_update_refreshes_pypi_pins_target_and_ignores_user_index(
    python_install, monkeypatch, capsys
):
    release, calls = python_install
    monkeypatch.setenv("UV_INDEX_URL", "https://invalid.example/simple")
    monkeypatch.setenv("UV_OFFLINE", "true")
    monkeypatch.setenv("PIP_EXTRA_INDEX_URL", "https://invalid.example/simple")
    monkeypatch.setenv("PYTHONPATH", "/local/checkout")
    manage.prepare_python(release, None)
    command, kwargs = next(c for c in calls if c[0][1:3] == ["pip", "install"])
    assert (
        "plotsrv==0.9.0" in command
        and "--refresh" in command
        and "--upgrade" in command
    )
    assert command[command.index("--index-url") + 1] == "https://pypi.org/simple"
    for key in ("UV_INDEX_URL", "UV_OFFLINE", "PIP_EXTRA_INDEX_URL", "PYTHONPATH"):
        assert key not in kwargs["env"]
    assert kwargs["env"]["UV_NO_CONFIG"] == "true"
    assert "previous: 0.8.0" in capsys.readouterr().out
    assert (release / "deployed-python-packages.txt").read_text() == "plotsrv==0.9.0\n"


def test_explicit_freeze_skips_latest_lookup(python_install, monkeypatch):
    release, calls = python_install
    req = release / "frozen.txt"
    req.write_text("plotsrv==0.8.0\npandas==3.0.0\n")
    monkeypatch.setattr(
        manage,
        "latest_plotsrv",
        lambda: pytest.fail("must not query latest for pinned packages"),
    )
    monkeypatch.setattr(manage, "installed_version", lambda p: "0.8.0")
    manage.prepare_python(release, req)
    assert any("plotsrv==0.8.0" in call for call, kw in calls)


@pytest.mark.parametrize("problem", ["download", "wrong-version", "bad-freeze"])
def test_package_failures_never_reach_activation(python_install, monkeypatch, problem):
    release, calls = python_install
    req = None
    if problem == "download":
        monkeypatch.setattr(
            manage,
            "latest_plotsrv",
            lambda: (_ for _ in ()).throw(OSError("PyPI unavailable")),
        )
    elif problem == "wrong-version":
        monkeypatch.setattr(manage, "installed_version", lambda p: "0.8.0")
    else:
        req = release / "bad.txt"
        req.write_text("pandas==3.0.0\n")
    with pytest.raises((OSError, ValueError, RuntimeError)):
        manage.prepare_python(release, req)
    assert not (release / "deployed-python-packages.txt").exists()
    assert not any(call[0] == "systemctl" for call, kw in calls)


def test_all_to_one_and_back_keeps_site_state_and_packages(tmp_path, monkeypatch):
    old, calls = legacy_installation(tmp_path, monkeypatch)
    manage.STATE.write_text(
        json.dumps({"website": True, "demos": manage.PROFILES["all"]})
    )
    for name, key in manage.TOKENS.items():
        (manage.ETC / f"{name}.env").write_text(key + "=fixture\n")
    for profile in ("retail", "all"):
        manage.deploy(
            SimpleNamespace(
                kind="demos", archive=None, profile=profile, requirements=None
            )
        )
        assert manage.load_state() == {
            "website": True,
            "demos": manage.PROFILES[profile],
        }
        assert manage.EXAMPLES.resolve() == old
    assert ("systemctl", "start", "plotsrv-demo@live_import.service") in calls
    assert not any("pip" in call for call in calls)


def test_status_reports_failed_expected_service_without_modifying_state(
    tmp_path, monkeypatch, capsys
):
    old, calls = legacy_installation(tmp_path, monkeypatch)
    monkeypatch.setattr(manage, "installed_version", lambda path: "0.9.0")

    def run(args, **kw):
        assert args[:2] == ["systemctl", "is-active"]
        return SimpleNamespace(stdout="failed\n", returncode=3)

    monkeypatch.setattr(bundle.subprocess, "run", run)
    assert bundle.status() == 1
    assert "Installed plotsrv: 0.9.0" in capsys.readouterr().out
    assert calls == [] and manage.EXAMPLES.resolve() == old
