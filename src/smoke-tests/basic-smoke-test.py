from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch plotsrv and then publish richer smoke-test objects into it."
    )

    parser.add_argument(
        "--host",
        default=os.getenv("PLOTSRV_HOST", os.getenv("HOST", "0.0.0.0")),
    )

    parser.add_argument(
        "--port",
        default=os.getenv("PLOTSRV_PORT", os.getenv("PORT", "8998")),
    )

    parser.add_argument(
        "--publisher-delay",
        type=float,
        default=5.0,
        help="Seconds to wait after starting plotsrv before running the publisher.",
    )

    parser.add_argument(
        "--publisher-module",
        default="smoke_tests.python_objs",
        help=(
            "Python module to run after plotsrv has started. "
            "Use a valid module path, e.g. smoke_tests.python_objs."
        ),
    )

    parser.add_argument(
        "--config",
        default="plotsrv.yml",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    return parser.parse_args()


def repo_root_from_script() -> Path:
    # Expected:
    #   plotsrv-examples/src/smoke-tests/basic-smoke-test.py
    return Path(__file__).resolve().parents[2]


def quote_command(cmd: list[str]) -> str:
    import shlex

    return " ".join(shlex.quote(part) for part in cmd)


def build_plotsrv_command(args: argparse.Namespace) -> list[str]:
    cmd = [
        "plotsrv",
        "run",
        "src/smoke-tests/python_objs.py",
        "--config",
        args.config,
        "--host",
        str(args.host),
        "--port",
        str(args.port),
        "--watch",
        "src/smoke-tests/long_text.txt",
        "--watch-label",
        "text-head",
        "--watch-section",
        "static-files",
        "--watch-head",
        "--truncate",
        "60000",
        "--watch",
        "src/smoke-tests/long_text.txt",
        "--watch-label",
        "text-tail",
        "--watch-section",
        "static-files",
        "--watch-tail",
        "--watch",
        "README.md",
        "--watch-label",
        "md",
        "--watch-section",
        "static-files",
        "--watch",
        "mock-files/jpeg-small-1.jpeg",
        "--watch-label",
        "jpeg",
        "--watch-section",
        "static-files",
        "--watch",
        "old_plotsrv.ini",
        "--watch-label",
        "ini",
        "--watch-section",
        "static-files",
        "--watch",
        "pyproject.toml",
        "--watch-label",
        "toml",
        "--watch-section",
        "static-files",
        "--watch",
        "plotsrv.yml",
        "--watch-label",
        "yml",
        "--watch-section",
        "static-files",
        "--watch",
        "mock-files/yaml1.yaml",
        "--watch-label",
        "yaml",
        "--watch-section",
        "static-files",
        "--watch",
        "mock-files/json-1.json",
        "--watch-label",
        "json",
        "--watch-section",
        "static-files",
        "--watch",
        "mock-files/html-simple-1.html",
        "--watch-label",
        "html-simple",
        "--watch-section",
        "static-files",
        "--watch",
        "mock-files/html-complex-1.html",
        "--watch-label",
        "html-complex",
        "--watch-section",
        "static-files",
        "--no-truncate",
        "--watch",
        "mock-files/",
        "--watch-label",
        "csv-very-large",
        "--watch-section",
        "static-files",
        "--watch",
        "mock-files/",
        "--watch-label",
        "csv-large-head",
        "--watch-section",
        "static-files",
        "--watch-head",
        "--watch",
        "mock-files/",
        "--watch-label",
        "csv-large-tail",
        "--watch-section",
        "static-files",
        "--watch-tail",
        "--watch",
        "mock-files/",
        "--watch-label",
        "csv-small",
        "--watch-section",
        "static-files",
    ]

    return cmd


def build_publisher_command(args: argparse.Namespace) -> list[str]:
    return [
        sys.executable,
        "-m",
        args.publisher_module,
    ]


def terminate_process(process: subprocess.Popen[bytes], name: str) -> None:
    if process.poll() is not None:
        return

    print(f"[INFO] Stopping {name} process: PID {process.pid}", flush=True)

    try:
        process.terminate()
        process.wait(timeout=10)
        return
    except subprocess.TimeoutExpired:
        print(f"[WARN] {name} did not stop after SIGTERM; sending SIGKILL", flush=True)
        process.kill()
        process.wait(timeout=10)


def main() -> int:
    args = parse_args()
    root = repo_root_from_script()
    os.chdir(root)

    env = os.environ.copy()
    env["PLOTSRV_HOST"] = str(args.host)
    env["PLOTSRV_PORT"] = str(args.port)
    env["HOST"] = str(args.host)
    env["PORT"] = str(args.port)

    plotsrv_cmd = build_plotsrv_command(args)
    publisher_cmd = build_publisher_command(args)

    print(f"[INFO] Repo root: {root}", flush=True)
    print(f"[INFO] Host: {args.host}", flush=True)
    print(f"[INFO] Port: {args.port}", flush=True)
    print("[INFO] plotsrv command:", flush=True)
    print(quote_command(plotsrv_cmd), flush=True)
    print("[INFO] publisher command:", flush=True)
    print(quote_command(publisher_cmd), flush=True)

    if args.dry_run:
        return 0

    plotsrv_process: subprocess.Popen[bytes] | None = None
    publisher_process: subprocess.Popen[bytes] | None = None
    shutting_down = False

    def handle_signal(signum: int, _frame: object) -> None:
        nonlocal shutting_down
        shutting_down = True
        print(f"[INFO] Received signal {signum}; shutting down children", flush=True)

        if publisher_process is not None:
            terminate_process(publisher_process, "publisher")

        if plotsrv_process is not None:
            terminate_process(plotsrv_process, "plotsrv")

        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        print("[INFO] Starting plotsrv server process", flush=True)
        plotsrv_process = subprocess.Popen(
            plotsrv_cmd,
            cwd=root,
            env=env,
        )

        print(
            f"[INFO] Waiting {args.publisher_delay} seconds before running publisher",
            flush=True,
        )
        time.sleep(args.publisher_delay)

        if plotsrv_process.poll() is not None:
            print(
                f"[ERROR] plotsrv exited early with code {plotsrv_process.returncode}",
                flush=True,
            )
            return plotsrv_process.returncode or 1

        print("[INFO] Starting publisher process", flush=True)
        publisher_process = subprocess.Popen(
            publisher_cmd,
            cwd=root,
            env=env,
        )

        publisher_return_code = publisher_process.wait()

        if publisher_return_code != 0:
            print(
                f"[ERROR] Publisher exited with code {publisher_return_code}",
                flush=True,
            )
            terminate_process(plotsrv_process, "plotsrv")
            return publisher_return_code

        print("[INFO] Publisher completed successfully", flush=True)
        print("[INFO] Keeping plotsrv server alive", flush=True)

        while not shutting_down:
            plotsrv_return_code = plotsrv_process.poll()

            if plotsrv_return_code is not None:
                print(
                    f"[ERROR] plotsrv exited with code {plotsrv_return_code}",
                    flush=True,
                )
                return plotsrv_return_code or 1

            time.sleep(1)

    finally:
        if publisher_process is not None:
            terminate_process(publisher_process, "publisher")

        if plotsrv_process is not None:
            terminate_process(plotsrv_process, "plotsrv")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
