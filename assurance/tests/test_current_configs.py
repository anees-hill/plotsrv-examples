"""Check representative configs against the explicitly installed live candidate."""

from pathlib import Path
import sys

import pytest

sys.dont_write_bytecode = True

from plotsrv import config, settings
from plotsrv.ui_config import load_ui_settings
from plotsrv_examples.doctor import report


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def selected_candidate():
    provenance = report()
    assert provenance["readiness"] == "ready", provenance


@pytest.mark.parametrize("name", ["minimal", "bounded"])
def test_current_limits(name, monkeypatch):
    monkeypatch.setattr(settings, "_CTX", settings.RuntimeContext())
    monkeypatch.setattr(settings, "_CONFIG_CACHE", {})
    monkeypatch.delenv("PLOTSRV_NAME", raising=False)
    path = ROOT / "configs/current" / f"{name}.yml"
    settings.set_runtime_context(config_path=path)
    assert settings.load_config()
    assert config.get_watch_max_bytes() == 2 * 1024 * 1024
    assert config.get_table_truncate_rows() == 100
    assert config.get_table_truncate_columns() == 20
    assert config.get_storage_enabled() is False
    if name == "bounded":
        assert config.get_table_view_mode() == "simple"
        assert config.get_plot_dpi() == 120
        assert config.get_publish_max_table_rows() == 500
        assert config.get_publish_max_table_columns() == 30
        assert config.get_publish_max_artifact_text_chars() == 24000
        assert config.get_watch_file_threshold_bytes() == 1024 * 1024
        assert config.get_watch_active_load_max_concurrent() == 1
        assert config.get_watch_active_load_wait_timeout_s() == 0.5
        assert config.get_storage_default_keep_last() == 3
        assert config.get_storage_max_snapshot_size_bytes() == 2 * 1024 * 1024
        assert config.get_freshness_enabled() is True
        assert config.get_freshness_expected_every_s() == 15
        assert config.get_freshness_warn_after_s() == 30
        assert config.get_freshness_overdue_after_s() == 60


def test_gallery_ui_profile(monkeypatch):
    monkeypatch.setattr(settings, "_CTX", settings.RuntimeContext())
    monkeypatch.setattr(settings, "_CONFIG_CACHE", {})
    monkeypatch.delenv("PLOTSRV_NAME", raising=False)
    path = ROOT / "configs/current/demo-ui.yml"
    settings.set_runtime_context(config_path=path)
    assert settings.load_config()
    ui = load_ui_settings()
    assert ui.page_title == "plotsrv examples gallery"
    assert ui.header_text == "Examples gallery"
    assert [item.view_id for item in ui.featured_views] == ["example-pandas", "example-matplotlib"]
    assert [item.view_id for item in ui.compact_views] == ["gallery-html", "gallery-text"]
