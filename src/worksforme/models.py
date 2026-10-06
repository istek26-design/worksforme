from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class Finding:
    section: str
    status: str
    code: str
    message: str
    suggestion: str | None = None
    requirement: str | None = None


@dataclass
class Context:
    root: Path
    dependencies: list = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    python_requirement: str | None = None
    imports: set[str] = field(default_factory=set)
    env_required: set[str] = field(default_factory=set)
    env_optional: set[str] = field(default_factory=set)
    findings: list[Finding] = field(default_factory=list)


class Check(Protocol):
    name: str

    def run(self, context: Context) -> list[Finding]: ...


@dataclass
class Report:
    project: str
    environment: dict
    checks: list[Finding]

    def to_dict(self):
        errors = sum(c.status == "error" for c in self.checks)
        warnings = sum(c.status == "warning" for c in self.checks)
        return {
            "schema_version": 1,
            "project": self.project,
            "environment": self.environment,
            "health_score": max(0, 100 - errors * 15 - warnings * 3),
            "errors": errors,
            "warnings": warnings,
            "checks": [asdict(c) for c in self.checks],
        }
