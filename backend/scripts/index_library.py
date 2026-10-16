import os
import sqlite3
import uuid

NAVIS_ROOT = os.getenv("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")
LIB_DIR = os.path.join(NAVIS_ROOT, "Library")
DB_PATH = os.path.join(LIB_DIR, "Library_Intelligence.db")


def init_db(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS library_vectors (
            id TEXT PRIMARY KEY,
            category TEXT,
            file_path TEXT,
            last_modified REAL,
            chunk_index INTEGER,
            chunk_text TEXT,
            vector_json TEXT
        )
    """)
    conn.commit()


def index_library():
    print("Indexing library...")
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    cur = conn.cursor()

    # Clear existing basic metadata
    cur.execute("DELETE FROM library_vectors WHERE chunk_index = 0")

    docs_inserted = 0
    for root, dirs, files in os.walk(LIB_DIR):
        for f in files:
            if f.endswith(".md"):
                file_path = os.path.join(root, f)

                # Determine category based on immediate subfolder of Library
                rel_path = os.path.relpath(root, LIB_DIR)
                if rel_path == ".":
                    category = "Root"
                else:
                    category = rel_path.split(os.sep)[0]

                last_mod = os.path.getmtime(file_path)
                doc_id = str(uuid.uuid4())

                cur.execute(
                    """
                    INSERT INTO library_vectors (id, category, file_path, last_modified, chunk_index, chunk_text, vector_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (doc_id, category, file_path, last_mod, 0, "", "[]"),
                )
                docs_inserted += 1

    conn.commit()
    conn.close()
    print(f"Indexing complete. Inserted {docs_inserted} documents.")


if __name__ == "__main__":
    index_library()
