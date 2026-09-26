"""Lifecycle primitives for foreground processes that do not spawn descendants.

Only Popen-owned children are signalled. No port-based killing or HTTP shutdown.
POSIX pipes are drained without threads; every wait services all owned children.
"""

from contextlib import contextmanager
import http.client
import io
import json
import math
import os
from pathlib import Path
import signal
import select
import socket
import subprocess
import threading
import time
from urllib.parse import urlencode

import psutil


class LifecycleError(RuntimeError):
    """A required lifecycle condition failed; CLI callers must exit nonzero."""


@contextmanager
def _defer_interrupts():
    """Register a launched child before delivering a pending interruption."""
    previous, pending = {}, []
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGALRM):
            previous[sig] = signal.signal(sig, lambda number, frame: pending.append(number))
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        if pending:
            signal.raise_signal(pending[0])


def _duration(value):
    if not math.isfinite(value) or value <= 0:
        raise ValueError("timeout must be finite and positive")
    return value


def require_candidate():
    from ..doctor import report
    evidence = report()
    if evidence["readiness"] != "ready":
        raise LifecycleError("Candidate/reference rejected: " + "; ".join(evidence["problems"]))
    return evidence


def available_port(port=0):
    """Check loopback availability, without adopting or changing a listener.

    This is a preflight only. Recheck child listener ownership after startup.
    """
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise LifecycleError(f"Loopback port {port} unavailable: {exc}") from exc
        return probe.getsockname()[1]


class Child:
    def __init__(self, process, label, limit):
        self.process, self.label, self.limit = process, label, limit
        self.output = bytearray()
        self.total_bytes = 0
        self.pipes = [process.stdout, process.stderr]
        for pipe in self.pipes:
            os.set_blocking(pipe.fileno(), False)

    def drain(self):
        # Limit each pass even if a producer writes continuously.
        for pipe in self.pipes[:]:
            for _ in range(16):
                try:
                    data = os.read(pipe.fileno(), 4096)
                except BlockingIOError:
                    break
                if not data:
                    pipe.close()
                    self.pipes.remove(pipe)
                    break
                self.total_bytes += len(data)
                self.output.extend(data)
                del self.output[:-self.limit]

    def diagnostic(self):
        return (f"{self.label} (pid={self.process.pid}, exit={self.process.poll()}, "
                f"output_bytes={self.total_bytes}):\n"
                + self.output.decode("utf-8", errors="replace"))

    def require_alive(self):
        if self.process.poll() is not None:
            self.drain()
            raise LifecycleError("Child exited before required evidence: " + self.diagnostic())

    def owns_listener(self, port):
        self.require_alive()
        try:
            connections = psutil.Process(self.process.pid).net_connections(kind="tcp")
        except psutil.NoSuchProcess:
            # procfs may disappear just before waitpid observes exit. Let the
            # next liveness check report the child's actual failure and output.
            return False
        except psutil.Error as exc:
            # Linux can deny /proc inspection during exit, before waitpid can
            # reap the child. Allow a bounded grace period for its diagnostic.
            try:
                self.process.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                pass
            self.require_alive()
            raise LifecycleError(f"Cannot verify {self.label} listener ownership: {exc}") from exc
        return any(c.status == psutil.CONN_LISTEN and c.laddr.ip == "127.0.0.1"
                   and c.laddr.port == port for c in connections)


class Processes:
    """Own children from launch through reaping; use as a context manager."""
    def __init__(self, *, log_bytes=65536, stop_timeout=3.0):
        if os.name != "posix":
            raise LifecycleError("Safe nonblocking child pipes require POSIX")
        if not isinstance(log_bytes, int) or log_bytes <= 0:
            raise ValueError("log_bytes must be positive")
        self.log_bytes = log_bytes
        self.stop_timeout = _duration(stop_timeout)
        self.children = []

    def __enter__(self):
        return self

    def start(self, argv, *, cwd: Path, env: dict, label: str):
        with _defer_interrupts():
            return self._start(argv, cwd=cwd, env=env, label=label)

    def _start(self, argv, *, cwd, env, label):
        try:
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       start_new_session=True)
        except OSError as exc:
            raise LifecycleError(f"Cannot start {label}: {exc}") from exc
        try:
            child = Child(process, label, self.log_bytes)
        except BaseException:
            process.kill()
            process.wait()
            process.stdout.close()
            process.stderr.close()
            raise
        self.children.append(child)
        return child

    def pump(self):
        for child in self.children:
            child.drain()

    def wait(self, child, *, timeout):
        deadline = time.monotonic() + _duration(timeout)
        while child.process.poll() is None:
            self.pump()
            if time.monotonic() >= deadline:
                raise LifecycleError("Child completion timed out: " + child.diagnostic())
            time.sleep(0.01)
        self.pump()
        if child.process.returncode:
            raise LifecycleError("Child failed: " + child.diagnostic())

    def close(self):
        for child in reversed(self.children):
            if child.process.poll() is None:
                child.process.terminate()
        deadline = time.monotonic() + self.stop_timeout
        while any(c.process.poll() is None for c in self.children) and time.monotonic() < deadline:
            self.pump()
            time.sleep(0.01)
        for child in self.children:
            if child.process.poll() is None:
                child.process.kill()
        errors = []
        for child in self.children:
            try:
                child.process.wait(timeout=self.stop_timeout)
            except subprocess.TimeoutExpired:
                errors.append(child.label)
            child.drain()
            for pipe in child.pipes:
                pipe.close()
            child.pipes.clear()
        if errors:
            raise LifecycleError("Could not reap owned children: " + ", ".join(errors))

    def __exit__(self, *_):
        # Deliver interruption/deadline signals only after bounded reaping.
        # A deadline during cleanup must still fail the scenario, not disappear.
        with _defer_interrupts():
            self.close()


@contextmanager
def interruption_cleanup():
    """Use outside Processes in the main thread; SIGTERM unwinds like Ctrl+C."""
    def interrupt(signum, frame):
        raise KeyboardInterrupt(f"received signal {signum}")
    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def _response(port, path, deadline, processes, max_bytes=262144):
    # Buffer a bounded HTTP/1.0 exchange before parsing. Socket-level timeouts
    # alone would allow a trickling header/body to extend a deadline indefinitely.
    with socket.create_connection(("127.0.0.1", port),
                                  timeout=min(0.2, max(0.001, deadline-time.monotonic()))) as connection:
        connection.setblocking(False)
        pending = memoryview((f"GET {path} HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\n"
                              "Connection: close\r\n\r\n").encode("ascii"))
        wire = bytearray()
        while True:
            processes.pump()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("HTTP evidence deadline expired")
            readable, writable, _ = select.select(
                [connection], [connection] if pending else [], [], min(0.02, remaining))
            if writable:
                pending = pending[connection.send(pending):]
            if readable:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                wire.extend(chunk)
                if len(wire) > max_bytes:
                    raise ValueError(f"{path}: response exceeds {max_bytes} bytes including headers")

    class BufferedSocket:
        def makefile(self, *args):
            return io.BytesIO(wire)

    with http.client.HTTPResponse(BufferedSocket()) as response:
        response.begin()
        if response.status != 200:
            raise ValueError(f"{path}: HTTP {response.status}")
        return response.read(max_bytes + 1)


def _json(port, path, deadline, processes, max_bytes=262144):
    return json.loads(_response(port, path, deadline, processes, max_bytes))


def wait_evidence(processes, receiver, port, *, timeout, view_id=None, sentinel=None):
    """Wait for owned receiver readiness or exact view plus rendered content.

    Publisher exit is deliberately not an input to the evidence predicate.
    """
    if (view_id is None) != (sentinel is None) or view_id == "" or sentinel == "":
        raise ValueError("content evidence requires nonempty view_id and sentinel together")
    deadline = time.monotonic() + _duration(timeout)
    last = "owned listener not ready"
    while time.monotonic() < deadline:
        processes.pump()
        receiver.require_alive()
        if receiver.owns_listener(port):
            try:
                status = _json(port, "/status", deadline, processes)
                if not isinstance(status, dict) or "view_id" not in status or "publish_queue" not in status:
                    raise ValueError("status does not match inspected plotsrv contract")
                if view_id is not None:
                    views = _json(port, "/views", deadline, processes)
                    if not isinstance(views, list) or not any(
                        isinstance(v, dict) and v.get("view_id") == view_id for v in views
                    ):
                        raise ValueError(f"expected logical view {view_id!r} absent")
                    artifact = _json(port, "/artifact?" + urlencode({"view": view_id}), deadline, processes)
                    if not isinstance(artifact, dict) or not isinstance(artifact.get("html"), str) or sentinel not in artifact["html"]:
                        raise ValueError(f"expected sentinel absent from artifact for {view_id!r}")
                receiver.require_alive()
                if receiver.owns_listener(port):
                    return status
            except (OSError, ValueError, http.client.HTTPException) as exc:
                if not isinstance(exc, TimeoutError) or last == "owned listener not ready":
                    last = str(exc)
        time.sleep(min(0.02, max(0, deadline-time.monotonic())))
    raise LifecycleError(f"Receiver evidence timed out: {last}\n{receiver.diagnostic()}")
