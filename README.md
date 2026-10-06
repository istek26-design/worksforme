# worksforme 🩺

**Because “it works on my machine” isn't a solution.**

Automatically diagnose common problems in Python development environments.

worksforme helps explain why a Python project runs on one machine and fails on
another: incompatible interpreters, missing packages, undeclared imports and absent
configuration. It reads source and metadata without executing the project.

[![CI](https://github.com/istek26-design/worksforme/actions/workflows/ci.yml/badge.svg)](https://github.com/istek26-design/worksforme/actions/workflows/ci.yml)
![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue)
![Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)

## Key features

- Human-readable diagnostics with actionable suggestions and a health score.
- Structured JSON and exit codes for CI integration.
- Static dependency/import/environment analysis with privacy-preserving output.
- Reviewable, explicitly confirmed pip repairs confined to an active virtual environment.
- Small Python check API for deliberate extensions.

## Installation

```bash
git clone https://github.com/istek26-design/worksforme.git
cd worksforme
```

The intended published command is `pip install worksforme`. The distribution has **not**
been published to PyPI and name ownership has not been verified. Install this
repository in a virtual environment:

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
worksforme --help
worksforme --version
worksforme info
```

## Quick start

Run inside your project, using that project's active interpreter:

```bash
worksforme diagnose
worksforme diagnose ./some-project
worksforme diagnose --json
worksforme fix --dry-run
worksforme fix
worksforme fix ./some-project
```

Diagnostics describe **the interpreter running worksforme**, not another discovered
virtual environment. Install worksforme into the environment you want to check.
Diagnostics never import project modules, run setup.py, install packages or rewrite files.
`fix` first prints a plan, then warns about modification risks and asks `Proceed? [y/N]`. Only declared ordinary
PyPI dependencies with missing/incompatible installed versions are eligible. Global
installations, direct URLs, extras and declaration edits require manual action.
A pip resolver preflight runs before installation (pip 22.2+ is required for fixes).
Package installation can execute third-party build code and is not transactional.
A failed installation may partially update a venv. Package manager output is suppressed
because it may contain private index credentials. Review suggestions and rerun diagnosis.

uv/Poetry lockfiles are detected; their sync/install operations are deliberately manual
in v0.1 because they can update project environments and lock state. `fix --dry-run`
never launches an installer or changes files. It exits 0 for a successfully generated
plan, including plans that require manual work.

Example (abbreviated; your environment affects results):

```text
🩺 worksforme doctor
Project
✓ pyproject.toml detected
Environment
❌ Python requirement >=3.99; current 3.12.4
Dependencies
❌ worksforme-demo-missing-package missing
❌ packaging 24.2 installed; project requires <1
Imports
❌ Pillow imported but not declared
Environment Variables
❌ WORKSFORME_DEMO_DATABASE_URL missing
Suggested fixes:
Select a compatible Python interpreter.
Configure WORKSFORME_DEMO_DATABASE_URL locally; do not commit its value.
```

Try `worksforme diagnose examples/broken_project` (expected exit 1).
Exit codes: 0 = no diagnostic errors, 1 = diagnostic errors, 2 = tool/input failure.
Warnings do not fail CI. JSON contains `schema_version`, `project`, `environment`,
`health_score`, `errors`, `warnings` and structured `checks`. Score subtracts 15 per
error and 3 per warning, floored at zero; it is a heuristic, not a security certification.

## Supported versions and project formats

Python 3.10+ is required; Python 3.10–3.13 are included in the CI matrix.

- PEP 621 dependencies and Python constraints in pyproject.toml
- Common Poetry string constraints, Pipfile packages, static setup.py keyword literals,
  setup.cfg, requirements.txt / requirements-dev.txt and contained `-r` includes
- poetry.lock / uv.lock inventory and basic direct dependency consistency
- .python-version, current OS/CPU/Python/executable, pip, uv, Poetry, Conda, Git
- AST imports, standard-library filtering, top-level and src local modules
- Extendable PIL/cv2/sklearn/yaml/dotenv/bs4 mapping and installed distribution providers
- PEP 440 installed version checks, PEP 508 markers, conflicting exact pins
- AST os.getenv/os.environ access, including common aliases and defaults
- .env names/configuration presence, example names, Git tracking/ignore checks
- Missing venv executables, inactive project venvs, conflicting manager files

## How it works

The scanner reads project declarations and parses source with Python AST.
`importlib.metadata` inventories the current interpreter; `packaging` evaluates
PEP 440 version constraints and PEP 508 markers. Checks return structured findings.
The repair planner only selects unambiguous declared dependencies. It never edits
metadata or lockfiles.

## Limitations

Optional extras and dependency groups are not selected; requirements-dev.txt is checked
when present. The default scan excludes tests, examples and docs directories. When diagnosing one
of those directories directly, its source is scanned. Conditional/TYPE_CHECKING imports
are scanned conservatively and
may produce warnings. Unknown import-to-distribution mappings never trigger installs.
Dynamic imports, dynamic metadata, shell expansion, full lock freshness/resolution,
transitive conflicts and binary architecture compatibility are outside v0.1 coverage.
Local namespace detection is heuristic. Recursive scanning skips common build/venv
folders and symlinks, but large monorepos can still take time.

## Privacy and security

No telemetry. No sudo, shell=True, deletion, silent installs or automatic secret edits.
Environment file values are read only long enough to determine nonempty presence;
only names and booleans are retained. Secret values, requirement URLs and source text
are not emitted. Malformed file details and internal exception text are omitted.
`.env` is treated as locally configured even if your application does not load it;
verify dotenv loading yourself. Example files are templates, never configured values.
Ordinary paths and dependency/environment **names** appear in reports; treat these
as potentially sensitive metadata when sharing a report.

## ⚠️ Disclaimer

`worksforme fix` can change your Python environment and project dependencies.
Automated repairs may cause conflicts or unexpected changes. For important projects,
commit current changes with Git and back up important files before proceeding.
Review the plan first:

```bash
worksforme diagnose
worksforme fix --dry-run
git status
worksforme fix
```

Installation is not transactional and can partially update an environment on failure.
See [DISCLAIMER.md](DISCLAIMER.md) for the full disclaimer and [SECURITY.md](SECURITY.md)
for the security policy.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) and follow the
[Code of Conduct](CODE_OF_CONDUCT.md). Small first contributions include tested import
mappings, OS-specific test cases and documentation improvements.

## Development and tests

```bash
python -m pip install -e '.[dev]'
python -m pytest
python -m ruff check .
python -m build
```

CI tests Linux, macOS and Windows with Python 3.10–3.13. See CONTRIBUTING.md.
[View CI runs](https://github.com/istek26-design/worksforme/actions/workflows/ci.yml) for verified execution status.

## Extend checks

```python
from pathlib import Path
from worksforme.diagnostics import DEFAULT_CHECKS, diagnose
from worksforme.models import Finding


class TeamCheck:
    name = "team"

    def run(self, context):
        return [Finding("Team", "ok", "team-policy", "Team check completed")]


report = diagnose(Path("."), checks=[*DEFAULT_CHECKS, TeamCheck()])
```

Checks return findings; use stable codes and `ok`, `info`, `warning`, `error` statuses.
Only built-in repair plans execute. There is no automatic discovery/execution of third-party
plugins; importing an extension is a deliberate Python API choice.

## Roadmap

1. Interpreter selection with verified subprocess inventory.
2. Explicit optional groups, extras and scan include/exclude controls.
3. Manager-native, reviewable uv/Poetry repair plans and post-fix verification.
4. Broader provider mapping, dynamic import hints and conditional import classification.
5. Full dependency resolution conflicts, lock fingerprints and wheel architecture checks.

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).

PyPI publishing remains a separate step. Distribution name ownership has not been
verified; `worksforme-doctor` is an alternative to investigate if needed.
