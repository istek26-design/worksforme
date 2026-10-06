"""Install a built wheel into a fresh temporary environment and test its entry point."""

import os
import subprocess
import tempfile
import venv
from pathlib import Path

root = Path(__file__).resolve().parents[1]
wheels = list((root / "dist").glob("worksforme-*.whl"))
if len(wheels) != 1:
    raise SystemExit("Expected exactly one worksforme wheel in dist/")
with tempfile.TemporaryDirectory(prefix="worksforme-wheel-") as directory:
    target = Path(directory)
    venv.EnvBuilder(with_pip=True).create(target)
    bin_dir = target / ("Scripts" if os.name == "nt" else "bin")
    python = bin_dir / ("python.exe" if os.name == "nt" else "python")
    cli = bin_dir / ("worksforme.exe" if os.name == "nt" else "worksforme")
    subprocess.run([str(python), "-m", "pip", "install", str(wheels[0])], check=True)
    for argument in ("--help", "--version"):
        subprocess.run([str(cli), argument], cwd=directory, check=True)
