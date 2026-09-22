"""Architecture and import-order checks for the external library boundary."""

import ast
import json
import subprocess
import sys
from pathlib import Path


def test_only_cognee_adapter_imports_external_package() -> None:
    package = Path(__file__).parents[1] / "src" / "cognee_retriever"
    offenders: list[str] = []
    for path in package.glob("*.py"):
        if path.name == "cognee_client.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(alias.name == "cognee" for alias in node.names):
                offenders.append(path.name)
            if isinstance(node, ast.ImportFrom) and node.module == "cognee":
                offenders.append(path.name)
    assert offenders == []


def test_local_paths_are_set_before_first_cognee_import(tmp_path: Path) -> None:
    fake_package = tmp_path / "fake-package"
    fake_package.mkdir()
    (fake_package / "cognee.py").write_text(
        "import os\n"
        "IMPORT_VALUES = {name: os.environ.get(name) for name in (\n"
        "    'SYSTEM_ROOT_DIRECTORY', 'DATA_ROOT_DIRECTORY',\n"
        "    'CACHE_ROOT_DIRECTORY', 'COGNEE_LOGS_DIR')}\n",
        encoding="utf-8",
    )
    project = tmp_path / "project"
    source = Path(__file__).parents[1] / "src"
    script = (
        "import json, sys\n"
        f"sys.path[:0] = [{str(source)!r}, {str(fake_package)!r}]\n"
        "from pathlib import Path\n"
        "from cognee_retriever.cognee_client import RealCogneeClient\n"
        f"module = RealCogneeClient._module(Path({str(project)!r}))\n"
        "print(json.dumps(module.IMPORT_VALUES))\n"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    values = json.loads(completed.stdout)
    assert all(Path(value).is_absolute() for value in values.values())
    assert all(Path(value).is_relative_to(project / ".local") for value in values.values())
