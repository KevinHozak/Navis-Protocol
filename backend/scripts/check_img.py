import sqlite3
import shutil
import tempfile
import os

fd, temp_path = tempfile.mkstemp()
os.close(fd)
shutil.copy2(r"C:\ProgramData\Jellyfin\Server\data\library.db", temp_path)
conn = sqlite3.connect(temp_path)
print(
    list(
        conn.execute(
            "SELECT Images FROM TypedBaseItems WHERE type = 'MediaBrowser.Controller.Entities.Movies.Movie' AND Images IS NOT NULL LIMIT 1"
        )
    )
)
conn.close()
os.unlink(temp_path)
