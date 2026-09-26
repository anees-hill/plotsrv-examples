"""Primitive checks with disposable processes; real core scenarios follow later."""

import os
import signal
import socket
import sys
import time

import pytest

from plotsrv_examples.support.lifecycle import (
    LifecycleError, Processes, available_port, interruption_cleanup,
    require_candidate, wait_evidence,
)


def start(owner, tmp_path, code, *args):
    return owner.start([sys.executable, "-c", code, *map(str, args)],
                       cwd=tmp_path, env=dict(os.environ), label="test child")


def test_both_pipes_large_output_is_bounded(tmp_path):
    with Processes(log_bytes=8192) as owner:
        child = start(owner, tmp_path,
                      "import os\nfor _ in range(512):\n os.write(1,b'x'*4096)\n os.write(2,b'y'*4096)")
        owner.wait(child, timeout=10)
        assert child.total_bytes == 2 * 512 * 4096
        assert len(child.output) == 8192
    assert child.process.returncode == 0


def test_timeout_and_exception_cleanup_reap_only_owned_child(tmp_path):
    with socket.socket() as neighbor:
        neighbor.bind(("127.0.0.1", 0))
        neighbor.listen()
        port = neighbor.getsockname()[1]
        with pytest.raises(LifecycleError, match="completion timed out"):
            with Processes(stop_timeout=0.1) as owner:
                child = start(owner, tmp_path,
                              "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('ready',flush=True); time.sleep(60)")
                owner.wait(child, timeout=0.3)
        assert child.process.poll() is not None
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass
        with pytest.raises(LifecycleError, match="unavailable"):
            available_port(port)


def test_failed_child_diagnostic_is_prompt(tmp_path):
    began = time.monotonic()
    with Processes() as owner:
        child = start(owner, tmp_path, "import sys; print('broken startup',file=sys.stderr); sys.exit(7)")
        with pytest.raises(LifecycleError, match="broken startup"):
            wait_evidence(owner, child, available_port(), timeout=5)
    assert time.monotonic() - began < 2


@pytest.mark.parametrize("exits", [True, False])
def test_listener_inspection_denial_preserves_exit_or_live_error(tmp_path, monkeypatch, exits):
    import psutil
    gate = tmp_path / "exit-gate"
    with Processes() as owner:
        child = start(owner, tmp_path,
                      "import pathlib,sys,time\n"
                      "while not pathlib.Path(sys.argv[1]).exists(): time.sleep(0.001)\n"
                      "print('controlled exit',file=sys.stderr); sys.exit(7)", gate)
        class Denied:
            def net_connections(self, **kwargs):
                if exits:
                    gate.touch()
                raise psutil.AccessDenied(child.process.pid)
        monkeypatch.setattr(psutil, "Process", lambda pid: Denied())
        message = "controlled exit" if exits else "Cannot verify.*listener ownership"
        with pytest.raises(LifecycleError, match=message):
            child.owns_listener(8000)
        if not exits:
            assert child.process.poll() is None


SERVER = '''
import json,sys
from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path == '/status': data = {'view_id':'test-view','publish_queue':{}}
  elif self.path == '/views': data = [{'view_id':'test-view'}]
  else: data = {'html':'<pre>unique-sentinel</pre>'}
  payload = json.dumps(data).encode()
  self.send_response(200)
  self.send_header('Content-Length',str(len(payload)))
  self.end_headers()
  self.wfile.write(payload)
 def log_message(self,*args): pass
HTTPServer(('127.0.0.1',int(sys.argv[1])),Handler).serve_forever()
'''


def test_owned_http_readiness_and_exact_artifact_predicate(tmp_path):
    port = available_port()
    with Processes() as owner:
        receiver = start(owner, tmp_path, SERVER, port)
        wait_evidence(owner, receiver, port, timeout=3)
        wait_evidence(owner, receiver, port, timeout=1,
                      view_id="test-view", sentinel="unique-sentinel")
        with pytest.raises(LifecycleError, match="sentinel absent"):
            wait_evidence(owner, receiver, port, timeout=0.2,
                          view_id="test-view", sentinel="missing")
        with pytest.raises(LifecycleError, match="logical view.*absent"):
            wait_evidence(owner, receiver, port, timeout=0.2,
                          view_id="wrong-view", sentinel="unique-sentinel")
    assert receiver.process.poll() is not None
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), timeout=0.2)


def test_unrelated_listener_cannot_supply_readiness(tmp_path):
    port = available_port()
    with Processes() as neighbor_owner:
        neighbor = start(neighbor_owner, tmp_path, SERVER, port)
        wait_evidence(neighbor_owner, neighbor, port, timeout=3)
        with Processes() as owner:
            sleeper = start(owner, tmp_path, "import time; time.sleep(60)")
            with pytest.raises(LifecycleError, match="owned listener not ready"):
                wait_evidence(owner, sleeper, port, timeout=0.2)
        assert neighbor.process.poll() is None
        wait_evidence(neighbor_owner, neighbor, port, timeout=1)


def test_sigterm_unwinds_owned_listener_and_restores_handler(tmp_path):
    previous = signal.getsignal(signal.SIGTERM)
    port = available_port()
    with pytest.raises(KeyboardInterrupt):
        with interruption_cleanup(), Processes() as owner:
            child = start(owner, tmp_path, SERVER, port)
            wait_evidence(owner, child, port, timeout=3)
            os.kill(os.getpid(), signal.SIGTERM)
    assert signal.getsignal(signal.SIGTERM) == previous
    assert child.process.poll() is not None
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), timeout=0.2)


def test_candidate_mismatch_is_explicit(monkeypatch):
    from plotsrv_examples import doctor
    monkeypatch.setattr(doctor, "report", lambda: {
        "readiness": "blocked", "problems": ["Imported candidate does not match the inspected core reference"]})
    with pytest.raises(LifecycleError, match="Candidate/reference rejected.*does not match"):
        require_candidate()


def test_trickling_http_headers_cannot_extend_deadline(tmp_path):
    port = available_port()
    code = '''
import socket,sys,time
with socket.socket() as server:
 server.bind(('127.0.0.1',int(sys.argv[1])))
 server.listen()
 connection,_ = server.accept()
 with connection:
  connection.recv(4096)
  connection.sendall(b'HTTP/1.0 200 OK\\r\\nX-Slow: ')
  while True:
   connection.sendall(b'x')
   time.sleep(0.01)
'''
    with Processes() as owner:
        child = start(owner, tmp_path, code, port)
        began = time.monotonic()
        with pytest.raises(LifecycleError, match="deadline expired"):
            wait_evidence(owner, child, port, timeout=0.4)
        assert time.monotonic() - began < 1.5


def test_interrupt_during_launch_cannot_lose_child(tmp_path, monkeypatch):
    from plotsrv_examples.support import lifecycle
    real_popen = lifecycle.subprocess.Popen

    def interrupted_launch(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        os.kill(os.getpid(), signal.SIGINT)
        return process

    monkeypatch.setattr(lifecycle.subprocess, "Popen", interrupted_launch)
    with pytest.raises(KeyboardInterrupt):
        with Processes() as owner:
            start(owner, tmp_path, "import time; time.sleep(60)")
    assert len(owner.children) == 1
    assert owner.children[0].process.poll() is not None


@pytest.mark.parametrize("point", ["launch", "cleanup"])
def test_release_alarm_cannot_lose_owned_child(tmp_path, monkeypatch, point):
    from plotsrv_examples.support import lifecycle
    from plotsrv_examples.suites import ScenarioTimeout
    def alarm(number, frame):
        raise ScenarioTimeout("injected deadline")
    previous = signal.signal(signal.SIGALRM, alarm)
    real_popen = lifecycle.subprocess.Popen
    real_close = Processes.close
    def launch(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        if point == "launch":
            signal.raise_signal(signal.SIGALRM)
        return process
    def close(owner):
        if point == "cleanup":
            signal.raise_signal(signal.SIGALRM)
        real_close(owner)
    monkeypatch.setattr(lifecycle.subprocess, "Popen", launch)
    monkeypatch.setattr(Processes, "close", close)
    try:
        with pytest.raises(ScenarioTimeout, match="injected deadline"):
            with Processes() as owner:
                start(owner, tmp_path, "import time; time.sleep(60)")
        assert len(owner.children) == 1
        assert owner.children[0].process.poll() is not None
    finally:
        signal.signal(signal.SIGALRM, previous)
