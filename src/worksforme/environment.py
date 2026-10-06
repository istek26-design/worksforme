import platform
import shutil
import sys
from importlib import metadata


def environment_info():
    try:
        pip = metadata.version("pip")
    except metadata.PackageNotFoundError:
        pip = None
    return {
        "os": platform.system(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "executable": sys.executable,
        "virtual_environment": sys.prefix if sys.prefix != sys.base_prefix else None,
        "pip": pip,
        "tools": {name: shutil.which(name) for name in ("uv", "poetry", "conda", "git")},
    }


def installed_packages():
    from packaging.utils import canonicalize_name

    return {
        canonicalize_name(d.metadata["Name"]): d.version
        for d in metadata.distributions()
        if d.metadata["Name"]
    }
