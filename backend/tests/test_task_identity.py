import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


@pytest.mark.parametrize("collection,route", [("tasks", "recurring"), ("active_tasks", "active")])
def test_task_crud_aliases_identity_and_conflicts(tmp_path, monkeypatch, collection, route):
    monkeypatch.setattr(main, "NAVIS_ROOT", str(tmp_path))
    path = tmp_path / "Bridge" / "ops_state.json"
    path.parent.mkdir()
    initial = {"tasks": [], "active_tasks": [], "unrelated": {"keep": "雪"}}
    initial[collection] = [{"id": "imported", "area": "GAUNTLET", "text": "legacy"}]
    path.write_text(json.dumps(initial), encoding="utf-8-sig")
    read = getattr(main, "get_" + route + "_tasks")
    create = getattr(main, "create_" + route + "_task")
    update = getattr(main, "update_" + route + "_task")
    delete = getattr(main, "delete_" + route + "_task")
    model = main.RecurringTaskCreate if route == "recurring" else main.ActiveTaskCreate
    update_model = main.RecurringTaskUpdate if route == "recurring" else main.ActiveTaskUpdate
    def add(area):
        args = {"area": area, "text": "fixture"}
        if route == "recurring": args["frequency"] = "weekly"
        return asyncio.run(create(model(**args)))["task"]
    first = add(" GaUnTlEt ")
    second = add("OUTLAND")
    rapid = [add("Sanctum") for _ in range(50)]
    assert len({t["id"] for t in [first, second] + rapid}) == 52
    assert all(len(t["id"]) == 36 for t in rapid)
    assert first["area"] == "bureaucratic"
    assert second["area"] == "world"
    for alias in ("GAUNTLET", "bureaucratic", " Bureaucratic "):
        assert {t["id"] for t in asyncio.run(read(alias))} == {"imported", first["id"]}
    assert [t["id"] for t in asyncio.run(read("World"))] == [second["id"]]
    assert len(asyncio.run(read(None))) == 53
    assert len(asyncio.run(read(" "))) == 53
    changed = asyncio.run(update(first["id"], update_model(area="oUtLaNd", text="changed")))["task"]
    assert changed["id"] == first["id"] and changed["area"] == "world"
    asyncio.run(delete(first["id"]))
    assert [t["id"] for t in asyncio.run(read("outland"))] == [second["id"]]
    saved = json.loads(path.read_text(encoding="utf-8-sig"))
    assert saved["unrelated"] == initial["unrelated"]
    saved[collection].extend([{"id": "duplicate"}, {"id": "duplicate"}])
    path.write_text(json.dumps(saved), encoding="utf-8-sig")
    before = path.read_bytes()
    for action in (lambda: update("duplicate", update_model(text="bad")), lambda: delete("duplicate")):
        with pytest.raises(HTTPException) as error: asyncio.run(action())
        assert error.value.status_code == 409
        assert path.read_bytes() == before
    with pytest.raises(HTTPException) as error: asyncio.run(delete("missing"))
    assert error.value.status_code == 404
