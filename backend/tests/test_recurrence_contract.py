import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from services import recurrence, sync_engine

FIXTURE = json.loads((Path(__file__).resolve().parents[2] / "tests/recurrence-contract.json").read_text())


@pytest.mark.parametrize("row", FIXTURE["intervals"])
def test_interval_parity(row):
    for calculate in (recurrence.calculate_next_due, main.calculate_next_due, sync_engine.calculate_next_due):
        assert calculate(row["frequency"], row["last_done"]) == row["next_due"]


@pytest.mark.parametrize("row", FIXTURE["instants"])
def test_local_day(row):
    assert recurrence.journal_day(datetime.fromisoformat(row["local"])) == row["day"]


@pytest.mark.parametrize("row", FIXTURE["intervals"])
def test_all_aliases_through_web_crud(tmp_path, monkeypatch, row):
    monkeypatch.setattr(main, "NAVIS_ROOT", str(tmp_path))
    (tmp_path / "Bridge").mkdir()
    task = asyncio.run(main.create_recurring_task(main.RecurringTaskCreate(
        text="fixture", area="World", frequency=row["frequency"], next_due=row["last_done"]
    )))["task"]
    assert task["last_done"] is None
    for _ in range(2):
        saved = asyncio.run(main.update_recurring_task(task["id"], main.RecurringTaskUpdate(last_done=row["last_done"])))["task"]
        assert saved["next_due"] == row["next_due"]


def test_crud_schedule_persistence(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "NAVIS_ROOT", str(tmp_path))
    monkeypatch.setattr(main, "journal_day", lambda: "2026-10-01")
    path = tmp_path / "Bridge/ops_state.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"tasks": [], "keep": "雪"}), encoding="utf-8-sig")
    task = asyncio.run(main.create_recurring_task(main.RecurringTaskCreate(text="fixture", area="Outland", frequency="monthly")))["task"]
    assert task["last_done"] is None and task["next_due"] == "2026-10-01"
    for _ in range(2):
        result = asyncio.run(main.update_recurring_task(task["id"], main.RecurringTaskUpdate(last_done="2024-01-31", next_due="2099-01-01")))
        assert result["task"]["next_due"] == "2024-02-29"
        assert json.loads(path.read_text(encoding="utf-8-sig"))["tasks"][0]["next_due"] == "2024-02-29"
    result = asyncio.run(main.update_recurring_task(task["id"], main.RecurringTaskUpdate(frequency="every 2 months")))
    assert result["task"]["next_due"] == "2024-03-31"
    before = path.read_bytes()
    for updates in ({"last_done": "2026-02-30"}, {"frequency": "unknown"}, {"next_due": "bad"}):
        with pytest.raises(HTTPException) as error:
            asyncio.run(main.update_recurring_task(task["id"], main.RecurringTaskUpdate(**updates)))
        assert error.value.status_code == 422
        assert path.read_bytes() == before
    assert json.loads(path.read_text(encoding="utf-8-sig"))["keep"] == "雪"
    task = asyncio.run(main.create_recurring_task(main.RecurringTaskCreate(text="fixture", area="World", frequency="weekly", next_due="2026-10-02")))["task"]
    assert task["last_done"] is None and task["next_due"] == "2026-10-02"


def test_sweep_uses_journal_date_and_is_repeatable(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_engine, "NAVIS_ROOT", str(tmp_path))
    bridge = tmp_path / "Bridge"
    bridge.mkdir()
    operations = tmp_path / "Operations"
    operations.mkdir()
    journal = tmp_path / "Journal/2024/01/2024-01-31.md"
    journal.parent.mkdir(parents=True)
    content = "## 🥾 The Kinetic Outland\n- [x] fixture mandate\n"
    journal.write_text(content, encoding="utf-8-sig")
    settings = bridge / "settings.json"
    settings.write_text(json.dumps({"paths": {"operations_dir": str(operations), "journal_root": str(tmp_path / "Journal")}}))
    monkeypatch.setattr(sync_engine, "SETTINGS_FILE", str(settings))
    (bridge / "status.json").write_text('{"last_updated":"2024-01-31"}')
    state = bridge / "ops_state.json"
    state.write_text(json.dumps({"tasks": [{"id":"fixture", "text":"fixture mandate", "frequency":"monthly", "last_done":None, "next_due":"2024-01-31"}], "keep":"雪"}), encoding="utf-8-sig")
    for _ in range(2):
        sync_engine.sync_active_tasks()
        saved = json.loads(state.read_text(encoding="utf-8-sig"))
        assert saved["tasks"][0]["last_done"] == "2024-01-31"
        assert saved["tasks"][0]["next_due"] == "2024-02-29"
        assert saved["keep"] == "雪"
        assert journal.read_text(encoding="utf-8-sig") == content
