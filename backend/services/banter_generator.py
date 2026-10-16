import os
import sys
import re
import json
import sqlite3
import random
import time
from hashlib import sha256

# Reconfigure stdout/stderr for Unicode support on Windows command prompt
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

NAVIS_ROOT = os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Protocol")
STATUS_PATH = os.path.join(NAVIS_ROOT, "Bridge", "status.json")
SETTINGS_PATH = os.path.join(NAVIS_ROOT, "Bridge", "settings.json")
MAX_BANTER_THREADS_PER_RUN = 3
USABLE_THREAD_MAX_AGE_SECONDS = 24 * 60 * 60


def retrieve_memories(query, db_path, api_key, top_k=3):
    """Legacy online journal embedding path; blocked until it has usage metering."""
    raise RuntimeError(
        "Online journal embedding is disabled because embedding pricing and usage "
        "are not covered by the text experiment budget guard."
    )


def extract_banter_protocol(content):
    match = re.search(
        r"## 🗣️ Banter Protocol\n(.*?)(?:\n---|\n##|$)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return "Standard dialogue protocols apply."


def extract_realm_briefing(content):
    match = re.search(
        r"## 🗣️ Environmental Briefing\n(.*?)(?:\n---|\n##|$)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return content[:800]


def add_banter_thread(db_path, chain, realm, participants):
    """Adds a new banter thread to the database with rotation logic."""
    if not chain:
        return

    # Prevent Duplicates via Hash (based on first line of text)
    first_text = chain[0].get("text", "")
    thread_hash = sha256(first_text.encode("utf-8")).hexdigest()

    participants_str = ",".join(sorted(participants))
    chain_json = json.dumps(chain, ensure_ascii=False)
    ts = time.time()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS banter_threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            realm TEXT,
            participants TEXT,
            chain TEXT,
            timestamp REAL,
            thread_hash TEXT UNIQUE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_realm ON banter_threads(realm)")

    try:
        cursor.execute(
            """
            INSERT INTO banter_threads (realm, participants, chain, timestamp, thread_hash)
            VALUES (?, ?, ?, ?, ?)
        """,
            (realm, participants_str, chain_json, ts, thread_hash),
        )

        # Rotation Logic: Cap threads per squad/realm to 10
        cursor.execute(
            """
            SELECT id FROM banter_threads 
            WHERE realm = ? AND participants = ?
            ORDER BY timestamp DESC
        """,
            (realm, participants_str),
        )

        existing_ids = [row[0] for row in cursor.fetchall()]
        if len(existing_ids) > 10:
            to_delete = existing_ids[10:]
            cursor.execute(
                f'DELETE FROM banter_threads WHERE id IN ({",".join(map(str, to_delete))})'
            )

        conn.commit()
        print(f"✅ Secured banter thread in database: {realm} with {participants_str}")
    except sqlite3.IntegrityError:
        # Duplicate thread found, skipping
        print("⚠️ Duplicate thread found in database, skipped.")
        pass
    finally:
        conn.close()


def has_usable_recent_thread(db_path, realm, participants, *, now=None):
    """Return whether this realm and exact squad already have a usable recent thread."""
    if not os.path.exists(db_path):
        return False

    participants_str = ",".join(sorted(participants))
    cutoff = (time.time() if now is None else now) - USABLE_THREAD_MAX_AGE_SECONDS
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT chain FROM banter_threads
                WHERE realm = ? AND participants = ? AND timestamp >= ?
                ORDER BY timestamp DESC
                """,
                (realm, participants_str, cutoff),
            ).fetchall()
    except sqlite3.Error:
        return False

    expected = set(participants)
    for (serialized_chain,) in rows:
        try:
            chain = json.loads(serialized_chain)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(chain, list) or len(chain) != len(expected):
            continue
        speakers = [
            turn.get("speaker") for turn in chain
            if isinstance(turn, dict) and isinstance(turn.get("text"), str) and turn["text"].strip()
        ]
        if len(speakers) == len(chain) and len(set(speakers)) == len(expected) and set(speakers) == expected:
            return True
    return False


def generate_squad_banter(count=3):
    from services.ai_provider import ProviderError, OllamaProvider
    import asyncio

    try:
        provider = OllamaProvider()
    except ProviderError as e:
        print(f"⚠️ Local banter generation unavailable: {e}")
        return False

    if not os.path.exists(STATUS_PATH):
        print(f"⚠️ status.json not found at {STATUS_PATH}")
        return False

    try:
        with open(STATUS_PATH, "r", encoding="utf-8-sig") as f:
            status = json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading status.json: {e}")
        return False

    realm = status.get("current_realm", "Unknown")
    squad = status.get("squad", [])
    squad_names = [
        m["name"].strip()
        for m in squad
        if isinstance(m, dict) and isinstance(m.get("name"), str) and m["name"].strip()
    ]
    squad_size = len(squad_names)

    if squad_size < 2 or len({name.casefold() for name in squad_names}) != squad_size:
        print("⚠️ At least two uniquely named squad members are required for banter.")
        return False

    # Get settings paths
    settings = {}
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8-sig") as f:
                settings = json.load(f)
        except Exception:
            pass

    paths = settings.get("paths", {})
    realms_dir = paths.get("realms_dir", os.path.join(NAVIS_ROOT, "Realms"))
    companions_dir = paths.get("companions_dir", os.path.join(NAVIS_ROOT, "Companions"))
    db_path = paths.get(
        "chronicle_db", os.path.join(NAVIS_ROOT, "Journal", "Chronicle.db")
    )

    if has_usable_recent_thread(db_path, realm, squad_names):
        print(f"ℹ️ A usable banter thread for {realm} and the active squad is already available.")
        return True

    try:
        count = max(1, min(int(count), MAX_BANTER_THREADS_PER_RUN))
    except (TypeError, ValueError):
        count = 1

    # Determine Realm Lore
    realm_path = os.path.join(realms_dir, realm, "Realm.md")
    realm_briefing = ""
    if os.path.exists(realm_path):
        try:
            with open(realm_path, "r", encoding="utf-8-sig") as f:
                realm_briefing = extract_realm_briefing(f.read())
        except Exception as e:
            print(f"Error reading Realm.md: {e}")

    # Gather specialized protocols
    character_instructions = []
    vanguard_name = next(
        (m["name"] for m in squad if isinstance(m, dict) and m.get("is_vanguard") and m.get("name")),
        None,
    )

    for member in squad:
        if not isinstance(member, dict) or not member.get("name"):
            continue
        name = member["name"]
        first = name.split(" ")[0]
        p_path = os.path.join(companions_dir, first, "Profile.md")
        if not os.path.exists(p_path):
            p_path = os.path.join(companions_dir, name, "Profile.md")

        protocol = "Standard behavior."
        if os.path.exists(p_path):
            try:
                with open(p_path, "r", encoding="utf-8-sig") as f:
                    protocol = extract_banter_protocol(f.read())
            except Exception as e:
                print(f"Error reading Profile.md for {name}: {e}")

        is_vanguard = name == vanguard_name
        leadership = " (PARTY LEADER)" if is_vanguard else ""

        # Check if native to realm
        is_native = False
        if os.path.exists(realm_path):
            try:
                with open(realm_path, "r", encoding="utf-8-sig") as f:
                    realm_full = f.read().lower()
                    is_native = (
                        first.lower() in realm_full or name.lower() in realm_full
                    )
            except Exception:
                pass

        native_status = " (LOCAL GUIDE)" if is_native else ""
        character_instructions.append(
            f"NAME: {name}{leadership}{native_status}\nPERSONALITY PROTOCOL:\n{protocol}"
        )

    print(f"📡 Generating {count} banter threads for realm {realm}...")

    # P1 deliberately excludes journal RAG from generation. Vault-derived
    # memories remain out of model prompts until a separate privacy decision.
    resonance_block = ""

    generated_count = 0
    for i in range(count):
        # Determine specific order for THIS thread
        initiator = random.choice(squad_names)
        others = [n for n in squad_names if n != initiator]
        random.shuffle(others)
        thread_order = [initiator] + others

        # Construct the JSON template for the LLM
        template_objects = []
        for speaker in thread_order:
            template_objects.append(f'  {{"speaker": "{speaker}", "text": "..."}}')
        template_str = "[\n" + ",\n".join(template_objects) + "\n]"

        current_protocols = list(character_instructions)
        random.shuffle(current_protocols)
        protocol_block = "\n----- \n".join(current_protocols)

        prompt = f"""
Act as a Storyteller for a role-playing game.
LOCATION: {realm}.

TASK: Fill in the 'text' fields for this EXACT conversational template. 
The party members are exploring their current surroundings. Each character speaks once in the specified order.

ATMOSPHERE & SETTING:
{realm_briefing}

{resonance_block}

PARTY MEMBER PROTOCOLS:
{protocol_block}

STORYTELLING CONSTRAINTS:
1. REMOVE all military and sci-fi terminology. Avoid words like 'scans', 'biometrics', 'tactical', 'squad', 'deployment', or 'stabilizers'.
2. Use immersive RPG language. Focus on the environment, the journey, and the feelings of the party.
3. Maintain the specified speaker order. The conversation MUST involve all {squad_size} party members.
4. DO NOT use character-identifying emojis.
5. VALID JSON ONLY: Do not include structural junk like '}}, {{"speaker":' inside the text field. Use single quotes (') for any internal dialogue punctuation to avoid breaking the JSON structure.
6. Place emotional emojis ONLY at the very end of dialogue strings.
7. Always refer to the user as 'Keeper'.
8. Use plain text (no italics, unless within an action/thought block).
9. ACTIONS & THOUGHTS: Use \\*asterisks\\* for physical actions and [brackets] for internal monologues.
10. FLAT STRUCTURE: Ensure each speaker's text is a single, self-contained string. Do not attempt to nest other speakers or JSON objects within another speaker's 'text'.
11. NEURAL RESONANCE: If a memory is provided above, at least one character should naturally reference its themes or events as a 'recollection' or 'lesson learned' during the journey.

REQUIRED TEMPLATE (Fill in the 'text' fields):
{template_str}
"""
        try:
            resp_text = asyncio.run(provider.generate(prompt))

            # Robust extraction
            final_chain = []
            json_match = re.search(r"(\[.*\])", resp_text, re.DOTALL)
            if json_match:
                try:
                    raw_json = json_match.group(1).strip()
                    raw_json = re.sub(r",\s*\]", "]", raw_json)
                    raw_json = re.sub(r",\s*\}", "}", raw_json)
                    final_chain = json.loads(raw_json)
                except Exception:
                    final_chain = []

            if not final_chain:
                # Fallback to regex parser
                pattern = (
                    r'\{\s*"speaker"\s*:\s*"(.*?)"\s*,\s*"text"\s*:\s*"(.*?)"\s*\}'
                )
                matches = re.findall(pattern, resp_text, re.DOTALL)
                if matches:
                    parsed_chain = []
                    for spk, txt in matches:
                        parsed_chain.append(
                            {"speaker": spk.strip(), "text": txt.strip()}
                        )
                    final_chain = parsed_chain

            if final_chain:
                cleaned_chain = []
                seen_speakers = set()
                for entry in final_chain:
                    if not isinstance(entry, dict):
                        continue
                    spk = entry.get("speaker", "")
                    txt = entry.get("text", "")
                    if not isinstance(spk, str) or not isinstance(txt, str):
                        continue
                    spk = spk.strip()
                    txt = txt.strip()
                    if not spk or not txt or spk not in squad_names:
                        continue
                    if spk in seen_speakers:
                        continue

                    # Prune structural remnants
                    for marker in ['"},', "},", '{"speaker"', '"speaker":', "speaker:"]:
                        if marker in txt:
                            txt = txt.split(marker)[0].strip()
                    txt = re.sub(r'[",\s]+$', "", txt).strip()
                    if txt:
                        cleaned_chain.append({"speaker": spk, "text": txt})
                        seen_speakers.add(spk)

                cleaned_speakers = [entry["speaker"] for entry in cleaned_chain]
                if cleaned_chain and cleaned_speakers == thread_order:
                    add_banter_thread(db_path, cleaned_chain, realm, squad_names)
                    generated_count += 1
                else:
                    print("⚠️ Banter response did not match the required party and speaker order.")
            else:
                print("⚠️ Failed to parse LLM response as JSON or match regex.")
        except ProviderError as e:
            print(f"⚠️ Local banter generation unavailable: {e}")
            return False
        except Exception as e:
            print(f"❌ Error generating banter thread: {type(e).__name__}")

    return generated_count > 0
