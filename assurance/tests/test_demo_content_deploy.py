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
