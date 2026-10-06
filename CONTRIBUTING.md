# Contributing to worksforme

Thank you for helping make Python projects easier to diagnose. Please follow the
[Code of Conduct](CODE_OF_CONDUCT.md). Contributions are licensed under Apache-2.0
as described in LICENSE; no additional contributor agreement is currently required.

## Clone and set up

Clone the repository URL shown on its GitHub page:

```bash
git clone https://github.com/istek26-design/worksforme.git worksforme
cd worksforme
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Create a focused branch (`git switch -c describe-your-change`). Keep credentials
and local configuration out of version control.

## Run locally and validate

```bash
worksforme --help
worksforme diagnose
worksforme diagnose --json
worksforme fix --dry-run
worksforme diagnose examples/broken_project
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m build
python scripts/check_wheel.py
```

The broken example deliberately exits 1. Run diagnosis with the intended project's
interpreter. CI covers Linux/macOS/Windows and Python 3.10–3.13. A wheel smoke test
requires network access to obtain declared dependencies in a fresh environment.

## Add a diagnostic check

Implement an object with `name: str` and `run(context: Context) -> list[Finding]`.
Pass it to `diagnose(path, checks=[*DEFAULT_CHECKS, your_check])`; see the README
example. CLI checks are registered in `DEFAULT_CHECKS` in diagnostics.py. Keep codes
stable, findings actionable and uncertain conclusions as warnings. Add temporary
project tests before registering a new built-in check. Checks must not mutate files,
install packages, execute setup.py or import project modules. Extensions are explicitly
trusted Python code, not automatically loaded plugins.

## Standards and pull requests

Use Python 3.10-compatible syntax, modular functions and clear names. Run Ruff formatting.
Test behavior with temporary projects and deterministic inventories; avoid relying on
whatever packages happen to be installed. Never store or print secret values, URLs
containing credentials or private paths. Document safety assumptions and failure modes.

Open a bug or feature issue using the templates for non-sensitive topics. Include
version, OS, command, expected/actual behavior and a minimal sanitized reproduction.
Discuss broad changes before implementation. Fork, push your branch and open a focused
PR against main. Explain the problem, resulting behavior, tests, breaking changes and
documentation updates. Update CHANGELOG.md for user-visible changes.

## Security and conduct reports

Follow [SECURITY.md](SECURITY.md) for vulnerabilities; do not open public exploit
reports or attach real `.env` files. Prefer GitHub Private Vulnerability Reporting
when enabled. Use an actual private contact method listed by the maintainer if needed.
Conduct reports follow CODE_OF_CONDUCT.md. No fictional contact address is provided.

## First contribution ideas

1. Add a verified import-to-distribution mapping with a deterministic test.
2. Add Windows, macOS or Linux path/venv regression cases.
3. Improve the JSON documentation with sanitized real output.
4. Propose a read-only package manager check with fixtures.
5. Clarify setup and troubleshooting instructions for a new user.
