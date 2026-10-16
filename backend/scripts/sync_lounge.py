import os
import sys
import json
import csv
import uuid
import urllib.request

# Add the backend root to the python path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Force unbuffered output so logs stream in real-time
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from database.lounge_db import get_db_connection
from services.jellyfin_parser import parse_jellyfin_movies, parse_jellyfin_series

NAVIS_ROOT = os.getenv("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")
LOUNGE_DIR = os.path.join(NAVIS_ROOT, "Lounge")
GOODREADS_CSV = os.path.join(LOUNGE_DIR, "Goodreads_library_export.csv")
YOUTUBE_JSON = os.path.join(LOUNGE_DIR, "youtube.json")
MANUAL_MEDIA_MD = os.path.join(LOUNGE_DIR, "Manual_Media.md")


def get_poster_blob(media):
    media_id = media.get("id")
    if media_id:
        import re

        safe_filename = re.sub(r'[\\/*?:"<>|]', "", f"{media_id}.jpg")
        poster_path = os.path.join(LOUNGE_DIR, "posters", safe_filename)
        if os.path.exists(poster_path):
            return None  # Already downloaded, don't re-fetch

    # Try reading local path first (Jellyfin)
    path = media.get("poster_path")
    if path and os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception:
            pass

    # Try downloading from URL
    url = media.get("poster_url")
    if url and url.startswith("http"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return resp.read()
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")

    return None


def upsert_media(conn, media):
    """
    media dict should have:
    id (str), type (str), title (str), creator (str), overview (str),
    release_year (int), duration_mins (int), rating (float), poster_url (str),
    poster_path (str) optional,
    poster_blob_override (bytes) optional,
    status (str), source (str), date_completed (str),
    series (str) optional, genres (list) optional
    """
    blob = media.get("poster_blob_override")
    if blob is None:
        blob = get_poster_blob(media)

    media_id = media.get("id")
    if blob:
        import re

        safe_filename = re.sub(r'[\\/*?:"<>|]', "", f"{media_id}.jpg")
        posters_dir = os.path.join(LOUNGE_DIR, "posters")
        os.makedirs(posters_dir, exist_ok=True)
        poster_path = os.path.join(posters_dir, safe_filename)
        with open(poster_path, "wb") as f:
            f.write(blob)

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO MediaItems (
            id, type, title, creator, series, overview, release_year, duration_mins, 
            rating, poster_url, status, source, date_completed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            creator=excluded.creator,
            series=excluded.series,
            overview=excluded.overview,
            release_year=excluded.release_year,
            duration_mins=excluded.duration_mins,
            rating=excluded.rating,
            poster_url=excluded.poster_url,
            status=excluded.status,
            date_completed=excluded.date_completed
    """,
        (
            media_id,
            media.get("type"),
            media.get("title"),
            media.get("creator"),
            media.get("series"),
            media.get("overview"),
            media.get("release_year"),
            media.get("duration_mins"),
            media.get("rating"),
            media.get("poster_url"),
            media.get("status"),
            media.get("source"),
            media.get("date_completed"),
        ),
    )

    # Process genres
    genres = media.get("genres", [])
    if genres:
        for g in genres:
            g_clean = g.strip()
            if not g_clean:
                continue
            cursor.execute("INSERT OR IGNORE INTO Genres (name) VALUES (?)", (g_clean,))
            cursor.execute("SELECT id FROM Genres WHERE name = ?", (g_clean,))
            genre_row = cursor.fetchone()
            if genre_row:
                genre_id = genre_row[0]
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO MediaGenres (media_id, genre_id)
                    VALUES (?, ?)
                """,
                    (media_id, genre_id),
                )


def guess_movie_series(title):
    import re

    if not title:
        return ""
    match = re.split(r"[:\-]", title, 1)
    if len(match) > 1 and len(match[0].strip()) > 3:
        return match[0].strip()
    match = re.match(r"^(.*?) \d+$", title)
    if match and len(match.group(1).strip()) > 3:
        return match.group(1).strip()
    return ""


def sync_jellyfin(conn):
    print("Syncing Jellyfin Movies...")
    movies_data = parse_jellyfin_movies()
    for m in movies_data.get("items", []):
        upsert_media(
            conn,
            {
                "id": f"jellyfin_movie_{m['title']}_{m['year']}",
                "type": "Movie",
                "title": m["title"],
                "creator": "",
                "series": guess_movie_series(m["title"]),
                "genres": m.get("genres", []),
                "overview": m["overview"],
                "release_year": m["year"],
                "duration_mins": m.get("duration_mins", 0),
                "rating": m["rating"],
                "poster_url": "",
                "poster_path": m.get("poster_path"),
                "status": "completed",  # Assumes it's in DB, you have it
                "source": "Jellyfin",
                "date_completed": "",
            },
        )

    print("Syncing Jellyfin TV Series...")
    tv_data = parse_jellyfin_series()
    for s in tv_data.get("items", []):
        upsert_media(
            conn,
            {
                "id": f"jellyfin_tv_{s['title']}_{s['year']}",
                "type": "TV Show",
                "title": s["title"],
                "creator": "",
                "series": s["title"],
                "genres": s.get("genres", []),
                "overview": s["overview"],
                "release_year": s["year"],
                "duration_mins": 0,
                "rating": s["rating"],
                "poster_url": "",
                "poster_path": s.get("poster_path"),
                "status": "completed",
                "source": "Jellyfin",
                "date_completed": "",
            },
        )


def sync_youtube(conn):
    print("Syncing YouTube...")
    if not os.path.exists(YOUTUBE_JSON):
        print("No youtube.json found.")
        return
    with open(YOUTUBE_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
        for v in data.get("videos", []):
            upsert_media(
                conn,
                {
                    "id": f"youtube_{v['id']}",
                    "type": "YouTube",
                    "title": v["title"],
                    "creator": v["channel"],
                    "overview": "",
                    "release_year": None,
                    "duration_mins": v.get("duration", 0) // 60,
                    "rating": 0,
                    "poster_url": v.get("thumbnail", ""),
                    "status": "pending",
                    "source": "YouTube",
                    "date_completed": "",
                },
            )


def sync_goodreads(conn):
    print("Syncing Goodreads...")
    if not os.path.exists(GOODREADS_CSV):
        print("No Goodreads CSV found.")
        return

    with open(GOODREADS_CSV, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            isbn13 = row.get("ISBN13", "").replace('="', "").replace('"', "")
            book_id = (
                f"book_{isbn13}"
                if isbn13
                else f"book_title_{row.get('Title', 'Unknown')}"
            )

            shelf = row.get("Exclusive Shelf", "").strip()
            status = (
                "completed"
                if shelf == "read"
                else ("in-progress" if shelf == "currently-reading" else "pending")
            )

            poster_url = (
                f"https://covers.openlibrary.org/b/isbn/{isbn13}-L.jpg"
                if isbn13
                else ""
            )

            upsert_media(
                conn,
                {
                    "id": book_id,
                    "type": "Book",
                    "title": row.get("Title", "Unknown Title"),
                    "creator": row.get("Author", "Unknown Author"),
                    "series": "",  # Goodreads export doesn't clearly split series from title without parsing
                    "genres": [row.get("Exclusive Shelf", "").strip().title()]
                    if row.get("Exclusive Shelf")
                    else [],
                    "overview": row.get("My Review", ""),
                    "release_year": None,
                    "duration_mins": 0,
                    "rating": int(row.get("My Rating", 0))
                    if row.get("My Rating", "").isdigit()
                    else 0,
                    "poster_url": poster_url,
                    "status": status,
                    "source": "Goodreads",
                    "date_completed": row.get("Date Read", ""),
                },
            )


def sync_audiobooks(conn):
    print("Syncing Audiobooks...")
    import sqlite3
    import os
    import hashlib

    try:
        # Pre-flight delete of all Audio entries
        cursor = conn.cursor()
        cursor.execute("DELETE FROM MediaItems WHERE type = 'Audio'")
        conn.commit()

        drive_conn = sqlite3.connect(r"C:\Projects\Agents\Manifests\Drive_Index.db")
        drive_cursor = drive_conn.cursor()
        drive_cursor.execute(r"""
            SELECT m.album, m.artist, m.duration_secs, a.path
            FROM artifacts a 
            INNER JOIN audio_metadata m ON a.id = m.artifact_id 
            WHERE a.path LIKE '%Audiobooks\%'
        """)
        rows = drive_cursor.fetchall()

        import re

        # Group by parent folder or file path if root
        books = {}
        for row in rows:
            row[0]
            m_artist = row[1]
            m_duration = row[2]
            file_path = row[3]

            parent_dir = os.path.dirname(file_path)
            parent_name = os.path.basename(parent_dir)

            # If the file is just loose in the root "Audiobooks" folder, treat it as its own book
            if parent_dir.lower().endswith("audiobooks"):
                group_key = file_path
                folder_name = os.path.splitext(os.path.basename(file_path))[0]
            else:
                # Intelligently detect multi-disc/part folders and step up to the actual book folder
                pattern = (
                    r"(?i)(disc\s*\d+|cd\s*\d+|pt\s*\d+|part\s*\d+|\(\d+\s*of\s*\d+\))"
                )
                if re.search(pattern, parent_name):
                    group_key = os.path.dirname(parent_dir)
                    folder_name = os.path.basename(group_key)
                else:
                    group_key = parent_dir
                    folder_name = parent_name

            if group_key not in books:
                folder_hash = hashlib.md5(group_key.encode("utf-8")).hexdigest()[:8]
                books[group_key] = {
                    "id": f"audio_book_{folder_hash}",
                    "title": folder_name,  # Prefer the folder name since album tags on discs are broken
                    "creator": m_artist if m_artist else "",
                    "duration_secs": 0,
                    "file_path": file_path,
                }

            # Aggregate duration
            if m_duration:
                books[group_key]["duration_secs"] += int(m_duration)

        # Insert aggregated books
        for group_key, book in books.items():
            duration_mins = book["duration_secs"] // 60

            # Extract image (try only first file)
            img_data = None
            try:
                from tinytag import TinyTag

                tag = TinyTag.get(book["file_path"], image=True)
                img_data = tag.get_image()
            except Exception:
                pass

            a_path = book["file_path"] or ""
            genre_part = ""
            if "Audiobooks\\" in a_path:
                parts = a_path.split("Audiobooks\\")
                if len(parts) > 1 and "\\" in parts[1]:
                    genre_part = parts[1].split("\\")[0]

            # Cross-reference with Goodreads for better genres
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT g.name 
                FROM MediaItems m
                JOIN MediaGenres mg ON m.id = mg.media_id
                JOIN Genres g ON mg.genre_id = g.id
                WHERE m.type = 'Book' AND m.title LIKE ?
            """,
                (f"%{book['title']}%",),
            )
            book_genres = [r[0] for r in cursor.fetchall()]

            final_genres = (
                list(set(book_genres))
                if book_genres
                else ([genre_part] if genre_part else [])
            )

            upsert_media(
                conn,
                {
                    "id": book["id"],
                    "type": "Audio",
                    "title": book["title"],
                    "creator": book["creator"],
                    "series": guess_movie_series(book["title"]),
                    "genres": final_genres,
                    "overview": book["file_path"],
                    "release_year": None,
                    "duration_mins": duration_mins,
                    "rating": 0,
                    "poster_url": "",
                    "poster_blob_override": img_data,
                    "status": "completed",
                    "source": "Drive_Index",
                    "date_completed": "",
                },
            )

        drive_conn.close()
    except Exception as e:
        print(f"Error syncing audiobooks: {e}")


def sync_manual_media(conn):
    print("Syncing Manual Media...")
    if not os.path.exists(MANUAL_MEDIA_MD):
        with open(MANUAL_MEDIA_MD, "w", encoding="utf-8") as f:
            f.write("# Manual Media Tracking\n\n")
            f.write(
                "Add your archived or watched movies here in JSON format inside the code block below.\n\n"
            )
            f.write(
                '```json\n[\n  {\n    "id": "manual_movie_1",\n    "type": "Movie",\n    "title": "Example Archived Movie",\n    "creator": "Director Name",\n    "release_year": 1999,\n    "rating": 5.0,\n    "status": "completed"\n  }\n]\n```\n'
            )
        print("Created template Manual_Media.md.")
        return

    try:
        with open(MANUAL_MEDIA_MD, "r", encoding="utf-8") as f:
            content = f.read()
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
                data = json.loads(json_str)
                for item in data:
                    upsert_media(
                        conn,
                        {
                            "id": item.get("id", f"manual_{uuid.uuid4()}"),
                            "type": item.get("type", "Movie"),
                            "title": item.get("title", "Unknown"),
                            "creator": item.get("creator", ""),
                            "series": item.get("series", ""),
                            "genres": item.get("genres", []),
                            "overview": item.get("overview", ""),
                            "release_year": item.get("release_year"),
                            "duration_mins": item.get("duration_mins", 0),
                            "rating": item.get("rating", 0),
                            "poster_url": item.get("poster_url", ""),
                            "status": item.get("status", "completed"),
                            "source": "Manual",
                            "date_completed": item.get("date_completed", ""),
                        },
                    )
    except Exception as e:
        print(f"Error parsing Manual_Media.md: {e}")


def fetch_imdb_poster(title, media_type=None):
    import urllib.request
    import json
    import urllib.parse
    import time

    try:
        term = urllib.parse.quote(title)
        url = f"https://v3.sg.media-imdb.com/suggestion/x/{term}.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        if "d" in data and len(data["d"]) > 0:
            results = data["d"]

            if media_type:
                valid_qids = []
                if media_type == "Movie":
                    valid_qids = ["movie"]
                elif media_type == "TV Show":
                    valid_qids = ["tvSeries", "tvMiniSeries", "tvSpecial"]
                elif media_type == "Game":
                    valid_qids = ["videoGame"]

                for r in results:
                    if r.get("qid") in valid_qids and "i" in r:
                        return r["i"]["imageUrl"]

                return ""

            for r in results:
                if "i" in r and "imageUrl" in r["i"]:
                    return r["i"]["imageUrl"]

    except Exception as e:
        print(f"Failed to fetch poster for {title}: {e}")
    time.sleep(0.5)
    return ""


def sync_archive_movies(conn):
    print("Syncing Archive Movies...")
    import sqlite3
    import os
    import re
    import hashlib

    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM MediaItems WHERE type = 'Movie' AND source = 'Disk'"
        )
        conn.commit()

        drive_conn = sqlite3.connect(r"C:\Projects\Agents\Manifests\Drive_Index.db")
        drive_cursor = drive_conn.cursor()
        drive_cursor.execute("""
            SELECT a.path FROM artifacts a 
            WHERE a.path LIKE 'D:\\Archive\\Movies\\%' 
            AND (a.path LIKE '%.mp4' OR a.path LIKE '%.mkv' OR a.path LIKE '%.avi')
        """)
        rows = drive_cursor.fetchall()

        for row in rows:
            file_path = row[0]
            filename = os.path.basename(file_path)

            match = re.match(r"^(.*?)\s*\((\d{4})\)", filename)
            if match:
                title = match.group(1).strip()
                year = int(match.group(2))
            else:
                title = os.path.splitext(filename)[0]
                year = None

            folder_hash = hashlib.md5(file_path.encode("utf-8")).hexdigest()[:8]

            poster_url = fetch_imdb_poster(title, "Movie")

            upsert_media(
                conn,
                {
                    "id": f"archive_movie_{folder_hash}",
                    "type": "Movie",
                    "title": title,
                    "creator": "",
                    "series": guess_movie_series(title),
                    "genres": [],
                    "overview": "",
                    "release_year": year,
                    "duration_mins": 0,
                    "rating": 0,
                    "poster_url": poster_url,
                    "status": "completed",
                    "source": "Disk",
                    "date_completed": "",
                },
            )

        drive_conn.close()
    except Exception as e:
        print(f"Error syncing archive movies: {e}")


def sync_archive_shows(conn):
    print("Syncing Archive Shows...")
    import sqlite3
    import os
    import hashlib

    try:
        # Pre-flight delete of all Disk-sourced TV Shows
        cursor = conn.cursor()
        cursor.execute("DELETE FROM MediaItems WHERE type = 'TV' AND source = 'Disk'")
        conn.commit()

        drive_conn = sqlite3.connect(r"C:\Projects\Agents\Manifests\Drive_Index.db")
        drive_cursor = drive_conn.cursor()
        drive_cursor.execute("""
            SELECT a.path FROM artifacts a 
            WHERE a.path LIKE 'D:\\Archive\\Shows\\%' 
            AND (a.path LIKE '%.mp4' OR a.path LIKE '%.mkv' OR a.path LIKE '%.avi' OR a.path LIKE '%.m4v')
        """)
        rows = drive_cursor.fetchall()

        shows = {}
        for row in rows:
            file_path = row[0]
            # Extract the show name which is the folder immediately inside D:\Archive\Shows\
            parts = file_path.split(os.sep)
            try:
                shows_idx = parts.index("Shows")
                show_name = parts[shows_idx + 1]
            except ValueError:
                show_name = "Unknown Show"

            if show_name not in shows:
                shows[show_name] = file_path

        for show_name, file_path in shows.items():
            folder_hash = hashlib.md5(show_name.encode("utf-8")).hexdigest()[:8]

            poster_url = fetch_imdb_poster(show_name, "TV Show")

            upsert_media(
                conn,
                {
                    "id": f"archive_show_{folder_hash}",
                    "type": "TV Show",
                    "title": show_name,
                    "creator": "",
                    "overview": "",
                    "release_year": None,
                    "duration_mins": 0,
                    "rating": 0,
                    "poster_url": poster_url,
                    "status": "completed",
                    "source": "Disk",
                    "date_completed": "",
                },
            )

        drive_conn.close()
    except Exception as e:
        print(f"Error syncing archive shows: {e}")


def sync_archive_games(conn):
    print("Syncing Archive Games...")
    import sqlite3
    import os
    import re
    import hashlib

    try:
        # Pre-flight delete of all Disk-sourced Games
        cursor = conn.cursor()
        cursor.execute("DELETE FROM MediaItems WHERE type = 'Game' AND source = 'Disk'")
        conn.commit()

        drive_conn = sqlite3.connect(r"C:\Projects\Agents\Manifests\Drive_Index.db")
        drive_cursor = drive_conn.cursor()
        drive_cursor.execute("""
            SELECT a.path FROM artifacts a 
            WHERE a.path LIKE 'D:\\Games\\%' 
            AND (a.path LIKE '%.zip' OR a.path LIKE '%.rar' OR a.path LIKE '%.iso' OR a.path LIKE '%.7z')
        """)
        rows = drive_cursor.fetchall()

        for row in rows:
            file_path = row[0]
            filename = os.path.basename(file_path)

            # Strip extension and " Data" from name
            title = os.path.splitext(filename)[0].strip()
            title = re.sub(r"(?i)\s+data$", "", title).strip()

            folder_hash = hashlib.md5(file_path.encode("utf-8")).hexdigest()[:8]

            poster_url = fetch_imdb_poster(title, "Game")

            upsert_media(
                conn,
                {
                    "id": f"archive_game_{folder_hash}",
                    "type": "Game",
                    "title": title,
                    "creator": "",
                    "series": guess_movie_series(title),
                    "genres": [],
                    "overview": "",
                    "release_year": None,
                    "duration_mins": 0,
                    "rating": 0,
                    "poster_url": poster_url,
                    "status": "completed",
                    "source": "Disk",
                    "date_completed": "",
                },
            )

        drive_conn.close()
    except Exception as e:
        print(f"Error syncing archive games: {e}")


def sync_gog_galaxy(conn):
    print("Syncing GOG Galaxy...")
    import sqlite3
    import os
    import json
    import hashlib

    gog_db_path = r"C:\ProgramData\GOG.com\Galaxy\storage\galaxy-2.0.db"
    if not os.path.exists(gog_db_path):
        print(f"GOG Galaxy database not found at {gog_db_path}")
        return

    try:
        # Pre-flight delete of all Platform-sourced Games
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM MediaItems WHERE type = 'Game' AND source != 'Disk'"
        )
        conn.commit()

        galaxy_conn = sqlite3.connect(gog_db_path)
        g_cursor = galaxy_conn.cursor()

        # Get owned releaseKeys
        g_cursor.execute("SELECT releaseKey FROM LibraryReleases")
        owned_keys = {row[0] for row in g_cursor.fetchall()}

        # Get all DLCs to exclude them
        g_cursor.execute("SELECT value FROM GamePieces WHERE gamePieceTypeId = 10")
        dlc_keys = set()
        for row in g_cursor.fetchall():
            data = json.loads(row[0])
            if data.get("dlcs"):
                dlc_keys.update(data["dlcs"])

        # Get titles
        g_cursor.execute(
            "SELECT releaseKey, value FROM GamePieces WHERE gamePieceTypeId = 47"
        )

        for row in g_cursor.fetchall():
            key = row[0]
            if key in owned_keys and key not in dlc_keys:
                title = json.loads(row[1]).get("title", "")
                if not title:
                    continue

                platform = key.split("_")[0]
                # Format platform nicely
                platform_map = {
                    "steam": "Steam",
                    "gog": "GOG",
                    "epic": "Epic Games",
                    "battlenet": "Battle.net",
                    "xboxone": "Xbox",
                    "uplay": "Ubisoft",
                    "origin": "EA",
                }
                source = platform_map.get(platform.lower(), platform.capitalize())

                folder_hash = hashlib.md5(key.encode("utf-8")).hexdigest()[:8]
                poster_url = fetch_imdb_poster(title, "Game")

                upsert_media(
                    conn,
                    {
                        "id": f"platform_game_{folder_hash}",
                        "type": "Game",
                        "title": title,
                        "creator": "",
                        "overview": "",
                        "release_year": None,
                        "duration_mins": 0,
                        "rating": 0,
                        "poster_url": poster_url,
                        "status": "completed",
                        "source": source,
                        "date_completed": "",
                    },
                )

        galaxy_conn.close()
    except Exception as e:
        print(f"Error syncing GOG Galaxy: {e}")


if __name__ == "__main__":
    db_path = r"G:\My Drive\Navis-Vault\Lounge\lounge.db"
    with get_db_connection() as conn:
        sync_jellyfin(conn)
        conn.commit()
        sync_youtube(conn)
        conn.commit()
        sync_goodreads(conn)
        conn.commit()
        sync_audiobooks(conn)
        conn.commit()
        sync_archive_movies(conn)
        conn.commit()
        sync_archive_shows(conn)
        conn.commit()
        sync_archive_games(conn)
        conn.commit()
        sync_gog_galaxy(conn)
        conn.commit()
        sync_manual_media(conn)
        conn.commit()
    print("Lounge Sync complete!")
