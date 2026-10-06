import ast
import os
import sys
import tokenize
from pathlib import Path

from .models import Finding

EXCLUDED = {
    "examples",
    "tests",
    "docs",
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    ".tox",
    ".nox",
    "site-packages",
}


def python_files(root):
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not (Path(base) / d).is_symlink())
        for name in sorted(files):
            path = Path(base) / name
            if name.endswith(".py") and not path.is_symlink():
                yield path


def scan(context):
    local = set()
    for base in (context.root, context.root / "src"):
        if base.is_dir():
            for child in base.iterdir():
                if child.is_symlink():
                    continue
                if child.suffix == ".py":
                    local.add(child.stem)
                elif child.is_dir() and child.name not in EXCLUDED and any(child.rglob("*.py")):
                    local.add(child.name)
    stdlib = sys.stdlib_module_names | set(sys.builtin_module_names)
    for path in python_files(context.root):
        try:
            with tokenize.open(path) as file:
                tree = ast.parse(file.read())
        except (SyntaxError, UnicodeError, OSError):
            context.findings.append(
                Finding(
                    "Imports",
                    "warning",
                    "syntax",
                    f"Cannot analyze {path.relative_to(context.root)}; source omitted.",
                )
            )
            continue
        os_aliases, environ_aliases, getenv_aliases = {"os"}, set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    context.imports.add(alias.name.split(".")[0])
                    if alias.name == "os":
                        os_aliases.add(alias.asname or "os")
            elif isinstance(node, ast.ImportFrom) and not node.level:
                if node.module:
                    context.imports.add(node.module.split(".")[0])
                if node.module == "os":
                    for alias in node.names:
                        if alias.name == "environ":
                            environ_aliases.add(alias.asname or alias.name)
                        elif alias.name == "getenv":
                            getenv_aliases.add(alias.asname or alias.name)

        def is_environ(node, environ_aliases=environ_aliases, os_aliases=os_aliases):
            return (
                isinstance(node, ast.Name)
                and node.id in environ_aliases
                or isinstance(node, ast.Attribute)
                and node.attr == "environ"
                and isinstance(node.value, ast.Name)
                and node.value.id in os_aliases
            )

        for node in ast.walk(tree):
            key, optional = None, False
            if isinstance(node, ast.Call) and node.args:
                f = node.func
                getenv = (
                    isinstance(f, ast.Name)
                    and f.id in getenv_aliases
                    or isinstance(f, ast.Attribute)
                    and f.attr == "getenv"
                    and isinstance(f.value, ast.Name)
                    and f.value.id in os_aliases
                )
                get = isinstance(f, ast.Attribute) and f.attr == "get" and is_environ(f.value)
                if getenv or get:
                    key = node.args[0]
                    optional = len(node.args) > 1 or any(k.arg == "default" for k in node.keywords)
            elif isinstance(node, ast.Subscript) and is_environ(node.value):
                key = node.slice
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                import re

                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key.value):
                    (context.env_optional if optional else context.env_required).add(key.value)
    context.imports -= stdlib | local
