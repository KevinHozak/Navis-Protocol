import sqlite3
import os

db_path = r"G:\My Drive\Navis-Vault\Library\Library_Intelligence.db"
print(f"Checking DB at: {db_path}")

if os.path.exists(db_path):
    print("DB exists. Connecting...")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
    for row in cur.fetchall():
        print(f"Table: {row[0]}")
        print(row[1])
        print("---")
else:
    print("DB not found")
