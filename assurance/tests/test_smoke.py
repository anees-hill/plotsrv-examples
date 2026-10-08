"""Receiver evidence for the restored release-smoke surfaces and honest failure."""

import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import psutil
import pytest

from plotsrv_examples.scenarios.smoke import publication_modes
from plotsrv_examples.smoke_inputs import prepare, table_rows
from plotsrv_examples.support.lifecycle import LifecycleError


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def disposable_repository(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "plotsrv-examples"\n')
    (tmp_path / ".git").mkdir()
    return tmp_path


@pytest.mark.parametrize("scenario", ["publication-modes", "watch-formats", "observation-changes"])
def test_live_smoke_receipt(scenario):
    completed = subprocess.run([sys.executable, "-B", "-m", "plotsrv_examples", "run", scenario],
                               cwd=ROOT, capture_output=True, text=True, timeout=120)
    result = json.loads(completed.stdout)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert result["success"] and result["owned_children_reaped"]
    assert result["manual_status"] == "pending"
    assert all(not psutil.pid_exists(c["pid"]) for c in result["children"])
    evidence = result["evidence"]
    if scenario == "publication-modes":
        assert len(evidence["publication_variants"]) == 4
        assert evidence["attached_modes"] == ["publish", "show", "watch"]
        assert evidence["render_limits"] == {"rows": 10, "columns": 5, "text_truncated": True}
    elif scenario == "watch-formats":
        assert evidence["memory"]["rows"] == evidence["file"]["rows"] == 1200
        assert evidence["head"]["excluded"] == evidence["tail"]["included"]
        assert "yaml" in evidence["formats"]
    else:
        assert evidence["metric_changes"] == [3, -3]
        assert [s["observed_missing"] for s in evidence["states"]] == [0, 3, 0]


def test_observation_fault_is_nonzero_and_reaps():
    completed = subprocess.run([sys.executable, "-B", "-m", "plotsrv_examples", "run",
                               "observation-changes", "--fault", "missing-evidence"],
                              cwd=ROOT, capture_output=True, text=True, timeout=45)
    result = json.loads(completed.stdout)
    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert not result["success"] and "deliberate failure" in result["error"]
    assert "evidence" not in result and result["owned_children_reaped"]
    assert all(not psutil.pid_exists(c["pid"]) for c in result["children"])


def test_wrong_export_cannot_pass_received_table_check():
    class Receiver:
        def start(self):
            pass

        def publish(self, *args):
            return SimpleNamespace(output=b'{"drained": true}')

        def artifact(self, *args):
            return {}

        def read(self, *args, **kwargs):
            return {"rows": table_rows()}

        def bytes(self, *args, **kwargs):
            return b'id,group,amount\n1,wrong,100\n'

    with pytest.raises(LifecycleError, match="Exported table differs"):
        publication_modes(Receiver())


@pytest.mark.parametrize("name", ["memory", "storage", "bounded", "simple", "no-tracebacks", "no-freshness"])
def test_manual_profile_effective_settings(disposable_repository, monkeypatch, name):
    from plotsrv import config, settings
    # prepare owns its workspace; the same helper backs the guide and scenarios.
    run = prepare(disposable_repository)
    monkeypatch.setattr(settings, "_CTX", settings.RuntimeContext())
    monkeypatch.setattr(settings, "_CONFIG_CACHE", {})
    monkeypatch.delenv("PLOTSRV_NAME", raising=False)
    settings.set_runtime_context(config_path=run / (name + ".yml"))
    assert settings.load_config()
    assert config.get_storage_enabled() is (name == "storage")
    assert config.get_storage_root_dir() == run / "store"
    assert config.get_storage_default_keep_last() == 3
    assert config.get_tracebacks_enabled() is (name != "no-tracebacks")
    assert config.get_freshness_enabled() is (name != "no-freshness")
    assert config.get_table_view_mode() == ("simple" if name == "simple" else "rich")
    assert config.get_table_truncate_rows() == (10 if name == "bounded" else 2000)
    assert config.get_table_truncate_columns() == (5 if name == "bounded" else 20)
    assert config.get_truncation_max_chars("text") == (80 if name == "bounded" else 20000)
    assert (run / "discovery").is_dir()


def test_manual_prepare_does_not_reuse_state(disposable_repository):
    first, second = prepare(disposable_repository), prepare(disposable_repository)
    assert first != second
    assert (first / "large.csv").read_bytes() == (second / "large.csv").read_bytes()
    assert (first / "small.csv").read_text().count("\n") == 100
    assert not (first / "store").exists()
