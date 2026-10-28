import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from services.actionable_brief import FIELDS, generate, save


def body():
    return {"original": "Need release but build pending; QA needs exact version.",
            "brief": {field: "Reviewed " + field for field in FIELDS}, "date": "2026-10-28", "section": "front"}


def test_save_preserves_original_and_retries_without_journal_side_effect(tmp_path):
    journal = tmp_path / "Journal/2026/10/2026-10-28.md"
    journal.parent.mkdir(parents=True)
    journal.write_text("- [ ] Existing task", encoding="utf-8")
    first = save(tmp_path, body())
    raw = (tmp_path / first["path"]).read_bytes()
    assert save(tmp_path, body()) == first
    assert (tmp_path / first["path"]).read_bytes() == raw
    record = json.loads(raw)
    assert record["original"] == body()["original"]
    assert record["brief"] == body()["brief"]
    assert record["source_kind"] == "unsaved composer draft"
    assert journal.read_text() == "- [ ] Existing task"
    assert len(list((tmp_path / "Library/Actionable Briefs").iterdir())) == 1


def test_invalid_save_writes_nothing(tmp_path):
    invalid = body(); invalid["brief"] = {"Goal": "incomplete"}
    with pytest.raises(ValueError):
        save(tmp_path, invalid)
    assert not list(tmp_path.iterdir())


def test_unavailable_model_does_not_write(tmp_path):
    with patch("services.actionable_brief.urlopen", side_effect=OSError("offline")):
        with pytest.raises(OSError):
            generate(body())
    assert not list(tmp_path.iterdir())


def test_native_save_uses_same_service(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    request = {"path": "/api/journal/brief/save", "body": body()}
    result = subprocess.run([sys.executable, str(backend / "native_actionable_brief.py")],
                            input=json.dumps(request), text=True, capture_output=True,
                            env={**os.environ, "NAVIS_ROOT": str(tmp_path)})
    response = json.loads(result.stdout)
    assert response["status"] == 200
    assert json.loads((tmp_path / response["body"]["path"]).read_text())["original"] == body()["original"]


def test_http_save_matches_native_contract(tmp_path):
    import ast
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    # Mount the actual endpoint without importing unrelated app startup integrations.
    tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8"))
    endpoint = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "actionable_brief")
    app = FastAPI()
    scope = {"app": app, "HTTPException": HTTPException, "NAVIS_ROOT": str(tmp_path)}
    exec(compile(ast.Module(body=[endpoint], type_ignores=[]), "main.py", "exec"), scope)
    with TestClient(app) as client:
        response = client.post("/api/journal/brief/save", json=body())
        assert response.status_code == 200
        result = response.json()
        assert json.loads((tmp_path / result["path"]).read_text())["brief"] == body()["brief"]
        invalid = client.post("/api/journal/brief/save", json={})
        assert invalid.status_code == 422


def test_generation_validates_local_response():
    from unittest.mock import MagicMock
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps({"response": json.dumps({field: 1 for field in FIELDS})}).encode()
    with patch("services.actionable_brief.urlopen", return_value=response) as transport:
        assert generate(body())["brief"]["Goal"] == "Source intention: Need release but build pending;"
        assert transport.call_args.args[0].full_url == "http://127.0.0.1:11434/api/generate"
    response.__enter__.return_value.read.return_value = b'{"response":"{}"}'
    with patch("services.actionable_brief.urlopen", return_value=response):
        with pytest.raises(ValueError):
            generate(body())


def test_generation_refuses_unsupported_assumptions():
    from unittest.mock import MagicMock
    response = MagicMock()
    candidate = {field: body()["original"] for field in FIELDS}
    candidate["One suggested next action"] = "Conduct a meeting with the team."
    response.__enter__.return_value.read.return_value = json.dumps({"response": json.dumps(candidate)}).encode()
    with patch("services.actionable_brief.urlopen", return_value=response):
        with pytest.raises(ValueError, match="outside your note"):
            generate(body())


def test_packaged_resources_include_brief_authority(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    config_path = repo / "frontend/src-tauri/tauri.conf.json"
    resources = json.loads(config_path.read_text())["bundle"]["resources"]
    package = tmp_path / "app"
    for source, destination in resources.items():
        if destination.startswith("backend/services/") or destination == "backend/native_actionable_brief.py":
            target = package / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((config_path.parent / source).read_bytes())
    request = {"path": "/api/journal/brief/save", "body": body()}
    result = subprocess.run([sys.executable, str(package / "backend/native_actionable_brief.py")],
                            input=json.dumps(request), text=True, capture_output=True,
                            cwd=package, env={**os.environ, "NAVIS_ROOT": str(tmp_path / "vault")})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == 200
