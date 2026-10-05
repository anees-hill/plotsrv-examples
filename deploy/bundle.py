"""Deploy a complete upload bundle using the tooling shipped with it."""

import argparse
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

import manage

REQUIRED = {
    "deploy-plotsrv.sh",
    "DEPLOYMENT-GUIDE.md",
    "BUILD-INFO.json",
    "build-plotsrv-bundle",
    "plotsrv-examples-demos.tar.gz",
    "plotsrv-homepage.tar.gz",
    "caddy-plotsrv",
    "tooling/deploy/bundle.py",
    "tooling/deploy/manage.py",
    "tooling/deploy/package.py",
    "tooling/deploy/render-caddy.py",
    "tooling/deploy/Caddyfile",
    "tooling/deploy/systemd/plotsrv-demo-proxy.service",
}


def verify_bundle(root):
    manifest = root / "SHA256SUMS"
    if manifest.is_symlink():
        raise ValueError("SHA256SUMS must be an ordinary file")
    entries = {}
    for line in manifest.read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise ValueError("Invalid SHA256SUMS entry")
        name = match[2]
        relative = PurePosixPath(name)
        if (
            relative.is_absolute()
            or str(relative) != name
            or any(part in {".", ".."} for part in relative.parts)
            or name in entries
        ):
            raise ValueError(f"Unsafe or duplicate checksum path: {name}")
        entries[name] = match[1]
    if not REQUIRED <= entries.keys():
        raise ValueError(
            "Incomplete bundle manifest; rebuild and transfer the whole bundle"
        )
    for name, expected in entries.items():
        path = root / name
        if any(
            p.is_symlink()
            for p in (path, *path.parents)
            if p != root and root in p.parents
        ):
            raise ValueError(f"Bundle symlink is not allowed: {name}")
        if not path.is_file():
            raise ValueError(f"Bundle file missing: {name}; transfer the whole bundle")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError(
                f"Checksum failed: {name}; transfer the whole bundle again"
            )
    # An overlaid upload must not leave obsolete executable/service files behind.
    for path in (root / "tooling").rglob("*"):
        if path.is_symlink() or (
            path.is_file() and path.relative_to(root).as_posix() not in entries
        ):
            raise ValueError(
                f"Unexpected tooling file: {path.relative_to(root)}; replace the bundle directory"
            )
    print("Bundle checksums OK.", flush=True)


def status():
    state = manage.load_state()
    print("Website:", "installed" if state["website"] else "not installed")
    print("Selected demos:", ", ".join(state["demos"]) or "none")
    print("Installed plotsrv:", manage.installed_version(manage.EXAMPLES))
    for label, path in [
        ("Website release", manage.WEBSITE),
        ("Demo release", manage.EXAMPLES),
    ]:
        if path.is_symlink():
            print(f"{label}: {path.resolve()}")
    units = [manage.PROXY] if state["website"] or state["demos"] else []
    for demo in state["demos"]:
        units.append(f"plotsrv-demo@{demo}.service")
        if manage.prepared_content_available():
            units.append(f"plotsrv-demo-content@{demo}.service")
        if demo == "live_import":
            units.extend(manage.JOBS[demo])
        elif demo == "scan_audit":
            units.append(manage.JOBS[demo][0])
    healthy = True
    for unit in units:
        result = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True,
            text=True,
            check=False,
        )
        print(f"{unit}: {result.stdout.strip() or 'unknown'}")
        healthy = healthy and result.returncode == 0
    return 0 if healthy else 1


def parser():
    p = argparse.ArgumentParser(
        prog="deploy-plotsrv.sh",
        description=__doc__,
        epilog="Run from the uploaded bundle on the VM. Profiles replace the current demo selection. See DEPLOYMENT-GUIDE.md.",
    )
    sub = p.add_subparsers(dest="command", required=True)
    for command in ("demos", "both", "select-demos"):
        item = sub.add_parser(
            command,
            help={
                "demos": "update demo code and plotsrv from PyPI; preserve the website",
                "both": "update demos first, then website (two separate transactions)",
                "select-demos": "change active demos using installed code; no package update",
            }[command],
        )
        item.add_argument("profile", choices=manage.PROFILES)
        if command != "select-demos":
            item.add_argument(
                "--requirements",
                type=Path,
                help="Advanced: reproduce pinned packages instead of upgrading to latest PyPI plotsrv",
            )
    sub.add_parser(
        "website", help="update website and demo landing page; preserve running demos"
    )
    sub.add_parser(
        "status",
        help="show installed version, selection and service health without changing anything",
    )
    return p


def execute(root, args):
    if args.command == "status":
        return status()
    if os.geteuid() != 0:
        raise ValueError("Run deployment commands with sudo")
    verify_bundle(root)
    requirements = getattr(args, "requirements", None)
    if requirements:
        requirements = requirements.resolve(strict=True)
    common = [sys.executable, "-B", str(root / "tooling/deploy/manage.py")]
    if args.command in {"demos", "both", "select-demos"}:
        command = [*common, "demos", args.profile]
        if args.command != "select-demos":
            command.append(str(root / "plotsrv-examples-demos.tar.gz"))
        if requirements:
            command.extend(["--requirements", str(requirements)])
        subprocess.run(command, check=True)
    if args.command in {"website", "both"}:
        try:
            subprocess.run(
                [*common, "website", str(root / "plotsrv-homepage.tar.gz")], check=True
            )
        except subprocess.CalledProcessError:
            if args.command == "both":
                print(
                    "Demos updated successfully. Website update failed; its installer attempted rollback. "
                    "Run status and inspect the error before retrying website.",
                    file=sys.stderr,
                )
            raise
    print("Verify the deployment with: sudo ./deploy-plotsrv.sh status", flush=True)
    return 0


def main():
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11+ is required on the VM")
    root = Path(sys.argv[1]).resolve()
    p = parser()
    args = p.parse_args(sys.argv[2:])
    try:
        return execute(root, args)
    except (
        OSError,
        ValueError,
        RuntimeError,
        KeyError,
        subprocess.CalledProcessError,
    ) as exc:
        p.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
