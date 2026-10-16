"""Shared conversation service for Reid, Neural Bridge, and War Room."""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import time
import tempfile
from contextlib import asynccontextmanager
import json
import re
import os
from pathlib import Path
import sys
from typing import Any

from services.ai_provider import ProviderError, TextProvider, get_provider
from services.online_ai import OnlineAIError
from services.reid_agent import chat_with_reid, get_parsed_session_history


class ConversationError(ValueError):
    """Raised for malformed conversation requests."""
    pass


def load_status(root: Path) -> dict[str, Any]:
    status_path = root / "Bridge" / "status.json"
    if status_path.is_file():
        try:
            with open(status_path, "r", encoding="utf-8-sig") as stream:
                return json.load(stream)
        except Exception:
            pass
    return {"current_realm": "Unknown", "squad": []}


async def handle_reid_chat(
    root: Path | str,
    request: dict[str, Any],
    provider: TextProvider | None = None,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    os.environ["NAVIS_ROOT"] = str(root_path)
    os.environ["NAVIS_VAULT_ROOT"] = str(root_path)

    message = request.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ConversationError("Message cannot be empty.")

    history = request.get("history")
    if history is not None and not isinstance(history, list):
        raise ConversationError("History must be a list of messages.")

    response = await chat_with_reid(message.strip(), history, provider=provider)
    return {"status": "success", "response": response}


def handle_reid_history(root: Path | str) -> dict[str, Any]:
    root_path = Path(root).resolve()
    os.environ["NAVIS_ROOT"] = str(root_path)
    os.environ["NAVIS_VAULT_ROOT"] = str(root_path)
    history = get_parsed_session_history()
    return {"status": "success", "history": history}


async def handle_neural_chat(
    root: Path | str,
    request: dict[str, Any],
    provider: TextProvider | None = None,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    os.environ["NAVIS_ROOT"] = str(root_path)

    message = request.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ConversationError("Message cannot be empty.")

    history = request.get("history") or []
    if not isinstance(history, list):
        raise ConversationError("History must be a list of messages.")

    persona = request.get("persona")
    status = load_status(root_path)
    realm = status.get("current_realm", "Unknown")
    squad = status.get("squad", [])
    squad_names = ", ".join([s.get("name", "") for s in squad if s.get("name")])

    sys_prompt = (
        f"You are the Neural Bridge for the Navis Protocol. The current realm is {realm}. "
        f"The active squad members are: {squad_names}. Assist the Keeper in operations."
    )

    if persona and isinstance(persona, str):
        # Look for persona profile in Residents or Companions
        profile_path = None
        for folder in ("Residents", "Companions"):
            candidate = root_path / folder / persona / "Profile.md"
            if candidate.is_file():
                profile_path = candidate
                break

        if profile_path is not None:
            try:
                with open(profile_path, "r", encoding="utf-8-sig") as stream:
                    profile_content = stream.read()
                sys_prompt = (
                    f"Act as {persona}. Use the following profile and lore to inform your responses, tone, and worldview:\n\n"
                    f"{profile_content}\n\nMaintain character at all times. Current realm is {realm}."
                )
            except Exception:
                pass

    contents = []
    for msg in history:
        if isinstance(msg, dict):
            role = "user" if msg.get("role") == "user" else "model"
            contents.append(f"{role}: {msg.get('content', '')}")
    contents.append(f"user: {message.strip()}")
    transcript = "\n".join(contents)

    active_provider = provider or get_provider()
    response = await active_provider.generate(transcript, system=sys_prompt, feature="neural_chat")
    return {"status": "success", "response": response}


def get_warroom_history(root: Path | str) -> list[dict[str, Any]]:
    root_path = Path(root).resolve()
    history_path = root_path / "Bridge" / "warroom_history.json"
    if history_path.is_file():
        try:
            with open(history_path, "r", encoding="utf-8") as stream:
                data = json.load(stream)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def clear_warroom_history(root: Path | str) -> dict[str, Any]:
    root_path = Path(root).resolve()
    history_path = root_path / "Bridge" / "warroom_history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with open(history_path, "w", encoding="utf-8") as stream:
        json.dump([], stream, indent=4)
    return {"status": "success"}


@asynccontextmanager
async def warroom_lock(root: Path):
    """Serialize desktop subprocesses and web requests without blocking the event loop."""
    lock_path = root / "Bridge" / "warroom_history.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+b") as lock:
        deadline = time.monotonic() + 600
        while True:
            try:
                lock.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise ProviderError("War Room is busy. Wait for the current request and retry.")
                await asyncio.sleep(0.05)
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


async def handle_warroom_chat(root, request, provider=None):
    root_path = Path(root).resolve()
    message = request.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ConversationError("Message cannot be empty.")
    request_id = request.get("request_id")
    if request_id is not None and (not isinstance(request_id, str) or not 1 <= len(request_id) <= 128
            or not all(c.isascii() and (c.isalnum() or c in "-_") for c in request_id)):
        raise ConversationError("Invalid conversation request identifier.")
    fingerprint = hashlib.sha256(message.strip().encode("utf-8")).hexdigest()
    async with warroom_lock(root_path):
        if request_id:
            for turn in get_warroom_history(root_path):
                if turn.get("role") == "assistant" and turn.get("request_id") == request_id:
                    if turn.get("request_hash") != fingerprint:
                        raise ConversationError("Conversation request identifier was already used for another message.")
                    return {"status": "success", "response": turn["content"]}
        return await _generate_warroom_chat(root_path, request, provider)


async def _generate_warroom_chat(
    root: Path | str,
    request: dict[str, Any],
    provider: TextProvider | None = None,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    os.environ["NAVIS_ROOT"] = str(root_path)

    message = request.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ConversationError("Message cannot be empty.")

    status = load_status(root_path)
    squad = [member for member in status.get("squad", [])
             if member.get("name", "").strip().lower() not in ("keeper", "kevin")]
    if not any(member.get("name") for member in squad):
        raise ConversationError("Assign a companion to the active squad before starting War Room.")
    lead_speaker = next(member["name"] for member in squad if member.get("name"))
    current_realm = status.get("current_realm", "Unknown")
    current_antagonist = status.get("current_antagonist", "None")
    current_beast = status.get("current_beast", "None")
    keeper = "Kevin"

    cache_path = root_path / "Bridge" / ".navis_cache" / "sector_cache.json"
    active_missions = []
    if cache_path.is_file():
        try:
            with open(cache_path, "r", encoding="utf-8") as stream:
                cache = json.load(stream)
            main_missions = cache.get("sectors", {}).get("MISSIONS", {}).get("Main", [])
            active_missions = [m.get("name") for m in main_missions if m.get("name")][:3]
        except Exception:
            pass
    missions_text = ", ".join(active_missions) if active_missions else "None"

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    year, month = today[:4], today[5:7]
    journal_path = root_path / "Journal" / year / month / f"{today}.md"
    journal_text = "No recent journal context."
    if journal_path.is_file():
        try:
            with open(journal_path, "r", encoding="utf-8-sig") as stream:
                content = stream.read()
                journal_text = content[:1500] + ("..." if len(content) > 1500 else "")
        except Exception:
            pass

    personas_text = ""
    for member in squad:
        name = member.get("name")
        if not name:
            continue
        personas_text += f"=== {name} ===\nRole: {member.get('role', 'Companion')}\n"
        persona_path = root_path / "Companions" / name / "Persona.json"
        if persona_path.is_file():
            try:
                with open(persona_path, "r", encoding="utf-8") as stream:
                    persona_data = json.load(stream)
                personas_text += f"=== {name} ===\n"
                personas_text += f"Role: {persona_data.get('role', 'Unknown')}\n"
                if "voice" in persona_data:
                    personas_text += f"Voice: {persona_data.get('voice', '')}\n"
                if "system_prompt" in persona_data:
                    personas_text += f"Persona Instructions: {persona_data.get('system_prompt', '')}\n\n"
            except Exception:
                pass

    system_prompt = f"""You are a multi-persona roleplay engine. You will adopt the personas of the active squad members and respond to the Keeper ({keeper}).
When responding, you MUST prefix each character's dialogue with their name in asterisks, like this:
*Character Name*: Dialogue

CRITICAL RULES:
1. DO NOT speak as a generic "System" or game master.
2. YOU ONLY speak as the companions in the active squad. Engage in a natural discussion with each other and the Keeper.
3. If multiple characters respond, put each character's response on a new line.
4. The Keeper and Kevin are the human user. NEVER generate their dialogue, thoughts, or actions.
5. Reply briefly as an active companion; greet the Keeper on entry, then answer their actual question.

Current Squad Personas:
{personas_text}

--- SITUATIONAL CONTEXT ---
Current Realm: {current_realm}
Current Antagonist: {current_antagonist}
Current Beast: {current_beast}
Active Missions: {missions_text}

Recent Keeper Journal:
{journal_text}
---------------------------
"""

    history = get_warroom_history(root_path)

    clean_message = message.strip()
    if clean_message.lower() == "/init":
        user_msg = {
            "role": "user",
            "content": "The Keeper has entered the War Room. Give a brief, immersive tactical greeting or banter.",
            "isHidden": True,
        }
    else:
        user_msg = {"role": "user", "content": clean_message}

    history.append(user_msg)

    prompt_parts = []
    for m in history:
        role = "Keeper" if m.get("role") == "user" else "Squad"
        prompt_parts.append(f"{role}: {m.get('content', '')}")
    # Prompt-only Ollama templates omit the separate system field. Keep the
    # instructions and the next companion turn in the actual model input.
    prompt = system_prompt + "\nCONVERSATION:\n" + "\n".join(prompt_parts)
    prompt += f"\n\nNext companion reply (never speak as Keeper):\n*{lead_speaker}*:"

    active_provider = provider or get_provider()
    response_text = await active_provider.generate(prompt, system=system_prompt, feature="warroom")
    clean_response = response_text.replace("<|im_end|>", "").strip()
    if not clean_response:
        raise ProviderError("Local model returned an empty companion reply. Retry the transmission.")
    if re.search(r"(?im)^\s*(?:\*+|\[)?(?:keeper|kevin)(?:\*+|\])?\s*:", clean_response):
        raise ProviderError("Local model tried to speak as the Keeper. Retry for a companion reply.")
    if not re.match(r"^(?:\*+|\[)?[\w -]+(?:\*+|\])?:", clean_response):
        clean_response = f"*{lead_speaker}*: {clean_response}"

    assistant_msg = {"role": "assistant", "content": clean_response}
    if request.get("request_id"):
        assistant_msg.update(request_id=request["request_id"], request_hash=hashlib.sha256(clean_message.encode("utf-8")).hexdigest())
    history.append(assistant_msg)
    if len(history) > 50:
        history = history[-50:]

    history_path = root_path / "Bridge" / "warroom_history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    # Commit the reply and its retry receipt together; a failed write must not
    # truncate existing history or leave a receipt without its response.
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=history_path.parent, delete=False) as stream:
            temporary_path = Path(stream.name)
            json.dump(history, stream, indent=4)
        os.replace(temporary_path, history_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return {"status": "success", "response": clean_response}


async def dispatch(
    root: Path | str,
    action: str,
    request: dict[str, Any],
    provider: TextProvider | None = None,
) -> dict[str, Any]:
    if action == "reid_chat":
        return await handle_reid_chat(root, request, provider=provider)
    if action == "reid_history":
        return handle_reid_history(root)
    if action == "neural_chat":
        return await handle_neural_chat(root, request, provider=provider)
    if action == "warroom_chat":
        return await handle_warroom_chat(root, request, provider=provider)
    if action == "warroom_history":
        return {"status": "success", "history": get_warroom_history(root)}
    if action == "warroom_clear":
        return clear_warroom_history(root)
    raise ConversationError(f"Unsupported conversation action: {action}")


if __name__ == "__main__":
    try:
        raw_input = sys.stdin.read(65537)
        req_data = json.loads(raw_input) if raw_input.strip() else {}
        action = sys.argv[1] if len(sys.argv) > 1 else ""
        root_dir = os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")
        result = asyncio.run(dispatch(root_dir, action, req_data))
        print(json.dumps({"http_status": 200, "body": result}))
    except (ProviderError, OnlineAIError) as exc:
        print(
            json.dumps(
                {
                    "http_status": 503,
                    "body": {
                        "status": "unavailable",
                        "code": "native_dependency_unavailable",
                        "detail": str(exc),
                    },
                }
            )
        )
    except ConversationError as exc:
        print(
            json.dumps(
                {
                    "http_status": 400,
                    "body": {"status": "error", "detail": str(exc)},
                }
            )
        )
    except Exception:
        print(
            json.dumps(
                {
                    "http_status": 503,
                    "body": {
                        "status": "unavailable",
                        "code": "native_dependency_unavailable",
                        "detail": "Conversation runtime unavailable. Verify Python dependencies and local model.",
                    },
                }
            )
        )
