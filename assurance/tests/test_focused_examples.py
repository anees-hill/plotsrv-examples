"""Run focused scripts against the selected core, outside the repository cwd."""

import os
from pathlib import Path
import sys
import time

import pytest

from plotsrv_examples.support.lifecycle import (
    Processes, _json, available_port, require_candidate, wait_evidence,
)


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def runtime(tmp_path):
    provenance = require_candidate()
    config = tmp_path / "plotsrv.yml"
    config.write_text("storage-settings:\n  enabled: false\n"
                      "security-settings:\n  tracebacks_enabled: true\n")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PLOTSRV_")}
    env.update(PLOTSRV_CONFIG=str(config), PLOTSRV_DEBUG="1",
               PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg",
               MPLCONFIGDIR=str(tmp_path / "mpl"), XDG_CACHE_HOME=str(tmp_path / "cache"),
               PYTHONPATH=str(Path(provenance["core_reference"]["path"]) / "src"))
    with Processes() as processes:
        yield processes, tmp_path, env, config, available_port()


def script(processes, cwd, env, name, *args):
    return processes.start([sys.executable, str(ROOT / "examples" / name), *args],
                           cwd=cwd, env=env, label=name)


def test_external_focused_scripts(runtime):
    processes, cwd, env, config, port = runtime
    receiver = processes.start(
        [sys.executable, "-m", "plotsrv.cli_entry", "serve", "--host", "127.0.0.1",
         "--port", str(port), "--config", str(config), "--quiet"],
        cwd=cwd, env=env, label="receiver")
    wait_evidence(processes, receiver, port, timeout=15)
    destination = f"http://127.0.0.1:{port}"
    for name, args in [("direct.py", [destination]),
                       ("async_live.py", [destination]),
                       ("files.py", [destination, str(config)]),
                       ("decorated.py", ["--port", str(port)]),
                       ("exceptions.py", ["--port", str(port)]),
                       ("objects.py", [destination])]:
        child = script(processes, cwd, env, name, *args)
        processes.wait(child, timeout=30)
    wait_evidence(processes, receiver, port, timeout=5,
                  view_id="example-direct", sentinel="rows_processed")
    wait_evidence(processes, receiver, port, timeout=5,
                  view_id="example-class", sentinel="Hubble")
    wait_evidence(processes, receiver, port, timeout=5,
                  view_id="example-mixed", sentinel="heterogeneous example")
    wait_evidence(processes, receiver, port, timeout=5,
                  view_id="example-async", sentinel="completed")
    wait_evidence(processes, receiver, port, timeout=5,
                  view_id="example-file", sentinel="storage-settings")
    for suffix in ("explicit", "captured", "decorated"):
        wait_evidence(processes, receiver, port, timeout=5,
                      view_id=f"example-exception-{suffix}", sentinel="example failure")
    table = _json(port, "/table/data?view=example-polars", time.monotonic() + 3, processes)
    assert table["rows"][0]["planet"] == "Earth"
    legacy = processes.start(
        [sys.executable, str(ROOT / "src/smoke-tests/python_objs.py")],
        cwd=cwd, env={**env, "PLOTSRV_HOST": "127.0.0.1", "PLOTSRV_PORT": str(port)},
        label="legacy object adapter")
    processes.wait(legacy, timeout=30)


@pytest.mark.parametrize("mode", ["publish", "show", "watch"])
def test_attached_lifecycle_modes(runtime, mode):
    processes, cwd, env, config, port = runtime
    args = ["--config", str(config), "--port", str(port), "--seconds", "3",
            "--mode", mode]
    if mode == "watch":
        watched = cwd / "message.txt"
        watched.write_text("Focused watch example\n")
        args += ["--watch", str(watched)]
    child = script(processes, cwd, env, "lifecycle.py", *args)
    wait_evidence(processes, child, port, timeout=15)
    if mode == "publish":
        wait_evidence(processes, child, port, timeout=2,
                      view_id="example-lifecycle", sentinel="attached")
    else:
        deadline = time.monotonic() + 2
        views = []
        while not views and time.monotonic() < deadline:
            child.require_alive()
            views = _json(port, "/views", deadline, processes)
            if not views:
                time.sleep(0.02)
        assert views, child.diagnostic()
        if mode == "show":
            assert any(view["kind"] == "plot" for view in views)
    processes.wait(child, timeout=15)
    assert child.process.returncode == 0


def test_object_builders_import_without_publication(runtime):
    processes, cwd, env, config, port = runtime
    env = {**env, "PYTHONPATH": os.pathsep.join([str(ROOT / "examples"), env["PYTHONPATH"]])}
    child = processes.start(
        [sys.executable, "-c",
         "import objects; assert objects.mixed_objects()[0]['moons'] == ['Moon']; "
         "assert len(objects.planet_table()) == 3"],
        cwd=cwd, env=env, label="independent builders")
    processes.wait(child, timeout=20)
