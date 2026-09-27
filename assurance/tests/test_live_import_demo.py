"""Check log-shape compatibility and bounded rename-and-recreate rotation."""

import importlib.util
import json
from pathlib import Path
import random

from plotsrv.streams.log_profile import detect


def _module():
    path = Path(__file__).resolve().parents[2] / "demos/live_import/generate_events.py"
    spec = importlib.util.spec_from_file_location("import_events", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_validation_outcomes_are_log_suggestions(tmp_path):
    module = _module()
    good = module.event(1, random.Random(1))
    bad = module.event(23, random.Random(1))
    assert good["level"] == "INFO" and bad["level"] == "WARNING"
    assert bad["validation_issue"] == "invalid_quantity"
    assert detect(good) is not None and detect(bad) is not None
    path = tmp_path / "import.jsonl"
    for index in range(1, 80):
        module.append_rotating(path, module.event(index, random.Random(index)), max_bytes=1024)
    paths = [path, path.with_name("import.jsonl.1"), path.with_name("import.jsonl.2")]
    assert all(p.exists() and p.stat().st_size <= 1024 for p in paths)
    assert all(json.loads(line) for p in paths for line in p.read_text().splitlines())
