import asyncio
import json
import pytest
from pydantic import ValidationError
import main
from services.recurrence import calculate_next_due

@pytest.mark.parametrize("freq,start,expected", [
("every 3 days","2024-02-28","2024-03-02"),
("every 4 weeks","2024-12-20","2025-01-17"),
("every 2 months","2024-12-31","2025-02-28"),
("every 1 month","2024-01-31","2024-02-29"),
("yearly","2024-02-29","2025-02-28"),
("quarterly","2024-11-30","2025-02-28"),
(" EVERY 3 DAYS ","2024-02-28","2024-03-02")])
def test_intervals(freq,start,expected):
    assert calculate_next_due(freq,start) == expected

@pytest.mark.parametrize("freq", ["every 0 days","every -1 weeks","every 1.5 months","every days","unknown","every 99999999999999 days","every 99999999999999 months"])
def test_invalid_intervals(freq):
    with pytest.raises(ValueError):
        calculate_next_due(freq,"2024-01-31")

MODELS=[main.ActiveTaskCreate,main.ActiveTaskUpdate,main.RecurringTaskCreate,main.RecurringTaskUpdate]
def payload(model):
    return {"text":"legacy","area":"World",**({"frequency":"weekly"} if model is main.RecurringTaskCreate else {})}

@pytest.mark.parametrize("model",MODELS)
def test_legacy_defaults(model):
    task=model(**payload(model))
    assert task.description == "" and task.priority == 4 and task.labels == []
    task.labels.append("local")
    assert model(**payload(model)).labels == []

@pytest.mark.parametrize("model",MODELS)
@pytest.mark.parametrize("extra",[{"priority":0},{"priority":5},{"priority":True},{"priority":"1"},{"labels":"home"},{"labels":[3]},{"due_date":"2024-02-30"},{"due_date":"20240229"},{"description":None}])
def test_invalid_metadata(model,extra):
    with pytest.raises(ValidationError):
        model(**payload(model),**extra)

@pytest.mark.parametrize("recurring",[False,True])
def test_crud_preserves_state(tmp_path,monkeypatch,recurring):
    monkeypatch.setattr(main,"NAVIS_ROOT",str(tmp_path))
    path=tmp_path / "Bridge/ops_state.json"
    path.parent.mkdir()
    legacy={"tasks":[{"id":"r","text":"legacy","frequency":"weekly","area":"World","last_done":None,"next_due":"2024-01-01","custom":"keep"}],"active_tasks":[{"id":"a","text":"legacy","area":"World","status":"pending","custom":"keep"}],"unknown":{"unicode":"雪"}}
    path.write_text(json.dumps(legacy),encoding="utf-8-sig")
    cm=main.RecurringTaskCreate if recurring else main.ActiveTaskCreate
    um=main.RecurringTaskUpdate if recurring else main.ActiveTaskUpdate
    create=main.create_recurring_task if recurring else main.create_active_task
    update=main.update_recurring_task if recurring else main.update_active_task
    task=asyncio.run(create(cm(**payload(cm),description="**Notes**\nDetails",labels=["home"],priority=2,due_date="2024-01-31")))["task"]
    assert task["due_date"] == "2024-01-31" and task["priority"] == 2
    task=asyncio.run(update(task["id"],um(text="renamed")))["task"]
    assert task["description"] == "**Notes**\nDetails" and task["labels"] == ["home"] and task["priority"] == 2
    task=asyncio.run(update(task["id"],um(description="",labels=[],priority=4,due_date="2024-03-01")))["task"]
    assert task["description"] == "" and task["labels"] == [] and task["due_date"] == "2024-03-01"
    if recurring:
        task=asyncio.run(update(task["id"],um(last_done="2024-03-01")))["task"]
        assert task["due_date"] == task["next_due"] == "2024-03-08"
        assert asyncio.run(main.get_recurring_tasks())[-1]["due_date"] == "2024-03-08"
    else:
        assert asyncio.run(update(task["id"],um(due_date=None)))["task"]["due_date"] is None
    saved=json.loads(path.read_text(encoding="utf-8-sig"))
    assert saved["tasks"][0] == legacy["tasks"][0]
    assert saved["active_tasks"][0] == legacy["active_tasks"][0]
    assert saved["unknown"] == legacy["unknown"]
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")

def test_conflicting_dates():
    with pytest.raises(ValidationError):
        main.RecurringTaskCreate(text="x",area="World",frequency="weekly",due_date="2024-01-01",next_due="2024-01-02")
    with pytest.raises(ValidationError):
        main.RecurringTaskUpdate(due_date=None)

def test_directives_navigation():
    cmd_sectors = [s["id"] for s in main.SECTOR_MAP.get("COMMAND", [])]
    assert "DIRECTIVES" in cmd_sectors
    entities = asyncio.run(main.get_entities("DIRECTIVES"))
    assert any(e.get("id") == "TASKS_COCKPIT" for e in entities)
    tasks_entities = asyncio.run(main.get_entities("TASKS"))
    assert any(e.get("id") == "TASKS_COCKPIT" for e in tasks_entities)

