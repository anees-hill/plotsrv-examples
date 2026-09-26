"""Report reference and runtime provenance without installing or configuring core."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tomllib


def git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(path), *args],
        capture_output=True, text=True, timeout=10,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Git inspection failed")
    return result.stdout.rstrip("\n")


def checkout(path: Path) -> dict:
    root = Path(git(path, "rev-parse", "--show-toplevel")).resolve()
    if root != path.resolve():
        raise ValueError(f"Not a checkout root: {path} (Git root is {root})")
    return {
        "path": str(root),
        "revision": git(root, "rev-parse", "HEAD"),
        "branch": git(root, "branch", "--show-current") or "(detached)",
        "status": git(root, "status", "--porcelain=v1", "--untracked-files=all"),
    }


def report() -> dict:
    examples = Path(__file__).resolve().parents[2]
    explicit = os.environ.get("PLOTSRV_CORE_DIR")
    reference = Path(explicit).expanduser().resolve() if explicit is not None else examples.parent / "plotsrv"
    result: dict = {
        "python": sys.executable, "platform": platform.platform(),
        "reference_selection": "PLOTSRV_CORE_DIR" if explicit is not None else "sibling fallback",
        "core_reference": {"path": str(reference)}, "runtime_candidate": {},
        "readiness": "blocked", "problems": [],
    }
    try:
        result["examples"] = checkout(examples)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result["examples"] = {"path": str(examples), "error": str(exc)}
    try:
        if explicit == "":
            raise ValueError("PLOTSRV_CORE_DIR is empty")
        metadata = tomllib.loads((reference / "pyproject.toml").read_text())
        if metadata.get("project", {}).get("name") != "plotsrv":
            raise ValueError("Reference project is not plotsrv")
        if not (reference / "src/plotsrv/__init__.py").is_file():
            raise ValueError("Reference plotsrv source is unavailable")
        result["core_reference"] = checkout(reference)
        result["core_reference"]["declared_version"] = metadata["project"].get("version")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result["problems"].append(f"Core reference unavailable: {exc}")
    try:
        # Core's public package initializer is lazy. Disable bytecode writes before import.
        sys.dont_write_bytecode = True
        module = importlib.import_module("plotsrv")
        origin = Path(module.__file__).resolve()
        candidate = result["runtime_candidate"]
        candidate["module"] = str(origin)
        try:
            distribution = importlib.metadata.distribution("plotsrv")
            candidate["version"] = distribution.version
            candidate["distribution_location"] = str(distribution.locate_file(""))
            direct_url = distribution.read_text("direct_url.json")
            candidate["direct_url"] = json.loads(direct_url) if direct_url else None
        except importlib.metadata.PackageNotFoundError:
            candidate["version"] = None
            candidate["metadata_note"] = "No installed distribution metadata; source import only"
        try:
            candidate_root = Path(git(origin.parent, "rev-parse", "--show-toplevel")).resolve()
            candidate["checkout"] = checkout(candidate_root)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            candidate["checkout"] = None
        expected = (reference / "src/plotsrv/__init__.py").resolve()
        if "revision" in result["core_reference"] and origin == expected:
            result["relationship"] = "matching source checkout"
        else:
            result["relationship"] = "different or unavailable reference"
            result["problems"].append("Imported candidate does not match the inspected core reference")
    except Exception as exc:
        result["problems"].append(f"Runtime candidate unavailable: {type(exc).__name__}: {exc}")
        result["relationship"] = "unverified"
    if not result["problems"]:
        result["readiness"] = "ready"
    return result


def main() -> int:
    result = report()
    print(json.dumps(result, indent=2))
    return 0 if result["readiness"] == "ready" else 1
