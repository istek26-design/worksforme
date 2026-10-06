# worksforme v0.1.0

The first open-source release of worksforme, a Python project doctor.

## Features

- Static metadata, interpreter, dependency version and AST import diagnostics.
- Environment variable presence checks without printing secret values.
- Rich terminal reports, structured JSON and CI-friendly exit codes.
- Reviewable venv-only pip repairs with default-No confirmation, dry-run and
  resolver preflight; manual guidance for uv, Poetry and Pipenv.
- Apache-2.0 license, contribution/security policies and cross-platform CI configuration.

## Known limitations

Diagnostics use the interpreter running the CLI. Import/provider and local namespace
analysis is heuristic. Dynamic imports, full resolution conflicts, optional groups,
complete lock freshness and binary architecture checks are not supported.
Manager-native repairs are manual. Installations may run third-party build code and
are not transactional: failures can partially update an environment. Review
DISCLAIMER.md and run `worksforme fix --dry-run` before applying changes.

Python 3.10–3.13 are included in the CI matrix. PyPI publishing is a separate step;
no PyPI release or distribution name ownership is claimed.
