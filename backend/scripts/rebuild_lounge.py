import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database.lounge_db import init_db

print("Initializing database schema...")
init_db()
print("Database schema initialized. Running sync...")

from scripts.sync_lounge import (
    sync_jellyfin,
    sync_youtube,
    sync_goodreads,
    sync_audiobooks,
    sync_manual_media,
)
from database.lounge_db import get_db_connection

with get_db_connection() as conn:
    sync_jellyfin(conn)
    sync_youtube(conn)
    sync_goodreads(conn)
    sync_audiobooks(conn)
    sync_manual_media(conn)
    conn.commit()
print("Lounge Sync complete!")
