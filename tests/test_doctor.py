import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest
from packaging.requirements import Requirement
from typer.testing import CliRunner

from worksforme.cli import app
from worksforme.dependencies import read_project
from worksforme.diagnostics import DependencyCheck, diagnose
from worksforme.envdoctor import read_keys
from worksforme.fixer import apply_plan, build_plan
from worksforme.models import Context, Finding, Report
from worksforme.scanner import scan

runner = CliRunner()


def put(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def codes(report):
    return {c.code for c in report.checks}


def test_requirements_includes_markers_and_privacy(tmp_path):
    put(
        tmp_path,
        "requirements.txt",
        "# comment\nrequests>=2 # comment\n-r extra.txt\n"
        'ignored-package; python_version < "2"\n-e .\nprivate @ https://user:SECRET@example.org/a.whl\n',
    )
    put(tmp_path, "extra.txt", "Pillow==10.0\n-r requirements.txt\n")
    context = Context(tmp_path)
    read_project(context)
    assert {r.name for r in context.dependencies} == {"requests", "Pillow", "private"}
    assert "SECRET" not in str(context.findings)


def test_include_escape(tmp_path):
    put(tmp_path, "requirements.txt", "-r ../outside.txt\n")
    c = Context(tmp_path)
    read_project(c)
    assert c.findings[-1].code == "include-missing"


@pytest.mark.parametrize(
    "name,content",
    [
        ("pyproject.toml", '[project]\nrequires-python=">=3.11"\ndependencies=["requests>=2"]'),
        ("setup.cfg", "[options]\npython_requires=>=3.11\ninstall_requires=\n requests>=2"),
        (
            "setup.py",
            'raise RuntimeError("must never run")\nsetup(install_requires=["requests>=2"], python_requires=">=3.11")',
        ),
        ("Pipfile", '[requires]\npython_version="3.11"\n[packages]\nrequests=">=2"'),
    ],
)
def test_metadata(tmp_path, name, content):
    put(tmp_path, name, content)
    c = Context(tmp_path)
    read_project(c)
    assert c.dependencies[0].name == "requests"
    assert "3.11" in c.python_requirement


def test_poetry(tmp_path):
    put(tmp_path, "pyproject.toml", '[tool.poetry.dependencies]\npython="^3.10"\nrequests="^2.31"')
    c = Context(tmp_path)
    read_project(c)
    assert c.dependencies[0].specifier.contains("2.32")
    assert not c.dependencies[0].specifier.contains("3.0")


def test_ast_local_stdlib_and_env(tmp_path):
    put(tmp_path, "src/localpkg/__init__.py", "")
    put(tmp_path, "helper.py", "")
    put(
        tmp_path,
        "app.py",
        "import os as operating\nimport sys, json, helper, localpkg\n"
        "from PIL import Image\nfrom .sibling import x\nfrom os import getenv as env, environ as e\n"
        'a=operating.getenv("KEY")\nb=e["DATABASE_URL"]\nc=env("OPTIONAL", "default")\n'
        'd=operating.environ.get("OTHER")\n',
    )
    c = Context(tmp_path)
    scan(c)
    assert c.imports == {"PIL"}
    assert c.env_required == {"KEY", "DATABASE_URL", "OTHER"}
    assert c.env_optional == {"OPTIONAL"}


def test_syntax_error_secret_omitted(tmp_path):
    put(tmp_path, "app.py", 'SECRET_TOKEN = "REAL_SECRET"\nthis is !invalid')
    report = diagnose(tmp_path)
    assert "syntax" in codes(report)
    assert "REAL_SECRET" not in json.dumps(report.to_dict())


def test_versions_and_mapping(tmp_path, monkeypatch):
    monkeypatch.setattr("worksforme.diagnostics.installed_packages", lambda: {"numpy": "1.26"})
    monkeypatch.setattr("worksforme.diagnostics.metadata.packages_distributions", lambda: {})
    c = Context(
        tmp_path,
        dependencies=[Requirement("numpy>=2"), Requirement("Pillow>=10")],
        imports={"numpy", "PIL", "mystery_provider"},
    )
    findings = DependencyCheck().run(c)
    assert {"missing", "version-mismatch", "unknown-import"} <= {f.code for f in findings}
    assert next(f for f in findings if f.code == "version-mismatch").requirement == "numpy>=2"


def test_conflicting_pins_block_repairs(tmp_path, monkeypatch):
    put(tmp_path, "requirements.txt", "requests==1\nrequests==2\n")
    monkeypatch.setattr("worksforme.diagnostics.installed_packages", lambda: {})
    report = diagnose(tmp_path)
    assert "conflicting-pins" in codes(report)
    assert not build_plan(report).commands


def test_secret_values_never_output(tmp_path, monkeypatch):
    put(tmp_path, "app.py", 'import os\nx=os.environ["WFM_KEY"]\ny=os.getenv("WFM_MISSING")')
    put(tmp_path, ".env", "WFM_KEY=SUPER_SECRET\nUNUSED=OTHER_SECRET\n")
    monkeypatch.delenv("WFM_MISSING", raising=False)
    for args in (
        ["diagnose", str(tmp_path)],
        ["diagnose", str(tmp_path), "--json"],
        ["fix", str(tmp_path), "--dry-run"],
    ):
        result = runner.invoke(app, args)
        assert "SUPER_SECRET" not in result.output
        assert "OTHER_SECRET" not in result.output
        assert "WFM_MISSING" in result.output
    assert read_keys(tmp_path / ".env") == ({"WFM_KEY", "UNUSED"}, {"WFM_KEY", "UNUSED"})


def test_json_exit_and_failure(tmp_path):
    put(tmp_path, "app.py", 'import os\nx=os.environ["WORKSFORME_TEST_MISSING_XYZ"]')
    result = runner.invoke(app, ["diagnose", str(tmp_path), "--json"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["errors"] >= 1 and data["schema_version"] == 1
    result = runner.invoke(app, ["diagnose", str(tmp_path / "absent"), "--json"])
    assert result.exit_code == 2 and json.loads(result.output)["internal_error"]


def test_healthy_exit(tmp_path):
    put(tmp_path, "app.py", "import sys\n")
    assert runner.invoke(app, ["diagnose", str(tmp_path), "--json"]).exit_code == 0


@pytest.mark.parametrize("args", [["--help"], ["--version"], ["info"]])
def test_entrypoints(args):
    assert runner.invoke(app, args).exit_code == 0


def test_dry_run_no_mutation(tmp_path, monkeypatch):
    put(tmp_path, "requirements.txt", "worksforme-test-not-installed==1\n")
    monkeypatch.setattr("worksforme.diagnostics.installed_packages", lambda: {})
    install = Mock(side_effect=AssertionError("installer must not run"))
    monkeypatch.setattr("worksforme.cli.apply_plan", install)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    env = os.environ.copy()
    assert runner.invoke(app, ["fix", str(tmp_path), "--dry-run"]).exit_code == 0
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    assert dict(os.environ) == env
    install.assert_not_called()


def synthetic_report(tmp_path, venv=True):
    return Report(
        str(tmp_path),
        {"virtual_environment": "/venv" if venv else None, "pip": "24"},
        [Finding("Dependencies", "error", "missing", "demo missing", requirement="demo>=1")],
    )


def test_global_and_manager_refusal(tmp_path):
    assert not build_plan(synthetic_report(tmp_path, False)).commands
    put(tmp_path, "uv.lock", "")
    assert not build_plan(synthetic_report(tmp_path)).commands


def test_default_decline(tmp_path, monkeypatch):
    monkeypatch.setattr("worksforme.cli.safe_report", lambda p: synthetic_report(tmp_path))
    installer = Mock()
    monkeypatch.setattr("worksforme.cli.apply_plan", installer)
    result = runner.invoke(app, ["fix", str(tmp_path)], input="\n")
    assert result.exit_code == 0
    installer.assert_not_called()


def test_confirmed_apply_argv(tmp_path, monkeypatch):
    monkeypatch.setattr("worksforme.fixer.sys.prefix", "/venv")
    monkeypatch.setattr("worksforme.fixer.sys.base_prefix", "/base")
    proc = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr("worksforme.fixer.subprocess.run", proc)
    plan = build_plan(synthetic_report(tmp_path))
    assert apply_plan(plan, tmp_path)
    args, kwargs = proc.call_args
    assert args[0][-2:] == ["--", "demo>=1"]
    assert "shell" not in kwargs


def test_broken_example():
    root = Path(__file__).parents[1] / "examples/broken_project"
    report = diagnose(root)
    assert {"python-compatibility", "missing", "env-missing", "undeclared"} <= codes(report)


def test_extension(tmp_path):
    class Extra:
        name = "extra"

        def run(self, context):
            return [Finding("Custom", "ok", "custom", "success")]

    assert "custom" in codes(diagnose(tmp_path, checks=[Extra()]))


def test_lock_drift(tmp_path, monkeypatch):
    put(tmp_path, "requirements.txt", "requests>=3\n")
    put(tmp_path, "uv.lock", '[[package]]\nname="requests"\nversion="2.0"')
    monkeypatch.setattr("worksforme.diagnostics.installed_packages", dict)
    assert "lock-drift" in codes(diagnose(tmp_path))


def test_poetry_without_lock_manual(tmp_path):
    put(tmp_path, "pyproject.toml", '[tool.poetry]\nname="demo"')
    plan = build_plan(synthetic_report(tmp_path))
    assert plan.manager == "poetry" and not plan.commands


def test_broken_venv(tmp_path):
    (tmp_path / ".venv").mkdir()
    assert "broken-venv" in codes(diagnose(tmp_path))


def test_missing_example_and_optional_defaults(tmp_path):
    put(tmp_path, ".env.example", "NEEDED=example-value\nOPTIONAL=template\n")
    put(tmp_path, "app.py", 'import os\na=os.getenv("OPTIONAL", "fallback")')
    report = diagnose(tmp_path)
    needed = next(c for c in report.checks if c.message.startswith("NEEDED"))
    optional = next(c for c in report.checks if c.message.startswith("OPTIONAL"))
    assert needed.status == "error" and optional.status == "warning"
    assert "example-value" not in json.dumps(report.to_dict())


def test_git_tracked_env(tmp_path):
    import shutil
    import subprocess

    git = shutil.which("git")
    if not git:
        pytest.skip("Git unavailable")
    subprocess.run([git, "init", str(tmp_path)], check=True, capture_output=True)
    put(tmp_path, ".env", "SAMPLE_KEY=secret-should-never-appear\n")
    subprocess.run([git, "-C", str(tmp_path), "add", ".env"], check=True, capture_output=True)
    report = diagnose(tmp_path)
    assert "env-tracked" in codes(report)
    assert "secret-should-never-appear" not in json.dumps(report.to_dict())


def test_diagnose_preserves_project(tmp_path):
    put(tmp_path, "app.py", "import json")
    put(tmp_path, ".env", "A=secret")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    diagnose(tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_joint_constraint_review(tmp_path, monkeypatch):
    put(tmp_path, "requirements.txt", "numpy<2\nnumpy>=2\n")
    monkeypatch.setattr("worksforme.diagnostics.installed_packages", lambda: {"numpy": "1.26"})
    report = diagnose(tmp_path)
    assert "multiple-constraints" in codes(report)
    assert not build_plan(report).commands


def test_confirmed_cli_fix(tmp_path, monkeypatch):
    monkeypatch.setattr("worksforme.cli.safe_report", lambda p: synthetic_report(tmp_path))
    installer = Mock(return_value=True)
    monkeypatch.setattr("worksforme.cli.apply_plan", installer)
    result = runner.invoke(app, ["fix", str(tmp_path)], input="y\n")
    assert result.exit_code == 0
    installer.assert_called_once()


def test_internal_error_does_not_leak_secret(tmp_path, monkeypatch):
    def fail(path):
        raise RuntimeError("TOP_SECRET")

    monkeypatch.setattr("worksforme.cli.run_diagnose", fail)
    result = runner.invoke(app, ["diagnose", str(tmp_path), "--json"])
    assert result.exit_code == 2
    assert "TOP_SECRET" not in result.output
    assert json.loads(result.output)["internal_error"]


@pytest.mark.parametrize("answer", ["n\n", "\n"])
def test_fix_warning_and_no_consent(tmp_path, monkeypatch, answer):
    monkeypatch.setattr("worksforme.cli.safe_report", lambda p: synthetic_report(tmp_path))
    installer = Mock()
    monkeypatch.setattr("worksforme.cli.apply_plan", installer)
    result = runner.invoke(app, ["fix", str(tmp_path)], input=answer)
    assert result.exit_code == 0
    assert "dependency conflicts" in result.output
    assert "Back up important files" in result.output
    assert "Proceed?" in result.output
    installer.assert_not_called()


@pytest.mark.parametrize("failure", [False, RuntimeError("private-index-secret")])
def test_failed_fix_privacy(tmp_path, monkeypatch, failure):
    monkeypatch.setattr("worksforme.cli.safe_report", lambda p: synthetic_report(tmp_path))
    installer = (
        Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=False)
    )
    monkeypatch.setattr("worksforme.cli.apply_plan", installer)
    result = runner.invoke(app, ["fix", str(tmp_path)], input="y\n")
    assert result.exit_code == 2
    assert "private-index-secret" not in result.output
    assert "failed" in result.output.lower()


def test_preflight_failure_does_not_install(tmp_path, monkeypatch):
    monkeypatch.setattr("worksforme.fixer.sys.prefix", "/venv")
    monkeypatch.setattr("worksforme.fixer.sys.base_prefix", "/base")
    proc = Mock(return_value=Mock(returncode=1))
    monkeypatch.setattr("worksforme.fixer.subprocess.run", proc)
    plan = build_plan(synthetic_report(tmp_path))
    assert not apply_plan(plan, tmp_path)
    proc.assert_called_once()
    assert "--dry-run" in proc.call_args.args[0]


def test_pip_preflight_version_guard(tmp_path):
    report = synthetic_report(tmp_path)
    report.environment["pip"] = "21.0"
    assert not build_plan(report).commands


def test_required_env_use_overrides_optional_use(tmp_path, monkeypatch):
    monkeypatch.delenv("WFM_SHARED_MISSING", raising=False)
    put(
        tmp_path,
        "app.py",
        'import os\na=os.getenv("WFM_SHARED_MISSING", "fallback")\nb=os.environ["WFM_SHARED_MISSING"]',
    )
    report = diagnose(tmp_path)
    finding = next(c for c in report.checks if c.message.startswith("WFM_SHARED_MISSING"))
    assert finding.status == "error"
