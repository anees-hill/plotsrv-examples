"""Deployment additions remain explicit and survive packaging/state relocation."""

import importlib.util
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "deploy"))
import manage
import package


def test_demo_archive_includes_only_the_required_new_assets(tmp_path):
    archive = tmp_path / "demos.tar.gz"
    package.archive(ROOT, "demos", archive)
    destination = tmp_path / "release"
    destination.mkdir()
    manage.extract(archive, destination, "demos")
    for path in (
        "demos/publishing.py",
        "demos/restore.py",
        "demos/retail/northstar.svg",
        "demos/live_import/reports.py",
        "deploy/systemd/plotsrv-demo-content@.service",
    ):
        assert (destination / path).read_bytes() == (ROOT / path).read_bytes()
    assert not list(destination.rglob("*.env"))
    spec = importlib.util.spec_from_file_location(
        "configure", ROOT / "deploy/configure-state.py"
    )
    configure = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(configure)
    configure.configure(destination, tmp_path / "state")
    for demo in ("retail", "live_import", "scan_audit"):
        source = destination / "demos" / demo / "plotsrv.source.yml"
        assert (
            source.read_bytes() == (ROOT / "demos" / demo / "plotsrv.yml").read_bytes()
        )
        runtime = yaml.safe_load(source.with_name("plotsrv.yml").read_text())
        assert Path(runtime["storage-settings"]["root_dir"]).is_relative_to(
            tmp_path / "state"
        )
    configure.configure(destination, tmp_path / "different-state")
    assert source.read_bytes() == (ROOT / "demos/scan_audit/plotsrv.yml").read_bytes()


def test_startup_work_is_separate_and_not_periodic():
    receiver = (ROOT / "deploy/systemd/plotsrv-demo@.service").read_text()
    content = (ROOT / "deploy/systemd/plotsrv-demo-content@.service").read_text()
    assert "Wants=plotsrv-demo-content@%i.service" in receiver
    assert "PartOf=plotsrv-demo@%i.service" in content
    assert "RemainAfterExit=yes" in content and "Nice=10" in content
    assert not list((ROOT / "deploy/systemd").glob("*content*.timer"))
    assert "MemoryMax=320M" in receiver and "MemoryMax=320M" in content
    assert "Restart=on-failure" in content


def test_missing_content_unit_rejected_before_extraction(tmp_path):
    import tarfile
    import pytest

    complete, incomplete = tmp_path / "complete.tar.gz", tmp_path / "incomplete.tar.gz"
    package.archive(ROOT, "demos", complete)
    with tarfile.open(complete) as source, tarfile.open(incomplete, "w:gz") as target:
        for member in source.getmembers():
            if member.name != "deploy/systemd/plotsrv-demo-content@.service":
                target.addfile(member, source.extractfile(member))
    destination = tmp_path / "release"
    destination.mkdir()
    with pytest.raises(ValueError, match="plotsrv-demo-content@"):
        manage.extract(incomplete, destination, "demos")
    assert not list(destination.iterdir())


def legacy_installation(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    for name, path in {
        "ETC": "etc",
        "STATE": "etc/deployment.json",
        "RELEASES": "releases",
        "UNITS": "units",
        "WEBSITE": "website",
        "EXAMPLES": "examples",
    }.items():
        monkeypatch.setattr(manage, name, tmp_path / path)
    manage.ETC.mkdir()
    manage.UNITS.mkdir()
    old = tmp_path / "old"
    source = old / "deploy/systemd"
    source.mkdir(parents=True)
    for path in (ROOT / "deploy/systemd").glob("*"):
        if path.name == "plotsrv-demo-content@.service":
            continue
        data = path.read_text().replace("Wants=plotsrv-demo-content@%i.service\n", "")
        (source / path.name).write_text(data)
        (manage.UNITS / path.name).write_text(data)
    manage.EXAMPLES.symlink_to(old)
    manage.STATE.write_text(json.dumps({"website": True, "demos": ["retail"]}))
    (manage.ETC / "Caddyfile").write_text("previous routes")
    (manage.ETC / "retail.env").write_text("PLOTSRV_RETAIL_TOKEN=fixture-token\n")
    calls = []

    def run(*args, **kwargs):
        call = tuple(map(str, args))
        calls.append(call)
        if call[:2] == ("systemctl", "start") and call[2].startswith(
            "plotsrv-demo-content@"
        ):
            assert (manage.UNITS / "plotsrv-demo-content@.service").is_file()
            assert (manage.EXAMPLES / "demos/restore.py").is_file()
        return SimpleNamespace(stdout="", returncode=0)

    for name in (
        "preflight",
        "ensure_user",
        "validate_proxy",
        "prepare_python",
        "check_data",
    ):
        monkeypatch.setattr(manage, name, lambda *args: None)
    monkeypatch.setattr(manage, "run", run)
    monkeypatch.setattr(manage.subprocess, "run", run)
    return old, calls


def test_failed_update_can_restart_release_without_content_job(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import pytest

    old, calls = legacy_installation(tmp_path, monkeypatch)
    archive = tmp_path / "demos.tar.gz"
    package.archive(ROOT, "demos", archive)

    def fail_readiness(name):
        raise RuntimeError("injected content failure")

    monkeypatch.setattr(manage, "check_data", fail_readiness)
    with pytest.raises(RuntimeError, match="injected content failure"):
        manage.deploy(
            SimpleNamespace(
                kind="demos", archive=archive, profile="retail", requirements=None
            )
        )
    assert manage.EXAMPLES.resolve() == old
    assert not (manage.UNITS / "plotsrv-demo-content@.service").exists()
    assert (
        "Wants=plotsrv-demo-content@"
        not in (manage.UNITS / "plotsrv-demo@.service").read_text()
    )
    assert calls[-1] == ("systemctl", "start", "plotsrv-demo-retail-publish.service")
    assert (manage.ETC / "Caddyfile").read_text() == "previous routes"


def test_profile_change_preserves_legacy_service_files(tmp_path, monkeypatch):
    from types import SimpleNamespace

    old, calls = legacy_installation(tmp_path, monkeypatch)
    manage.deploy(
        SimpleNamespace(kind="demos", archive=None, profile="retail", requirements=None)
    )
    assert manage.EXAMPLES.resolve() == old
    assert not (manage.UNITS / "plotsrv-demo-content@.service").exists()
    assert not any("plotsrv-demo-content@retail.service" in call for call in calls)
    assert (
        "Wants=plotsrv-demo-content@"
        not in (manage.UNITS / "plotsrv-demo@.service").read_text()
    )
