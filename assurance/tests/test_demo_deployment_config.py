"""Keep the public demo receiver boundaries explicit as examples evolve."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_receivers_are_separate_locked_and_loopback_only():
    expected = {
        "retail": (8101, "PLOTSRV_RETAIL_TOKEN", {"retail:orders", "retail:sales", "retail:categories", "retail:returns", "retail:fulfillment", "retail:guide", "retail:summary"}),
        "live_import": (8102, "PLOTSRV_LIVE_TOKEN", {"live:imports"}),
        "scan_audit": (8103, "PLOTSRV_SCANS_TOKEN", {"scans:results", "scans:example", "scans:observed", "scans:changes"}),
    }
    for name, (port, token, ids) in expected.items():
        cfg = yaml.safe_load((ROOT / "demos" / name / "plotsrv.yml").read_text())
        server = cfg["server-settings"]
        assert server["bind"] == {"host": "127.0.0.1", "port": port}
        assert server["ingestion"] == {"bearer_token_env": token, "allow_remote_without_key": False}
        assert server["admission"]["mode"] == "catalogue-locked"
        assert set(server["admission"]["allowed_ids"]) == ids
        assert cfg["publisher-settings"]["destination"] == {
            "url": f"http://127.0.0.1:{port}", "bearer_token_env": token
        }
        assert cfg["security-settings"]["docs_enabled"] is False
        assert cfg["security-settings"]["openapi_enabled"] is False
        assert cfg["security-settings"]["shutdown_enabled"] is False
        assert cfg["browser-update-settings"] == {
            "max_connections": 96, "max_connections_per_client": 64,
            "max_connection_seconds": 600,
        }
    live = yaml.safe_load((ROOT / "demos/live_import/plotsrv.yml").read_text())
    scans = yaml.safe_load((ROOT / "demos/scan_audit/plotsrv.yml").read_text())
    assert live["storage-settings"]["enabled"] is False
    assert scans["storage-settings"]["default_keep_last"] == 7
    assert scans["security-settings"]["history_local_only"] is False
