import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from . import __version__
from .diagnostics import diagnose as run_diagnose
from .environment import environment_info
from .fixer import apply_plan, build_plan, display_command

app = typer.Typer(
    help="Because “it works on my machine” isn't a solution.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
console = Console(markup=False)


def version_callback(value: bool):
    if value:
        typer.echo(f"worksforme {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None, "--version", callback=version_callback, is_eager=True
    ),
):
    pass


def safe_report(path, json_mode=False):
    try:
        return run_diagnose(path)
    except Exception:
        if json_mode:
            typer.echo(
                json.dumps(
                    {
                        "schema_version": 1,
                        "internal_error": True,
                        "message": "Unable to analyze project; details omitted for privacy.",
                    }
                )
            )
        else:
            console.print("Unable to analyze project; details omitted for privacy.")
        raise typer.Exit(2) from None


@app.command()
def diagnose(
    path: Path = typer.Argument(Path(".")), json_output: bool = typer.Option(False, "--json")
):
    """Analyze project files and the interpreter running this CLI without changing them."""
    report = safe_report(path, json_output)
    data = report.to_dict()
    if json_output:
        typer.echo(json.dumps(data, indent=2, ensure_ascii=True))
    else:
        console.print(Panel("🩺 worksforme doctor"))
        for section in dict.fromkeys(c.section for c in report.checks):
            console.rule(section)
            for check in report.checks:
                if check.section == section:
                    symbol = {"ok": "✓", "error": "❌", "warning": "⚠", "info": "•"}[check.status]
                    console.print(f"{symbol} {check.message}")
        console.rule("Score")
        console.print(f"Project health: {data['health_score']}/100")
        console.print(f"{data['errors']} errors, {data['warnings']} warnings.")
        suggestions = list(dict.fromkeys(c.suggestion for c in report.checks if c.suggestion))
        if suggestions:
            console.print("Suggested fixes:")
            for i, suggestion in enumerate(suggestions, 1):
                console.print(f"{i}. {suggestion}")
    raise typer.Exit(1 if data["errors"] else 0)


@app.command()
def fix(path: Path = typer.Argument(Path(".")), dry_run: bool = typer.Option(False, "--dry-run")):
    """Show a repair plan; ask before installing declared packages into an active venv."""
    report = safe_report(path)
    plan = build_plan(report)
    console.print(f"Proposed fixes (manager: {plan.manager}):")
    for command in plan.commands:
        console.print(display_command(command))
    for reason in plan.blocked:
        console.print(f"Manual action required: {reason}")
    for suggestion in dict.fromkeys(c.suggestion for c in report.checks if c.suggestion):
        console.print(suggestion)
    if not plan.commands:
        console.print("No automatic repairs available.")
        return
    console.print("Installation downloads packages and may execute third-party build code.")
    if dry_run:
        console.print("No changes made.")
        return
    console.print("⚠ worksforme is about to modify your Python environment or project.")
    console.print("Automated fixes may cause dependency conflicts or unexpected changes.")
    console.print("Recommended before continuing:")
    console.print("• Commit your current changes with Git")
    console.print("• Back up important files")
    console.print("• Review the proposed fixes")
    console.print("• Run worksforme fix --dry-run first")
    if not typer.confirm("Proceed?", default=False):
        console.print("No changes made.")
        return
    try:
        success = apply_plan(plan, report.project)
    except Exception:
        console.print("Repair failed; package manager output omitted for privacy.")
        raise typer.Exit(2) from None
    if not success:
        console.print("Installation failed; environment may be partially updated.")
        raise typer.Exit(2) from None
    console.print("Repair completed. Run worksforme diagnose again.")


@app.command()
def info():
    """Show interpreter and available tool paths; never show environment variable values."""
    typer.echo(json.dumps(environment_info(), indent=2))
