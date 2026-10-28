import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from services.knowledge_notes import selected_sources, save
from services.vault_access import VaultAccessError


def fixture(root):
    source = root / "Documentation/Example.md"
    source.parent.mkdir()
    source.write_text("# Original\nA supported finding. An unresolved choice.", encoding="utf-8")
    loaded = selected_sources(root, ["Documentation/Example.md"])
    return source, {"question": "What next?", "findings": "A supported finding [1].", "uncertainty": "Choice is unresolved.", "application": "Review the choice.", "sources": [{k: s[k] for k in ("path", "sha256")} for s in loaded["sources"]], "destination": "Library/Knowledge Notes", "filename": "example"}


def test_save_destination_provenance_retry_and_no_overwrite(tmp_path):
    source, body = fixture(tmp_path)
    original = source.read_bytes()
    first = save(tmp_path, body)
    note = tmp_path / first["path"]
    content = note.read_bytes()
    assert first["path"] == "Library/Knowledge Notes/example.md"
    assert body["sources"][0]["sha256"] in content.decode()
    assert "../../Documentation/Example.md" in content.decode()
    assert save(tmp_path, body) == first
    body["findings"] = "Different reviewed finding"
    with pytest.raises(ValueError, match="already contains"):
        save(tmp_path, body)
    assert note.read_bytes() == content
    assert source.read_bytes() == original
    assert not (tmp_path / "Bridge").exists()


def test_changed_or_unavailable_source_does_not_save(tmp_path):
    source, body = fixture(tmp_path)
    source.write_text("Changed source")
    with pytest.raises(ValueError, match="changed"):
        save(tmp_path, body)
    source.unlink()
    with pytest.raises(VaultAccessError):
        save(tmp_path, body)
    assert not (tmp_path / "Library").exists()


@pytest.mark.parametrize("destination,filename", [("../Other", "example"), ("Library/Notes", "../escape"), ("Library/Notes", "CON")])
def test_destination_rejection(tmp_path, destination, filename):
    _, body = fixture(tmp_path)
    body.update(destination=destination, filename=filename)
    with pytest.raises(ValueError):
        save(tmp_path, body)
    assert not (tmp_path / "Library").exists()


def test_native_uses_same_selected_source_contract(tmp_path):
    _, body = fixture(tmp_path)
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(backend / "native_knowledge_notes.py")], input=json.dumps({"path": "/api/knowledge-notes/save", "body": body}), text=True, capture_output=True, env={**os.environ, "NAVIS_ROOT": str(tmp_path)})
    response = json.loads(result.stdout)
    assert response["status"] == 200
    assert (tmp_path / response["body"]["path"]).exists()


def test_unselected_and_non_markdown_sources_are_not_loaded(tmp_path):
    fixture(tmp_path)
    unrelated = tmp_path / "Documentation/Other.md"
    unrelated.write_text("Must not appear in selected previews")
    loaded = selected_sources(tmp_path, ["Documentation/Example.md"])
    assert len(loaded["sources"]) == 1
    assert "Must not appear" not in loaded["sources"][0]["content"]
    with pytest.raises(VaultAccessError):
        selected_sources(tmp_path, ["../escape.md"])
    with pytest.raises(VaultAccessError):
        selected_sources(tmp_path, ["Documentation/data.json"])


def test_packaged_note_resources_support_save(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    config = repo / "frontend/src-tauri/tauri.conf.json"
    package = tmp_path / "package"
    for source, destination in json.loads(config.read_text())["bundle"]["resources"].items():
        if destination.startswith("backend/services/") or destination == "backend/native_knowledge_notes.py":
            target = package / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((config.parent / source).read_bytes())
    root = tmp_path / "vault"
    root.mkdir()
    _, body = fixture(root)
    result = subprocess.run([sys.executable, str(package / "backend/native_knowledge_notes.py")], input=json.dumps({"path": "/api/knowledge-notes/save", "body": body}), text=True, capture_output=True, cwd=package, env={**os.environ, "NAVIS_ROOT": str(root)})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == 200


def test_http_sources_and_save_match_native_contract(tmp_path):
    import ast
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    _, body = fixture(tmp_path)
    tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8"))
    endpoint = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "knowledge_note")
    app = FastAPI()
    scope = {"app": app, "HTTPException": HTTPException, "NAVIS_ROOT": str(tmp_path)}
    exec(compile(ast.Module(body=[endpoint], type_ignores=[]), "main.py", "exec"), scope)
    with TestClient(app) as client:
        source = client.post("/api/knowledge-notes/sources", json={"paths": ["Documentation/Example.md"]})
        assert source.status_code == 200
        assert source.json()["sources"][0]["sha256"] == body["sources"][0]["sha256"]
        saved = client.post("/api/knowledge-notes/save", json=body)
        assert saved.status_code == 200 and saved.json()["saved"]
        missing = client.post("/api/knowledge-notes/sources", json={"paths": ["Documentation/Missing.md"]})
        assert missing.status_code == 422
