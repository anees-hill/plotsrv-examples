"""Workspace tooling and bounded public-workflow assurance."""

import argparse
import sys

sys.dont_write_bytecode = True

from .doctor import main
from pathlib import Path
from .workspace import create, clean
from .fixtures import generate

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="python -m plotsrv_examples")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    commands.add_parser("list")
    run = commands.add_parser("run")
    run.add_argument("scenario", choices=["gallery", "publication-modes", "watch-formats", "observation-changes", "resource-monitor", "weather-demo", "stream-structured", "stream-http", "stream-python-logs", "observe-etl",
                                          "local-watch", "remote-publish", "remote-watch",
                                          "admission", "outage", "config-discovery", "storage-history", "checks-webhook"])
    run.add_argument("--port", type=int, default=0)
    run.add_argument("--inspect", action="store_true")
    run.add_argument("--inspect-seconds", type=float, default=30)
    run.add_argument("--fault", choices=["missing-evidence"])
    run.add_argument("--weather-mode", choices=["sample", "live"], default="sample")
    check = commands.add_parser("check")
    check.add_argument("suite", choices=["quick", "release", "wheel"])
    check.add_argument("--wheel-path", type=Path, help="Explicit artifact for check wheel")
    check.add_argument("--scenario-timeout", type=float, default=120.0)
    check.add_argument("--port", type=int, default=0)
    check.add_argument("--evidence-timeout", type=float, default=3.0)
    check.add_argument("--fault", choices=["missing-evidence", "startup", "high-output"],
                       help="Deliberate assurance drill (high-output should pass)")
    commands.add_parser("workspace-create")
    commands.add_parser("smoke-prepare", help="Create inputs/configs for assurance/manual-smoke-test.md")
    fixtures = commands.add_parser("fixtures-create")
    fixtures.add_argument("--seed", type=int, default=17)
    fixtures.add_argument("--rows", type=int, default=100000)
    fixtures.add_argument("--lines", type=int, default=4096)
    cleanup = commands.add_parser("workspace-clean")
    cleanup.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "doctor":
        raise SystemExit(main())
    if args.command == "list":
        from .suites import listing
        raise SystemExit(listing())
    if args.command == "run":
        if args.scenario in ("publication-modes", "watch-formats", "observation-changes"):
            from functools import partial
            from .scenarios.smoke import main as smoke_main
            scenario_main = partial(smoke_main, scenario=args.scenario)
        elif args.scenario == "weather-demo":
            from functools import partial
            from .scenarios.weather_demo import main as weather_main
            scenario_main = partial(weather_main, mode=args.weather_mode)
        elif args.scenario == "resource-monitor":
            from .scenarios.resource_monitor import main as scenario_main
        elif args.scenario == "checks-webhook":
            from .scenarios.checks_webhook import main as scenario_main
        elif args.scenario == "storage-history":
            from .scenarios.storage_history import main as scenario_main
        elif args.scenario in ("admission", "outage", "config-discovery"):
            from functools import partial
            from .scenarios.admission_config import main as assurance_main
            scenario_main = partial(assurance_main, scenario=args.scenario)
        elif args.scenario in ("local-watch", "remote-publish", "remote-watch"):
            from functools import partial
            from .scenarios.watch import main as watch_main
            scenario_main = partial(watch_main, scenario=args.scenario)
        elif args.scenario == "observe-etl":
            from .scenarios.observe_etl import main as scenario_main
        elif args.scenario == "stream-http":
            from .scenarios.stream_http import main as scenario_main
        elif args.scenario == "stream-structured":
            from .scenarios.stream_structured import main as scenario_main
        elif args.scenario == "stream-python-logs":
            from .scenarios.stream_python_logs import main as scenario_main
        else:
            from .scenarios.gallery import main as scenario_main
        raise SystemExit(scenario_main(port=args.port, inspect=args.inspect,
                                      inspect_seconds=args.inspect_seconds, fault=args.fault))
    if args.command == "check":
        if args.suite == "wheel":
            if args.wheel_path is None:
                parser.error("check wheel requires --wheel-path")
            if args.port or args.fault or args.scenario_timeout != 120.0 or args.evidence_timeout != 3.0:
                parser.error("check wheel accepts only --wheel-path")
            from .wheel_smoke import main as wheel_main
            raise SystemExit(wheel_main(args.wheel_path))
        if args.wheel_path is not None:
            parser.error("--wheel-path is wheel-only")
        if args.suite == "release":
            if args.port != 0 or args.evidence_timeout != 3.0:
                parser.error("--port and --evidence-timeout are quick-only options")
            from .suites import main as release_main
            raise SystemExit(release_main(scenario_timeout=args.scenario_timeout, fault=args.fault))
        from .scenarios.basic import main as check_main
        raise SystemExit(check_main(port=args.port, evidence_timeout=args.evidence_timeout,
                                    fault=args.fault))
    try:
        if args.command == "smoke-prepare":
            from .smoke_inputs import prepare
            print(prepare(Path.cwd()))
        elif args.command == "workspace-create":
            print(create(Path.cwd()))
        elif args.command == "fixtures-create":
            print(generate(Path.cwd(), seed=args.seed, rows=args.rows, lines=args.lines))
        else:
            clean(Path.cwd(), args.path)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Workspace rejected: {exc}\n")
