"""Configure Cognee storage before its package is imported."""

import os
from pathlib import Path


def configure_cognee_paths(project_root: Path) -> Path:
    local = (project_root / ".local").resolve()
    values = {
        "SYSTEM_ROOT_DIRECTORY": local / "system",
        "DATA_ROOT_DIRECTORY": local / "data",
        "CACHE_ROOT_DIRECTORY": local / "cache",
        "COGNEE_LOGS_DIR": local / "logs",
    }
    for name, path in values.items():
        path.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(path)
    return local
