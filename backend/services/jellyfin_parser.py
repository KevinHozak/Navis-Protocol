import os
import sqlite3
import shutil
import tempfile
from contextlib import contextmanager

JELLYFIN_DB = r"C:\ProgramData\Jellyfin\Server\data\library.db"


def extract_poster_path(images_str):
    if not images_str:
        return ""
    for img_info in images_str.split("|"):
        parts = img_info.split("*")
        if len(parts) >= 3 and parts[2] == "Primary":
            # Jellyfin stores paths with forward slashes or backslashes, handle accordingly
            path = parts[0].replace(
                "%MetadataPath%", r"C:\ProgramData\Jellyfin\Server\metadata"
            )
            return path
    return ""


@contextmanager
def get_jellyfin_db():
    if not os.path.exists(JELLYFIN_DB):
        raise FileNotFoundError(f"Jellyfin database not found at {JELLYFIN_DB}")

    # Copy to temp file to avoid "database is locked" errors while Jellyfin is running
    fd, temp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        shutil.copy2(JELLYFIN_DB, temp_path)
        conn = sqlite3.connect(temp_path)
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()
        try:
            os.unlink(temp_path)
        except Exception:
            pass


def parse_jellyfin_movies():
    movies = []
    try:
        with get_jellyfin_db() as conn:
            cursor = conn.execute("""
                SELECT Name, Overview, ProductionYear, Genres, RunTimeTicks, CommunityRating, Images
                FROM TypedBaseItems 
                WHERE type = 'MediaBrowser.Controller.Entities.Movies.Movie'
                ORDER BY DateCreated DESC
            """)
            for row in cursor:
                # RunTimeTicks is 10,000,000 ticks per second
                runtime_seconds = (
                    row["RunTimeTicks"] // 10_000_000 if row["RunTimeTicks"] else 0
                )
                runtime_mins = runtime_seconds // 60

                movies.append(
                    {
                        "title": row["Name"],
                        "overview": row["Overview"] or "",
                        "year": row["ProductionYear"],
                        "genres": row["Genres"].split("|") if row["Genres"] else [],
                        "duration_mins": runtime_mins,
                        "rating": row["CommunityRating"],
                        "poster_path": extract_poster_path(row["Images"]),
                    }
                )
    except Exception as e:
        print(f"Error parsing Jellyfin movies: {e}")
    return {"total": len(movies), "items": movies}


def parse_jellyfin_series():
    series = []
    try:
        with get_jellyfin_db() as conn:
            cursor = conn.execute("""
                SELECT Name, Overview, ProductionYear, Genres, RunTimeTicks, CommunityRating, Images
                FROM TypedBaseItems 
                WHERE type = 'MediaBrowser.Controller.Entities.TV.Series'
                ORDER BY DateCreated DESC
            """)
            for row in cursor:
                series.append(
                    {
                        "title": row["Name"],
                        "overview": row["Overview"] or "",
                        "year": row["ProductionYear"],
                        "genres": row["Genres"].split("|") if row["Genres"] else [],
                        "rating": row["CommunityRating"],
                        "poster_path": extract_poster_path(row["Images"]),
                    }
                )
    except Exception as e:
        print(f"Error parsing Jellyfin series: {e}")
    return {"total": len(series), "items": series}
