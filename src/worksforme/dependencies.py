"""Static metadata parsing. Never execute setup.py or expand credentials."""

import ast
import configparser
import re
import sys
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet

from .models import Finding

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

FILES = (
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.py",
    "setup.cfg",
    "Pipfile",
    "poetry.lock",
    "uv.lock",
    ".python-version",
)


def parse_requirement(text, context):
    try:
        req = Requirement(text)
        if req.url:
            context.findings.append(
                Finding(
                    "Dependencies",
                    "warning",
                    "direct-reference",
                    "A direct URL dependency requires manual review; URL omitted.",
                )
            )
        if not req.marker or req.marker.evaluate():
            context.dependencies.append(req)
    except InvalidRequirement:
        context.findings.append(
            Finding(
                "Project",
                "warning",
                "unsupported-requirement",
                "An unsupported dependency entry was skipped; contents omitted.",
            )
        )


def requirements(path: Path, context, seen=None):
    seen = set() if seen is None else seen
    if path.is_symlink():
        return
    path = path.resolve()
    if path in seen:
        return
    seen.add(path)
    if not path.is_relative_to(context.root) or path.is_symlink():
        return
    for line in path.read_text().splitlines():
        line = re.split(r"\s+#", line, maxsplit=1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-r ", "--requirement ")):
            child = path.parent / line.split(maxsplit=1)[1]
            if child.is_relative_to(context.root) and child.is_file():
                requirements(child, context, seen)
            else:
                context.findings.append(
                    Finding(
                        "Project",
                        "warning",
                        "include-missing",
                        "Requirements include is unavailable or outside the project.",
                    )
                )
        elif line.startswith("-"):
            context.findings.append(
                Finding(
                    "Project",
                    "warning",
                    "pip-option",
                    "A pip option/editable entry needs manual review.",
                )
            )
        else:
            parse_requirement(line.split(" --hash=", 1)[0], context)


def poetry_spec(value):
    if value == "*":
        return ""
    if value.startswith("^"):
        parts = [int(n) for n in value[1:].split(".")]
        parts += [0] * (3 - len(parts))
        index = next((i for i, n in enumerate(parts) if n), 2)
        upper = parts[:]
        upper[index] += 1
        for i in range(index + 1, 3):
            upper[i] = 0
        return f">={value[1:]},<{'.'.join(map(str, upper))}"
    if value.startswith("~") and not value.startswith("~="):
        parts = value[1:].split(".")
        index = 0 if len(parts) == 1 else 1
        upper = [int(n) for n in parts]
        upper[index] += 1
        upper[index + 1 :] = [0] * (len(upper) - index - 1)
        return f">={value[1:]},<{'.'.join(map(str, upper))}"
    return "==" + value if value[0].isdigit() else value


def read_project(context):
    for name in FILES:
        path = context.root / name
        if not path.is_file() or path.is_symlink():
            continue
        context.files.append(name)
        context.findings.append(Finding("Project", "ok", "file-detected", f"{name} detected"))
        try:
            if name.startswith("requirements"):
                requirements(path, context)
            elif name == "pyproject.toml":
                data = tomllib.loads(path.read_text())
                project = data.get("project", {})
                context.python_requirement = project.get("requires-python")
                for req in project.get("dependencies", []):
                    parse_requirement(req, context)
                for _group in project.get("optional-dependencies", {}).values():
                    context.findings.append(
                        Finding(
                            "Project",
                            "warning",
                            "optional-group",
                            "Optional dependencies are excluded from the default environment check.",
                        )
                    )
                    break
                poetry = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
                for key, value in poetry.items():
                    if key == "python":
                        context.python_requirement = context.python_requirement or poetry_spec(
                            value
                        )
                    elif isinstance(value, str):
                        parse_requirement(key + poetry_spec(value), context)
                    else:
                        context.findings.append(
                            Finding(
                                "Project",
                                "warning",
                                "poetry-complex",
                                "A complex Poetry dependency needs manual review.",
                            )
                        )
            elif name == "Pipfile":
                data = tomllib.loads(path.read_text())
                for key, value in data.get("packages", {}).items():
                    if isinstance(value, str):
                        parse_requirement(key + ("" if value == "*" else value), context)
                required = data.get("requires", {}).get("python_version")
                if required and not context.python_requirement:
                    context.python_requirement = f"=={required}.*"
            elif name == "setup.cfg":
                cfg = configparser.ConfigParser(interpolation=None)
                cfg.read(path)
                if cfg.has_section("options"):
                    for req in cfg.get("options", "install_requires", fallback="").splitlines():
                        if req.strip():
                            parse_requirement(req.strip(), context)
                    context.python_requirement = context.python_requirement or cfg.get(
                        "options", "python_requires", fallback=None
                    )
            elif name == "setup.py":
                tree = ast.parse(path.read_text())
                found = False
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        for kw in node.keywords:
                            if kw.arg in ("install_requires", "python_requires"):
                                try:
                                    value = ast.literal_eval(kw.value)
                                except (ValueError, TypeError):
                                    continue
                                found = True
                                if kw.arg == "install_requires":
                                    for req in value:
                                        parse_requirement(req, context)
                                else:
                                    context.python_requirement = context.python_requirement or value
                if not found:
                    context.findings.append(
                        Finding(
                            "Project",
                            "warning",
                            "dynamic-setup",
                            "Dynamic setup.py metadata cannot be evaluated safely.",
                        )
                    )
            elif name == ".python-version" and not context.python_requirement:
                value = path.read_text().strip()
                if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", value):
                    context.python_requirement = (
                        "==" + value + (".*" if value.count(".") == 1 else "")
                    )
        except (ValueError, OSError, SyntaxError, configparser.Error, TypeError):
            context.findings.append(
                Finding(
                    "Project",
                    "error",
                    "invalid-metadata",
                    f"Cannot parse {name}; contents omitted.",
                )
            )
    if context.python_requirement:
        try:
            SpecifierSet(context.python_requirement)
        except InvalidSpecifier:
            context.findings.append(
                Finding(
                    "Project",
                    "warning",
                    "python-specifier",
                    "Python version constraint cannot be interpreted.",
                )
            )
            context.python_requirement = None
