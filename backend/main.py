from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import hmac
import os
import sys


def load_hermes_env():
    # Cloud credentials belong to the service that uses them. Loading a global
    # Hermes key here made unrelated app initialization depend on paid AI setup.
    return None


load_hermes_env()

# Reconfigure stdout/stderr to UTF-8 to prevent cp1252 encoding crashes on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr.encoding != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
import json
from pydantic import BaseModel, Field, StrictBool, field_validator, model_validator
from typing import List, Optional
import re
import glob
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from urllib.parse import quote
from services.recurrence import calculate_next_due, journal_day, validate_date

NAVIS_ROOT = os.getenv("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")


class SquadActionRequest(BaseModel):
    name: str
    target_recall: Optional[str] = None


class RealmHopRequest(BaseModel):
    realm_name: str
    squad_names: List[str] = []


class NeuralChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = []
    persona: Optional[str] = None


class WarRoomChatRequest(BaseModel):
    message: str
    request_id: Optional[str] = None


class ForgeSubmitRequest(BaseModel):
    entity_type: str
    name: str
    prompt: str


class ForgeApproveRequest(BaseModel):
    proposal_id: str
    approved: StrictBool = False


class ForgeDiscardRequest(BaseModel):
    proposal_id: str


class AIExperimentSettingsRequest(BaseModel):
    enabled: bool | None = None
    allow_vault_content: bool | None = None
    monthly_budget_usd: float | None = None


class TaskMetadataCreate(BaseModel):
    description: str = ""
    priority: int = Field(default=4, ge=1, le=4, strict=True)
    labels: List[str] = Field(default_factory=list)
    due_date: Optional[str] = None

    @field_validator("due_date")
    @classmethod
    def valid_due_date(cls, value):
        if value is not None:
            validate_date(value)
        return value


class TaskMetadataUpdate(TaskMetadataCreate):
    # Omitted fields remain untouched; null explicitly clears a due date.
    pass


class RecurringTaskCreate(TaskMetadataCreate):
    text: str
    frequency: str
    area: str
    next_due: Optional[str] = None

    @model_validator(mode="after")
    def consistent_due_dates(self):
        if self.due_date is not None and self.next_due is not None and self.due_date != self.next_due:
            raise ValueError("due_date and next_due must agree")
        return self


class RecurringTaskUpdate(TaskMetadataUpdate):
    text: Optional[str] = None
    frequency: Optional[str] = None
    area: Optional[str] = None
    last_done: Optional[str] = None
    next_due: Optional[str] = None

    @model_validator(mode="after")
    def consistent_due_dates(self):
        if "due_date" in self.model_fields_set:
            if self.due_date is None:
                raise ValueError("Recurring tasks require a due date")
            if self.next_due is not None and self.due_date != self.next_due:
                raise ValueError("due_date and next_due must agree")
        return self


class ActiveTaskCreate(TaskMetadataCreate):
    text: str
    area: str


class ActiveTaskUpdate(TaskMetadataUpdate):
    text: Optional[str] = None
    area: Optional[str] = None
    status: Optional[str] = None


def task_metadata(req):
    return req.model_dump(include={"description", "priority", "labels"})


def update_task_metadata(task, req):
    task.update(req.model_dump(include={"description", "priority", "labels"}, exclude_unset=True))


async def proactive_checkin_task():
    from services.reid_daemon import check_biometrics_and_intervene

    while True:
        try:
            await asyncio.to_thread(check_biometrics_and_intervene)
        except Exception as e:
            print(f"Error in proactive checkin task: {e}")
        await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(proactive_checkin_task())
    try:
        from services.sync_engine import check_startup_holocron_catchup
        check_startup_holocron_catchup(NAVIS_ROOT)
    except Exception:
        pass

    from services.watcher_service import get_vault_watcher
    from services.event_bus import get_event_bus
    watcher = get_vault_watcher(NAVIS_ROOT)
    event_bus = get_event_bus()
    event_bus.attach_watcher(watcher)
    await watcher.start()

    try:
        yield
    finally:
        await watcher.stop()
        event_bus.detach_watcher()
        task.cancel()


app = FastAPI(title="Navis Bridge API", lifespan=lifespan)

# Global job tracker for background tasks
active_jobs = {}

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "tauri://localhost",
    "http://vault.localhost",
    "https://vault.localhost",
]


def get_allowed_origins() -> List[str]:
    custom_origins = os.getenv("NAVIS_ALLOWED_ORIGINS", "")
    origins = list(DEFAULT_ALLOWED_ORIGINS)
    if custom_origins:
        for orig in custom_origins.split(","):
            clean = orig.strip()
            if clean and clean not in origins:
                origins.append(clean)
    return origins


EXEMPT_PATHS = {
    "/",
    "/health",
    "/api/health",
    "/api/auth/status",
    "/api/auth/verify",
    "/favicon.ico",
}


def is_request_authorized(request: Request) -> bool:
    api_key = os.getenv("NAVIS_API_KEY", "").strip()
    require_auth = os.getenv("NAVIS_REQUIRE_AUTH", "").lower() in ("1", "true", "yes")

    auth_header = request.headers.get("Authorization", "").strip()
    vanguard_header = request.headers.get("X-Vanguard-Key", "").strip()

    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif auth_header:
        token = auth_header
    elif vanguard_header:
        token = vanguard_header

    # 1. If NAVIS_API_KEY is configured, strict token match is required
    if api_key:
        return bool(token) and hmac.compare_digest(token, api_key)

    # 2. If NAVIS_REQUIRE_AUTH is set but no key is configured on server, reject
    if require_auth:
        return False

    # 3. Local loopback dev mode (default when NAVIS_API_KEY is unset)
    client_host = request.client.host if request.client else ""
    is_loopback = client_host in ("127.0.0.1", "::1", "localhost", "testclient")

    origin = request.headers.get("Origin", "")
    allowed = get_allowed_origins()
    if origin and origin not in allowed:
        return False

    return is_loopback


@app.middleware("http")
async def authorization_boundary_middleware(request: Request, call_next):
    # CORS preflight requests do not carry auth credentials and must pass to CORSMiddleware
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if path in EXEMPT_PATHS or path.startswith(("/docs", "/openapi.json", "/redoc")):
        return await call_next(request)

    if not is_request_authorized(request):
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized: valid authentication token required"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await call_next(request)


# Enable CORS with constrained allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthVerifyRequest(BaseModel):
    key: Optional[str] = None


@app.get("/api/auth/status")
async def get_auth_status(request: Request):
    api_key = os.getenv("NAVIS_API_KEY", "").strip()
    require_auth = os.getenv("NAVIS_REQUIRE_AUTH", "").lower() in ("1", "true", "yes")
    authenticated = is_request_authorized(request)
    mode = "api_key" if api_key else ("enforced" if require_auth else "loopback_dev")
    return {
        "status": "success",
        "auth_required": bool(api_key or require_auth),
        "mode": mode,
        "authenticated": authenticated,
    }


@app.post("/api/auth/verify")
async def verify_auth(req: Optional[AuthVerifyRequest] = None, request: Request = None):
    api_key = os.getenv("NAVIS_API_KEY", "").strip()
    token = ""
    if req and req.key:
        token = req.key.strip()
    elif request:
        auth_header = request.headers.get("Authorization", "").strip()
        vanguard_header = request.headers.get("X-Vanguard-Key", "").strip()
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif auth_header:
            token = auth_header
        elif vanguard_header:
            token = vanguard_header

    if api_key:
        if token and hmac.compare_digest(token, api_key):
            return {"status": "success", "authenticated": True, "message": "Terminal authorized"}
        raise HTTPException(status_code=401, detail="Invalid authorization key")

    require_auth = os.getenv("NAVIS_REQUIRE_AUTH", "").lower() in ("1", "true", "yes")
    if require_auth:
        raise HTTPException(status_code=401, detail="Server authorization key not configured")

    client_host = request.client.host if request and request.client else ""
    if client_host in ("127.0.0.1", "::1", "localhost", "testclient"):
        return {
            "status": "success",
            "authenticated": True,
            "message": "Loopback terminal authorized",
        }
    raise HTTPException(
        status_code=401, detail="Authentication required for non-loopback connections"
    )

# -----------------------------------------------------------------------------
# BATTLE ENGINE ENDPOINTS
# -----------------------------------------------------------------------------


class BattleLinkRequest(BaseModel):
    task_id: str
    top_card_id: str
    bottom_card_id: str
    source: dict
    resolution_id: Optional[str] = None


class BattleResolveRequest(BaseModel):
    task_id: str
    is_completed: bool = True
    resolution_id: str
    source: Optional[dict] = None


@app.get("/api/battle/state")
async def get_battle_state():
    from services.combat_completion import dispatch

    try:
        return dispatch("/api/battle/state", {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/battle/link")
async def link_battle_task(req: BattleLinkRequest):
    from services.combat_completion import dispatch

    try:
        return dispatch("/api/battle/link", req.model_dump())
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/battle/resolve")
async def resolve_battle_task(req: BattleResolveRequest):
    from services.combat_completion import dispatch

    try:
        return dispatch("/api/battle/resolve", req.model_dump())
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/battle/rest")
async def battle_short_rest():
    from services.combat_completion import dispatch

    try:
        return dispatch("/api/battle/rest", {})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------
# TASKS ENDPOINTS
# -----------------------------------------------------------------------------


# --- Path Configuration (Matching existing Navis Protocol) ---
NAVIS_ROOT = os.getenv("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")


def resolve_vault_path(file_path: str) -> str:
    """HTTP compatibility wrapper around the import-safe Vault path resolver."""
    from services.vault_paths import VaultPathError, resolve_relative_path

    try:
        return resolve_relative_path(NAVIS_ROOT, file_path)
    except VaultPathError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None


def vault_asset_url(abs_path: str) -> str:
    relative_path = os.path.relpath(abs_path, NAVIS_ROOT).replace("\\", "/")
    return f"/api/vault/{quote(relative_path, safe='/')}"
STATUS_PATH = os.path.join(NAVIS_ROOT, "Bridge", "status.json")
SETTINGS_PATH = os.path.join(NAVIS_ROOT, "Bridge", "settings.json")


def load_json(path):
    print(f"DEBUG: Attempting to load: {path}")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
                print(
                    f"DEBUG: Successfully loaded {len(data)} keys from {os.path.basename(path)}"
                )
                return data
        except Exception as e:
            print(f"DEBUG: ERROR loading {path}: {e}")
            return {}
    print(f"DEBUG: Path DOES NOT EXIST: {path}")
    return {}


@app.get("/")
async def root():
    return {
        "status": "online",
        "manifold": "Navis Bridge API",
        "version": "1.0.0-skyvault",
    }


@app.get("/api/events/stream")
async def events_stream(
    request: Request,
    limit: Optional[int] = None,
):
    """
    Server-Sent Events (SSE) Bus Endpoint (Reactive-P2).
    Streams formatted SSE messages (event, data, id), periodic keepalive pings (every 15s),
    and filesystem/vault change notifications.
    """
    from services.event_bus import get_event_bus, sse_event_generator
    bus = get_event_bus()
    return StreamingResponse(
        sse_event_generator(request, bus, limit=limit),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/status")
async def get_status():
    status = load_json(STATUS_PATH)
    if not status:
        return {"current_realm": "Earth", "squad": []}

    # Merge current XP and Level from CompanionStats
    stats_path = os.path.join(NAVIS_ROOT, "Bridge", "CompanionStats.json")
    cstats = load_json(stats_path)
    if cstats and "companions" in cstats:
        for member in status.get("squad", []):
            name = member.get("name")
            if name in cstats["companions"]:
                member["xp"] = cstats["companions"][name].get("xp", 0)
                member["level"] = cstats["companions"][name].get("level", 1)

        if "Keeper" in cstats["companions"]:
            status["keeper_xp"] = cstats["companions"]["Keeper"].get("xp", 0)
            status["keeper_level"] = cstats["companions"]["Keeper"].get("level", 1)

    return status


@app.get("/api/settings")
async def get_settings():
    settings = load_json(SETTINGS_PATH)
    if not settings:
        return {
            "lexicon": {
                "pillars": {
                    "COMMAND": "Command Hub",
                    "SANCTUM": "The Sanctum",
                    "CODEX": "Knowledge Base",
                }
            }
        }
    return settings


@app.get("/api/navigation")
async def get_navigation():
    settings = load_json(SETTINGS_PATH)
    pillars = settings.get("lexicon", {}).get("pillars", {})

    nav_items = []
    for key, label in pillars.items():
        nav_items.append({"id": key, "label": label, "icon": get_icon_for_pillar(key)})
    return nav_items


@app.get("/api/readiness")
async def get_readiness():
    return load_json(os.path.join(NAVIS_ROOT, "Bridge", "readiness.json"))


@app.get("/api/ops")
async def get_ops():
    return load_json(os.path.join(NAVIS_ROOT, "Bridge", "ops_state.json"))


@app.get("/api/companions")
async def get_companions():
    companions_dir = os.path.join(NAVIS_ROOT, "Companions")
    if not os.path.exists(companions_dir):
        return []
    companions = []
    for item in os.listdir(companions_dir):
        if item == "Keeper":
            continue
        item_path = os.path.join(companions_dir, item)
        if os.path.isdir(item_path) and not item.startswith("."):
            persona_path = os.path.join(item_path, "Persona.json")
            persona = load_json(persona_path)
            companions.append(
                {
                    "name": item,
                    "role": persona.get("role", "Companion"),
                    "voice": persona.get("voice", ""),
                    "edge_tts_voice": persona.get("edge_tts_voice", ""),
                }
            )
    return companions


@app.get("/api/antagonists")
async def get_antagonists():
    antagonists_dir = os.path.join(NAVIS_ROOT, "Obstacles", "Antagonists")
    if not os.path.exists(antagonists_dir):
        return []
    antagonists = []
    for item in os.listdir(antagonists_dir):
        item_path = os.path.join(antagonists_dir, item)
        if os.path.isdir(item_path) and not item.startswith("."):
            persona_path = os.path.join(item_path, "Persona.json")
            persona = load_json(persona_path)
            antagonists.append(
                {
                    "name": item,
                    "role": persona.get("role", "Antagonist"),
                    "voice": persona.get("voice", ""),
                }
            )
    return antagonists


@app.get("/api/battle/bestiary")
async def get_bestiary():
    from services.bestiary import build_bestiary
    return build_bestiary(NAVIS_ROOT)


@app.get("/api/beasts")
async def get_beasts():
    beasts_dir = os.path.join(NAVIS_ROOT, "Obstacles", "Beasts")
    if not os.path.exists(beasts_dir):
        return []
    beasts = []
    for item in os.listdir(beasts_dir):
        item_path = os.path.join(beasts_dir, item)
        if os.path.isdir(item_path) and not item.startswith("."):
            beasts.append({"name": item})
    return beasts


@app.get("/api/journal/recent")
async def get_recent_journals():
    journal_dir = os.path.join(NAVIS_ROOT, "Journal")
    if not os.path.exists(journal_dir):
        return []

    entries = []
    pattern = os.path.join(journal_dir, "*", "*", "*.md")
    files = glob.glob(pattern)
    files.sort(key=lambda x: os.path.basename(x), reverse=True)

    for f in files[:30]:
        date_str = os.path.basename(f).replace(".md", "")
        highlights = []
        try:
            with open(f, "r", encoding="utf-8-sig") as file:
                lines = file.readlines()
                for line in lines:
                    line_stripped = line.strip()
                    if (
                        line_stripped.startswith("- [x]")
                        or line_stripped.startswith("- [ ]")
                        or line_stripped.startswith("- [/]")
                    ):
                        highlights.append(line_stripped)
                        if len(highlights) >= 5:
                            break
        except Exception:
            pass
        entries.append(
            {
                "date": date_str,
                "path": os.path.relpath(f, NAVIS_ROOT).replace("\\", "/"),
                "highlights": highlights,
            }
        )
    return entries


@app.get("/api/journal/month")
async def get_journal_month(year: int, month: int):
    from datetime import date
    from services.vault_paths import resolve_relative_path, VaultPathError
    try:
        date(year, month, 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid journal month") from None
    try:
        journal_root = resolve_relative_path(NAVIS_ROOT, "Journal")
        # Opening the source distinguishes a readable empty calendar from a
        # disconnected or inaccessible Journal, including absent month folders.
        with os.scandir(journal_root) as entries:
            list(entries)
        year_dir = resolve_relative_path(NAVIS_ROOT, f"Journal/{year}")
        if os.path.lexists(year_dir) and not os.path.isdir(year_dir):
            raise NotADirectoryError("Journal year unavailable")
        journal_dir = resolve_relative_path(NAVIS_ROOT, f"Journal/{year}/{month:02d}")
        if os.path.lexists(journal_dir) and not os.path.isdir(journal_dir):
            raise NotADirectoryError("Journal month unavailable")
        try:
            with os.scandir(journal_dir) as entries:
                dates = []
                for entry in entries:
                    if entry.is_file(follow_symlinks=False) and entry.name.endswith(".md"):
                        try:
                            day = date.fromisoformat(entry.name[:-3])
                        except ValueError:
                            continue
                        if day.isoformat() == entry.name[:-3] and day.year == year and day.month == month:
                            dates.append(day.isoformat())
        except FileNotFoundError:
            # A vanished Journal is a failure, not an empty historical month.
            with os.scandir(journal_root) as entries:
                list(entries)
            dates = []
        return {"dates": sorted(dates), "availability": "available", "year": year, "month": month}
    except (OSError, VaultPathError):
        raise HTTPException(status_code=503, detail={"code": "journal_unavailable", "message": "Journal dates unavailable. Reconnect the Vault and retry."}) from None


class JournalEntryPolishRequest(BaseModel):
    entry: str
    section: str = "sanctum"


class JournalEntryRequest(BaseModel):
    date: str
    section: str
    entry: str
    request_id: str | None = None
    expected_sha256: str | None = None


JOURNAL_SECTION_HEADINGS = {
    "sanctum": "## 🏰 The Sanctum",
    "domestic": "## 🏠 The Domestic Breach",
    "front": "## ⚔️ The High-Velocity Front",
    "gauntlet": "## ⚖️ The Bureaucratic Gauntlet",
    "outland": "## 🥾 The Kinetic Outland",
}

JOURNAL_SECTION_EMOJIS = {
    "sanctum": "🏰",
    "domestic": "🏠",
    "front": "⚔️",
    "gauntlet": "⚖️",
    "outland": "🥾",
}


def polish_output_emoji(entry: str, section: str) -> str:
    lowered = entry.casefold()
    if re.search(r"\b(test|testing|experiment|diagnostic)\b", lowered):
        return "🧪"
    if re.search(r"\b(read|reading|book|library)\b", lowered):
        return "📚"
    if re.search(r"\b(watch|watched|movie|film|episode)\b", lowered):
        return "🎬"
    if re.search(r"\b(workout|exercise|training|lift|lifting)\b", lowered):
        return "💪"
    return JOURNAL_SECTION_EMOJIS.get(section, JOURNAL_SECTION_EMOJIS["sanctum"])


def format_polished_journal_entry(suggestion: str, entry: str, section: str) -> str:
    suggestion = suggestion.strip()
    suggestion = re.sub(r"(?i)^(?:edited|polished)(?: journal)? entry:\s*", "", suggestion)
    suggestion = re.sub(r"\.+\s*$", "", suggestion).rstrip()

    first_letter = re.search(r"[^\W\d_]", suggestion, flags=re.UNICODE)
    if first_letter:
        start, end = first_letter.span()
        suggestion = suggestion[:start] + suggestion[start:end].upper() + suggestion[end:]

    emoji_pattern = r"^[\U0001F000-\U0001FAFF\u2600-\u27BF]\ufe0f?\s+"
    leading_emoji = re.match(emoji_pattern, suggestion)
    if leading_emoji:
        emoji = leading_emoji.group(0).strip()
        content = suggestion[leading_emoji.end() :]
    else:
        emoji = polish_output_emoji(entry, section)
        content = suggestion

    checklist_prefix = re.match(r"^([ \t]*[-*+][ \t]*\[[ xX/]\][ \t]*)", content)
    if checklist_prefix:
        body = content[checklist_prefix.end() :].lstrip()
        body_emoji = re.match(emoji_pattern, body)
        if body_emoji:
            emoji = body_emoji.group(0).strip()
            body = body[body_emoji.end() :]
        return f"{content[:checklist_prefix.end()]}{emoji} {body}"

    return f"{emoji} {content}"


from services.journal_entry import checked_journal_list_item as checked_journal_list_item



@app.post("/api/journal/entry/polish")
async def polish_journal_entry(req: JournalEntryPolishRequest):
    entry = req.entry.strip()
    if not entry:
        raise HTTPException(status_code=422, detail="Journal entry cannot be empty.")
    if len(entry) > 10000:
        raise HTTPException(
            status_code=422,
            detail="Journal entry must be 10,000 characters or fewer.",
        )

    section = req.section if req.section in JOURNAL_SECTION_HEADINGS else "sanctum"
    section_heading = JOURNAL_SECTION_HEADINGS[section].removeprefix("## ")
    prompt = (
        "You copy-edit one personal journal entry. This is an editing task, never a "
        "conversation. Return only the edited entry, preserving its existing line and "
        "Markdown structure. Preserve meaning, facts, and checklist states. Correct "
        "obvious spelling mistakes and accidentally "
        "joined words using context. Always capitalize the first word, do not end with "
        "a period, and prefix one relevant emoji chosen for BOTH the entry and its "
        "journal section. For checklist entries, put the emoji immediately after the "
        "existing list and checkbox markers. Do not add explanations or facts.\n\n"
        "Examples:\n"
        "Section: The Sanctum\n"
        "Draft: okay this is another test of the msystem\n"
        "Edited: 🧪 Okay, this is another test of the system\n\n"
        "Section: The Domestic Breach\n"
        "Draft: i fixed the broken shelf\n"
        "Edited: 🏠 I fixed the broken shelf\n\n"
        f"Section: {section_heading}\n"
        f"Draft: {entry}\n"
        "Edited:"
    )
    payload = {
        "model": "Kimiko-20B:latest",
        "prompt": prompt,
        "stream": False,
        "keep_alive": "1h",
        "options": {"temperature": 0.2, "num_predict": 1024},
    }
    import aiohttp

    try:
        timeout = aiohttp.ClientTimeout(total=90)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "http://localhost:11434/api/generate", json=payload
            ) as response:
                if response.status != 200:
                    detail = (await response.text())[:400]
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Local Ollama could not polish this draft: "
                            f"{detail or response.status}"
                        ),
                    )
                result = await response.json()
    except HTTPException:
        raise
    except (aiohttp.ClientError, TimeoutError) as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Local Ollama is unavailable or timed out. "
                "Your draft has not been changed."
            ),
        ) from error
    suggestion = result.get("response", "")
    suggestion = suggestion.strip() if isinstance(suggestion, str) else ""
    if not suggestion:
        raise HTTPException(
            status_code=503,
            detail=(
                "Local Ollama returned an empty suggestion. "
                "Your draft has not been changed."
            ),
        )
    if re.search(
        r"(?i)\b(?:i(?:'m| am) sorry|i don['’]t understand your response|please rephrase your message)\b",
        suggestion,
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "Local Ollama returned a conversational reply instead of a polished "
                "draft. Your draft has not been changed."
            ),
        )
    suggestion = format_polished_journal_entry(suggestion, entry, section)
    checklist_pattern = r"(?m)^[ \t]*[-*+][ \t]*\[[ xX/]\]"
    original_checklists = re.findall(checklist_pattern, entry)
    suggested_checklists = re.findall(checklist_pattern, suggestion)
    if original_checklists != suggested_checklists:
        raise HTTPException(
            status_code=503,
            detail=(
                "Local Ollama changed checklist formatting. "
                "Your draft has not been changed."
            ),
        )
    return {"suggestion": suggestion}


@app.post("/api/journal/entry")
async def append_journal_entry(req: JournalEntryRequest):
    from services.journal_entry import append, JournalError
    from services.vault_access import VaultAccessError
    try:
        return await asyncio.to_thread(append, NAVIS_ROOT, req.model_dump(exclude_none=True))
    except JournalError as error:
        raise HTTPException(status_code=error.status, detail=error.code) from None
    except VaultAccessError as error:
        raise HTTPException(status_code=404 if error.code == "not_found" else 503, detail=error.code) from None
    except (OSError, ValueError):
        raise HTTPException(status_code=503, detail="append_outcome_unknown_retry_same_request") from None


async def _submit_sync_operation(operation, run_async, background_tasks, request_id):
    import uuid
    from services.operation_outcomes import _identifier, read_operation, run_operation
    try:
        job_id = _identifier(request_id or str(uuid.uuid4()))
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid operation identity") from None
    try:
        previous = read_operation(NAVIS_ROOT, job_id)
    except FileNotFoundError:
        previous = None
    except Exception:
        raise HTTPException(status_code=503, detail="Saved operation state unavailable") from None
    if previous and previous["operation"] != operation:
        raise HTTPException(status_code=409, detail="Operation identity conflict")
    if run_async and background_tasks:
        if previous:
            return {"status": "accepted", "job_id": job_id}
        if job_id in active_jobs and active_jobs[job_id].get("operation") != operation:
            raise HTTPException(status_code=409, detail="Operation identity conflict")
        if job_id not in active_jobs:
            active_jobs[job_id] = {"job_id": job_id, "operation": operation, "status": "running", "output": "Operation queued."}
            background_tasks.add_task(_run_sync_job, job_id, operation)
        return {"status": "accepted", "job_id": job_id}
    try:
        return await asyncio.to_thread(run_operation, NAVIS_ROOT, operation, job_id)
    except Exception:
        raise HTTPException(status_code=409, detail="Operation unavailable; review the latest saved outcome") from None


@app.post("/api/journal/rollover")
async def journal_rollover(run_async: bool = False, background_tasks: BackgroundTasks = None, request_id: str = None):
    return await _submit_sync_operation("rollover", run_async, background_tasks, request_id)


@app.post("/api/sync")
async def execute_sync(run_async: bool = False, background_tasks: BackgroundTasks = None, request_id: str = None):
    return await _submit_sync_operation("sync", run_async, background_tasks, request_id)


@app.post("/api/squad/deploy")
async def deploy_squad_member(req: SquadActionRequest):
    status = load_json(STATUS_PATH)
    if not status:
        raise HTTPException(status_code=500, detail="Could not load status manifold.")

    squad = status.get("squad", [])
    if any(m.get("name") == req.name for m in squad):
        return {
            "status": "success",
            "message": f"{req.name} is already deployed.",
            "squad": squad,
        }

    if len(squad) >= 3:
        target = req.target_recall
        if target and any(m.get("name") == target for m in squad):
            squad = [m for m in squad if m.get("name") != target]
        else:
            raise HTTPException(
                status_code=400, detail="SQUAD FULL: Recall a member to reserve first."
            )

    role = "Active Personnel"
    comp_dir = os.path.join(NAVIS_ROOT, "Companions")
    json_path = os.path.join(comp_dir, req.name, "companion_data.json")
    if os.path.exists(json_path):
        try:
            cdata = load_json(json_path)
            if cdata and "role" in cdata:
                role = cdata["role"]
        except:
            pass
    else:
        profile_path = os.path.join(comp_dir, req.name, "Profile.md")
        if os.path.exists(profile_path):
            with open(profile_path, "r", encoding="utf-8-sig") as pf:
                content = pf.read()
                role_match = re.search(r"- \*\*Role:\*\* (.*?)\n", content)
                if role_match:
                    role = role_match.group(1).strip()

    entry_xp = 0
    stats_path = os.path.join(NAVIS_ROOT, "Bridge", "CompanionStats.json")
    stats = load_json(stats_path)
    if req.name in stats:
        entry_xp = stats[req.name].get("xp", 0)

    squad.append(
        {"name": req.name, "role": role, "is_vanguard": False, "entry_xp": entry_xp}
    )
    status["squad"] = squad

    with open(STATUS_PATH, "w", encoding="utf-8-sig") as f:
        json.dump(status, f, indent=4, ensure_ascii=False)

    try:
        from services.sync_engine import sync_status_to_today_journal

        sync_status_to_today_journal()
    except Exception as e:
        print(f"Failed to sync journal on status update: {e}")

    return {
        "status": "success",
        "message": f"{req.name} deployed to active squad.",
        "squad": squad,
    }


@app.post("/api/squad/bench")
async def bench_squad_member(req: SquadActionRequest):
    status = load_json(STATUS_PATH)
    if not status:
        raise HTTPException(status_code=500, detail="Could not load status manifold.")

    squad = status.get("squad", [])
    new_squad = [m for m in squad if m.get("name") != req.name]

    if len(new_squad) == len(squad):
        return {
            "status": "success",
            "message": f"{req.name} is not in the active squad.",
            "squad": squad,
        }

    status["squad"] = new_squad
    with open(STATUS_PATH, "w", encoding="utf-8-sig") as f:
        json.dump(status, f, indent=4, ensure_ascii=False)

    try:
        from services.sync_engine import sync_status_to_today_journal

        sync_status_to_today_journal()
    except Exception as e:
        print(f"Failed to sync journal on status update: {e}")

    return {
        "status": "success",
        "message": f"{req.name} recalled to reserve.",
        "squad": new_squad,
    }


@app.post("/api/realm/hop")
async def execute_realm_hop_endpoint(req: RealmHopRequest):
    from services.moongate import execute_realm_hop

    try:
        res = execute_realm_hop(req.realm_name, req.squad_names)
        return res
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error executing realm hop: {str(e)}"
        )


@app.get("/api/realm/options")
async def get_realm_options():
    import random

    # 1. Context
    status = load_json(STATUS_PATH) or {"current_realm": "Unknown"}
    current_realm = status.get("current_realm", "Unknown")

    stats_path = os.path.join(NAVIS_ROOT, "Bridge", "realm_stats.json")
    history = (load_json(stats_path) or {}).get("history", [])

    # 2. Exclusions
    exclusions = [current_realm]
    unique_history = []
    for w in reversed(history):
        if w not in unique_history and w != current_realm:
            unique_history.append(w)
        if len(unique_history) >= 3:
            break
    exclusions.extend(unique_history)

    # 3. Read realms
    realms_root = os.path.join(NAVIS_ROOT, "Realms")
    all_realms = {}
    if os.path.exists(realms_root):
        for realm_name in os.listdir(realms_root):
            if realm_name.startswith(".") or realm_name.lower() == "default":
                continue
            realm_path = os.path.join(realms_root, realm_name)
            if os.path.isdir(realm_path):
                desc = "A mysterious realm."
                json_path = os.path.join(realm_path, "realm_data.json")
                if os.path.exists(json_path):
                    try:
                        data = load_json(json_path)
                        if data and "description" in data:
                            desc = data["description"]
                    except:
                        pass
                else:
                    realm_md = os.path.join(realm_path, "Realm.md")
                    if os.path.exists(realm_md):
                        with open(realm_md, "r", encoding="utf-8-sig") as f:
                            content = f.read()
                            lore_match = re.search(
                                r"## 📜 LORE\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL
                            )
                            if lore_match:
                                desc = lore_match.group(1).strip().rstrip("-").strip()
                            elif re.search(
                                r"## 📜 Realm Overview\s*\n(.*?)(?=\n##|\Z)",
                                content,
                                re.DOTALL,
                            ):
                                desc = (
                                    re.search(
                                        r"## 📜 Realm Overview\s*\n(.*?)(?=\n##|\Z)",
                                        content,
                                        re.DOTALL,
                                    )
                                    .group(1)
                                    .strip()
                                    .rstrip("-")
                                    .strip()
                                )
                all_realms[realm_name] = desc

    available = [r for r in all_realms.keys() if r not in exclusions]
    if not available:
        available = [r for r in all_realms.keys() if r != current_realm]

    options = random.sample(available, min(len(available), 3))

    result = []
    for opt in options:
        result.append(
            {
                "name": opt,
                "description": all_realms.get(opt, "Unknown Realm"),
                "image": f"/api/vault/Realms/{opt}/Landscape.png",
            }
        )

    return result


@app.get("/api/realm/draft")
async def get_realm_draft(realm_name: str):
    import random

    realms_root = os.path.join(NAVIS_ROOT, "Realms")
    realm_path = os.path.join(realms_root, realm_name)
    if not os.path.exists(realm_path):
        raise HTTPException(status_code=404, detail="Realm not found.")

    realm_tags = []
    natives = []
    json_path = os.path.join(realm_path, "realm_data.json")
    if os.path.exists(json_path):
        try:
            data = load_json(json_path)
            if data:
                realm_tags = data.get("tags", [])
                natives = data.get("natives", [])
        except:
            pass

    if not realm_tags and not natives:
        realm_md = os.path.join(realm_path, "Realm.md")
        if os.path.exists(realm_md):
            with open(realm_md, "r", encoding="utf-8-sig") as f:
                content = f.read()
                tag_match = re.search(r"## 🏷️ TAGS\s*\n`(.*?)`", content, re.IGNORECASE)
                if not tag_match:
                    tag_match = re.search(
                        r"## 🏷️ Tags\s*\n`(.*?)`", content, re.IGNORECASE
                    )
                if tag_match:
                    realm_tags = [
                        t.strip()
                        for t in tag_match.group(1).replace("`", "").split(",")
                    ]

                native_section_match = re.search(
                    r"## 🛡️ Native Guides\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL
                )
                if native_section_match:
                    section_content = native_section_match.group(1)
                    for line in section_content.split("\n"):
                        name_match = re.search(
                            r"\*\*.*?(?:Guide|Companion):\*\*\s*\[?\[?(.*?)\]?\]?", line
                        )
                        if name_match:
                            natives.append(name_match.group(1).strip())
                        elif "-" in line and "[" in line and "]" in line:
                            name_match = re.search(
                                r"\]\s*(?:\*\*?)?(.*?)(?:\*\*?)?$", line
                            )
                            if name_match:
                                name = name_match.group(1).strip()
                                if name:
                                    natives.append(name)

                thematic_match = re.search(
                    r"\*(?:Companions like )?(.*?) (?:is the primary guide|are the primary guides|finds? deep resonance|serves? as the primary guide)",
                    content,
                    re.IGNORECASE,
                )
                if thematic_match:
                    found_names = thematic_match.group(1)
                    for part in re.split(r" and |, | & ", found_names):
                        natives.append(part.strip())

    natives = list(set([n for n in natives if n]))

    comp_dir = os.path.join(NAVIS_ROOT, "Companions")
    stats_path = os.path.join(NAVIS_ROOT, "Bridge", "CompanionStats.json")
    xp_data = (load_json(stats_path) or {}).get("companions", {})

    comp_data = {}
    if os.path.exists(comp_dir):
        for name in os.listdir(comp_dir):
            if name.startswith("."):
                continue
            comp_path = os.path.join(comp_dir, name)
            if os.path.isdir(comp_path):
                data = {
                    "tags": [],
                    "xp": xp_data.get(name, {}).get("xp", 0),
                    "role": "Active Personnel",
                }
                json_path = os.path.join(comp_path, "companion_data.json")
                if os.path.exists(json_path):
                    try:
                        cdata = load_json(json_path)
                        if cdata:
                            data["tags"] = cdata.get("tags", [])
                            data["role"] = cdata.get("role", "Active Personnel")
                    except:
                        pass
                else:
                    profile_path = os.path.join(comp_path, "Profile.md")
                    if os.path.exists(profile_path):
                        with open(profile_path, "r", encoding="utf-8-sig") as f:
                            content = f.read()
                            tag_match = re.search(
                                r"## 🏷️ TAGS\s*\n`(.*?)`", content, re.IGNORECASE
                            )
                            if not tag_match:
                                tag_match = re.search(
                                    r"## 🏷️ Tags\s*\n`(.*?)`", content, re.IGNORECASE
                                )
                            if tag_match:
                                data["tags"] = [
                                    t.strip()
                                    for t in tag_match.group(1)
                                    .replace("`", "")
                                    .split(",")
                                ]
                            role_match = re.search(r"- \*\*Role:\*\* (.*?)\n", content)
                            if role_match:
                                data["role"] = role_match.group(1).strip()
                comp_data[name] = data

    def calc_synergy(ctags, rtags):
        score = 0
        genres = ["Fantasy", "Science Fiction", "Historical", "Eldritch", "Modern"]
        for t in ctags:
            if t in rtags:
                score += 2 if t in genres else 1
        return score

    for name in comp_data:
        comp_data[name]["synergy"] = calc_synergy(comp_data[name]["tags"], realm_tags)

    native_name = next((n for n in natives if n in comp_data), None)
    if native_name:
        captain = native_name
    else:
        scores = {n: d["synergy"] for n, d in comp_data.items()}
        if scores:
            max_score = max(scores.values())
            winners = [n for n, s in scores.items() if s == max_score]
            captain = random.choice(winners)
        else:
            captain = random.choice(list(comp_data.keys())) if comp_data else "Unknown"

    remaining = [n for n in comp_data.keys() if n != captain]
    low_xp = sorted(
        remaining, key=lambda x: (comp_data[x]["xp"], -comp_data[x]["synergy"])
    )

    choices = []
    choices.extend(low_xp[:2])
    rest = [n for n in remaining if n not in choices]
    high_synergy = sorted(rest, key=lambda x: comp_data[x]["synergy"], reverse=True)
    choices.extend(high_synergy[:3])

    draft_pool = []
    for name in choices:
        draft_pool.append(
            {
                "name": name,
                "role": comp_data[name]["role"],
                "xp": comp_data[name]["xp"],
                "synergy": comp_data[name]["synergy"],
                "tags": comp_data[name]["tags"],
            }
        )

    return {
        "vanguard": {
            "name": captain,
            "role": comp_data.get(captain, {}).get("role", "Vanguard"),
            "synergy": comp_data.get(captain, {}).get("synergy", 0),
        },
        "draft_pool": draft_pool,
    }


# Task areas use lowercase storage keys; both query and stored legacy aliases
# are normalized. Unknown areas remain usable as trimmed lowercase names.
def canonical_task_area(area):
    value = area.strip().lower()
    return {"gauntlet": "bureaucratic", "outland": "world"}.get(value, value)


def filter_task_area(tasks, area):
    if not area or not area.strip():
        return tasks
    return [t for t in tasks if canonical_task_area(t.get("area", "")) == canonical_task_area(area)]


def unique_task_id(state):
    import uuid
    existing = {t.get("id") for key in ("tasks", "active_tasks") for t in state.get(key, [])}
    while True:
        candidate = str(uuid.uuid4())
        if candidate not in existing:
            return candidate


def require_unique_task(tasks, task_id):
    matches = [t for t in tasks if t.get("id") == task_id]
    if len(matches) > 1:
        raise HTTPException(status_code=409, detail="Ambiguous duplicate task ID; repair IDs before mutation")
    if not matches:
        raise HTTPException(status_code=404, detail="Task not found")
    return matches[0]


def recurring_task_view(task):
    # Persist only next_due so sweep/native readers retain one schedule.
    return {**task, "due_date": task.get("next_due")}


# --- Recurring Tasks API ---
def get_ops_state_path():
    return os.path.join(NAVIS_ROOT, "Bridge", "ops_state.json")




@app.get("/api/recurring")
async def get_recurring_tasks(area: Optional[str] = None):
    ops_path = get_ops_state_path()
    if not os.path.exists(ops_path):
        return []
    state = load_json(ops_path) or {}
    tasks = state.get("tasks", [])
    return [recurring_task_view(task) for task in filter_task_area(tasks, area)]


@app.post("/api/recurring")
async def create_recurring_task(req: RecurringTaskCreate):
    due = req.due_date if req.due_date is not None else req.next_due
    if due is None:
        due = journal_day()
    try:
        calculate_next_due(req.frequency, due)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    ops_path = get_ops_state_path()
    state = load_json(ops_path) if os.path.exists(ops_path) else {"tasks": []}

    new_task = {
        "id": unique_task_id(state),
        "text": req.text,
        "frequency": req.frequency,
        "area": canonical_task_area(req.area),
        "last_done": None,
        "next_due": due,
        **task_metadata(req),
    }
    state.setdefault("tasks", []).append(new_task)
    with open(ops_path, "w", encoding="utf-8-sig") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)
    return {"status": "success", "task": recurring_task_view(new_task)}


@app.put("/api/recurring/{task_id}")
async def update_recurring_task(task_id: str, req: RecurringTaskUpdate):
    ops_path = get_ops_state_path()
    if not os.path.exists(ops_path):
        raise HTTPException(status_code=404, detail="ops_state.json not found")
    state = load_json(ops_path)

    require_unique_task(state.get("tasks", []), task_id)
    for t in state.get("tasks", []):
        if t.get("id") == task_id:
            if req.text is not None:
                t["text"] = req.text
            if req.frequency is not None:
                t["frequency"] = req.frequency
            if req.area is not None:
                t["area"] = canonical_task_area(req.area)

            try:
                calculate_next_due(t["frequency"], req.last_done or t.get("last_done") or journal_day())
                if req.last_done is not None:
                    t["last_done"] = req.last_done
                    t["next_due"] = calculate_next_due(t["frequency"], t["last_done"])
                elif req.due_date is not None or req.next_due is not None:
                    due = req.due_date or req.next_due
                    validate_date(due)
                    t["next_due"] = due
                elif req.frequency is not None and t.get("last_done"):
                    t["next_due"] = calculate_next_due(t["frequency"], t["last_done"])
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error

            update_task_metadata(t, req)
            with open(ops_path, "w", encoding="utf-8-sig") as f:
                json.dump(state, f, indent=4, ensure_ascii=False)
            return {"status": "success", "task": recurring_task_view(t)}

    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/api/recurring/{task_id}")
async def delete_recurring_task(task_id: str):
    ops_path = get_ops_state_path()
    if not os.path.exists(ops_path):
        raise HTTPException(status_code=404, detail="ops_state.json not found")
    state = load_json(ops_path)

    require_unique_task(state.get("tasks", []), task_id)
    original_count = len(state.get("tasks", []))
    state["tasks"] = [t for t in state.get("tasks", []) if t.get("id") != task_id]

    if len(state["tasks"]) == original_count:
        raise HTTPException(status_code=404, detail="Task not found")

    with open(ops_path, "w", encoding="utf-8-sig") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)
    return {"status": "success"}


@app.post("/api/recurring/{task_id}/complete")
async def complete_recurring_task(task_id: str):
    from services.directive_completion import complete_recurring
    try:
        result = complete_recurring(NAVIS_ROOT, task_id)
        if "task" in result:
            result["task"] = recurring_task_view(result["task"])
        return result
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail="Completion interrupted; retry Mark Done to recover") from error


# --- Active Tasks API ---
@app.get("/api/active_tasks")
async def get_active_tasks(area: Optional[str] = None):
    ops_path = get_ops_state_path()
    if not os.path.exists(ops_path):
        return []
    state = load_json(ops_path) or {}
    tasks = [t for t in state.get("active_tasks", []) if t.get("status") != "completed"]
    return filter_task_area(tasks, area)


@app.post("/api/active_tasks")
async def create_active_task(req: ActiveTaskCreate):
    from datetime import datetime

    ops_path = get_ops_state_path()
    state = load_json(ops_path) if os.path.exists(ops_path) else {}
    if "active_tasks" not in state:
        state["active_tasks"] = []

    new_task = {
        "id": unique_task_id(state),
        "text": req.text,
        "area": canonical_task_area(req.area),
        "status": "pending",
        **task_metadata(req),
        "due_date": req.due_date,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    state["active_tasks"].append(new_task)
    with open(ops_path, "w", encoding="utf-8-sig") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)
    return {"status": "success", "task": new_task}


@app.post("/api/active_tasks/{task_id}/complete")
async def complete_active_task(task_id: str):
    from services.directive_completion import complete
    try:
        return complete(NAVIS_ROOT, task_id)
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail="Completion interrupted; retry Mark Done to recover") from error


@app.put("/api/active_tasks/{task_id}")
async def update_active_task(task_id: str, req: ActiveTaskUpdate):
    ops_path = get_ops_state_path()
    if not os.path.exists(ops_path):
        raise HTTPException(status_code=404, detail="ops_state.json not found")
    state = load_json(ops_path)

    require_unique_task(state.get("active_tasks", []), task_id)
    if any(t.get("id") == task_id and t.get("completion") for t in state.get("active_tasks", [])):
        raise HTTPException(status_code=409, detail="Completion history is immutable")
    for t in state.get("active_tasks", []):
        if t.get("id") == task_id:
            if req.text is not None:
                t["text"] = req.text
            if req.area is not None:
                t["area"] = canonical_task_area(req.area)
            if req.status is not None:
                if req.status != t.get("status", "pending"):
                    raise HTTPException(status_code=409, detail="Use the explicit completion transition")

            if "due_date" in req.model_fields_set:
                t["due_date"] = req.due_date
            update_task_metadata(t, req)
            with open(ops_path, "w", encoding="utf-8-sig") as f:
                json.dump(state, f, indent=4, ensure_ascii=False)
            return {"status": "success", "task": t}

    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/api/active_tasks/{task_id}")
async def delete_active_task(task_id: str):
    ops_path = get_ops_state_path()
    if not os.path.exists(ops_path):
        raise HTTPException(status_code=404, detail="ops_state.json not found")
    state = load_json(ops_path)

    require_unique_task(state.get("active_tasks", []), task_id)
    if any(t.get("id") == task_id and t.get("completion") for t in state.get("active_tasks", [])):
        raise HTTPException(status_code=409, detail="Completion history cannot be deleted")
    original_count = len(state.get("active_tasks", []))
    state["active_tasks"] = [
        t for t in state.get("active_tasks", []) if t.get("id") != task_id
    ]

    if len(state.get("active_tasks", [])) == original_count:
        raise HTTPException(status_code=404, detail="Task not found")

    with open(ops_path, "w", encoding="utf-8-sig") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)
    return {"status": "success"}


# --- 4-Fold Navigation Sector Map ---
SECTOR_MAP = {
    "COMMAND": [
        {"id": "STATUS", "label": "Status", "icon": "📡"},
        {"id": "DIRECTIVES", "label": "Directives", "icon": "📋"},
        {"id": "PARTY", "label": "Party", "icon": "🛡️"},
        {"id": "REALM_HOP", "label": "Realm Hop", "icon": "🌀"},
        {"id": "COMBAT", "label": "Combat Theater", "icon": "⚔️"},
        {"id": "WORLD_MAP", "label": "World Map", "icon": "🗺️"},
    ],
    "SANCTUM": [
        {"id": "SANCTUM", "label": "Operation", "icon": "🛡️"},
        {"id": "TASKS:The Sanctum", "label": "Tasks", "icon": "📋"},
        {"id": "RECURRING:The Sanctum", "label": "Recurring", "icon": "🔄"},
        {"id": "MISSIONS:The Sanctum", "label": "Missions", "icon": "🚩"},
    ],
    "DOMESTIC": [
        {"id": "DOMESTIC", "label": "Operation", "icon": "🏠"},
        {"id": "TASKS:The Domestic Breach", "label": "Tasks", "icon": "📋"},
        {"id": "RECURRING:The Domestic Breach", "label": "Recurring", "icon": "🔄"},
        {"id": "MISSIONS:The Domestic Breach", "label": "Missions", "icon": "🚩"},
    ],
    "FRONT": [
        {"id": "FRONT", "label": "Operation", "icon": "⚔️"},
        {"id": "TASKS:The High-Velocity Front", "label": "Tasks", "icon": "📋"},
        {"id": "RECURRING:The High-Velocity Front", "label": "Recurring", "icon": "🔄"},
        {"id": "MISSIONS:The High-Velocity Front", "label": "Missions", "icon": "🚩"},
    ],
    "GAUNTLET": [
        {"id": "GAUNTLET", "label": "Operation", "icon": "⚖️"},
        {"id": "TASKS:The Bureaucratic Gauntlet", "label": "Tasks", "icon": "📋"},
        {
            "id": "RECURRING:The Bureaucratic Gauntlet",
            "label": "Recurring",
            "icon": "🔄",
        },
        {"id": "MISSIONS:The Bureaucratic Gauntlet", "label": "Missions", "icon": "🚩"},
    ],
    "OUTLAND": [
        {"id": "OUTLAND", "label": "Operation", "icon": "🧭"},
        {"id": "TASKS:The Kinetic Outland", "label": "Tasks", "icon": "📋"},
        {"id": "RECURRING:The Kinetic Outland", "label": "Recurring", "icon": "🔄"},
        {"id": "MISSIONS:The Kinetic Outland", "label": "Missions", "icon": "🚩"},
    ],
    "LAB": [{"id": "SYNTHESIS_LAB", "label": "Synthesis Lab", "icon": "🧪"}],
    "PRISM": [{"id": "PRISM_NEXUS", "label": "Lounge", "icon": "🧋"}],
    "REFLECTION": [{"id": "REFLECTION_CHAMBER", "label": "Friðr Hall", "icon": "🧠"}],
    "IRON": [{"id": "IRON_SANCTUM", "label": "Iron Sanctum", "icon": "💪"}],
    "LIBRARY": [{"id": "LIBRARY", "label": "Library", "icon": "📚"}],
    "CHRONICLE": [
        {"id": "JOURNAL", "label": "Daily Journal", "icon": "🗓️"},
        {"id": "KEEPER", "label": "Keeper Ledger", "icon": "👑"},
        {"id": "HOLOCRON", "label": "Weekly Holocron", "icon": "💠"},
    ],
    "CODEX": [
        {"id": "COMPANIONS", "label": "Companions", "icon": "🛡️"},
        {"id": "RESIDENTS", "label": "Residents", "icon": "👥"},
        {"id": "ANTAGONISTS", "label": "Antagonists", "icon": "💀"},
        {"id": "BEASTS", "label": "Beasts", "icon": "👾"},
        {"id": "REALMS", "label": "Realms", "icon": "🌌"},
        {"id": "ARCHIVE", "label": "Archive", "icon": "📖"},
    ],
    "SYSTEM": [
        {"id": "CONFIG", "label": "Config", "icon": "⚙️"},
        {"id": "NEURAL", "label": "Neural", "icon": "🧠"},
        {"id": "MAINTENANCE", "label": "Maintenance", "icon": "🛰️"},
    ],
}


def to_rel_path(abs_path):
    p = abs_path.replace("\\", "/")

    # 1. Check if the path contains the repository marker "Navis-Vault/"
    marker = "Navis-Vault/"
    if marker in p:
        rel = p.split(marker, 1)[1]
    else:
        # 2. Check if it starts with the normalized NAVIS_ROOT
        navis_root_norm = NAVIS_ROOT.replace("\\", "/")
        if p.startswith(navis_root_norm):
            rel = p[len(navis_root_norm) :].lstrip("/")
        else:
            # 3. Fallback to os.path.relpath
            try:
                rel = os.path.relpath(p, navis_root_norm).replace("\\", "/")
            except Exception:
                rel = p

    if rel.startswith("./"):
        rel = rel[2:]
    return rel


@app.get("/api/navigation/pillars")
async def get_navigation_pillars():
    settings = load_json(SETTINGS_PATH)
    pillars = settings.get("lexicon", {}).get("pillars", {})

    result = []
    for key, label in pillars.items():
        result.append(
            {
                "id": key,
                "label": label,
                "icon": get_icon_for_pillar(key),
                "sectors": SECTOR_MAP.get(key, []),
            }
        )
    return result


def _list_keeper_entities():
    if not os.path.isdir(NAVIS_ROOT):
        raise HTTPException(status_code=503, detail="Configured Vault root is unavailable.")
    keeper_dir = os.path.join(NAVIS_ROOT, "Keeper")
    if not os.path.isdir(keeper_dir):
        raise HTTPException(status_code=404, detail="Keeper source directory is unavailable.")
    try:
        return [
            {"id": f"Keeper/{item}", "name": item[:-3], "type": "file"}
            for item in sorted(os.listdir(keeper_dir))
            if item.endswith(".md") and os.path.isfile(os.path.join(keeper_dir, item))
        ]
    except OSError as error:
        raise HTTPException(status_code=503, detail="Keeper source directory could not be read.") from error


@app.get("/api/entities")
async def get_entities(sectorId: str):
    if sectorId == "KEEPER":
        return _list_keeper_entities()

    cache_path = os.path.join(NAVIS_ROOT, "Bridge", ".navis_cache", "sector_cache.json")
    if not os.path.exists(cache_path):
        from services.cache_builder import build_sector_cache

        cache = build_sector_cache(NAVIS_ROOT)
    else:
        cache = load_json(cache_path)

    entities = []

    # 1. Mission Regions
    if sectorId.startswith("MISSIONS:"):
        prefix, region = sectorId.split(":", 1)
        main_missions = cache.get("sectors", {}).get("MISSIONS", {}).get("Main", [])
        side_missions = cache.get("sectors", {}).get("MISSIONS", {}).get("Side", [])

        filtered_main = [m for m in main_missions if m.get("region") == region]
        filtered_side = [m for m in side_missions if m.get("region") == region]

        entities.append({"id": "QUEST_BOARD", "name": "Quest Board", "type": "virtual"})

        for m in filtered_main:
            entities.append(
                {
                    "id": to_rel_path(m["path"]),
                    "name": m["name"],
                    "type": "file",
                    "mission_type": "Main",
                }
            )

        for m in filtered_side:
            entities.append(
                {
                    "id": to_rel_path(m["path"]),
                    "name": m["name"],
                    "type": "file",
                    "mission_type": "Side",
                }
            )

    # 1.5 Recurring View
    elif sectorId.startswith("RECURRING:"):
        prefix, region = sectorId.split(":", 1)
        # Convert region to area
        area_map = {
            "The Sanctum": "Sanctum",
            "The Domestic Breach": "Domestic",
            "The High-Velocity Front": "Front",
            "The Bureaucratic Gauntlet": "Gauntlet",
            "The Kinetic Outland": "Outland",
        }
        area = area_map.get(region, region)
        entities.append(
            {
                "id": f"RECURRING_BOARD:{area}",
                "name": "Recurring Protocols",
                "type": "virtual",
            }
        )

    # 1.6 Tasks View
    elif sectorId.startswith("TASKS:"):
        prefix, region = sectorId.split(":", 1)
        area_map = {
            "The Sanctum": "Sanctum",
            "The Domestic Breach": "Domestic",
            "The High-Velocity Front": "Front",
            "The Bureaucratic Gauntlet": "Gauntlet",
            "The Kinetic Outland": "Outland",
        }
        area = area_map.get(region, region)
        entities.append(
            {
                "id": f"TASKS_BOARD:{area}",
                "name": "Active Directives",
                "type": "virtual",
            }
        )

    # 2. Config
    elif sectorId == "CONFIG":
        settings = load_json(SETTINGS_PATH)
        for key in sorted(list(settings.keys())):
            entities.append(
                {
                    "id": f"CONFIG:{key}",
                    "name": key.replace("_", " ").title(),
                    "type": "virtual",
                }
            )

    # 3. Party
    elif sectorId == "PARTY":
        entities = [
            {"id": "BANTER", "name": "Banter Feed", "type": "virtual"},
            {"id": "WAR_ROOM", "name": "War Room", "type": "virtual"},
            {"id": "XP", "name": "XP Manifold", "type": "virtual"},
        ]

    # 4. Roster
    elif sectorId == "ROSTER":
        entities = [
            {"id": "RESERVE_ROSTER", "name": "Reserve Roster", "type": "virtual"}
        ]

    # 6. Status
    elif sectorId == "STATUS":
        entities = [
            {"id": "STATUS_HUD", "name": "System HUD", "type": "virtual"},
            {"id": "STATUS_NEWS", "name": "Daily Briefing", "type": "virtual"},
            {"id": "STATUS_TASKS", "name": "Task Checklist", "type": "virtual"},
        ]

    # 6.5 Directives Cockpit
    elif sectorId in ("DIRECTIVES", "TASKS"):
        entities = [
            {"id": "TASKS_COCKPIT", "name": "Directives Cockpit", "type": "virtual"}
        ]

    # 7. Prism Nexus
    elif sectorId == "PRISM_NEXUS":
        entities = [{"id": "PRISM_NEXUS", "name": "Boba Lounge", "type": "virtual"}]

    # 8. Combat
    elif sectorId == "COMBAT":
        entities = [
            {"id": "BATTLE", "name": "Battle Field", "type": "virtual"},
            {"id": "TACTICAL_COCKPIT", "name": "Tactical Cockpit", "type": "virtual"},
        ]

    elif sectorId == "WORLD_MAP":
        entities = [{"id": "WORLD_MAP", "name": "World Map", "type": "virtual"}]

    # 10. Cache based direct categories
    elif sectorId == "COMPANIONS":
        comps = cache.get("sectors", {}).get("COMPANIONS", {}).get("Companions", [])
        entities.append(
            {"id": "CODEX_BOARD", "name": "Companions Codex", "type": "virtual"}
        )
        for m in comps:
            entities.append(
                {"id": to_rel_path(m["path"]), "name": m["name"], "type": "directory"}
            )
    elif sectorId == "RESIDENTS":
        res = cache.get("sectors", {}).get("RESIDENTS", {}).get("Residents", [])
        entities.append(
            {"id": "CODEX_BOARD", "name": "Residents Codex", "type": "virtual"}
        )
        for m in res:
            entities.append(
                {"id": to_rel_path(m["path"]), "name": m["name"], "type": "directory"}
            )
    elif sectorId == "ANTAGONISTS":
        ants = cache.get("sectors", {}).get("OBSTACLES", {}).get("Antagonists", [])
        entities.append(
            {"id": "CODEX_BOARD", "name": "Antagonists Codex", "type": "virtual"}
        )
        for m in ants:
            entities.append(
                {"id": to_rel_path(m["path"]), "name": m["name"], "type": "directory"}
            )
    elif sectorId == "BEASTS":
        beasts = cache.get("sectors", {}).get("OBSTACLES", {}).get("Beasts", [])
        entities.append(
            {"id": "CODEX_BOARD", "name": "Beasts Codex", "type": "virtual"}
        )
        for m in beasts:
            entities.append(
                {"id": to_rel_path(m["path"]), "name": m["name"], "type": "directory"}
            )
    elif sectorId == "REALMS":
        realms = cache.get("sectors", {}).get("REALMS", {}).get("Discoveries", [])
        entities.append(
            {"id": "CODEX_BOARD", "name": "Realms Codex", "type": "virtual"}
        )
        for m in realms:
            entities.append(
                {"id": to_rel_path(m["path"]), "name": m["name"], "type": "directory"}
            )
    elif sectorId == "REALM_HOP":
        entities = [
            {"id": "REALM_HOP_MODAL", "name": "Moongate Protocol", "type": "virtual"}
        ]
    elif sectorId == "SYNTHESIS_LAB":
        labs = cache.get("sectors", {}).get("SYNTHESIS_LAB", {}).get("Archival", [])
        for m in labs:
            entities.append(
                {"id": to_rel_path(m["path"]), "name": m["name"], "type": "file"}
            )
    elif sectorId == "REFLECTION_CHAMBER":
        entities.append(
            {"id": "REFLECTION_CHAMBER", "name": "Friðr Hall", "type": "virtual"}
        )
        refs = cache.get("sectors", {}).get("REFLECTION_CHAMBER", {}).get("Mental", [])
        for m in refs:
            entities.append(
                {
                    "id": to_rel_path(m["path"]),
                    "name": m["name"],
                    "type": m.get("type", "file"),
                }
            )
    elif sectorId == "IRON_SANCTUM":
        entities.append(
            {"id": "IRON_SANCTUM", "name": "Iron Sanctum", "type": "virtual"}
        )
        iron = cache.get("sectors", {}).get("IRON_SANCTUM", {}).get("Physical", [])
        for m in iron:
            if m["name"] == "Vitals" or "Vitals.md" in m["path"]:
                continue
            entities.append(
                {
                    "id": to_rel_path(m["path"]),
                    "name": m["name"],
                    "type": m.get("type", "file"),
                }
            )

    # 11. Archive
    elif sectorId == "ARCHIVE":
        archives_dir = os.path.join(NAVIS_ROOT, "Archives")
        if os.path.exists(archives_dir):
            for item in sorted(os.listdir(archives_dir)):
                if item.endswith(".md"):
                    entities.append(
                        {
                            "id": f"Archives/{item}",
                            "name": item.replace(".md", ""),
                            "type": "file",
                        }
                    )

    # 12. Library
    elif sectorId == "LIBRARY":
        entities.append(
            {"id": "LIBRARY_DASHBOARD", "name": "Zettelkasten Nexus", "type": "virtual"}
        )

    # 13b. Weekly Holocron
    elif sectorId == "HOLOCRON":
        from services.holocron_engine import get_holocron_manifest
        manifest = get_holocron_manifest(NAVIS_ROOT)
        for item in manifest:
            wid = item.get("week_id")
            entities.append(
                {
                    "id": f"Holocron/{wid}",
                    "name": f"Cycle {wid}",
                    "type": "holocron",
                    "week_id": wid,
                    "precision": item.get("precision_rate", 0),
                }
            )

    # 14. Gallery
    elif sectorId == "GALLERY":
        gallery_dir = os.path.join(NAVIS_ROOT, "Chronicle", "Gallery")
        if not os.path.exists(gallery_dir):
            gallery_dir = os.path.join(NAVIS_ROOT, "Chronicle")
        if os.path.exists(gallery_dir):
            for root, dirs, files in os.walk(gallery_dir):
                for f in files:
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                        p = os.path.join(root, f)
                        entities.append(
                            {"id": to_rel_path(p), "name": f, "type": "image"}
                        )

    # 15. Journal (list recent journals)
    elif sectorId == "JOURNAL":
        recent = await get_recent_journals()
        for r in recent:
            entities.append({"id": r["path"], "name": r["date"], "type": "file"})

    # 16. Operations folders: SANCTUM, DOMESTIC, FRONT, GAUNTLET, OUTLAND
    elif sectorId in ["SANCTUM", "DOMESTIC", "FRONT", "GAUNTLET", "OUTLAND"]:
        folder_map = {
            "SANCTUM": "The Sanctum",
            "DOMESTIC": "The Domestic Breach",
            "FRONT": "The High-Velocity Front",
            "GAUNTLET": "The Bureaucratic Gauntlet",
            "OUTLAND": "The Kinetic Outland",
        }
        folder_name = folder_map.get(sectorId)
        base_path = os.path.join(NAVIS_ROOT, "Operations", folder_name)
        if os.path.exists(base_path):
            excluded_dirs = ["Main", "Side", "Archive"]
            for item in sorted(os.listdir(base_path)):
                item_path = os.path.join(base_path, item)
                if (
                    (os.path.isdir(item_path) or item.endswith(".md"))
                    and not item.startswith(".")
                    and item not in excluded_dirs
                    and item not in ["Recurring.md", "Tasks.md"]
                ):
                    if item.endswith(".md"):
                        entities.append(
                            {
                                "id": to_rel_path(item_path),
                                "name": item.replace(".md", ""),
                                "type": "file",
                            }
                        )
                    else:
                        profile_md = os.path.join(item_path, "Profile.md")
                        if os.path.exists(profile_md):
                            entities.append(
                                {
                                    "id": to_rel_path(profile_md),
                                    "name": item,
                                    "type": "file",
                                }
                            )

    # 17. Neural Arbiter virtual view
    elif sectorId == "NEURAL":
        entities = [
            {"id": "NEURAL_CHAT", "name": "Cognitive Arbiter", "type": "virtual"}
        ]
    if sectorId == "JOURNAL":
        return entities

    def sort_key(x):
        if x.get("type") == "virtual":
            return (0, x.get("name", ""))
        is_profile = (
            str(x.get("id", "")).endswith("Profile.md")
            or x.get("name", "").lower() == "profile"
        )
        priority = 1 if is_profile else 2
        return (priority, x.get("name", ""))

    return sorted(entities, key=sort_key)


def rewrite_image_links(content: str, parent_dir: str) -> str:
    from urllib.parse import quote, unquote

    # 1. Wiki-links: ![[Portrait.png|portrait]] or ![[Portrait.png]]
    def wiki_replacer(match):
        img_name = unquote(match.group(1).strip())
        if "|" in img_name:
            img_name, label = img_name.split("|", 1)
        else:
            label = "portrait"

        if img_name.startswith(("http://", "https://", "/")):
            return f"![{label}]({img_name})"

        rel_img_path = os.path.join(parent_dir, img_name).replace("\\", "/")
        # Cache busting timestamp
        t_param = ""
        try:
            abs_img_path = os.path.join(NAVIS_ROOT, rel_img_path.replace("/", os.sep))
            if os.path.exists(abs_img_path):
                t_param = f"?t={int(os.path.getmtime(abs_img_path))}"
        except Exception as e:
            print(f"DEBUG: Error getting mtime for {rel_img_path}: {e}")

        quoted_path = quote(rel_img_path)
        return f"![{label}](/api/vault/{quoted_path}{t_param})"

    content = re.sub(r"!\[\[([^\]]+)\]\]", wiki_replacer, content)

    # 2. Standard markdown images: ![caption](image.png)
    def md_replacer(match):
        caption = match.group(1)
        img_path = unquote(match.group(2).strip())
        if img_path.startswith(("http://", "https://", "/", "data:")):
            return match.group(0)

        rel_img_path = os.path.join(parent_dir, img_path).replace("\\", "/")
        # Cache busting timestamp
        t_param = ""
        try:
            abs_img_path = os.path.join(NAVIS_ROOT, rel_img_path.replace("/", os.sep))
            if os.path.exists(abs_img_path):
                t_param = f"?t={int(os.path.getmtime(abs_img_path))}"
        except Exception as e:
            print(f"DEBUG: Error getting mtime for {rel_img_path}: {e}")

        quoted_path = quote(rel_img_path)
        return f"![{caption}](/api/vault/{quoted_path}{t_param})"

    content = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", md_replacer, content)
    return content


@app.get("/api/entity/{entity_type}/{entity_name}")
def get_entity_profile(entity_type: str, entity_name: str):
    """
    Parses a Vault markdown file for an entity and returns structured data.
    """
    valid_types = {"Companions", "Residents", "Realms", "Antagonists", "Beasts"}

    # Map singular to plural if needed
    type_map = {
        "companion": "Companions",
        "resident": "Residents",
        "realm": "Realms",
        "antagonist": "Antagonists",
        "beast": "Beasts",
    }

    mapped_type = type_map.get(entity_type.lower(), entity_type)
    if mapped_type not in valid_types:
        raise HTTPException(status_code=400, detail="Invalid entity type")

    base_folder = mapped_type
    if mapped_type in ["Antagonists", "Beasts"]:
        base_folder = f"Obstacles/{mapped_type}"

    entity_dir = resolve_vault_path(f"{base_folder}/{entity_name}")
    if not os.path.exists(entity_dir):
        # try splitting name
        entity_dir = resolve_vault_path(f"{base_folder}/{entity_name.split(' ')[0]}")
        if not os.path.exists(entity_dir):
            raise HTTPException(
                status_code=404, detail=f"Entity not found: {entity_dir}"
            )

    # For Realms it might be Realm.md, for others Profile.md
    file_name = "Realm.md" if mapped_type == "Realms" else "Profile.md"
    file_path = os.path.join(entity_dir, file_name)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Profile not found")

    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            content = f.read()

        # Very basic parsing
        lines = content.split("\n")

        attributes = {}
        lore_sections = []
        current_section = None
        current_text = []

        in_frontmatter = False

        for line in lines:
            if (
                line.startswith("---")
                and not in_frontmatter
                and not attributes
                and not lore_sections
            ):
                in_frontmatter = True
                continue
            if line.startswith("---") and in_frontmatter:
                in_frontmatter = False
                continue

            if in_frontmatter:
                continue

            if line.startswith("## "):
                if current_section:
                    lore_sections.append(
                        {
                            "title": current_section,
                            "content": "\n".join(current_text).strip(),
                        }
                    )
                current_section = line[3:].strip()
                current_text = []
            elif line.startswith("---") and current_section:
                # end of section via hr
                pass
            elif not current_section:
                # parsing attributes
                match = re.match(r"^- \*\*(.*?):\*\*\s*(.*)", line)
                if match:
                    attributes[match.group(1).strip()] = match.group(2).strip()
            else:
                current_text.append(line)

        if current_section:
            lore_sections.append(
                {"title": current_section, "content": "\n".join(current_text).strip()}
            )

        portrait_url = None
        card_url = None
        for cand_name in ["Portrait", "Landscape", "Card"]:
            for ext in [".png", ".jpg", ".jpeg", ".webp"]:
                cand = os.path.join(entity_dir, f"{cand_name}{ext}")
                if os.path.exists(cand):
                    if cand_name == "Card":
                        card_url = vault_asset_url(cand)
                    elif not portrait_url:
                        portrait_url = vault_asset_url(cand)

        # A Card is the last-resort visible asset when no portrait exists.
        portrait_url = portrait_url or card_url

        # Discover sub-documents in the entity's directory
        sub_documents = []
        for root_dir, dirs, files in os.walk(entity_dir):
            rel_root = os.path.relpath(root_dir, entity_dir)
            for file in files:
                if file.endswith(".md") and file not in [
                    "Profile.md",
                    "Realm.md",
                    "Tasks.md",
                ]:
                    path_rel = file if rel_root == "." else os.path.join(rel_root, file)
                    path_rel = path_rel.replace("\\", "/")

                    # Construct full vault ID
                    # base_folder is e.g. "Realms", entity_name is "Reflection Chamber"
                    # file_id would be "Realms/Reflection Chamber/Strategic Planning/Doc.md"
                    file_id = f"{base_folder}/{entity_name}/{path_rel}"

                    sub_documents.append(
                        {
                            "name": file.replace(".md", ""),
                            "path": path_rel,
                            "id": file_id,
                        }
                    )

        return {
            "name": entity_name,
            "type": mapped_type,
            "attributes": attributes,
            "sections": lore_sections,
            "portrait_url": portrait_url,
            "card_url": card_url or portrait_url,
            "sub_documents": sub_documents,
            "raw": content,
        }
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/vault/{file_path:path}")
async def get_vault_file(file_path: str):
    full_path = resolve_vault_path(file_path)

    # If the requested path is a directory, check for Profile.md or other md files
    if os.path.isdir(full_path):
        is_directory = True
        for candidate in ["Profile.md", "profile.md", "README.md", "readme.md"]:
            cand_path = os.path.join(full_path, candidate)
            cand_real = os.path.normcase(os.path.realpath(cand_path))
            root_real = os.path.normcase(os.path.realpath(NAVIS_ROOT))
            try:
                if os.path.commonpath([root_real, cand_real]) != root_real:
                    continue
            except ValueError:
                continue
            if os.path.exists(cand_path) and os.path.isfile(cand_path):
                full_path = cand_path
                is_directory = False
                break

        if is_directory:
            items = []
            for item in os.listdir(full_path):
                if item in [
                    ".navis_cache",
                    "Profile.md",
                    "Realm.md",
                    "Tasks.md",
                    "SFX",
                    "Landscape.png",
                    "Portrait.png",
                ]:
                    continue
                item_path = os.path.join(full_path, item)
                rel_path = to_rel_path(item_path)
                if os.path.isdir(item_path):
                    items.append({"name": item, "path": rel_path, "type": "directory"})
                elif item.endswith(".md"):
                    items.append(
                        {
                            "name": item.replace(".md", ""),
                            "path": rel_path,
                            "type": "file",
                        }
                    )
            return {
                "content": {
                    "type": "directory_listing",
                    "name": os.path.basename(full_path),
                    "items": items,
                }
            }

    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Resource not found")

    ext = os.path.splitext(full_path)[1].lower()
    if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"]:
        return FileResponse(full_path)

    if full_path.endswith(".json"):
        return load_json(full_path)
    elif full_path.endswith((".md", ".txt", ".log")):
        try:
            with open(full_path, "r", encoding="utf-8-sig", newline="") as f:
                content = f.read()
                # Rewrite image links relative to the actual directory of the file
                source_content = content
                content = rewrite_image_links(
                    content, to_rel_path(os.path.dirname(full_path))
                )
                return {"content": content, "source_content": source_content, "path": to_rel_path(full_path)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        return FileResponse(full_path)


@app.put("/api/vault/{file_path:path}")
async def save_vault_file(file_path: str, data: dict):
    full_path = resolve_vault_path(file_path)

    # If the requested path resolved to a directory, check for default profiles
    if os.path.isdir(full_path):
        for candidate in ["Profile.md", "profile.md", "README.md", "readme.md"]:
            cand_path = os.path.join(full_path, candidate)
            cand_real = os.path.normcase(os.path.realpath(cand_path))
            root_real = os.path.normcase(os.path.realpath(NAVIS_ROOT))
            try:
                if os.path.commonpath([root_real, cand_real]) != root_real:
                    continue
            except ValueError:
                continue
            if os.path.exists(cand_path) and os.path.isfile(cand_path):
                full_path = cand_path
                break

    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Resource not found")

    try:
        content = data.get("content", "")
        # Always use utf-8-sig on Windows to preserve emojis and special characters
        with open(full_path, "w", encoding="utf-8-sig") as f:
            f.write(content)
        return {"status": "success", "message": "File updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_icon_for_pillar(pillar):
    icons = {
        "COMMAND": "🛰️",
        "SANCTUM": "🏰",
        "DOMESTIC": "🏠",
        "FRONT": "⚔️",
        "GAUNTLET": "⚖️",
        "OUTLAND": "🧭",
        "LAB": "🧪",
        "PRISM": "🧋",
        "REFLECTION": "🧠",
        "IRON": "💪",
        "LIBRARY": "📚",
        "CHRONICLE": "📜",
        "CODEX": "📖",
        "FORGE": "🔨",
        "SYSTEM": "⚙️",
    }
    return icons.get(pillar, "🔹")


class CombatTargetRequest(BaseModel):
    type: str
    name: Optional[str] = None


@app.get("/api/combat/log")
async def get_combat_log(limit: int = 50):
    log_path = os.path.join(NAVIS_ROOT, "Battle", "Combat_Log.md")
    if not os.path.exists(log_path):
        return {"logs": ["> Combat Log Offline."]}

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Filter out empty lines and header lines, keeping only log entries
        logs = []
        for line in reversed(lines):
            line = line.strip()
            if line.startswith(">"):
                logs.append(line)
            if len(logs) >= limit:
                break

        return {"logs": logs}
    except Exception as e:
        return {"logs": [f"> Error reading log: {str(e)}"]}


@app.post("/api/combat/target")
async def set_combat_target(req: CombatTargetRequest):
    status = load_json(STATUS_PATH)
    if not status:
        raise HTTPException(status_code=500, detail="Could not load status manifold.")

    val = req.name if req.name else ""
    if req.type == "antagonist":
        status["current_antagonist"] = val
    elif req.type == "beast":
        status["current_beast"] = val
    else:
        raise HTTPException(
            status_code=400, detail="Invalid target type. Use 'antagonist' or 'beast'."
        )

    with open(STATUS_PATH, "w", encoding="utf-8-sig") as f:
        json.dump(status, f, indent=4, ensure_ascii=False)

    try:
        from services.sync_engine import sync_status_to_today_journal

        sync_status_to_today_journal()
    except Exception as e:
        print(f"Failed to sync journal on status update: {e}")

    msg = (
        f"{req.type.capitalize()} updated to {val}"
        if val
        else f"{req.type.capitalize()} cleared"
    )
    return {"status": "success", "message": msg, "current_status": status}


@app.post("/api/squad/vanguard")
async def set_vanguard(req: SquadActionRequest):
    status = load_json(STATUS_PATH)
    if not status:
        raise HTTPException(status_code=500, detail="Could not load status manifold.")

    squad = status.get("squad", [])
    if not any(m.get("name") == req.name for m in squad):
        raise HTTPException(
            status_code=400, detail=f"{req.name} is not in the active squad."
        )

    for m in squad:
        m["is_vanguard"] = m.get("name") == req.name

    status["squad"] = squad
    with open(STATUS_PATH, "w", encoding="utf-8-sig") as f:
        json.dump(status, f, indent=4, ensure_ascii=False)

    try:
        from services.sync_engine import sync_status_to_today_journal

        sync_status_to_today_journal()
    except Exception as e:
        print(f"Failed to sync journal on status update: {e}")

    return {
        "status": "success",
        "message": f"{req.name} designated as Vanguard.",
        "squad": squad,
    }


# --- Phase 1: Precision State Management ---


class TaskToggleRequest(BaseModel):
    file_path: str
    target_text: str
    is_checked: bool
    line_number: Optional[int] = None
    expected_content: Optional[str] = None


class BioAdjustRequest(BaseModel):
    field: str
    delta: int
    companion_name: Optional[str] = None


class XPAwardRequest(BaseModel):
    award_id: str
    entity_id: str
    amount: int
    source_type: str
    source_ref: str
    source_event_at: str
    local_date: str
    rule_version: str
    provenance: dict = Field(default_factory=dict)
    reason: Optional[str] = None
    details: str = ""
    correction_of: Optional[str] = None


class TalentAllocationRequest(BaseModel):
    entity_id: str = "keeper"
    node_id: str
    rank: Optional[int] = None



@app.post("/api/tasks/toggle")
async def toggle_task(req: TaskToggleRequest):
    full_path = resolve_vault_path(req.file_path)

    if os.path.isdir(full_path):
        for candidate in ["Profile.md", "profile.md", "README.md", "readme.md"]:
            cand_path = os.path.join(full_path, candidate)
            cand_real = os.path.normcase(os.path.realpath(cand_path))
            root_real = os.path.normcase(os.path.realpath(NAVIS_ROOT))
            try:
                if os.path.commonpath([root_real, cand_real]) != root_real:
                    continue
            except ValueError:
                continue
            if os.path.exists(cand_path) and os.path.isfile(cand_path):
                full_path = cand_path
                break

    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")

    from services.task_toggle import toggle, ToggleConflict
    try:
        result = toggle(NAVIS_ROOT, full_path, req.model_dump())
        result["source_content"] = result["content"]
        result["content"] = rewrite_image_links(result["content"], to_rel_path(os.path.dirname(full_path)))
        return result
    except ToggleConflict as error:
        raise HTTPException(status_code=409, detail={"saved": False, "content": error.content, "message": str(error)})
    except Exception as error:
        raise HTTPException(status_code=500, detail={"saved": False, "message": str(error)})


@app.post("/api/bio/adjust")
async def adjust_bio(req: BioAdjustRequest):
    if req.field.lower() == "xp":
        raise HTTPException(
            status_code=422,
            detail="XP must be recorded through the entity-scoped progression ledger.",
        )
    if req.companion_name:
        stats_path = os.path.join(NAVIS_ROOT, "Bridge", "CompanionStats.json")
        cstats = load_json(stats_path)
        if not cstats:
            raise HTTPException(
                status_code=500, detail="Could not load companion stats."
            )

        companions = cstats.get("companions", {})
        if req.companion_name not in companions:
            raise HTTPException(
                status_code=404, detail=f"Companion {req.companion_name} not found."
            )

        comp = companions[req.companion_name]

        # Check if field belongs to stats (STR, AGI, INT)
        if req.field in ["STR", "AGI", "INT"]:
            stats_block = comp.get("stats", {})
            stats_block[req.field] = stats_block.get(req.field, 0) + req.delta
            comp["stats"] = stats_block
        else:
            comp[req.field] = comp.get(req.field, 0) + req.delta

        cstats["companions"] = companions
        with open(stats_path, "w", encoding="utf-8-sig") as f:
            json.dump(cstats, f, indent=4, ensure_ascii=False)

        return {
            "status": "success",
            "message": f"Adjusted {req.companion_name}'s {req.field} by {req.delta}",
            "data": comp,
        }
    else:
        status = load_json(STATUS_PATH)
        if not status:
            raise HTTPException(
                status_code=500, detail="Could not load status manifold."
            )

        status[req.field] = status.get(req.field, 0) + req.delta
        with open(STATUS_PATH, "w", encoding="utf-8-sig") as f:
            json.dump(status, f, indent=4, ensure_ascii=False)

    try:
        from services.sync_engine import sync_status_to_today_journal

        sync_status_to_today_journal()
    except Exception as e:
        print(f"Failed to sync journal on status update: {e}")

        return {
            "status": "success",
            "message": f"Adjusted status {req.field} by {req.delta}",
            "data": status,
        }


@app.post("/api/settings/save")
async def save_settings(payload: dict):
    settings = load_json(SETTINGS_PATH)
    if not settings:
        raise HTTPException(status_code=500, detail="Could not load settings.")

    def merge_dot_notation(target: dict, dot_key: str, val):
        parts = dot_key.split(".")
        current = target
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = val

    def merge_dicts(dict1, dict2):
        for k, v in dict2.items():
            if isinstance(v, dict) and k in dict1 and isinstance(dict1[k], dict):
                merge_dicts(dict1[k], v)
            else:
                dict1[k] = v

    for key, value in payload.items():
        if "." in key:
            merge_dot_notation(settings, key, value)
        else:
            if isinstance(value, dict):
                if key not in settings or not isinstance(settings[key], dict):
                    settings[key] = {}
                merge_dicts(settings[key], value)
            else:
                settings[key] = value

    with open(SETTINGS_PATH, "w", encoding="utf-8-sig") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

    return {
        "status": "success",
        "message": "Settings merged and saved.",
        "settings": settings,
    }


@app.get("/api/ai/experiments")
async def get_ai_experiment_status():
    from services.online_ai import diagnostics

    return diagnostics()


@app.put("/api/ai/experiments")
async def update_ai_experiment_settings(req: AIExperimentSettingsRequest):
    from services.online_ai import OnlineAIError, configure

    try:
        values = req.model_dump(exclude_unset=True)
        if not values:
            raise HTTPException(status_code=422, detail="Supply at least one AI experiment setting.")
        return configure(values)
    except OnlineAIError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/neural/chat")
async def neural_chat(req: NeuralChatRequest):
    from services.conversation_service import handle_neural_chat, ConversationError
    from services.ai_provider import ProviderError
    from services.online_ai import OnlineAIError

    try:
        return await handle_neural_chat(NAVIS_ROOT, req.model_dump())
    except (OnlineAIError, ProviderError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ConversationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as e:
        raise HTTPException(status_code=500, detail="Neural generation failed.") from e


@app.get("/api/neural/banter")
def get_banter():
    import random

    status = load_json(STATUS_PATH)
    squad = status.get("squad", [])
    if not squad:
        raise HTTPException(status_code=404, detail="No active squad members")

    # Pick a random squad member
    speaker = random.choice(squad).get("name")

    comp_dir = os.path.join(NAVIS_ROOT, "Companions")
    # Try loading Persona.json
    persona_path = os.path.join(comp_dir, speaker, "Persona.json")
    if not os.path.exists(persona_path):
        persona_path = os.path.join(comp_dir, speaker.split(" ")[0], "Persona.json")

    system_prompt = None
    voice_desc = None
    if os.path.exists(persona_path):
        try:
            with open(persona_path, "r", encoding="utf-8-sig") as f:
                p_data = json.load(f)
                system_prompt = p_data.get("system_prompt")
                voice_desc = p_data.get("voice")
        except Exception as e:
            print(f"Error reading Persona.json: {e}")

    # Try getting quotes from Profile.md first (as fallback)
    p_path = os.path.join(comp_dir, speaker, "Profile.md")
    if not os.path.exists(p_path):
        p_path = os.path.join(comp_dir, speaker.split(" ")[0], "Profile.md")

    quote = None
    if os.path.exists(p_path):
        try:
            with open(p_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
            quotes_match = re.search(
                r"## 📜 Internal Logs \(Core Quotes\)\n(.*?)(?:\n##|\Z)",
                content,
                re.DOTALL,
            )
            if quotes_match:
                quotes = re.findall(
                    r'^\d+\.\s*"(.*?)"|^[-*]\s*"(.*?)"',
                    quotes_match.group(1),
                    re.MULTILINE,
                )
                clean_quotes = [q[0] if q[0] else q[1] for q in quotes if q[0] or q[1]]
                if clean_quotes:
                    quote = random.choice(clean_quotes)
            if not quote:
                motto_match = re.search(
                    r'^- \*\*Motto:\*\* "(.*?)"', content, re.MULTILINE
                )
                if motto_match:
                    quote = motto_match.group(1)
        except Exception as e:
            print(f"Error reading quotes for {speaker}: {e}")

    if quote:
        return {"speaker": speaker, "quote": quote}

    # If no static quote, use the local-first provider.
    try:
        import asyncio
        from services.ai_provider import get_provider

        realm = status.get("current_realm", "Unknown")
        loc = status.get("location", "Unknown")

        prompt = f"""
Act as a Storyteller / Writer for a companion in a high-fidelity RPG.
CHARACTER NAME: {speaker}
CHARACTER DETAILS/VOICE: {voice_desc or system_prompt or "A loyal companion to the Keeper"}
ENVIRONMENT: {loc} in {realm}

TASK: Generate a single short sentence of immersive dialogue/banter in this character's voice as they travel with the Keeper. 

CONSTRAINTS:
1. Speak directly to the Keeper.
2. Keep it under 20 words.
3. No modern jargon (no tech, no stats, no files, no sensors). Focus on the RPG atmosphere, environment, or a word of encouragement/vigilance.
4. Do NOT use emojis.
5. Return ONLY the spoken dialogue. Do not include quotes, actions, or character name prefix. E.g. "We must tread carefully; the shadows here feel heavier than before."
"""
        quote = asyncio.run(get_provider().generate(prompt)).replace('"', "")
        if quote:
            return {"speaker": speaker, "quote": quote}
    except Exception as e:
        print(f"⚠️ Local dynamic banter unavailable: {type(e).__name__}")

    # Ultimate fallback if everything else fails
    fallback_quotes = [
        "We must keep moving forward, Keeper.",
        "The path ahead is unclear, but we shall find our way.",
        "Let us remain vigilant.",
        "I stand ready, Keeper.",
    ]
    return {"speaker": speaker, "quote": random.choice(fallback_quotes)}


def _read_banter_status():
    try:
        with open(STATUS_PATH, "r", encoding="utf-8-sig") as status_file:
            status = json.load(status_file)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Squad status is missing. Restore Bridge/status.json in the configured Vault, then retry.")
    except UnicodeDecodeError:
        raise HTTPException(status_code=503, detail="Squad status is malformed. Repair Bridge/status.json in the configured Vault, then retry.")
    except OSError:
        raise HTTPException(status_code=503, detail="Squad status could not be read. Check Vault access and retry.")
    except json.JSONDecodeError:
        raise HTTPException(status_code=503, detail="Squad status is malformed. Repair Bridge/status.json in the configured Vault, then retry.")
    if not isinstance(status, dict):
        raise HTTPException(status_code=503, detail="Squad status is malformed. Repair Bridge/status.json in the configured Vault, then retry.")
    if not isinstance(status.get("squad"), list):
        raise HTTPException(status_code=503, detail="Squad status has an invalid squad field. Repair Bridge/status.json, then retry.")
    return status


def _validate_banter_squad(status):
    squad = status.get("squad")
    if not isinstance(squad, list):
        raise HTTPException(status_code=503, detail="Squad status has an invalid squad field. Repair Bridge/status.json, then retry.")
    names = [
        member.get("name", "").strip()
        for member in squad
        if isinstance(member, dict) and isinstance(member.get("name", ""), str)
    ]
    names = [name for name in names if name]
    if len(names) < 2 or len({name.casefold() for name in names}) != len(names):
        raise HTTPException(status_code=422, detail="At least two uniquely named active squad members are required.")


@app.get("/api/neural/banter/history")
def get_banter_history():
    import sqlite3
    import urllib.parse

    status = _read_banter_status()
    settings = load_json(SETTINGS_PATH)
    paths = settings.get("paths", {})
    db_path = paths.get("chronicle_db")
    if not db_path:
        db_path = os.path.join(NAVIS_ROOT, "Journal", "Chronicle.db")

    if not os.path.exists(db_path):
        return []

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'banter_threads'"
        )
        if c.fetchone() is None:
            conn.close()
            return []
        c.execute(
            "SELECT realm, participants, chain, timestamp FROM banter_threads ORDER BY id DESC LIMIT 50"
        )
        rows = c.fetchall()
        conn.close()

        comp_dir = os.path.join(NAVIS_ROOT, "Companions")
        companion_roles = {}
        if os.path.exists(comp_dir):
            for item in os.listdir(comp_dir):
                item_path = os.path.join(comp_dir, item)
                if os.path.isdir(item_path) and not item.startswith("."):
                    persona_path = os.path.join(item_path, "Persona.json")
                    persona = load_json(persona_path)
                    companion_roles[item] = persona.get("role", "Companion")

        # Get active squad names to filter history. Never report an unavailable
        # status file as an empty feed; the client will retain its last good data.
        squad = status.get("squad", [])
        squad_names = {m["name"].strip().lower() for m in squad if "name" in m}

        flat_banter = []
        seen_speakers = set()

        # Process newest threads first
        for r_realm, r_participants, r_chain, r_timestamp in rows:
            # Check if all participants are part of the active squad
            t_participants = (
                {p.strip().lower() for p in r_participants.split(",")}
                if r_participants
                else set()
            )
            if not t_participants.issubset(squad_names):
                continue

            try:
                chain = json.loads(r_chain)
            except Exception:
                continue

            # Process newest statements in the thread first
            for turn in reversed(chain):
                speaker = turn.get("speaker")
                text = turn.get("text")
                if not speaker or not text:
                    continue

                if speaker in seen_speakers:
                    continue

                seen_speakers.add(speaker)

                role = companion_roles.get(speaker)
                if not role:
                    short_name = speaker.split(" ")[0]
                    role = companion_roles.get(short_name, "Companion")

                speaker_dir = speaker
                if not os.path.exists(os.path.join(comp_dir, speaker_dir)):
                    short_name = speaker.split(" ")[0]
                    if os.path.exists(os.path.join(comp_dir, short_name)):
                        speaker_dir = short_name

                avatar_url = f"/api/vault/Companions/{urllib.parse.quote(speaker_dir)}/Portrait.png"

                flat_banter.append(
                    {
                        "sender": speaker,
                        "role": role,
                        "text": text,
                        "avatar": avatar_url,
                        "realm": r_realm,
                        "timestamp": r_timestamp,
                    }
                )

        # Reverse to return chronologically
        flat_banter.reverse()
        return flat_banter
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching banter history: {e}")
        raise HTTPException(status_code=503, detail="Banter history could not be read. Check Vault access and the Chronicle database, then retry.")


@app.post("/api/neural/banter/generate")
def trigger_banter_generation(count: int = 1):
    _validate_banter_squad(_read_banter_status())
    from services.banter_generator import generate_squad_banter

    success = generate_squad_banter(count=count)
    if success:
        return {
            "status": "success",
            "message": f"Successfully generated {count} squad banter threads.",
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Local banter generation failed. Check the local provider and Vault access, then retry. No online fallback was used.",
        )


@app.get("/api/neural/warroom/history")
async def get_warroom_history():
    from services.conversation_service import get_warroom_history as get_history

    return get_history(NAVIS_ROOT)


@app.post("/api/neural/warroom/clear")
async def clear_warroom_history():
    from services.conversation_service import clear_warroom_history as clear_history

    return clear_history(NAVIS_ROOT)


@app.post("/api/neural/warroom/chat")
async def warroom_chat(req: WarRoomChatRequest):
    # War Room includes recent journals and persona dossiers; it stays local-only.
    from services.conversation_service import handle_warroom_chat, ConversationError
    from services.ai_provider import ProviderError
    from services.online_ai import OnlineAIError
    from fastapi.responses import PlainTextResponse

    try:
        result = await handle_warroom_chat(NAVIS_ROOT, req.model_dump())
        return PlainTextResponse(result.get("response", ""))
    except (OnlineAIError, ProviderError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ConversationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as e:
        raise HTTPException(status_code=500, detail="War Room generation failed. Verify backend dependencies and the configured local model, then retry.") from e


@app.post("/api/forge/submit")
async def forge_submit(req: ForgeSubmitRequest):
    from services.forge_service import submit, ForgeError
    from services.ai_provider import ProviderError
    try:
        return await submit(NAVIS_ROOT, req.model_dump())
    except ForgeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=503, detail="Forge preview could not be stored. Retry generation.") from None


@app.post("/api/forge/discard")
async def forge_discard(req: ForgeDiscardRequest):
    from services.forge_service import discard, ForgeError
    try:
        return discard(NAVIS_ROOT, req.model_dump())
    except ForgeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def run_forge_sequence_in_background(job_id, request):
    from services.forge_service import approve, ForgeError
    def progress(message):
        active_jobs[job_id]["output"] += message + "\n"
    try:
        approve(NAVIS_ROOT, request, progress)
        active_jobs[job_id]["status"] = "completed"
    except ForgeError as exc:
        progress(str(exc))
        active_jobs[job_id]["status"] = "failed"
    except Exception:
        progress("Forge could not complete. Retry the approved proposal to check publication.")
        active_jobs[job_id]["status"] = "failed"


@app.post("/api/forge/approve")
async def forge_approve(req: ForgeApproveRequest, background_tasks: BackgroundTasks):
    from services.forge_service import proposal_path, ForgeError
    if not req.approved:
        raise HTTPException(status_code=400, detail="Explicit approval is required.")
    try:
        if not proposal_path(NAVIS_ROOT, req.proposal_id).is_file():
            raise ForgeError("Proposal is missing or discarded.")
    except ForgeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    import uuid
    job_id = str(uuid.uuid4())
    active_jobs[job_id] = {"id": job_id, "status": "running", "output": "Approved Forge queued.\n"}
    background_tasks.add_task(run_forge_sequence_in_background, job_id, req.model_dump())
    return {"status": "success", "job_id": job_id}


# --- Phase 5: Expeditionary Features ---


class ScriptExecuteRequest(BaseModel):
    script_id: str


WHITELISTED_SCRIPTS = {
    "backup": os.path.join("Engine", "sync", "backup_protocol.py"),
    "apply_xp": os.path.join("Engine", "rpg", "apply_xp.py"),
    "daily_rollover": os.path.join("Engine", "sync", "daily_rollover.py"),
    "sync_bridge": os.path.join("Engine", "sync", "sync_bridge.py"),
}


def run_script_in_background(job_id: str, script_rel_path: str):
    import subprocess
    import sys

    full_path = os.path.join(NAVIS_ROOT, script_rel_path)
    engine_path = os.path.join(NAVIS_ROOT, "Engine")

    # Build PYTHONPATH env
    env = os.environ.copy()
    subdirs = [
        os.path.join(engine_path, d)
        for d in os.listdir(engine_path)
        if os.path.isdir(os.path.join(engine_path, d))
    ]
    paths_to_add = [engine_path] + subdirs
    existing_pythonpath = env.get("PYTHONPATH", "")
    if existing_pythonpath:
        paths_to_add.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(paths_to_add)

    try:
        res = subprocess.run(
            [sys.executable, full_path],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        active_jobs[job_id]["status"] = "completed" if res.returncode == 0 else "failed"
        active_jobs[job_id]["output"] = (
            f"STDOUT:\n{res.stdout}\n\nSTDERR:\n{res.stderr}"
        )
    except Exception as e:
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["output"] = f"CRITICAL ERROR: {str(e)}"


def _run_sync_job(job_id, operation):
    from services.operation_outcomes import run_operation
    job = active_jobs.setdefault(job_id, {"job_id": job_id, "status": "running", "output": ""})
    def log(message):
        job["output"] = (job.get("output", "") + "\n" + message)[-65536:]
    def publish(result):
        job.update(result)
    try:
        job.update(run_operation(NAVIS_ROOT, operation, job_id, log=log, publish=publish))
    except Exception:
        job.update(status="failed", recovery="review_saved_changes",
                   message="Operation unavailable. Review the latest saved outcome before starting another.")


def run_rollover_sequence_in_background(job_id, env, backup_script, rollover_script, sync_bridge_script):
    _run_sync_job(job_id, "rollover")


def run_sync_sequence_in_background(job_id, env, scripts):
    _run_sync_job(job_id, "sync")


@app.post("/api/ops/execute")
async def execute_ops_script(
    req: ScriptExecuteRequest, background_tasks: BackgroundTasks
):
    import uuid

    if req.script_id not in WHITELISTED_SCRIPTS:
        raise HTTPException(
            status_code=400, detail="Requested script is not whitelisted."
        )

    script_rel_path = WHITELISTED_SCRIPTS[req.script_id]
    full_path = os.path.join(NAVIS_ROOT, script_rel_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Script file not found in Vault.")

    job_id = str(uuid.uuid4())
    active_jobs[job_id] = {
        "status": "running",
        "output": "Execution started. Awaiting logs...",
        "script": req.script_id,
    }

    background_tasks.add_task(run_script_in_background, job_id, script_rel_path)
    return {"status": "accepted", "job_id": job_id}


@app.get("/api/ops/latest")
async def get_latest_sync_operation():
    from services.operation_outcomes import read_latest
    try:
        return read_latest(NAVIS_ROOT)
    except Exception:
        raise HTTPException(status_code=404, detail="Saved operation unavailable") from None


@app.get("/api/ops/jobs/{job_id}")
async def get_ops_job_status(job_id: str):
    from services.operation_outcomes import read_operation
    try:
        result = read_operation(NAVIS_ROOT, job_id)
        if job_id in active_jobs:
            result["output"] = active_jobs[job_id].get("output", "")
        return result
    except FileNotFoundError:
        if job_id in active_jobs:
            return active_jobs[job_id]
        raise HTTPException(status_code=404, detail="Job ID not found") from None
    except Exception:
        raise HTTPException(status_code=503, detail="Operation state unavailable; review saved changes") from None


@app.post("/api/ops/jobs/{job_id}/review")
async def review_ops_job(job_id: str):
    from services.operation_outcomes import acknowledge
    try:
        return await asyncio.to_thread(acknowledge, NAVIS_ROOT, job_id)
    except Exception:
        raise HTTPException(status_code=409, detail="Review unavailable while an operation is active or its state is unavailable") from None



# -----------------------------------------------------------------------------
# PROGRESSION & XP SYSTEM
# -----------------------------------------------------------------------------


@app.get("/api/v1/progression/xp")
async def get_progression_xp(limit: int = 100, entity_id: str = "keeper"):
    from services.progression_db import (
        ProgressionValidationError,
        get_total_xp,
        get_unresolved_legacy_count,
        get_xp_history,
        level_progress,
    )

    try:
        history = get_xp_history(limit, entity_id)
        total = get_total_xp(entity_id)
        return {
            "entity_id": entity_id,
            "total_xp": total,
            **level_progress(total),
            "legacy_history_unresolved": get_unresolved_legacy_count() > 0,
            "history": history,
        }
    except ProgressionValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/progression/xp")
async def log_progression_xp(req: XPAwardRequest):
    from services.progression_db import record_award, ProgressionValidationError, ProjectionError

    try:
        result = record_award(req.model_dump())
        return {
            "status": "success",
            "message": f"Recorded {req.amount:+d} XP for {req.entity_id}",
            **result,
        }
    except ProgressionValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ProjectionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/progression/xp/corrections")
async def correct_progression_xp(req: XPAwardRequest):
    from services.progression_db import record_award, ProgressionValidationError, ProjectionError
    payload = req.model_dump()
    if payload["source_type"] != "correction" or not payload.get("correction_of"):
        raise HTTPException(status_code=422, detail="Corrections require source_type=correction and correction_of.")
    try:
        return {"status": "success", **record_award(payload)}
    except ProgressionValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ProjectionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/progression/achievements")
async def get_progression_achievements():
    from services.progression_db import get_achievements

    try:
        achievements = get_achievements()
        return achievements
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/progression/talents")
async def get_progression_talents(entity_id: str = "keeper"):
    from services.progression_db import ProgressionValidationError
    from services.talent_service import get_talent_state

    try:
        return get_talent_state(entity_id=entity_id)
    except ProgressionValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/progression/talents/nodes")
async def get_progression_talent_nodes():
    from services.talent_service import get_talent_nodes

    try:
        return get_talent_nodes()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/progression/talents/allocate")
async def allocate_progression_talent(req: TalentAllocationRequest):
    from services.progression_db import ProgressionValidationError
    from services.talent_service import allocate_talent

    try:
        return allocate_talent(
            entity_id=req.entity_id,
            node_id=req.node_id,
            rank=req.rank,
        )
    except ProgressionValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# -----------------------------------------------------------------------------
# BIOMETRICS SYSTEM
# -----------------------------------------------------------------------------


@app.get("/api/v1/biometrics/vitals/latest")
async def get_latest_biometrics():
    from services.biometrics import get_latest_vitals

    try:
        vitals = get_latest_vitals()
        if not vitals:
            raise HTTPException(status_code=404, detail="No vitals found")
        return vitals
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/biometrics/vitals/history")
async def get_biometrics_history(limit: int = 7):
    from services.biometrics import get_vitals_history

    try:
        return get_vitals_history(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/biometrics/exercises/recent")
async def get_recent_exercises(limit: int = 5):
    from services.biometrics import get_recent_exercises

    try:
        return get_recent_exercises(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------
# PRISM NEXUS SYSTEM
# -----------------------------------------------------------------------------


@app.get("/api/v1/lounge/media")
async def get_lounge_media_endpoint(type: str = None):
    from database.lounge_db import get_db_connection

    try:
        with get_db_connection() as conn:
            query = """
                SELECT m.id, m.type, m.title, m.creator, m.series, m.overview, m.release_year, 
                       m.duration_mins, m.rating, m.poster_url, m.status, m.source, 
                       m.date_added, m.date_completed, GROUP_CONCAT(g.name, '|') as genres
                FROM MediaItems m
                LEFT JOIN MediaGenres mg ON m.id = mg.media_id
                LEFT JOIN Genres g ON mg.genre_id = g.id
            """
            params = []
            if type:
                # Map frontend tab types to DB types
                type_map = {
                    "movies": "Movie",
                    "tv": "TV Show",
                    "youtube": "YouTube",
                    "books": "Book",
                    "audio": "Audio",
                    "games": "Game",
                }
                db_type = type_map.get(type.lower(), type)
                query += " WHERE m.type = ?"
                params.append(db_type)

            query += " GROUP BY m.id ORDER BY m.date_added DESC, m.date_completed DESC"

            cursor = conn.execute(query, params)
            items = []
            for row in cursor:
                item_dict = dict(row)
                if item_dict["genres"]:
                    item_dict["genres"] = item_dict["genres"].split("|")
                else:
                    item_dict["genres"] = []
                items.append(item_dict)
            return {"total_items": len(items), "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/lounge/media/{media_id}/poster")
async def get_lounge_media_poster(media_id: str):
    from fastapi.responses import FileResponse
    import os
    import re

    try:
        NAVIS_ROOT = os.getenv("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")
        safe_filename = re.sub(r'[\\/*?:"<>|]', "", f"{media_id}.jpg")
        poster_path = os.path.join(NAVIS_ROOT, "Lounge", "posters", safe_filename)

        if os.path.exists(poster_path):
            return FileResponse(poster_path, media_type="image/jpeg")
        else:
            raise HTTPException(status_code=404, detail="Poster not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------
# LIBRARY ZETTELKASTEN SYSTEM
# -----------------------------------------------------------------------------


@app.get("/api/v1/library/dashboard")
async def get_library_dashboard():
    from services.library_service import LibraryDataError, get_library_dashboard_metrics

    try:
        return get_library_dashboard_metrics()
    except LibraryDataError as error:
        status = 503 if error.code in {"library_database_missing", "library_database_unreadable"} else 500
        raise HTTPException(status_code=status, detail={"code": error.code}) from error
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "library_dashboard_failed"}) from e


@app.get("/api/v1/library/search")
async def search_library_endpoint(q: str = None, category: str = None):
    from services.library_service import LibraryDataError, search_library

    try:
        results = search_library(query=q, category=category)
        return {"results": results}
    except LibraryDataError as error:
        raise HTTPException(status_code=503, detail={"code": error.code}) from error
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "library_search_failed"}) from e


# -----------------------------------------------------------------------------
# REID: MENTAL STABILIZER (ANTIGRAVITY SDK)
# -----------------------------------------------------------------------------

from typing import Optional, List, Dict


class ReidChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None


@app.post("/api/reid/chat")
async def reid_chat_endpoint(req: ReidChatRequest):
    from services.conversation_service import handle_reid_chat, ConversationError
    from services.ai_provider import ProviderError
    from services.online_ai import OnlineAIError

    try:
        return await handle_reid_chat(NAVIS_ROOT, req.model_dump())
    except (OnlineAIError, ProviderError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ConversationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reid conversation failed: {e}") from e


@app.get("/api/reid/history")
async def reid_history_endpoint():
    from services.conversation_service import handle_reid_history

    try:
        return handle_reid_history(NAVIS_ROOT)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


# --- Mission Slot State Management ---
class MissionSlotRequest(BaseModel):
    slot_index: int
    mission_name: str


@app.get("/api/missions/all")
async def get_all_missions():
    cache_path = os.path.join(NAVIS_ROOT, "Bridge", ".navis_cache", "sector_cache.json")
    if not os.path.exists(cache_path):
        from services.cache_builder import build_sector_cache

        cache = build_sector_cache(NAVIS_ROOT)
    else:
        cache = load_json(cache_path)

    main_missions = cache.get("sectors", {}).get("MISSIONS", {}).get("Main", [])
    return main_missions


@app.post("/api/status/mission")
async def set_active_mission(req: MissionSlotRequest):
    status = load_json(STATUS_PATH)
    if not status:
        raise HTTPException(status_code=500, detail="Could not load status.")

    if "active_missions" not in status:
        status["active_missions"] = [
            "Midnight Restoration",
            "Cognitive Offload",
            "Protected Deep Play",
        ]

    if 0 <= req.slot_index < len(status["active_missions"]):
        status["active_missions"][req.slot_index] = req.mission_name
    else:
        raise HTTPException(
            status_code=400,
            detail=f"slot_index {req.slot_index} out of range (0..{len(status['active_missions'])-1})"
        )

    with open(STATUS_PATH, "w", encoding="utf-8-sig") as f:
        json.dump(status, f, indent=4)

    return {"status": "success", "active_missions": status["active_missions"]}


# ---------------------------------------------------------
# Weekly Holocron Telemetry & Cockpit Endpoints
# ---------------------------------------------------------

@app.get("/api/holocron/weekly/{week_id}/evidence/{source_id}")
async def inspect_weekly_holocron_source(week_id: str, source_id: str):
    from services.holocron_evidence import inspect_source
    try:
        return inspect_source(NAVIS_ROOT, week_id, source_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unsupported Holocron source")


@app.get("/api/holocron/weekly/latest")
async def get_latest_weekly_holocron():
    from services.holocron_engine import build_weekly_holocron
    try:
        data = build_weekly_holocron(NAVIS_ROOT)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compile Weekly Holocron: {str(e)}")


@app.get("/api/holocron/weekly/current")
async def get_current_weekly_holocron():
    from services.holocron_engine import build_weekly_holocron, get_current_iso_week
    try:
        current_week = get_current_iso_week()
        data = build_weekly_holocron(NAVIS_ROOT, week_id=current_week, force=True)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compile current Weekly Holocron: {str(e)}")


@app.get("/api/holocron/weekly/manifest")
async def get_holocron_weekly_manifest():
    from services.holocron_engine import get_holocron_manifest
    try:
        manifest = get_holocron_manifest(NAVIS_ROOT)
        return manifest
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load Holocron manifest: {str(e)}")


@app.get("/api/holocron/weekly/{week_id}")
async def get_weekly_holocron_by_id(week_id: str):
    from services.holocron_engine import build_weekly_holocron
    try:
        data = build_weekly_holocron(NAVIS_ROOT, week_id=week_id)
        return data
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load Weekly Holocron '{week_id}': {str(e)}")


@app.post("/api/holocron/weekly/{week_id}/regenerate")
async def regenerate_weekly_holocron(week_id: str):
    from services.holocron_engine import build_weekly_holocron
    try:
        data = build_weekly_holocron(NAVIS_ROOT, week_id=week_id, force=True)
        return data
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to regenerate Weekly Holocron '{week_id}': {str(e)}")


@app.post("/api/holocron/weekly/{week_id}/debrief/ai")
async def generate_holocron_ai_debrief(week_id: str):
    from services.holocron_engine import build_weekly_holocron, synthesize_ollama_debrief
    try:
        holocron_data = build_weekly_holocron(NAVIS_ROOT, week_id=week_id)
        debrief, source = await synthesize_ollama_debrief(holocron_data)
        
        from services.holocron_evidence import share_safe, source_path
        debrief = share_safe(debrief)
        holocron_data["tactical_debrief"] = debrief
        holocron_data["debrief_source"] = source
        holocron_data["evidence"]["interpretation"]["kind"] = "ai_interpretation" if source == "ollama" else "deterministic_summary"
        
        # Persist updated debrief in json artifact if it exists on disk
        artifact_path = os.path.join(NAVIS_ROOT, "Bridge", "Holocron", "Weekly", f"{week_id}.json")
        if source_path(NAVIS_ROOT, f"Bridge/Holocron/Weekly/{week_id}.json") and os.path.isfile(artifact_path):
            try:
                with open(artifact_path, "w", encoding="utf-8") as f:
                    json.dump(holocron_data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

        return {
            "week_id": week_id,
            "tactical_debrief": debrief,
            "debrief_source": source,
            "holocron": holocron_data
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate AI tactical debrief for '{week_id}': {str(e)}")


@app.get("/api/holocron/weekly/{week_id}/html")
async def get_weekly_holocron_html(week_id: str):
    from services.holocron_engine import build_weekly_holocron, export_standalone_html
    from fastapi.responses import HTMLResponse
    try:
        data = build_weekly_holocron(NAVIS_ROOT, week_id=week_id)
        html_content = export_standalone_html(data)
        return HTMLResponse(content=html_content)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate HTML Holocron '{week_id}': {str(e)}")


