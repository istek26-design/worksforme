from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

from .dependencies import read_project, tomllib
from .envdoctor import check_env
from .environment import environment_info, installed_packages
from .models import Context, Finding, Report
from .scanner import scan

IMPORT_MAPPING = {
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "yaml": "PyYAML",
    "dotenv": "python-dotenv",
    "bs4": "beautifulsoup4",
}


class DependencyCheck:
    name = "dependencies"

    def run(self, context):
        installed = installed_packages()
        findings = []
        declared = {canonicalize_name(r.name) for r in context.dependencies}
        used = set()
        providers = metadata.packages_distributions()
        for module in sorted(context.imports):
            choices = providers.get(module, [])
            package = IMPORT_MAPPING.get(module)
            if package is None and len(choices) == 1:
                package = choices[0]
            if package is None and canonicalize_name(module) in declared:
                package = module
            if package is None:
                findings.append(
                    Finding(
                        "Imports",
                        "warning",
                        "unknown-import",
                        f"{module} is external; distribution mapping needs review",
                        f"Identify the distribution providing {module}.",
                    )
                )
                continue
            name = canonicalize_name(package)
            used.add(name)
            if name not in declared:
                findings.append(
                    Finding(
                        "Imports",
                        "error",
                        "undeclared",
                        f"{package} imported but not declared",
                        f"Add {package} to project dependencies after review.",
                    )
                )
                if name not in installed:
                    findings.append(
                        Finding(
                            "Imports",
                            "error",
                            "import-missing",
                            f"{package} appears required but is not installed",
                            f"Declare and install {package}.",
                        )
                    )
        for req in context.dependencies:
            name = canonicalize_name(req.name)
            version = installed.get(name)
            repair = None if req.url or req.extras else req.name + str(req.specifier)
            if version is None:
                findings.append(
                    Finding(
                        "Dependencies",
                        "error",
                        "missing",
                        f"{req.name} missing",
                        f"Install {req.name}{req.specifier}.",
                        repair,
                    )
                )
            elif req.specifier and not req.specifier.contains(version):
                findings.append(
                    Finding(
                        "Dependencies",
                        "error",
                        "version-mismatch",
                        f"{req.name} {version} installed; project requires {req.specifier}",
                        f"Install a compatible {req.name} version.",
                        repair,
                    )
                )
            else:
                findings.append(
                    Finding("Dependencies", "ok", "installed", f"{req.name} {version} installed")
                )
            if name not in used:
                findings.append(
                    Finding(
                        "Imports",
                        "warning",
                        "unused-dependency",
                        f"{req.name} declared but no mapped static import detected",
                    )
                )
        for distribution in metadata.distributions():
            direct = distribution.read_text("direct_url.json")
            if direct:
                try:
                    import json

                    if json.loads(direct).get("dir_info", {}).get("editable"):
                        name = distribution.metadata.get("Name", "unnamed")
                        findings.append(
                            Finding(
                                "Dependencies",
                                "info",
                                "editable",
                                f"{name} installed in editable mode",
                            )
                        )
                except (ValueError, TypeError):
                    pass
        # Exact pins can be checked reliably without pretending to solve all dependency ranges.
        pins = {}
        for req in context.dependencies:
            for spec in req.specifier:
                if spec.operator == "==" and "*" not in spec.version:
                    pins.setdefault(canonicalize_name(req.name), set()).add(spec.version)
        for name, versions in pins.items():
            if len(versions) > 1:
                findings.append(
                    Finding(
                        "Dependencies",
                        "error",
                        "conflicting-pins",
                        f"{name} has conflicting exact pins",
                        "Resolve the conflicting declarations.",
                    )
                )
                for finding in findings:
                    if (
                        finding.requirement
                        and canonicalize_name(Requirement(finding.requirement).name) == name
                    ):
                        finding.requirement = None
        declarations = {}
        for req in context.dependencies:
            declarations.setdefault(canonicalize_name(req.name), set()).add(str(req))
        for name, entries in declarations.items():
            if len(entries) > 1:
                findings.append(
                    Finding(
                        "Dependencies",
                        "warning",
                        "multiple-constraints",
                        f"{name} has multiple declarations; review their combined constraints",
                    )
                )
                for finding in findings:
                    if (
                        finding.requirement
                        and canonicalize_name(Requirement(finding.requirement).name) == name
                    ):
                        finding.requirement = None
        for lock in ("uv.lock", "poetry.lock"):
            if lock in context.files:
                try:
                    data = tomllib.loads((context.root / lock).read_text())
                    locked = {
                        canonicalize_name(x["name"]): x.get("version")
                        for x in data.get("package", [])
                    }
                    for req in context.dependencies:
                        version = locked.get(canonicalize_name(req.name))
                        if version is None or req.specifier and not req.specifier.contains(version):
                            findings.append(
                                Finding(
                                    "Dependencies",
                                    "warning",
                                    "lock-drift",
                                    f"{lock} may be inconsistent with {req.name}",
                                    "Regenerate the lockfile with the project manager.",
                                )
                            )
                except (ValueError, OSError, KeyError, TypeError):
                    findings.append(
                        Finding(
                            "Dependencies",
                            "warning",
                            "lock-unreadable",
                            f"Cannot interpret {lock}; contents omitted.",
                        )
                    )
        return findings


DEFAULT_CHECKS = (DependencyCheck(),)


def diagnose(path: Path, checks=None):
    root = path.resolve()
    if not root.is_dir():
        raise ValueError("Project directory does not exist")
    context = Context(root)
    info = environment_info()
    read_project(context)
    scan(context)
    if not context.files and not any(root.glob("*.py")) and not (root / "src").is_dir():
        context.findings.append(
            Finding(
                "Project", "warning", "not-python", "No Python project metadata or source detected."
            )
        )
    context.findings.append(
        Finding(
            "Environment",
            "ok",
            "python",
            f"Python {info['python']} on {info['os']} {info['architecture']}",
        )
    )
    context.findings.append(
        Finding(
            "Environment",
            "ok" if info["virtual_environment"] else "warning",
            "venv",
            "Virtual environment active"
            if info["virtual_environment"]
            else "No active virtual environment",
            "Activate a project virtual environment." if not info["virtual_environment"] else None,
        )
    )
    if context.python_requirement:
        compatible = SpecifierSet(context.python_requirement).contains(info["python"])
        context.findings.append(
            Finding(
                "Environment",
                "ok" if compatible else "error",
                "python-compatibility",
                f"Python requirement {context.python_requirement}; current {info['python']}",
                None if compatible else "Select a compatible Python interpreter.",
            )
        )
    for tool, location in info["tools"].items():
        context.findings.append(
            Finding(
                "Environment",
                "ok" if location else "info",
                "tool",
                f"{tool} {'available' if location else 'not found'}",
            )
        )
    context.findings.append(
        Finding(
            "Environment",
            "ok" if info["pip"] else "warning",
            "pip",
            f"pip {info['pip']}" if info["pip"] else "pip not found in this interpreter",
        )
    )
    for venv in (root / ".venv", root / "venv"):
        if venv.is_dir():
            executable = venv / ("Scripts/python.exe" if info["os"] == "Windows" else "bin/python")
            if not executable.exists():
                context.findings.append(
                    Finding(
                        "Environment",
                        "error",
                        "broken-venv",
                        f"{venv.name} has no working Python executable",
                        "Recreate the virtual environment.",
                    )
                )
            elif str(venv.resolve()) != info["virtual_environment"]:
                context.findings.append(
                    Finding(
                        "Environment",
                        "warning",
                        "different-venv",
                        f"{venv.name} exists; diagnostics use the current CLI interpreter",
                    )
                )
    if "uv.lock" in context.files and "poetry.lock" in context.files:
        context.findings.append(
            Finding(
                "Project",
                "warning",
                "manager-conflict",
                "Both uv and Poetry lockfiles exist; choose the authoritative manager.",
            )
        )
    for check in DEFAULT_CHECKS if checks is None else checks:
        context.findings.extend(check.run(context))
    context.findings.extend(check_env(context))
    return Report(str(root), info, context.findings)
