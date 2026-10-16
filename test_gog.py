import sqlite3
import json
conn = sqlite3.connect(r'C:\ProgramData\GOG.com\Galaxy\storage\galaxy-2.0.db')
cursor = conn.cursor()

# Get owned releaseKeys
cursor.execute('SELECT releaseKey FROM LibraryReleases')
owned_keys = {row[0] for row in cursor.fetchall()}

# Get all DLCs to exclude them
cursor.execute('SELECT value FROM GamePieces WHERE gamePieceTypeId = 10')
dlc_keys = set()
for row in cursor.fetchall():
    data = json.loads(row[0])
    if data.get('dlcs'):
        dlc_keys.update(data['dlcs'])

# Get titles
cursor.execute('SELECT releaseKey, value FROM GamePieces WHERE gamePieceTypeId = 47')
games = []
for row in cursor.fetchall():
    key = row[0]
    if key in owned_keys and key not in dlc_keys:
        title = json.loads(row[1]).get('title', '')
        platform = key.split('_')[0].capitalize()
        games.append((platform, title))

print(f'Found {len(games)} owned base games across {len(set(g[0] for g in games))} platforms!')
print('Sample:', games[:5])
