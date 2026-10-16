import sqlite3
import os

DB_PATH = r"G:\My Drive\Navis-Vault\Lounge\lounge.db"


def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS MediaGenres")
        conn.execute("DROP TABLE IF EXISTS Genres")
        conn.execute("DROP TABLE IF EXISTS MediaItems")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS MediaItems (
                id TEXT PRIMARY KEY,
                type TEXT,
                title TEXT,
                creator TEXT,
                series TEXT,
                overview TEXT,
                release_year INTEGER,
                duration_mins INTEGER,
                rating REAL,
                poster_url TEXT,
                status TEXT,
                source TEXT,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_completed TIMESTAMP
            )
        """)

        # Create indexes for optimal querying performance
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_media_type_date 
            ON MediaItems(type, date_added DESC, date_completed DESC)
        """)

        # Genres many-to-many relationship
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Genres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS MediaGenres (
                media_id TEXT,
                genre_id INTEGER,
                PRIMARY KEY (media_id, genre_id),
                FOREIGN KEY (media_id) REFERENCES MediaItems(id),
                FOREIGN KEY (genre_id) REFERENCES Genres(id)
            )
        """)
        conn.commit()


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
