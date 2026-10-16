import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


def test_keeper_entities_returns_direct_markdown_files_from_synthetic_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "NAVIS_ROOT", str(tmp_path))
    keeper = tmp_path / "Keeper"
    (keeper / "Nested").mkdir(parents=True)
    (keeper / "zeta.md").write_text("zeta fixture", encoding="utf-8")
    (keeper / "Alpha.md").write_text("alpha fixture", encoding="utf-8")
    (keeper / "navis_progression.db").write_bytes(b"synthetic database")
    (keeper / "Nested" / "nested.md").write_text("nested fixture", encoding="utf-8")

    assert main._list_keeper_entities() == [
        {"id": "Keeper/Alpha.md", "name": "Alpha", "type": "file"},
        {"id": "Keeper/zeta.md", "name": "zeta", "type": "file"},
    ]


def test_keeper_entities_distinguishes_empty_source_from_missing_source(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "NAVIS_ROOT", str(tmp_path))
    (tmp_path / "Keeper").mkdir()
    assert main._list_keeper_entities() == []

    (tmp_path / "Keeper").rmdir()
    with pytest.raises(HTTPException) as exc:
        main._list_keeper_entities()
    assert exc.value.status_code == 404


def test_keeper_entities_reports_unavailable_vault_root(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "NAVIS_ROOT", str(tmp_path / "missing-vault"))
    with pytest.raises(HTTPException) as exc:
        main._list_keeper_entities()
    assert exc.value.status_code == 503
