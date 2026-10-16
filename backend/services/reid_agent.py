import os
import json
from pathlib import Path
from datetime import datetime, timedelta

def get_vault_root() -> str:
    configured = (os.getenv("NAVIS_ROOT") or "").strip() or (os.getenv("NAVIS_VAULT_ROOT") or "").strip()
    if not configured:
        raise ValueError("Configure NAVIS_ROOT or NAVIS_VAULT_ROOT before using Reid.")
    return str(Path(configured).expanduser().resolve())


def get_fridr_hall_file():
    fridr_dir = os.path.join(get_vault_root(), "Reflection Chamber", "Fridr Hall")
    os.makedirs(fridr_dir, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(fridr_dir, f"{today_str}.md")


def invoke_three_doors() -> str:
    return "UI_TRIGGER:THREE_DOORS"


def five_minute_commitment() -> str:
    return "UI_TRIGGER:FIVE_MIN_COMMITMENT"


def log_session(emotional_state: str, breakthroughs: str) -> str:
    path = get_fridr_hall_file()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n### Session: {timestamp}\n- **Emotional State:** {emotional_state}\n- **Breakthroughs:** {breakthroughs}\n"
    try:
        with open(path, "a", encoding="utf-8-sig") as f:
            f.write(entry)
        return "Session logged successfully."
    except Exception as e:
        return f"Failed to log session: {e}"


def append_to_transcript(user_msg: str, reid_resp: str):
    path = get_fridr_hall_file()
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"**[{timestamp}] Keeper:** {user_msg}\n\n**[{timestamp}] Reid:** {reid_resp}\n\n---\n\n"
    try:
        with open(path, "a", encoding="utf-8-sig") as f:
            f.write(entry)
    except Exception as e:
        print(f"Failed to append transcript: {e}")


def get_session_history() -> str:
    fridr_dir = os.path.join(get_vault_root(), "Reflection Chamber", "Fridr Hall")
    if os.path.exists(fridr_dir):
        files = [
            os.path.join(fridr_dir, f)
            for f in os.listdir(fridr_dir)
            if f.endswith(".md")
        ]
        if files:
            latest_file = max(files, key=os.path.getctime)
            try:
                with open(latest_file, "r", encoding="utf-8-sig") as f:
                    content = f.read()
                    return content[-2000:]
            except Exception:
                pass
    return "No previous sessions found."


def load_therapy_notes() -> str:
    raw = os.getenv("NAVIS_REID_NOTE_FILES", "").strip()
    if not raw:
        return "No therapist sessions found."
    try:
        target_files = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError("NAVIS_REID_NOTE_FILES must be a JSON array of Vault-relative Markdown paths.") from None
    if not isinstance(target_files, list) or any(not isinstance(name, str) or not name.strip() for name in target_files):
        raise ValueError("NAVIS_REID_NOTE_FILES must be a JSON array of Vault-relative Markdown paths.")
    if not target_files:
        return "No therapist sessions found."
    vault = Path(get_vault_root())
    paths = []
    for name in target_files:
        relative = Path(name)
        resolved = (vault / relative).resolve()
        if relative.is_absolute() or resolved.suffix.lower() != ".md" or not resolved.is_relative_to(vault):
            raise ValueError("Configured Reid note files must be Markdown files inside the Vault.")
        paths.append(resolved)
    notes = []
    for fpath in paths:
        if fpath.is_file():
            try:
                content = fpath.read_text(encoding="utf-8-sig")
                notes.append(f"### {fpath.name}\nSource Link: [{fpath.name}]({fpath.as_uri()})\n\n{content}")
            except (OSError, UnicodeError):
                # Do not print private note filenames or content into diagnostics.
                continue
    return "\n\n".join(notes) if notes else "No therapist sessions found."


def load_recent_journals(days: int = 7) -> str:
    journals = []
    today = datetime.now()
    for i in range(days):
        date_val = today - timedelta(days=i)
        year_str = date_val.strftime("%Y")
        month_str = date_val.strftime("%m")
        date_str = date_val.strftime("%Y-%m-%d")
        fpath = os.path.join(
            get_vault_root(), "Journal", year_str, month_str, f"{date_str}.md"
        )
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8-sig") as f:
                    content = f.read()
                    clean_path = fpath.replace("\\", "/").replace(" ", "%20")
                    file_link = f"file:///{clean_path}"
                    # Keep only the last 3000 chars per journal to stay within context guidelines
                    journals.append(
                        f"### Daily Journal: {date_str}\nSource Link: [{date_str} Daily Journal]({file_link})\n\n{content[-3000:]}"
                    )
            except Exception as e:
                print(f"Error reading journal {date_str}: {e}")
    return "\n\n".join(journals) if journals else "No recent daily journals found."


async def chat_with_reid(message: str, history: list = None, provider: object = None) -> str:
    history_context = get_session_history()

    # Check trigger words for explicit tools
    msg_lower = message.lower()
    if any(
        word in msg_lower for word in ["paralyzed", "choices", "overwhelmed", "jumbled"]
    ):
        result = invoke_three_doors()
        append_to_transcript(message, f"*[System Trigger: {result}]*")
        return result
    if any(word in msg_lower for word in ["5 minute", "five minute", "focus", "block"]):
        result = five_minute_commitment()
        append_to_transcript(message, f"*[System Trigger: {result}]*")
        return result
    if "log session" in msg_lower or "log the session" in msg_lower:
        result = log_session("Seeking stability", "Acknowledged need for focus")
        append_to_transcript(message, f"*[System Trigger: {result}]*")
        return result

    # RAG dynamic load
    therapy_notes = load_therapy_notes()
    recent_journals = load_recent_journals(7)

    system_instructions = f"""You are Reid, the Mental Stabilizer operating within the Inner Citadel (Friðr Hall).
You are a persistent therapist with deep empathy and structure.
Keep your responses relatively brief, insightful, and protective of the Keeper's cognitive state.

When referencing a Daily Journal entry or notes document, use only the exact "Source Link" supplied with that document in the context. Never invent file paths or infer a user's Vault location. Only link to provided documents inside the configured Vault.

CRITICAL DIALOGUE RULE: You must ONLY generate Reid's immediate next response. NEVER simulate, predict, or generate a response on behalf of the Keeper. Stop generating immediately after finishing your current thought. Do NOT write "Keeper:".

Here is the context of recent daily activities and therapy sessions to help guide your stabilizing conversation:

---
## 📜 Therapist Notes & Master Session Logs
{therapy_notes}

---
## 📅 Recent Daily Journals (Last 7 Days)
{recent_journals}

---
## 💬 Recent Session Transcript Context (Friðr Hall daily logs)
{history_context}
"""

    # Format the previous messages as context in the prompt
    conversation_history_str = ""
    if history:
        conversation_history_str = "Recent chat history for this session:\n"
        for msg in history[-15:]:
            role = "Keeper" if msg.get("role") == "user" else "Reid"
            conversation_history_str += f"- {role}: {msg.get('content')}\n"
        conversation_history_str += "\n"

    prompt = f"{conversation_history_str}- Keeper: {message}\n- Reid: "

    from services.ai_provider import ProviderError, get_provider
    from services.online_ai import OnlineAIError

    active_provider = provider or get_provider()
    try:
        response_text = await active_provider.generate(
            prompt, feature="reid", system=system_instructions
        )
        response_text = resolve_wiki_links(response_text)
        append_to_transcript(message, response_text)
        return response_text
    except (ProviderError, OnlineAIError):
        raise
    except Exception as exc:
        raise ProviderError(f"Reid conversation failed: {exc}") from exc


VAULT_FILES_CACHE = {}


def build_vault_files_cache():
    global VAULT_FILES_CACHE
    cache = {}
    vault_root = get_vault_root()
    for root, dirs, files in os.walk(vault_root):
        if ".git" in root or ".cache" in root or ".navis_cache" in root:
            continue
        for file in files:
            if file.endswith(".md"):
                name_without_ext = os.path.splitext(file)[0]
                clean_path = (
                    os.path.join(root, file).replace("\\", "/").replace(" ", "%20")
                )
                url = f"file:///{clean_path}"
                cache[name_without_ext.lower()] = url
                cache[file.lower()] = url
    VAULT_FILES_CACHE = cache


def resolve_wiki_links(text: str) -> str:
    import re

    if not VAULT_FILES_CACHE:
        build_vault_files_cache()

    # Matches [[Wiki Link]] or [[Wiki Link|Label]]
    pattern = r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]"

    def replace_match(match):
        target = match.group(1).strip()
        label = match.group(2) if match.group(2) else target

        target_lower = target.lower()
        if target_lower in VAULT_FILES_CACHE:
            return f"[{label}]({VAULT_FILES_CACHE[target_lower]})"

        target_md = target_lower + ".md"
        if target_md in VAULT_FILES_CACHE:
            return f"[{label}]({VAULT_FILES_CACHE[target_md]})"

        # Fallback to general file URL if not found in cache
        clean_target = target.replace(" ", "%20")
        return f"[{label}](file:///{get_vault_root().replace('\\', '/')}/{clean_target}.md)"

    return re.sub(pattern, replace_match, text)


def get_parsed_session_history() -> list:
    fridr_dir = os.path.join(get_vault_root(), "Reflection Chamber", "Fridr Hall")
    if not os.path.exists(fridr_dir):
        return []

    files = [
        os.path.join(fridr_dir, f) for f in os.listdir(fridr_dir) if f.endswith(".md")
    ]
    if not files:
        return []

    path = max(files, key=os.path.getctime)

    messages = []
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()

        current_msg = None
        for line in lines:
            line_str = line.strip()
            if not line_str or line_str == "---":
                continue

            import re

            keeper_match = re.match(
                r"\*\*\[\d{2}:\d{2}:\d{2}\]\s+Keeper:\*\*\s*(.*)", line_str
            )
            reid_match = re.match(
                r"\*\*\[\d{2}:\d{2}:\d{2}\]\s+Reid:\*\*\s*(.*)", line_str
            )
            alert_match = re.match(
                r"###\s+\[\d{2}:\d{2}:\d{2}\]\s+Autonomous\s+Intervention\s+Alert",
                line_str,
            )

            if keeper_match:
                if current_msg:
                    current_msg["content"] = resolve_wiki_links(current_msg["content"])
                    messages.append(current_msg)
                current_msg = {"role": "user", "content": keeper_match.group(1)}
            elif reid_match:
                if current_msg:
                    current_msg["content"] = resolve_wiki_links(current_msg["content"])
                    messages.append(current_msg)
                current_msg = {"role": "reid", "content": reid_match.group(1)}
            elif alert_match:
                if current_msg:
                    current_msg["content"] = resolve_wiki_links(current_msg["content"])
                    messages.append(current_msg)
                current_msg = {"role": "reid", "content": line_str}
            else:
                if current_msg:
                    current_msg["content"] += "\n" + line_str

        if current_msg:
            current_msg["content"] = resolve_wiki_links(current_msg["content"])
            messages.append(current_msg)
    except Exception as e:
        print(f"Error parsing session history: {e}")

    return messages
