"""Only retain key names and whether a value exists; never retain secret values."""

import os
import re
import shutil
import subprocess

from .models import Finding


def read_keys(path):
    keys, configured = set(), set()
    for line in path.read_text().splitlines():
        match = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
        if match:
            key = match[1]
            keys.add(key)
            if match[2].strip().strip("\"'"):
                configured.add(key)
    return keys, configured


def check_env(context):
    configured = {key for key in context.env_required | context.env_optional if os.environ.get(key)}
    actual, expected = set(), set()
    findings = []
    for path in sorted(context.root.glob(".env*")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            keys, populated = read_keys(path)
        except (OSError, UnicodeError):
            findings.append(
                Finding(
                    "Environment Variables",
                    "warning",
                    "env-unreadable",
                    "An environment file could not be read; contents omitted.",
                )
            )
            continue
        if path.name.endswith((".example", ".sample", ".template")):
            expected |= keys
        else:
            actual |= keys
            if path.name == ".env":
                configured |= populated
    required = context.env_required | (expected - context.env_optional)
    for key in sorted(required | context.env_optional):
        present = key in configured
        status = "ok" if present else "warning" if key not in required else "error"
        findings.append(
            Finding(
                "Environment Variables",
                status,
                "env-configured" if present else "env-missing",
                f"{key} {'configured' if present else 'missing'}",
                None if present else f"Configure {key} locally; do not commit its value.",
            )
        )
    for key in sorted(actual - required - context.env_optional):
        findings.append(
            Finding(
                "Environment Variables",
                "warning",
                "env-unused",
                f"{key} exists but has no detected use",
            )
        )
    git = shutil.which("git")
    if git and (context.root / ".env").is_file():

        def run(args):
            return subprocess.run(
                [git, "-C", str(context.root), *args], capture_output=True, timeout=5, check=False
            )

        try:
            if run(["rev-parse", "--is-inside-work-tree"]).returncode == 0:
                tracked = run(["ls-files", "--error-unmatch", "--", ".env"]).returncode == 0
                ignored = run(["check-ignore", "--quiet", "--", ".env"]).returncode == 0
                if tracked:
                    findings.append(
                        Finding(
                            "Security",
                            "error",
                            "env-tracked",
                            ".env is tracked by Git",
                            "Remove it from Git tracking and rotate exposed keys.",
                        )
                    )
                elif not ignored:
                    findings.append(
                        Finding(
                            "Security",
                            "warning",
                            "env-not-ignored",
                            ".env is not ignored by Git",
                            "Add .env to .gitignore.",
                        )
                    )
        except (OSError, subprocess.TimeoutExpired):
            findings.append(
                Finding(
                    "Security",
                    "warning",
                    "git-unavailable",
                    "Git tracking check could not complete.",
                )
            )
    elif (context.root / ".env").is_file():
        ignore = context.root / ".gitignore"
        if not ignore.is_file() or ".env" not in ignore.read_text().splitlines():
            findings.append(
                Finding(
                    "Security",
                    "warning",
                    "env-ignore-review",
                    "Review .gitignore protection for .env.",
                )
            )
    return findings
