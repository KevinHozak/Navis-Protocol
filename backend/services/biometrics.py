import sqlite3
import os

NAVIS_ROOT = os.getenv("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")
FITBIT_DB_PATH = os.path.join(NAVIS_ROOT, "Keeper", "FitbitChronicle.db")


def get_connection(timeout: float = 5.0):
    conn = sqlite3.connect(FITBIT_DB_PATH, timeout=timeout)
    conn.row_factory = sqlite3.Row
    return conn


def record_vitals_sample(date_str: str, resting_heart_rate: int, timeout: float = 5.0):
    """Write or update daily vitals with configurable SQLite busy timeout."""
    with get_connection(timeout=timeout) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_vitals (
                date TEXT PRIMARY KEY,
                resting_heart_rate INTEGER
            )
            """
        )
        conn.execute(
            """
            INSERT INTO daily_vitals (date, resting_heart_rate)
            VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET resting_heart_rate=excluded.resting_heart_rate
            """,
            (date_str, resting_heart_rate),
        )
        conn.commit()


def adjust_energy_points(date_str: str, delta: int, timeout: float = 5.0) -> int:
    """Adjust energy points for a date with configurable SQLite busy timeout."""
    with get_connection(timeout=timeout) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS energy_logs (
                date TEXT PRIMARY KEY,
                energy_points INTEGER DEFAULT 100
            )
            """
        )
        row = conn.execute("SELECT energy_points FROM energy_logs WHERE date = ?", (date_str,)).fetchone()
        current = row["energy_points"] if row else 100
        new_val = current + delta
        conn.execute(
            """
            INSERT INTO energy_logs (date, energy_points)
            VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET energy_points=excluded.energy_points
            """,
            (date_str, new_val),
        )
        conn.commit()
        return new_val


def get_latest_vitals():
    if not os.path.exists(FITBIT_DB_PATH):
        return None

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM daily_vitals ORDER BY date DESC LIMIT 1"
        ).fetchone()
        if row:
            return dict(row)
        return None


def get_vitals_history(limit=7):
    if not os.path.exists(FITBIT_DB_PATH):
        return []

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_vitals ORDER BY date DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_recent_exercises(limit=5):
    if not os.path.exists(FITBIT_DB_PATH):
        return []

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM exercise_logs ORDER BY date DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
