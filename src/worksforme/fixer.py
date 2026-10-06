"""Explicit environment-only repairs; never rewrite declarations or lockfiles."""

import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from .dependencies import tomllib


@dataclass
class Plan:
    commands: list[list[str]]
    blocked: list[str]
    manager: str


def build_plan(report):
    root = Path(report.project)
    manager = (
        "uv"
        if (root / "uv.lock").is_file()
        else "poetry"
        if (root / "poetry.lock").is_file()
        else "pip"
    )
    metadata_path = root / "pyproject.toml"
    if manager == "pip" and metadata_path.is_file() and not metadata_path.is_symlink():
        try:
            data = tomllib.loads(metadata_path.read_text())
            if "poetry" in data.get("tool", {}):
                manager = "poetry"
            elif "uv" in data.get("tool", {}):
                manager = "uv"
        except (OSError, ValueError):
            pass
    if manager == "pip" and (root / "Pipfile").is_file():
        manager = "pipenv"
    blocked = []
    requirements = sorted({c.requirement for c in report.checks if c.requirement})
    if not report.environment["virtual_environment"]:
        blocked.append("Activate a project virtual environment; global installation is refused.")
    if manager != "pip":
        blocked.append(
            f"{manager} manages this project; run its sync/install command manually "
            "after reviewing metadata and lockfiles."
        )
    if any(
        c.code
        in {
            "conflicting-pins",
            "python-compatibility",
            "manager-conflict",
            "invalid-metadata",
            "broken-venv",
        }
        and c.status != "ok"
        for c in report.checks
    ):
        blocked.append("Resolve metadata/interpreter conflicts before installing dependencies.")
    if not report.environment["pip"]:
        blocked.append("pip is unavailable in the current interpreter.")
    elif Version(report.environment["pip"]) < Version("22.2"):
        blocked.append("Upgrade pip to at least 22.2 manually for resolver preflight support.")
    # Differing requirements for the same package need joint review before mutation.
    grouped = {}
    for item in requirements:
        grouped.setdefault(canonicalize_name(Requirement(item).name), set()).add(item)
    if any(len(items) > 1 for items in grouped.values()):
        blocked.append("Multiple constraints for the same package require manual review.")
    commands = (
        []
        if blocked or not requirements
        else [[sys.executable, "-m", "pip", "install", "--", *requirements]]
    )
    return Plan(commands, blocked, manager)


def display_command(command):
    return shlex.join(command)


def apply_plan(plan, root):
    if not plan.commands:
        return True
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("A virtual environment is required")
    for command in plan.commands:
        # Package installation may execute third-party build code. Suppress its output to
        # avoid echoing credentials from index configuration or subprocess diagnostics.
        # Resolve before mutation to prevent predictable dependency conflicts leaving changes.
        preflight = command[:4] + ["--dry-run"] + command[4:]
        checked = subprocess.run(
            preflight,
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=300,
        )
        if checked.returncode:
            return False
        result = subprocess.run(
            command,
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=300,
        )
        if result.returncode:
            return False
    return True
