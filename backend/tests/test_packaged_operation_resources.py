"""Exercise actual resource files without checkout module fallback."""
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from test_native_operations import fixture_root, fixture_vault  # noqa: F401 -- shared isolated fixtures


REPO = Path(__file__).resolve().parents[2]


def test_resource_import_closure_and_isolated_fixture_sync(fixture_vault, tmp_path):  # noqa: F811 -- pytest fixture injection
    config = json.loads((REPO / "frontend/src-tauri/tauri.conf.json").read_text())
    included = set()
    bundle = tmp_path / "standalone"
    for source, target in config["bundle"]["resources"].items():
        path = (REPO / "frontend/src-tauri" / source).resolve()
        included.add(path)
        destination = bundle / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    backend = REPO / "backend"
    pending = [backend / "native_operations.py", backend / "native_operation_status.py"]
    visited = set()
    while pending:
        path = pending.pop().resolve()
        if path in visited:
            continue
        visited.add(path)
        assert path in included, f"Required local module missing from bundle: {path.name}"
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            names = ([node.module] if isinstance(node, ast.ImportFrom) and node.module
                     else [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
            for name in names:
                local = backend.joinpath(*name.split(".")).with_suffix(".py")
                if local.is_file():
                    pending.append(local)
    vault, _, git = fixture_vault
    env = os.environ.copy()
    env.update(NAVIS_ROOT=str(vault), NAVIS_NATIVE_FIXTURE_MODE="1", NAVIS_FIXTURE_GIT_DIR=str(git),
               PYTHONPATH=str(bundle / "backend"), PYTHONIOENCODING="utf-8", NAVIS_OPERATION_ID="packaged")
    process = subprocess.run([sys.executable, str(bundle / "backend/native_operations.py"), "sync"],
                             cwd=bundle, env=env, capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert process.returncode == 0, process.stdout + process.stderr
    assert "FIXTURE MODE: Jellyfin watch history integration disabled" in process.stdout
    result = json.loads((vault / "Bridge/.navis_operations/packaged.json").read_text(encoding="utf-8-sig"))
    assert result["status"] == "completed"
