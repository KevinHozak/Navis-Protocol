import sqlite3

import pytest
from fastapi.testclient import TestClient

import main
from services import biometrics


@pytest.fixture
def vitals_db(tmp_path, monkeypatch):
    path = tmp_path / "FitbitChronicle.db"
    monkeypatch.setattr(biometrics, "FITBIT_DB_PATH", str(path))
    return path


def populate(path):
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE daily_vitals (date TEXT PRIMARY KEY, resting_heart_rate INTEGER);
            CREATE TABLE exercise_logs (date TEXT, activity TEXT);
            INSERT INTO daily_vitals VALUES ('2026-09-28', 65), ('2026-09-30', 61), ('2026-09-29', 63);
            INSERT INTO exercise_logs VALUES ('2026-09-28', 'Walk'), ('2026-09-30', 'Cycle');
        """)


def test_absent_database_is_not_created(vitals_db):
    assert biometrics.get_latest_vitals() is None
    assert biometrics.get_vitals_history() == []
    assert biometrics.get_recent_exercises() == []
    assert not vitals_db.exists()


@pytest.mark.parametrize("limit,count", [(0, 0), (1, 1), (3, 3), (20, 3)])
def test_history_orders_newest_first_and_respects_limit(vitals_db, limit, count):
    populate(vitals_db)
    before = vitals_db.read_bytes()
    rows = biometrics.get_vitals_history(limit)
    assert rows == [{"date": day, "resting_heart_rate": rate} for day, rate in
                    [("2026-09-30", 61), ("2026-09-29", 63), ("2026-09-28", 65)][:count]]
    assert biometrics.get_latest_vitals() == {"date": "2026-09-30", "resting_heart_rate": 61}
    assert biometrics.get_recent_exercises(1) == [{"date": "2026-09-30", "activity": "Cycle"}]
    assert vitals_db.read_bytes() == before


def test_empty_tables_return_empty_values(vitals_db):
    populate(vitals_db)
    with sqlite3.connect(vitals_db) as conn:
        conn.execute("DELETE FROM daily_vitals")
        conn.execute("DELETE FROM exercise_logs")
    assert biometrics.get_latest_vitals() is None
    assert biometrics.get_vitals_history() == []
    assert biometrics.get_recent_exercises() == []


def test_http_history_success_and_database_failure(vitals_db):
    # No context manager: startup daemon and background jobs must not run.
    client = TestClient(main.app)
    populate(vitals_db)
    response = client.get("/api/v1/biometrics/vitals/history?limit=1")
    assert response.status_code == 200
    assert response.json() == [{"date": "2026-09-30", "resting_heart_rate": 61}]
    with sqlite3.connect(vitals_db) as conn:
        conn.execute("DROP TABLE daily_vitals")
    before = vitals_db.read_bytes()
    response = client.get("/api/v1/biometrics/vitals/history")
    assert response.status_code == 500
    assert "daily_vitals" in response.json()["detail"]
    assert vitals_db.read_bytes() == before


def test_biometrics_concurrent_writes_and_busy_timeout(vitals_db):
    """Test SQLite busy timeouts when background daemon writes while frontend adjusts energy points."""
    import threading
    import time

    populate(vitals_db)

    # 1. Test busy timeout error when another thread holds an exclusive lock beyond the timeout threshold
    lock_held = threading.Event()
    release_lock = threading.Event()
    worker_error = None

    def holding_worker():
        nonlocal worker_error
        try:
            conn = sqlite3.connect(vitals_db, timeout=5.0)
            conn.execute("BEGIN EXCLUSIVE")
            conn.execute("INSERT OR REPLACE INTO daily_vitals VALUES ('2026-10-01', 58)")
            lock_held.set()
            release_lock.wait(timeout=3.0)
            conn.commit()
            conn.close()
        except Exception as e:
            worker_error = e

    holder = threading.Thread(target=holding_worker)
    holder.start()
    assert lock_held.wait(timeout=2.0)

    # Frontend attempts to adjust energy with tiny timeout (0.05s) while daemon holds lock
    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        biometrics.adjust_energy_points("2026-10-01", 15, timeout=0.05)

    release_lock.set()
    holder.join(timeout=2.0)
    assert worker_error is None

    # Verify daemon's write succeeded
    with sqlite3.connect(vitals_db) as conn:
        row = conn.execute("SELECT resting_heart_rate FROM daily_vitals WHERE date = '2026-10-01'").fetchone()
        assert row[0] == 58

    # 2. Test concurrent successful write coordination when sufficient timeout is provided
    results = []

    def daemon_write():
        time.sleep(0.02)
        biometrics.record_vitals_sample("2026-10-02", 60, timeout=5.0)
        results.append("daemon_ok")

    def frontend_write():
        time.sleep(0.01)
        val = biometrics.adjust_energy_points("2026-10-02", 25, timeout=5.0)
        results.append(f"frontend_{val}")

    t1 = threading.Thread(target=daemon_write)
    t2 = threading.Thread(target=frontend_write)
    t1.start()
    t2.start()
    t1.join(timeout=3.0)
    t2.join(timeout=3.0)

    assert "daemon_ok" in results
    assert "frontend_125" in results

    # Verify both records committed cleanly
    with sqlite3.connect(vitals_db) as conn:
        conn.row_factory = sqlite3.Row
        vital = conn.execute("SELECT * FROM daily_vitals WHERE date = '2026-10-02'").fetchone()
        assert vital["resting_heart_rate"] == 60
        energy = conn.execute("SELECT * FROM energy_logs WHERE date = '2026-10-02'").fetchone()
        assert energy["energy_points"] == 125

