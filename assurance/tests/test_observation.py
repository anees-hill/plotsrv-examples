"""Public ETL receipt, original application semantics, and finite lifecycle."""

import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys

import psutil
import pytest

from plotsrv_examples.scenarios.observe_etl import EXPECTED


ROOT = Path(__file__).resolve().parents[2]
COMMAND = [sys.executable, "-m", "plotsrv_examples", "run", "observe-etl"]


def reaped(result):
    assert result["owned_children_reaped"]
    assert {child["label"] for child in result["children"]} == {"receiver", "etl", "custom"}
    for child in result["children"]:
        assert not psutil.pid_exists(child["pid"])


@pytest.mark.parametrize("fault", [False, True])
def test_receiver_evidence_independent_of_application_success(fault):
    completed = subprocess.run(COMMAND + (["--fault", "missing-evidence"] if fault else []),
                               cwd=ROOT, capture_output=True, text=True, timeout=45)
    result = json.loads(completed.stdout)
    assert completed.returncode == (1 if fault else 0), completed.stdout + completed.stderr
    reaped(result)
    if fault:
        assert not result["success"] and "evidence" not in result
        assert "timed out" in result["error"].lower()
        assert all(child["exit"] == 0 for child in result["children"] if child["label"] != "receiver")
    else:
        assert result["success"]
        assert result["evidence"]["application_result"] == EXPECTED
        assert result["evidence"]["metrics"]["input_orders"] == 48
        assert result["evidence"]["sample_scope"] == "base_sample"
        assert result["evidence"]["drained"]


def test_inspection_interrupt_reaps_receiver_after_publishers_finish():
    process = subprocess.Popen(COMMAND + ["--inspect", "--inspect-seconds", "60"],
                               cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        readable, _, _ = select.select([process.stderr], [], [], 30)
        assert readable, "Observation inspection did not become ready"
        assert "Observation ready:" in process.stderr.readline()
        assert len(psutil.Process(process.pid).children()) == 1
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=10)
        result = json.loads(stdout)
        assert process.returncode == 130, stdout + stderr
        assert result["evidence"]["drained"]
        reaped(result)
    finally:
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=10)


def test_sync_async_identity_errors_and_rapid_calls(tmp_path):
    # Real public decorators, with an unavailable receiver: observer failures
    # must not affect the application's result or exception identity.
    code = r'''
import asyncio
import copy
import inspect
import plotsrv as ps
from plotsrv_examples.etl import order_fixture, transform_orders, regional_totals
source = order_fixture()
before = copy.deepcopy(source)
columns = transform_orders(source)
assert source == before and len(source) == 48
assert len(columns['order_id']) == 42
assert regional_totals(columns)['net_cents'] == 61925
calls = []
@ps.view(observe=True, host='127.0.0.1', port=1, view_id='rapid')
def observed(value):
    calls.append(value)
    return value
for _ in range(12):
    assert observed(columns) is columns
assert len(calls) == 12 and columns == transform_orders(source)
assert str(inspect.signature(observed)) == '(value)'
@ps.view(observe=True, host='127.0.0.1', port=1, view_id='async')
async def asynchronous(value):
    return value
assert asyncio.run(asynchronous(columns)) is columns
for error in (ValueError('bad order'), asyncio.CancelledError()):
    @ps.view(observe=True, host='127.0.0.1', port=1)
    def failed():
        raise error
    try:
        failed()
    except BaseException as caught:
        assert caught is error
    else:
        raise AssertionError('application exception swallowed')
bad = order_fixture()
bad[1]['discount_cents'] = -1
decorated = ps.view(observe=True, host='127.0.0.1', port=1)(transform_orders)
for function in (transform_orders, decorated):
    try:
        function(bad)
    except ValueError as caught:
        assert str(caught) == 'invalid paid-order amounts'
    else:
        raise AssertionError('invalid ETL order accepted')
assert ps.flush_views(timeout=3)
# No assertion that all 12 rapid observations reached a receiver.
print('semantics preserved')
'''
    config = tmp_path / "plotsrv.yml"
    config.write_text("storage-settings:\n  enabled: false\n")
    env = {key: value for key, value in os.environ.items() if not key.startswith("PLOTSRV_")}
    env.update(PLOTSRV_CONFIG=str(config), PYTHONDONTWRITEBYTECODE="1", PLOTSRV_DEBUG="1")
    completed = subprocess.run([sys.executable, "-B", "-c", code], cwd=tmp_path, env=env,
                               capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "semantics preserved" in completed.stdout
