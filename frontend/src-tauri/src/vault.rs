use percent_encoding::percent_decode_str;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::{Emitter, Manager};

pub const VAULT_CHANGE_EVENT: &str = "navis://vault-change";

pub fn current_epoch_timestamp() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct VaultChangeEvent {
    #[serde(rename = "type")]
    pub r#type: String,
    pub path: String,
    #[serde(default = "current_epoch_timestamp")]
    pub timestamp: f64,
    pub action: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub full_path: Option<String>,
}

pub fn determine_event_type(rel_path: &str) -> String {
    let normalized = rel_path.replace('\\', "/");
    let clean = normalized.trim_start_matches('/');
    if let Some(first) = clean.split('/').next() {
        let lower = first.to_lowercase();
        if !lower.is_empty() {
            return lower;
        }
    }
    "vault".to_string()
}

pub fn parse_watcher_line(line: &str) -> Option<VaultChangeEvent> {
    let trimmed = line.trim();
    let json_str = if let Some(stripped) = trimmed.strip_prefix("EVENT:") {
        stripped.trim()
    } else if trimmed.starts_with('{') && trimmed.ends_with('}') {
        trimmed
    } else {
        return None;
    };
    serde_json::from_str::<VaultChangeEvent>(json_str).ok()
}

pub fn emit_vault_change(app: &tauri::AppHandle, event: &VaultChangeEvent) -> Result<(), String> {
    if event.path.trim().is_empty() {
        return Err("path is required".to_string());
    }
    if event.action.trim().is_empty() {
        return Err("action is required".to_string());
    }
    app.emit(VAULT_CHANGE_EVENT, event)
        .map_err(|error| format!("failed to emit vault change event: {error}"))
}

#[tauri::command]
pub fn emit_vault_change_event(app: tauri::AppHandle, event: VaultChangeEvent) -> Result<(), String> {
    emit_vault_change(&app, &event)
}

#[derive(Clone, Default)]
pub struct VaultWatcherState {
    pub is_running: Arc<AtomicBool>,
    pub cancel: Arc<Mutex<Option<Arc<AtomicBool>>>>,
    #[cfg(windows)]
    pub process_job: Arc<Mutex<Option<isize>>>,
}

impl VaultWatcherState {
    pub fn stop(&self) {
        self.is_running.store(false, Ordering::Release);
        if let Ok(mut lock) = self.cancel.lock() {
            if let Some(token) = lock.take() {
                token.store(true, Ordering::Release);
            }
        }
        #[cfg(windows)]
        close_watcher_job(&self.process_job, None);
    }
}

#[cfg(windows)]
fn close_watcher_job(job: &Mutex<Option<isize>>, expected: Option<isize>) {
    if let Ok(mut lock) = job.lock() {
        if expected.is_some() && *lock != expected { return; }
        if let Some(handle) = lock.take() {
            // Kill-on-close wakes an idle stdout reader and terminates Python's children.
            unsafe { windows_sys::Win32::Foundation::CloseHandle(handle as _); }
        }
    }
}

pub fn stop_all_vault_watchers(app: &tauri::AppHandle) {
    if let Some(state) = app.try_state::<VaultWatcherState>() {
        state.stop();
    }
}

#[tauri::command]
pub fn stop_vault_watcher(state: tauri::State<'_, VaultWatcherState>) -> Result<bool, String> {
    state.stop();
    Ok(true)
}

#[tauri::command]
pub fn vault_watcher_status(state: tauri::State<'_, VaultWatcherState>) -> Value {
    json!({
        "running": state.is_running.load(Ordering::Acquire)
    })
}

#[tauri::command]
pub fn start_vault_watcher(
    app: tauri::AppHandle,
    state: tauri::State<'_, VaultWatcherState>,
) -> Result<bool, String> {
    if state.is_running.load(Ordering::Acquire) {
        return Ok(true);
    }

    let backend = crate::operations::backend_root(&app)?;
    let vault_root = crate::operations::configured_vault_root()?;
    let runtime = crate::command::resolve_python_runtime(&backend, !cfg!(debug_assertions))?;

    let cancel_token = Arc::new(AtomicBool::new(false));
    if let Ok(mut lock) = state.cancel.lock() {
        *lock = Some(cancel_token.clone());
    }

    let mut command = crate::command::hidden_command(&runtime.to_string_lossy());
    command
        .arg(backend.join("native_operations.py"))
        .arg("watch")
        .env("NAVIS_ROOT", &vault_root)
        .env("PYTHONPATH", &backend)
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUNBUFFERED", "1")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mut child = command.spawn().map_err(|e| format!("failed to spawn watcher: {e}"))?;
    #[cfg(windows)]
    let watcher_job = {
        let job = match crate::operations::attach_windows_job(&child) {
            Ok(job) => job,
            Err(error) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(error);
            }
        };
        match state.process_job.lock() {
            Ok(mut lock) => *lock = Some(job),
            Err(_) => {
                unsafe { windows_sys::Win32::Foundation::CloseHandle(job as _); }
                let _ = child.wait();
                return Err("watcher process state unavailable".into());
            }
        }
        job
    };
    let stdout = child.stdout.take().ok_or("failed to capture watcher stdout")?;

    state.is_running.store(true, Ordering::Release);
    let app_handle = app.clone();
    let is_running = state.is_running.clone();
    #[cfg(windows)]
    let process_job = state.process_job.clone();

    tauri::async_runtime::spawn_blocking(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            if cancel_token.load(Ordering::Acquire) {
                break;
            }
            if let Ok(line_str) = line {
                if let Some(event) = parse_watcher_line(&line_str) {
                    let _ = emit_vault_change(&app_handle, &event);
                }
            } else {
                break;
            }
        }
        #[cfg(windows)]
        close_watcher_job(&process_job, Some(watcher_job));
        let _ = child.kill();
        let _ = child.wait();
        is_running.store(false, Ordering::Release);
    });

    Ok(true)
}

#[derive(Debug, serde::Serialize)]
pub struct ApiResponse {
    pub status: u16,
    pub body: Value,
    pub text: String,
}

fn root() -> Result<PathBuf, String> {
    Ok(std::env::var("NAVIS_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(r"G:\My Drive\Navis-Vault")))
}

fn vault_relative_path(path: &Path) -> Result<String, String> {
    let base = root()?
        .canonicalize()
        .map_err(|e| format!("Vault root is unavailable: {e}"))?;
    let canonical_path = path
        .canonicalize()
        .map_err(|e| format!("unable to resolve Vault path: {e}"))?;
    let relative = canonical_path
        .strip_prefix(&base)
        .map_err(|_| "path escapes NAVIS_ROOT")?;
    if relative.as_os_str().is_empty() {
        return Err("Vault root is not a file path".into());
    }
    Ok(relative.to_string_lossy().replace('\\', "/"))
}

pub fn resolve_relative_path(relative: &str) -> Result<PathBuf, String> {
    let normalized = relative.replace('\\', "/");
    if normalized.is_empty()
        || normalized.starts_with('/')
        || normalized.contains(':')
        || normalized
            .split('/')
            .any(|part| part.is_empty() || part == "." || part == "..")
    {
        return Err("path must be a safe relative Vault path".into());
    }
    let root = root()?;
    let root = root
        .canonicalize()
        .map_err(|e| format!("Vault root is unavailable: {e}"))?;
    let candidate = root.join(normalized);
    let checked = if candidate.exists() {
        candidate.canonicalize().map_err(|e| e.to_string())?
    } else {
        candidate
            .parent()
            .ok_or("missing parent")?
            .canonicalize()
            .map_err(|e| e.to_string())?
            .join(candidate.file_name().ok_or("missing filename")?)
    };
    if !checked.starts_with(&root) {
        return Err("path escapes NAVIS_ROOT".into());
    }
    Ok(checked)
}

pub fn asset_response(relative: &str) -> Result<(Vec<u8>, &'static str), String> {
    let decoded = percent_decode_str(relative)
        .decode_utf8()
        .map_err(|e| e.to_string())?;
    let path = resolve_relative_path(&decoded)?;
    let bytes =
        fs::read(&path).map_err(|e| format!("unable to read asset {}: {e}", path.display()))?;
    let content_type = match path.extension().and_then(|extension| extension.to_str()) {
        Some("avif") => "image/avif",
        Some("gif") => "image/gif",
        Some("jpeg") | Some("jpg") => "image/jpeg",
        Some("json") => "application/json",
        Some("png") => "image/png",
        Some("svg") => "image/svg+xml",
        Some("webp") => "image/webp",
        _ => "application/octet-stream",
    };
    Ok((bytes, content_type))
}

fn text(path: &Path) -> Result<String, String> {
    let bytes = fs::read(path).map_err(|e| format!("unable to read {}: {e}", path.display()))?;
    let bytes = bytes.strip_prefix(&[0xEF, 0xBB, 0xBF]).unwrap_or(&bytes);
    String::from_utf8(bytes.to_vec()).map_err(|e| e.to_string())
}

fn atomic(path: &Path, value: &str) -> Result<(), String> {
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_nanos();
    let temp = path
        .parent()
        .ok_or("missing parent")?
        .join(format!(".navis-{}.tmp", stamp));
    let mut bytes = vec![0xEF, 0xBB, 0xBF];
    bytes.extend_from_slice(value.as_bytes());
    fs::write(&temp, bytes).map_err(|e| e.to_string())?;
    fs::rename(&temp, path).map_err(|e| {
        let _ = fs::remove_file(&temp);
        e.to_string()
    })
}

fn read_json(relative: &str, fallback: Value) -> Result<Value, String> {
    let decoded = percent_decode_str(relative)
        .decode_utf8()
        .map_err(|e| e.to_string())?;
    let path = resolve_relative_path(&decoded)?;
    if !path.exists() {
        return Ok(fallback);
    }
    serde_json::from_str(&text(&path)?).map_err(|e| format!("invalid JSON in {relative}: {e}"))
}
fn write_json(relative: &str, value: &Value) -> Result<(), String> {
    atomic(
        &resolve_relative_path(relative)?,
        &serde_json::to_string_pretty(value).map_err(|e| e.to_string())?,
    )
}
fn response(body: Value) -> ApiResponse {
    ApiResponse {
        status: 200,
        text: body.to_string(),
        body,
    }
}
fn response_status(status: u16, body: Value) -> ApiResponse {
    ApiResponse {
        status,
        text: body.to_string(),
        body,
    }
}
fn query(path: &str, key: &str) -> Option<String> {
    path.split('?').nth(1)?.split('&').find_map(|p| {
        let (k, v) = p.split_once('=')?;
        let decoded_key = percent_decode_str(k).decode_utf8().ok()?;
        if decoded_key != key {
            return None;
        }
        percent_decode_str(&v.replace('+', " "))
            .decode_utf8()
            .ok()
            .map(|value| value.into_owned())
    })
}
fn route(path: &str) -> &str {
    path.split('?').next().unwrap_or(path)
}

fn status() -> Result<Value, String> {
    let mut value = read_json(
        "Bridge/status.json",
        Value::Null,
    )?;
    if value.as_object().map_or(true, |object| object.is_empty()) ||
        value.get("squad").map_or(false, |squad| squad.as_array()
            .map_or(true, |members| members.iter().any(|member| !member.is_object()))) {
        return Err("Status source unavailable. Restore it, then retry.".into());
    }
    let stats = read_json("Bridge/CompanionStats.json", json!({}))?;
    if let Some(companions) = stats.get("companions").and_then(Value::as_object) {
        if let Some(squad) = value.get_mut("squad").and_then(Value::as_array_mut) {
            for member in squad {
                if let Some(name) = member.get("name").and_then(Value::as_str) {
                    if let Some(comp) = companions.get(name) {
                        if let Some(m) = member.as_object_mut() {
                            m.insert("xp".into(), comp.get("xp").cloned().unwrap_or(json!(0)));
                            m.insert(
                                "level".into(),
                                comp.get("level").cloned().unwrap_or(json!(1)),
                            );
                        }
                    }
                }
            }
        }
        if let Some(keeper) = companions.get("Keeper") {
            if let Some(m) = value.as_object_mut() {
                m.insert(
                    "keeper_xp".into(),
                    keeper.get("xp").cloned().unwrap_or(json!(0)),
                );
                m.insert(
                    "keeper_level".into(),
                    keeper.get("level").cloned().unwrap_or(json!(1)),
                );
            }
        }
    }
    Ok(value)
}

fn settings() -> Result<Value, String> {
    read_json(
        "Bridge/settings.json",
        json!({"lexicon":{"pillars":{"COMMAND":"Command Hub","SANCTUM":"The Sanctum","CHRONICLE":"Archives & Logs","CODEX":"Knowledge Base"}}}),
    )
}
fn icon(key: &str) -> &str {
    match key {
        "COMMAND" => "🛰️",
        "SANCTUM" => "🏰",
        "CODEX" => "📖",
        "LIBRARY" => "📚",
        "IRON" => "💪",
        _ => "🔹",
    }
}
fn navigation() -> Result<Value, String> {
    let pillars = settings()?
        .get("lexicon")
        .and_then(|v| v.get("pillars"))
        .cloned()
        .unwrap_or(json!({}));
    let mut out = Vec::new();
    for (key, label) in pillars.as_object().cloned().unwrap_or_default() {
        let sectors = match key.as_str() {
            "COMMAND" => json!([
                {"id":"STATUS","label":"Status","icon":"📡"}, {"id":"DIRECTIVES","label":"Directives","icon":"📋"}, {"id":"PARTY","label":"Party","icon":"🛡️"},
                {"id":"REALM_HOP","label":"Realm Hop","icon":"🌀"}, {"id":"COMBAT","label":"Combat Theater","icon":"⚔️"},
                {"id":"WORLD_MAP","label":"World Map","icon":"🗺️"}
            ]),
            "SANCTUM" => json!([
                {"id":"SANCTUM","label":"Operation","icon":"🛡️"}, {"id":"TASKS:The Sanctum","label":"Tasks","icon":"📋"},
                {"id":"RECURRING:The Sanctum","label":"Recurring","icon":"🔄"}, {"id":"MISSIONS:The Sanctum","label":"Missions","icon":"🚩"}
            ]),
            "DOMESTIC" => json!([
                {"id":"DOMESTIC","label":"Operation","icon":"🏠"}, {"id":"TASKS:The Domestic Breach","label":"Tasks","icon":"📋"},
                {"id":"RECURRING:The Domestic Breach","label":"Recurring","icon":"🔄"}, {"id":"MISSIONS:The Domestic Breach","label":"Missions","icon":"🚩"}
            ]),
            "FRONT" => json!([
                {"id":"FRONT","label":"Operation","icon":"⚔️"}, {"id":"TASKS:The High-Velocity Front","label":"Tasks","icon":"📋"},
                {"id":"RECURRING:The High-Velocity Front","label":"Recurring","icon":"🔄"}, {"id":"MISSIONS:The High-Velocity Front","label":"Missions","icon":"🚩"}
            ]),
            "GAUNTLET" => json!([
                {"id":"GAUNTLET","label":"Operation","icon":"⚖️"}, {"id":"TASKS:The Bureaucratic Gauntlet","label":"Tasks","icon":"📋"},
                {"id":"RECURRING:The Bureaucratic Gauntlet","label":"Recurring","icon":"🔄"}, {"id":"MISSIONS:The Bureaucratic Gauntlet","label":"Missions","icon":"🚩"}
            ]),
            "OUTLAND" => json!([
                {"id":"OUTLAND","label":"Operation","icon":"🧭"}, {"id":"TASKS:The Kinetic Outland","label":"Tasks","icon":"📋"},
                {"id":"RECURRING:The Kinetic Outland","label":"Recurring","icon":"🔄"}, {"id":"MISSIONS:The Kinetic Outland","label":"Missions","icon":"🚩"}
            ]),
            "LAB" => json!([{ "id":"SYNTHESIS_LAB", "label":"Synthesis Lab", "icon":"🧪" }]),
            "PRISM" => json!([{ "id":"PRISM_NEXUS", "label":"Lounge", "icon":"🧋" }]),
            "REFLECTION" => {
                json!([{ "id":"REFLECTION_CHAMBER", "label":"Friðr Hall", "icon":"🧠" }])
            }
            "IRON" => json!([{ "id":"IRON_SANCTUM", "label":"Iron Sanctum", "icon":"💪" }]),
            "LIBRARY" => json!([{ "id":"LIBRARY", "label":"Library", "icon":"📚" }]),
            "CHRONICLE" => {
                json!([
                    { "id":"JOURNAL", "label":"Daily Journal", "icon":"🗓️" },
                    { "id":"KEEPER", "label":"Keeper Ledger", "icon":"👑" },
                    { "id":"HOLOCRON", "label":"Weekly Holocron", "icon":"💠" }
                ])
            }
            "CODEX" => json!([
                {"id":"COMPANIONS","label":"Companions","icon":"🛡️"}, {"id":"RESIDENTS","label":"Residents","icon":"👥"},
                {"id":"ANTAGONISTS","label":"Antagonists","icon":"💀"}, {"id":"BEASTS","label":"Beasts","icon":"👾"}, {"id":"REALMS","label":"Realms","icon":"🌌"}
            ]),
            "SYSTEM" => {
                json!([{ "id":"CONFIG", "label":"Config", "icon":"⚙️" }, { "id":"NEURAL", "label":"Neural", "icon":"🧠" }, { "id":"MAINTENANCE", "label":"Maintenance", "icon":"🛰️" }])
            }
            _ => json!([]),
        };
        out.push(json!({"id":key,"label":label,"icon":icon(&key),"sectors":sectors}));
    }
    Ok(Value::Array(out))
}

fn operation_entities(sector: &str) -> Result<Value, String> {
    let folder = match sector {
        "SANCTUM" => "The Sanctum",
        "DOMESTIC" => "The Domestic Breach",
        "FRONT" => "The High-Velocity Front",
        "GAUNTLET" => "The Bureaucratic Gauntlet",
        "OUTLAND" => "The Kinetic Outland",
        _ => return Ok(json!([])),
    };
    let dir = resolve_relative_path(&format!("Operations/{folder}"))?;
    if !dir.exists() {
        return Ok(json!([]));
    }

    let operation_prefix = format!("Operations/{folder}");
    let mut entities = Vec::new();
    for entry in fs::read_dir(&dir).map_err(|e| e.to_string())?.flatten() {
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        if name.starts_with('.')
            || ["Main", "Side", "Archive", "Recurring.md", "Tasks.md"].contains(&name.as_str())
        {
            continue;
        }
        if path.is_file() && path.extension().and_then(|e| e.to_str()) == Some("md") {
            let id = format!(
                "{operation_prefix}/{}",
                path.strip_prefix(&dir)
                    .unwrap_or(&path)
                    .to_string_lossy()
                    .replace('\\', "/")
            );
            entities.push(json!({"id":id,"name":name.trim_end_matches(".md"),"type":"file"}));
        } else if path.is_dir() {
            let profile = path.join("Profile.md");
            if profile.exists() {
                let id = format!(
                    "{operation_prefix}/{}",
                    profile
                        .strip_prefix(&dir)
                        .unwrap_or(&profile)
                        .to_string_lossy()
                        .replace('\\', "/")
                );
                entities.push(json!({"id":id,"name":name,"type":"file"}));
            }
        }
    }
    for section in ["Main", "Side"] {
        let section_path = dir.join(section);
        if !section_path.exists() {
            continue;
        }
        let mut mission_files = Vec::new();
        collect_operation_missions(&section_path, &mut mission_files)?;
        for mission in mission_files {
            let id = format!(
                "{operation_prefix}/{}",
                mission
                    .strip_prefix(&dir)
                    .unwrap_or(&mission)
                    .to_string_lossy()
                    .replace('\\', "/")
            );
            let name = mission
                .parent()
                .and_then(Path::file_name)
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();
            entities.push(json!({"id":id,"name":name,"type":"file"}));
        }
    }
    entities.sort_by(|a, b| {
        a.get("name")
            .and_then(Value::as_str)
            .cmp(&b.get("name").and_then(Value::as_str))
    });
    Ok(Value::Array(entities))
}

fn collect_operation_missions(dir: &Path, files: &mut Vec<PathBuf>) -> Result<(), String> {
    for entry in fs::read_dir(dir).map_err(|e| e.to_string())?.flatten() {
        let path = entry.path();
        if path.is_dir() {
            if path.join("Mission.md").is_file() {
                files.push(path.join("Mission.md"));
            } else {
                collect_operation_missions(&path, files)?;
            }
        }
    }
    Ok(())
}

fn collect_markdown_files(dir: &Path, files: &mut Vec<PathBuf>) -> Result<(), String> {
    for entry in fs::read_dir(dir).map_err(|e| e.to_string())?.flatten() {
        let path = entry.path();
        if path.is_dir() {
            collect_markdown_files(&path, files)?;
        } else if path.extension().and_then(|e| e.to_str()) == Some("md") {
            files.push(path);
        }
    }
    Ok(())
}

fn journal_entities() -> Result<Value, String> {
    let dir = resolve_relative_path("Journal")?;
    if !dir.exists() {
        return Ok(json!([]));
    }

    let mut files = Vec::new();
    collect_markdown_files(&dir, &mut files)?;
    files.sort_by(|a, b| b.file_name().cmp(&a.file_name()));
    Ok(Value::Array(
        files
            .into_iter()
            .take(30)
            .map(|path| {
                let id = format!(
                    "Journal/{}",
                    path.strip_prefix(&dir)
                        .unwrap_or(&path)
                        .to_string_lossy()
                        .replace('\\', "/")
                );
                let name = path
                    .file_stem()
                    .unwrap_or_default()
                    .to_string_lossy()
                    .to_string();
                json!({"id":id,"name":name,"type":"file"})
            })
            .collect(),
    ))
}

fn holocron_entities() -> Result<Value, String> {
    let manifest = read_json("Bridge/Holocron/weekly_manifest.json", json!([]))?;
    let mut out = Vec::new();
    if let Some(arr) = manifest.as_array() {
        for item in arr {
            if let Some(wid) = item.get("week_id").and_then(Value::as_str) {
                out.push(json!({
                    "id": format!("Holocron/{}", wid),
                    "name": format!("Cycle {}", wid),
                    "type": "holocron",
                    "week_id": wid,
                    "precision": item.get("precision_rate").unwrap_or(&json!(0))
                }));
            }
        }
    }
    if out.is_empty() {
        out.push(json!({
            "id": "HOLOCRON",
            "name": "Weekly Holocron",
            "type": "virtual"
        }));
    }
    Ok(Value::Array(out))
}

fn holocron_manifest() -> Result<Value, String> {
    let manifest = read_json("Bridge/Holocron/weekly_manifest.json", json!([]))?;
    if let Some(arr) = manifest.as_array() {
        if !arr.is_empty() {
            return Ok(manifest);
        }
    }
    let base = resolve_relative_path("Bridge/Holocron/Weekly")?;
    let mut out = Vec::new();
    if base.is_dir() {
        if let Ok(entries) = fs::read_dir(base) {
            let mut wids = Vec::new();
            for entry in entries.flatten() {
                let p = entry.path();
                if p.is_file() && p.extension().map_or(false, |ext| ext == "json") {
                    if let Some(stem) = p.file_stem().and_then(|s| s.to_str()) {
                        wids.push(stem.to_string());
                    }
                }
            }
            wids.sort_by(|a, b| b.cmp(a));
            for wid in wids {
                out.push(json!({
                    "week_id": wid,
                    "name": format!("Cycle {}", wid),
                    "is_in_flight": false,
                    "status": "concluded"
                }));
            }
        }
    }
    Ok(Value::Array(out))
}

fn list_entities(sector: &str) -> Result<Value, String> {
    if sector == "KEEPER" {
        let dir = resolve_relative_path("Keeper")?;
        if !dir.is_dir() {
            return Err("Keeper source directory is unavailable.".into());
        }
        let mut out = Vec::new();
        for entry in fs::read_dir(dir)
            .map_err(|e| format!("unable to read Keeper source: {e}"))?
            .flatten()
        {
            let path = entry.path();
            if path.is_file() && path.extension().and_then(|extension| extension.to_str()) == Some("md") {
                let name = path.file_stem().unwrap_or_default().to_string_lossy().to_string();
                let relative = vault_relative_path(&path)?;
                out.push(json!({"id": relative, "name": name, "type": "file"}));
            }
        }
        out.sort_by(|a, b| {
            a.get("name")
                .and_then(Value::as_str)
                .cmp(&b.get("name").and_then(Value::as_str))
        });
        return Ok(Value::Array(out));
    }
    if matches!(
        sector,
        "SANCTUM" | "DOMESTIC" | "FRONT" | "GAUNTLET" | "OUTLAND"
    ) {
        return operation_entities(sector);
    }
    if sector == "JOURNAL" {
        return journal_entities();
    }

    let virtual_entities = match sector {
        "STATUS" => Some(json!([
            {"id":"STATUS_HUD","name":"System HUD","type":"virtual"},
            {"id":"STATUS_NEWS","name":"Daily Briefing","type":"virtual"},
            {"id":"STATUS_TASKS","name":"Task Checklist","type":"virtual"}
        ])),
        "PARTY" => Some(json!([
            {"id":"BANTER","name":"Banter Feed","type":"virtual"},
            {"id":"WAR_ROOM","name":"War Room","type":"virtual"},
            {"id":"XP","name":"XP Manifold","type":"virtual"}
        ])),
        "ROSTER" => {
            Some(json!([{ "id":"RESERVE_ROSTER", "name":"Reserve Roster", "type":"virtual" }]))
        }
        "REALM_HOP" => {
            Some(json!([{ "id":"REALM_HOP_MODAL", "name":"Moongate Protocol", "type":"virtual" }]))
        }
        "COMBAT" => Some(json!([
            {"id":"BATTLE","name":"Battle Field","type":"virtual"},
            {"id":"TACTICAL_COCKPIT","name":"Tactical Cockpit","type":"virtual"}
        ])),
        "WORLD_MAP" => Some(json!([{ "id":"WORLD_MAP", "name":"World Map", "type":"virtual" }])),
        "PRISM_NEXUS" => {
            Some(json!([{ "id":"PRISM_NEXUS", "name":"Boba Lounge", "type":"virtual" }]))
        }
        "REFLECTION_CHAMBER" => {
            Some(json!([{ "id":"REFLECTION_CHAMBER", "name":"Friðr Hall", "type":"virtual" }]))
        }
        "IRON_SANCTUM" => {
            Some(json!([{ "id":"IRON_SANCTUM", "name":"Iron Sanctum", "type":"virtual" }]))
        }
        "LIBRARY" => Some(
            json!([{ "id":"LIBRARY_DASHBOARD", "name":"Zettelkasten Nexus", "type":"virtual" }]),
        ),
        "NEURAL" => {
            Some(json!([{ "id":"NEURAL_CHAT", "name":"Cognitive Arbiter", "type":"virtual" }]))
        }
        "CONFIG" => Some(json!([{ "id":"CONFIG:settings", "name":"Settings", "type":"virtual" }])),
        "DIRECTIVES" | "TASKS" => Some(json!([
            {"id":"TASKS_COCKPIT","name":"Directives Cockpit","type":"virtual"}
        ])),
        "HOLOCRON" => Some(holocron_entities()?),
        s if s.starts_with("TASKS:") => Some(
            json!([{ "id":format!("TASKS_BOARD:{}", match s.trim_start_matches("TASKS:") { "The Sanctum" => "Sanctum", "The Domestic Breach" => "Domestic", "The High-Velocity Front" => "Front", "The Bureaucratic Gauntlet" => "Gauntlet", "The Kinetic Outland" => "Outland", value => value }), "name":"Active Directives", "type":"virtual" }]),
        ),
        s if s.starts_with("RECURRING:") => Some(
            json!([{ "id":format!("RECURRING_BOARD:{}", match s.trim_start_matches("RECURRING:") { "The Sanctum" => "Sanctum", "The Domestic Breach" => "Domestic", "The High-Velocity Front" => "Front", "The Bureaucratic Gauntlet" => "Gauntlet", "The Kinetic Outland" => "Outland", value => value }), "name":"Recurring Protocols", "type":"virtual" }]),
        ),
        s if s.starts_with("MISSIONS:") => {
            Some(json!([{ "id":"QUEST_BOARD", "name":"Quest Board", "type":"virtual" }]))
        }
        _ => None,
    };
    if let Some(entities) = virtual_entities {
        return Ok(entities);
    }

    let base = match sector {
        "JOURNAL" => "Journal",
        "COMPANIONS" => "Companions",
        "RESIDENTS" => "Residents",
        "ANTAGONISTS" => "Obstacles/Antagonists",
        "BEASTS" => "Obstacles/Beasts",
        "REALMS" => "Realms",
        _ => return Ok(json!([])),
    };
    let dir = resolve_relative_path(base)?;
    if !dir.exists() {
        return Ok(json!([]));
    }
    let file_mode = sector == "JOURNAL";
    let mut out = Vec::new();
    for entry in fs::read_dir(dir).map_err(|e| e.to_string())?.flatten() {
        let p = entry.path();
        let name = p
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string();
        let valid = if file_mode {
            p.extension().and_then(|e| e.to_str()) == Some("md")
        } else {
            p.is_dir() && !name.starts_with('.') && name != "Keeper"
        };
        if valid {
            let rel = vault_relative_path(&p)?;
            out.push(json!({"id":rel,"name":p.file_stem().unwrap_or_default().to_string_lossy(),"type":if file_mode{"file"}else{"directory"}}));
        }
    }
    out.sort_by(|a, b| {
        a.get("name")
            .and_then(Value::as_str)
            .cmp(&b.get("name").and_then(Value::as_str))
    });
    Ok(Value::Array(out))
}

fn journal_month(path: &str) -> ApiResponse {
    let year = query(path, "year").and_then(|v| v.parse::<i32>().ok());
    let month = query(path, "month").and_then(|v| v.parse::<u32>().ok());
    let (year, month) = match (year, month) {
        (Some(y), Some(m)) if (1..=9999).contains(&y) && chrono::NaiveDate::from_ymd_opt(y, m, 1).is_some() => (y, m),
        _ => return response_status(400, json!({"detail":"Invalid journal month"})),
    };
    let load = || -> Result<Value, String> {
        let journal = resolve_relative_path("Journal")?;
        let verify_source = || -> Result<(), String> {
            fs::read_dir(&journal).map_err(|e| e.to_string())?
                .collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())?;
            Ok(())
        };
        verify_source()?;
        let year_dir = resolve_relative_path(&format!("Journal/{year}"))?;
        let mut dates: Vec<String> = Vec::new();
        // The shared resolver requires an existing parent. An absent year is
        // empty only after the Journal itself was successfully enumerated.
        let directory = match fs::read_dir(&year_dir) {
            Ok(_) => Some(resolve_relative_path(&format!("Journal/{year}/{month:02}"))?),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => None,
            Err(e) => return Err(e.to_string()),
        };
        if let Some(dir) = directory {
            match fs::read_dir(dir) {
                Ok(entries) => for entry in entries {
                    let entry = entry.map_err(|e| e.to_string())?;
                    let name = entry.file_name().to_string_lossy().into_owned();
                    if entry.file_type().map_err(|e| e.to_string())?.is_file() {
                        if let Some(stem) = name.strip_suffix(".md") {
                            if let Ok(day) = chrono::NaiveDate::parse_from_str(stem, "%Y-%m-%d") {
                                let canonical = day.format("%Y-%m-%d").to_string();
                                if canonical == stem && canonical.starts_with(&format!("{year:04}-{month:02}-")) { dates.push(canonical); }
                            }
                        }
                    }
                },
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => {},
                Err(e) => return Err(e.to_string()),
            }
        }
        verify_source()?;
        dates.sort();
        Ok(json!({"dates":dates,"availability":"available","year":year,"month":month}))
    };
    match load() {
        Ok(value) => response(value),
        Err(_) => response_status(503, json!({"detail":{"code":"journal_unavailable","message":"Journal dates unavailable. Reconnect the Vault and retry."}})),
    }
}

fn markdown_section(content: &str, heading: &str) -> Option<String> {
    let heading = heading.to_ascii_lowercase();
    let mut in_section = false;
    let mut lines = Vec::new();
    for line in content.lines() {
        if line.trim().to_ascii_lowercase() == heading {
            in_section = true;
            continue;
        }
        if in_section && line.trim_start().starts_with("##") {
            break;
        }
        if in_section {
            lines.push(line.trim());
        }
    }
    let value = lines.join(" ").trim().trim_matches('-').trim().to_string();
    (!value.is_empty()).then_some(value)
}

fn select_realm_indices<F>(count: usize, limit: usize, mut choose_index: F) -> Vec<usize>
where
    F: FnMut(usize) -> usize,
{
    let mut remaining: Vec<_> = (0..count).collect();
    let mut selected = Vec::with_capacity(count.min(limit));
    while !remaining.is_empty() && selected.len() < limit {
        let index = choose_index(remaining.len()) % remaining.len();
        selected.push(remaining.swap_remove(index));
    }
    selected
}

#[cfg(windows)]
fn random_index(upper: usize) -> usize {
    use windows_sys::Win32::Security::Cryptography::{
        BCryptGenRandom, BCRYPT_USE_SYSTEM_PREFERRED_RNG,
    };

    let mut bytes = [0_u8; 8];
    let status = unsafe {
        BCryptGenRandom(
            std::ptr::null_mut(),
            bytes.as_mut_ptr(),
            bytes.len() as u32,
            BCRYPT_USE_SYSTEM_PREFERRED_RNG,
        )
    };
    if status >= 0 {
        (u64::from_ne_bytes(bytes) as usize) % upper
    } else {
        upper - 1
    }
}

#[cfg(not(windows))]
fn random_index(upper: usize) -> usize {
    use std::hash::{Hash, Hasher};
    use std::time::{SystemTime, UNIX_EPOCH};

    let mut seed = std::collections::hash_map::DefaultHasher::new();
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos()
        .hash(&mut seed);
    std::thread::current().id().hash(&mut seed);
    upper.hash(&mut seed);
    (seed.finish() as usize) % upper
}

fn realm_options() -> Result<Value, String> {
    let status = read_json("Bridge/status.json", json!({"current_realm":"Unknown"}))?;
    let current_realm = status
        .get("current_realm")
        .and_then(Value::as_str)
        .unwrap_or("Unknown");
    let realm_stats = read_json("Bridge/realm_stats.json", json!({"history":[]}))?;
    let history = realm_stats
        .get("history")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();

    let mut exclusions = vec![current_realm.to_string()];
    for visited in history.iter().rev().filter_map(Value::as_str) {
        if visited != current_realm && !exclusions.iter().any(|item| item == visited) {
            exclusions.push(visited.to_string());
        }
        if exclusions.len() >= 4 {
            break;
        }
    }

    let realms_dir = resolve_relative_path("Realms")?;
    let mut realms = Vec::new();
    if realms_dir.exists() {
        for entry in fs::read_dir(realms_dir)
            .map_err(|e| e.to_string())?
            .flatten()
        {
            let path = entry.path();
            let name = path
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();
            if !path.is_dir() || name.starts_with('.') || name.eq_ignore_ascii_case("default") {
                continue;
            }

            let mut description = "A mysterious realm.".to_string();
            let data_path = path.join("realm_data.json");
            if data_path.exists() {
                if let Ok(data) = serde_json::from_str::<Value>(&text(&data_path)?) {
                    if let Some(value) = data.get("description").and_then(Value::as_str) {
                        description = value.to_string();
                    }
                }
            } else {
                let realm_path = path.join("Realm.md");
                if realm_path.exists() {
                    let content = text(&realm_path)?;
                    description = markdown_section(&content, "## 📜 LORE")
                        .or_else(|| markdown_section(&content, "## 📜 Realm Overview"))
                        .unwrap_or(description);
                }
            }
            realms.push((name, description));
        }
    }
    realms.sort_by(|a, b| a.0.cmp(&b.0));

    let mut available: Vec<_> = realms
        .iter()
        .filter(|(name, _)| !exclusions.iter().any(|item| item == name))
        .collect();
    if available.is_empty() {
        available = realms
            .iter()
            .filter(|(name, _)| name.as_str() != current_realm)
            .collect();
    }

    Ok(Value::Array(
        select_realm_indices(available.len(), 3, random_index)
            .into_iter()
            .map(|index| {
                let (name, description) = available[index];
                json!({
                    "name": name,
                    "description": description,
                    "image": format!("/api/vault/Realms/{name}/Landscape.png")
                })
            })
            .collect(),
    ))
}

fn csv_tags(value: Option<&Value>) -> Vec<String> {
    value
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .map(str::to_string)
                .collect()
        })
        .unwrap_or_default()
}

fn realm_draft(path: &str) -> Result<Value, String> {
    let realm_name = query(path, "realm_name").ok_or("realm_name required")?;
    let realm_path = resolve_relative_path(&format!("Realms/{realm_name}"))?;
    if !realm_path.is_dir() {
        return Err("Realm not found.".into());
    }

    let mut realm_tags = Vec::new();
    let mut natives = Vec::new();
    let realm_data_path = realm_path.join("realm_data.json");
    if realm_data_path.exists() {
        let data = serde_json::from_str::<Value>(&text(&realm_data_path)?)
            .map_err(|e| format!("invalid realm data: {e}"))?;
        realm_tags = csv_tags(data.get("tags"));
        natives = csv_tags(data.get("natives"));
    } else if realm_path.join("Realm.md").exists() {
        let content = text(&realm_path.join("Realm.md"))?;
        let tags = markdown_section(&content, "## 🏷️ TAGS")
            .or_else(|| markdown_section(&content, "## 🏷️ Tags"))
            .unwrap_or_default();
        realm_tags = tags
            .trim_matches('`')
            .split(',')
            .map(str::trim)
            .filter(|tag| !tag.is_empty())
            .map(str::to_string)
            .collect();
    }

    let stats = read_json("Bridge/CompanionStats.json", json!({}))?;
    let stats = stats.get("companions").cloned().unwrap_or(json!({}));
    let companions_dir = resolve_relative_path("Companions")?;
    let mut companions: Vec<(String, Vec<String>, i64, String, i64)> = Vec::new();
    if companions_dir.exists() {
        for entry in fs::read_dir(companions_dir)
            .map_err(|e| e.to_string())?
            .flatten()
        {
            let companion_path = entry.path();
            let name = companion_path
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();
            if !companion_path.is_dir() || name.starts_with('.') || name == "Keeper" {
                continue;
            }

            let xp = stats
                .get(&name)
                .and_then(|value| value.get("xp"))
                .and_then(Value::as_i64)
                .unwrap_or(0);
            let mut tags = Vec::new();
            let mut role = "Active Personnel".to_string();
            let data_path = companion_path.join("companion_data.json");
            if data_path.exists() {
                let data = serde_json::from_str::<Value>(&text(&data_path)?)
                    .map_err(|e| format!("invalid companion data: {e}"))?;
                tags = csv_tags(data.get("tags"));
                role = data
                    .get("role")
                    .and_then(Value::as_str)
                    .unwrap_or(&role)
                    .to_string();
            } else if companion_path.join("Profile.md").exists() {
                let content = text(&companion_path.join("Profile.md"))?;
                let tag_text = markdown_section(&content, "## 🏷️ TAGS")
                    .or_else(|| markdown_section(&content, "## 🏷️ Tags"))
                    .unwrap_or_default();
                tags = tag_text
                    .trim_matches('`')
                    .split(',')
                    .map(str::trim)
                    .filter(|tag| !tag.is_empty())
                    .map(str::to_string)
                    .collect();
                if let Some(line) = content.lines().find(|line| line.contains("**Role:**")) {
                    role = line
                        .split("**Role:**")
                        .nth(1)
                        .unwrap_or("")
                        .trim()
                        .to_string();
                }
            }

            let genres = [
                "Fantasy",
                "Science Fiction",
                "Historical",
                "Eldritch",
                "Modern",
            ];
            let synergy = tags
                .iter()
                .filter(|tag| realm_tags.iter().any(|realm_tag| realm_tag == *tag))
                .map(|tag| if genres.contains(&tag.as_str()) { 2 } else { 1 })
                .sum();
            companions.push((name, tags, xp, role, synergy));
        }
    }

    let captain = natives
        .iter()
        .find_map(|native| companions.iter().find(|companion| &companion.0 == native))
        .or_else(|| {
            companions
                .iter()
                .max_by_key(|companion| (companion.4, &companion.0))
        })
        .ok_or("No companions available for realm draft.")?;
    let captain_name = captain.0.clone();
    let mut remaining: Vec<_> = companions
        .iter()
        .filter(|companion| companion.0 != captain_name)
        .collect();
    remaining.sort_by_key(|companion| (companion.2, -companion.4, companion.0.clone()));
    let mut choices: Vec<_> = remaining.iter().take(2).copied().collect();
    let mut high_synergy: Vec<_> = remaining
        .iter()
        .filter(|companion| !choices.iter().any(|choice| choice.0 == companion.0))
        .copied()
        .collect();
    high_synergy.sort_by_key(|companion| (-companion.4, companion.0.clone()));
    choices.extend(high_synergy.into_iter().take(3));

    Ok(json!({
        "vanguard": {"name": captain.0, "role": captain.3, "synergy": captain.4},
        "draft_pool": choices.into_iter().map(|companion| json!({
            "name": companion.0,
            "role": companion.3,
            "xp": companion.2,
            "synergy": companion.4,
            "tags": companion.1,
        })).collect::<Vec<_>>()
    }))
}

fn execute_realm_hop(body: &Value) -> Result<Value, String> {
    let realm_name = body
        .get("realm_name")
        .and_then(Value::as_str)
        .filter(|name| !name.trim().is_empty())
        .ok_or("realm_name required")?;
    let realm_path = resolve_relative_path(&format!("Realms/{realm_name}"))?;
    if !realm_path.is_dir() {
        return Err("Realm not found".into());
    }

    let squad_names = body
        .get("squad_names")
        .and_then(Value::as_array)
        .ok_or("squad_names required")?;
    if squad_names.len() != 3 {
        return Err("Exactly three squad members are required".into());
    }
    let companions_dir = resolve_relative_path("Companions")?;
    let companion_stats = read_json("Bridge/CompanionStats.json", json!({}))?;
    let companion_stats = companion_stats
        .get("companions")
        .cloned()
        .unwrap_or(json!({}));
    let mut seen = Vec::new();
    let mut squad = Vec::new();
    for (index, value) in squad_names.iter().enumerate() {
        let name = value.as_str().ok_or("squad member names must be strings")?;
        if name.trim().is_empty() || seen.iter().any(|existing| existing == name) {
            return Err("Squad members must be distinct valid names".into());
        }
        let companion_path = resolve_relative_path(&format!("Companions/{name}"))?;
        if !companion_path.is_dir() || !companion_path.starts_with(&companions_dir) {
            return Err(format!("Companion not found: {name}"));
        }
        let mut role = "Active Personnel".to_string();
        let data_path = companion_path.join("companion_data.json");
        if data_path.is_file() {
            let data = serde_json::from_str::<Value>(&text(&data_path)?)
                .map_err(|error| format!("invalid companion data for {name}: {error}"))?;
            role = data
                .get("role")
                .and_then(Value::as_str)
                .unwrap_or(&role)
                .to_string();
        } else if companion_path.join("Profile.md").is_file() {
            let profile = text(&companion_path.join("Profile.md"))?;
            if let Some(line) = profile.lines().find(|line| line.contains("**Role:**")) {
                role = line
                    .split("**Role:**")
                    .nth(1)
                    .unwrap_or("")
                    .trim()
                    .to_string();
            }
        }
        let entry_xp = companion_stats
            .get(name)
            .and_then(|stats| stats.get("xp"))
            .and_then(Value::as_i64)
            .unwrap_or(0);
        seen.push(name.to_string());
        squad.push(json!({
            "name": name,
            "role": role,
            "is_vanguard": index == 0,
            "entry_xp": entry_xp
        }));
    }

    let mut status = status()?;
    let keeper_xp = companion_stats
        .get("Keeper")
        .and_then(|stats| stats.get("xp"))
        .and_then(Value::as_i64)
        .unwrap_or(0);
    let status_object = status.as_object_mut().ok_or("invalid status data")?;
    status_object.insert("current_realm".into(), json!(realm_name));
    status_object.insert("squad".into(), json!(squad));
    status_object.insert("keeper_entry_xp".into(), json!(keeper_xp));
    write_json("Bridge/status.json", &status)?;
    let _ = sync_status_to_today_journal(&status);

    let mut stats = read_json(
        "Bridge/realm_stats.json",
        json!({"visit_counts": {}, "history": [], "last_updated": ""}),
    )?;
    let stats_object = stats.as_object_mut().ok_or("invalid realm stats data")?;
    let counts = stats_object
        .entry("visit_counts")
        .or_insert_with(|| json!({}))
        .as_object_mut()
        .ok_or("invalid realm visit counts")?;
    let count = counts.get(realm_name).and_then(Value::as_u64).unwrap_or(0);
    counts.insert(realm_name.to_string(), json!(count + 1));
    let history = stats_object
        .entry("history")
        .or_insert_with(|| json!([]))
        .as_array_mut()
        .ok_or("invalid realm history")?;
    history.push(json!(realm_name));
    write_json("Bridge/realm_stats.json", &stats)?;

    Ok(json!({
        "status": "success",
        "message": format!("Successfully anchored to {realm_name}.")
    }))
}

fn sync_status_to_today_journal(status: &Value) -> Result<(), String> {
    let day_str = if let Some(last_updated) = status.get("last_updated").and_then(Value::as_str) {
        if last_updated.len() == 10 && last_updated.chars().nth(4) == Some('-') {
            last_updated.to_string()
        } else {
            chrono::Local::now().format("%Y-%m-%d").to_string()
        }
    } else {
        chrono::Local::now().format("%Y-%m-%d").to_string()
    };

    let parts: Vec<&str> = day_str.split('-').collect();
    if parts.len() != 3 {
        return Ok(());
    }
    let year = parts[0];
    let month = parts[1];
    let rel_path = format!("Journal/{year}/{month}/{day_str}.md");
    if let Ok(journal_path) = resolve_relative_path(&rel_path) {
        if journal_path.is_file() {
            return sync_status_to_journal_file(&journal_path, &day_str, status);
        }
    }

    let today_str = chrono::Local::now().format("%Y-%m-%d").to_string();
    if today_str != day_str {
        let today_parts: Vec<&str> = today_str.split('-').collect();
        if today_parts.len() == 3 {
            let today_rel = format!("Journal/{}/{}/{today_str}.md", today_parts[0], today_parts[1]);
            if let Ok(journal_path) = resolve_relative_path(&today_rel) {
                if journal_path.is_file() {
                    return sync_status_to_journal_file(&journal_path, &today_str, status);
                }
            }
        }
    }
    Ok(())
}

fn sync_status_to_journal_file(path: &Path, day_str: &str, status: &Value) -> Result<(), String> {
    let content = text(path)?;
    let newline = if content.contains("\r\n") { "\r\n" } else { "\n" };

    let realm = status
        .get("current_realm")
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty())
        .unwrap_or("Unknown");
    let antagonist = status
        .get("current_antagonist")
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty() && *s != "None")
        .unwrap_or("None");
    let beast = status
        .get("current_beast")
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty() && *s != "None")
        .unwrap_or("None");

    let mut squad_lines = Vec::new();
    if let Some(squad) = status.get("squad").and_then(Value::as_array) {
        for member in squad {
            if let Some(name) = member.get("name").and_then(Value::as_str) {
                if !name.trim().is_empty() {
                    squad_lines.push(format!("    - {name}"));
                }
            }
        }
    }
    let squad_block = if squad_lines.is_empty() {
        "    - None".to_string()
    } else {
        squad_lines.join(newline)
    };

    let new_header = format!(
        "# {day_str}{newline}{newline}- **🌀 Realm:** {realm}{newline}- **🛡️ Active Squad**{newline}{squad_block}{newline}- **👹 Antagonist:** {antagonist}{newline}- **👾 Prime Beast:** {beast}{newline}{newline}---"
    );

    let search_slice = content.trim_start_matches('\u{feff}');
    let header_prefix = format!("# {day_str}");
    if !search_slice.starts_with(&header_prefix) && !search_slice.starts_with("# ") {
        return Ok(());
    }

    if let Some(idx) = search_slice.find("\n## ").or_else(|| search_slice.find("\r\n## ")) {
        let rest = &search_slice[idx..];
        let updated = format!("{new_header}{rest}");
        if updated != search_slice {
            atomic(path, &updated)?;
        }
    }
    Ok(())
}

fn deploy_squad_member(body: &Value) -> Result<ApiResponse, String> {
    let name = body
        .get("name")
        .and_then(Value::as_str)
        .map(str::trim)
        .unwrap_or("");
    if name.is_empty() {
        return Ok(response_status(
            400,
            json!({"detail": "Companion name is required"}),
        ));
    }
    if name == "Keeper" {
        return Ok(response_status(
            400,
            json!({"detail": "Keeper cannot be deployed to squad"}),
        ));
    }

    let target_recall = body
        .get("target_recall")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty());
    if target_recall == Some("Keeper") {
        return Ok(response_status(
            400,
            json!({"detail": "Keeper cannot be recalled from squad"}),
        ));
    }

    let companions_dir = resolve_relative_path("Companions")?;
    let companion_path = resolve_relative_path(&format!("Companions/{name}"))?;
    if !companion_path.is_dir() || !companion_path.starts_with(&companions_dir) {
        return Ok(response_status(
            404,
            json!({"detail": format!("Companion not found: {name}")}),
        ));
    }

    let mut status = read_json(
        "Bridge/status.json",
        json!({"current_realm": "Earth", "squad": []}),
    )?;
    let squad_arr = status
        .get("squad")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();

    if squad_arr
        .iter()
        .any(|m| m.get("name").and_then(Value::as_str) == Some(name))
    {
        return Ok(response(json!({
            "status": "success",
            "message": format!("{name} is already deployed."),
            "squad": squad_arr
        })));
    }

    let mut new_squad = squad_arr;
    if new_squad.len() >= 3 {
        if let Some(target) = target_recall {
            if new_squad
                .iter()
                .any(|m| m.get("name").and_then(Value::as_str) == Some(target))
            {
                new_squad.retain(|m| m.get("name").and_then(Value::as_str) != Some(target));
            } else {
                return Ok(response_status(
                    400,
                    json!({"detail": "SQUAD FULL: Recall a member to reserve first."}),
                ));
            }
        } else {
            return Ok(response_status(
                400,
                json!({"detail": "SQUAD FULL: Recall a member to reserve first."}),
            ));
        }
    } else if let Some(target) = target_recall {
        if new_squad
            .iter()
            .any(|m| m.get("name").and_then(Value::as_str) == Some(target))
        {
            new_squad.retain(|m| m.get("name").and_then(Value::as_str) != Some(target));
        }
    }

    let mut role = "Active Personnel".to_string();
    let data_path = companion_path.join("companion_data.json");
    if data_path.is_file() {
        if let Ok(data_content) = text(&data_path) {
            if let Ok(data) = serde_json::from_str::<Value>(&data_content) {
                if let Some(r) = data.get("role").and_then(Value::as_str) {
                    role = r.to_string();
                }
            }
        }
    } else if companion_path.join("Profile.md").is_file() {
        if let Ok(profile) = text(&companion_path.join("Profile.md")) {
            if let Some(line) = profile.lines().find(|l| l.contains("**Role:**")) {
                if let Some(r) = line.split("**Role:**").nth(1) {
                    let trimmed = r.trim();
                    if !trimmed.is_empty() {
                        role = trimmed.to_string();
                    }
                }
            }
        }
    }

    let companion_stats = read_json("Bridge/CompanionStats.json", json!({}))?;
    let entry_xp = companion_stats
        .get("companions")
        .and_then(|c| c.get(name))
        .and_then(|comp| comp.get("xp"))
        .or_else(|| companion_stats.get(name).and_then(|comp| comp.get("xp")))
        .and_then(Value::as_i64)
        .unwrap_or(0);

    new_squad.push(json!({
        "name": name,
        "role": role,
        "is_vanguard": false,
        "entry_xp": entry_xp
    }));

    status["squad"] = Value::Array(new_squad.clone());
    write_json("Bridge/status.json", &status)?;
    let _ = sync_status_to_today_journal(&status);

    Ok(response(json!({
        "status": "success",
        "message": format!("{name} deployed to active squad."),
        "squad": new_squad
    })))
}

fn bench_squad_member(body: &Value) -> Result<ApiResponse, String> {
    let name = body
        .get("name")
        .and_then(Value::as_str)
        .map(str::trim)
        .unwrap_or("");
    if name.is_empty() {
        return Ok(response_status(
            400,
            json!({"detail": "Companion name is required"}),
        ));
    }
    if name == "Keeper" {
        return Ok(response_status(
            400,
            json!({"detail": "Keeper cannot be recalled to reserve"}),
        ));
    }

    let mut status = read_json(
        "Bridge/status.json",
        json!({"current_realm": "Earth", "squad": []}),
    )?;
    let squad_arr = status
        .get("squad")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();

    if !squad_arr
        .iter()
        .any(|m| m.get("name").and_then(Value::as_str) == Some(name))
    {
        return Ok(response(json!({
            "status": "success",
            "message": format!("{name} is not in the active squad."),
            "squad": squad_arr
        })));
    }

    let mut new_squad = squad_arr;
    new_squad.retain(|m| m.get("name").and_then(Value::as_str) != Some(name));

    status["squad"] = Value::Array(new_squad.clone());
    write_json("Bridge/status.json", &status)?;
    let _ = sync_status_to_today_journal(&status);

    Ok(response(json!({
        "status": "success",
        "message": format!("{name} recalled to reserve."),
        "squad": new_squad
    })))
}

fn set_vanguard(body: &Value) -> Result<ApiResponse, String> {
    let name = body
        .get("name")
        .and_then(Value::as_str)
        .map(str::trim)
        .unwrap_or("");
    if name.is_empty() {
        return Ok(response_status(
            400,
            json!({"detail": "Companion name is required"}),
        ));
    }
    if name == "Keeper" {
        return Ok(response_status(
            400,
            json!({"detail": "Keeper cannot be designated as Vanguard."}),
        ));
    }

    let mut status = read_json(
        "Bridge/status.json",
        json!({"current_realm": "Earth", "squad": []}),
    )?;
    let mut squad_arr = status
        .get("squad")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();

    if !squad_arr
        .iter()
        .any(|m| m.get("name").and_then(Value::as_str) == Some(name))
    {
        return Ok(response_status(
            400,
            json!({"detail": format!("{name} is not in the active squad.")}),
        ));
    }

    for member in squad_arr.iter_mut() {
        if let Some(m_obj) = member.as_object_mut() {
            let is_vg = m_obj.get("name").and_then(Value::as_str) == Some(name);
            m_obj.insert("is_vanguard".into(), json!(is_vg));
        }
    }

    status["squad"] = Value::Array(squad_arr.clone());
    write_json("Bridge/status.json", &status)?;
    let _ = sync_status_to_today_journal(&status);

    Ok(response(json!({
        "status": "success",
        "message": format!("{name} designated as Vanguard."),
        "squad": squad_arr
    })))
}

fn set_combat_target(body: &Value) -> Result<ApiResponse, String> {
    let target_type = body
        .get("type")
        .and_then(Value::as_str)
        .map(str::trim)
        .unwrap_or("");
    if target_type != "antagonist" && target_type != "beast" {
        return Ok(response_status(
            400,
            json!({"detail": "Invalid target type. Use 'antagonist' or 'beast'."}),
        ));
    }

    let target_name = body
        .get("name")
        .and_then(Value::as_str)
        .map(str::trim)
        .unwrap_or("");

    if !target_name.is_empty() {
        if target_name.contains('/')
            || target_name.contains('\\')
            || target_name.contains(':')
            || target_name.starts_with('.')
        {
            return Ok(response_status(
                400,
                json!({"detail": format!("Invalid target name: {target_name}")}),
            ));
        }

        let base = if target_type == "antagonist" {
            "Obstacles/Antagonists"
        } else {
            "Obstacles/Beasts"
        };
        let base_dir = resolve_relative_path(base)?;
        let target_path = resolve_relative_path(&format!("{base}/{target_name}"))?;
        if !target_path.is_dir() || !target_path.starts_with(&base_dir) {
            return Ok(response_status(
                400,
                json!({"detail": format!("Invalid target: {target_name} not found")}),
            ));
        }
    }

    let mut status_val = read_json(
        "Bridge/status.json",
        json!({"current_realm": "Earth", "squad": []}),
    )?;
    if target_type == "antagonist" {
        status_val["current_antagonist"] = json!(target_name);
    } else {
        status_val["current_beast"] = json!(target_name);
    }
    write_json("Bridge/status.json", &status_val)?;
    let _ = sync_status_to_today_journal(&status_val);

    let current_status = status()?;
    let capitalized = if target_type == "antagonist" {
        "Antagonist"
    } else {
        "Beast"
    };
    let message = if target_name.is_empty() {
        format!("{capitalized} cleared")
    } else {
        format!("{capitalized} updated to {target_name}")
    };

    Ok(response(json!({
        "status": "success",
        "message": message,
        "current_status": current_status
    })))
}

fn combat_log(path: &str) -> Result<ApiResponse, String> {
    let limit = query(path, "limit")
        .and_then(|s| s.parse::<usize>().ok())
        .unwrap_or(50);
    let log_path = resolve_relative_path("Battle/Combat_Log.md");
    let p = match log_path {
        Ok(ref p) if p.is_file() => p,
        _ => return Ok(response(json!({"logs": ["> Combat Log Offline."]}))),
    };

    let content = match text(p) {
        Ok(c) => c,
        Err(e) => return Ok(response(json!({"logs": [format!("> Error reading log: {e}")]}))),
    };

    let mut logs = Vec::new();
    for line in content.lines().rev() {
        let trimmed = line.trim();
        if trimmed.starts_with('>') {
            logs.push(json!(trimmed));
            if logs.len() >= limit {
                break;
            }
        }
    }

    if logs.is_empty() {
        logs.push(json!("> Combat Log Offline."));
    }

    Ok(response(json!({"logs": logs})))
}

fn adjust_bio(body: &Value) -> Result<ApiResponse, String> {
    let field = body
        .get("field")
        .and_then(Value::as_str)
        .map(str::trim)
        .unwrap_or("");
    if field.is_empty() {
        return Ok(response_status(400, json!({"detail": "Field is required"})));
    }
    if field.eq_ignore_ascii_case("xp") {
        return Ok(response_status(
            422,
            json!({"detail": "XP must be recorded through the entity-scoped progression ledger."}),
        ));
    }

    let delta = body.get("delta").and_then(Value::as_i64).unwrap_or(0);
    let companion_name = body
        .get("companion_name")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty());

    if let Some(comp_name) = companion_name {
        let mut cstats = read_json("Bridge/CompanionStats.json", json!({}))?;
        let companions = cstats.get_mut("companions").and_then(Value::as_object_mut);
        let companions = match companions {
            Some(c) => c,
            None => {
                return Ok(response_status(
                    500,
                    json!({"detail": "Could not load companion stats."}),
                ))
            }
        };
        let comp = match companions.get_mut(comp_name) {
            Some(c) => c,
            None => {
                return Ok(response_status(
                    404,
                    json!({"detail": format!("Companion {comp_name} not found.")}),
                ))
            }
        };

        if matches!(field, "STR" | "AGI" | "INT") {
            if let Some(comp_obj) = comp.as_object_mut() {
                let stats_val = comp_obj.entry("stats").or_insert_with(|| json!({}));
                if let Some(sb) = stats_val.as_object_mut() {
                    let curr = sb.get(field).and_then(Value::as_i64).unwrap_or(0);
                    sb.insert(field.to_string(), json!(curr + delta));
                }
            }
        } else {
            let curr = comp.get(field).and_then(Value::as_i64).unwrap_or(0);
            if let Some(comp_obj) = comp.as_object_mut() {
                comp_obj.insert(field.to_string(), json!(curr + delta));
            }
        }

        let updated_comp = comp.clone();
        write_json("Bridge/CompanionStats.json", &cstats)?;

        Ok(response(json!({
            "status": "success",
            "message": format!("Adjusted {comp_name}'s {field} by {delta}"),
            "data": updated_comp
        })))
    } else {
        let mut status_val = read_json(
            "Bridge/status.json",
            json!({"current_realm": "Earth", "squad": []}),
        )?;
        let curr = status_val.get(field).and_then(Value::as_i64).unwrap_or(0);
        if let Some(status_obj) = status_val.as_object_mut() {
            status_obj.insert(field.to_string(), json!(curr + delta));
        }
        write_json("Bridge/status.json", &status_val)?;
        let _ = sync_status_to_today_journal(&status_val);

        Ok(response(json!({
            "status": "success",
            "message": format!("Adjusted status {field} by {delta}"),
            "data": status_val
        })))
    }
}

fn vault_file(relative: &str) -> Result<Value, String> {
    let decoded = percent_decode_str(relative)
        .decode_utf8()
        .map_err(|e| e.to_string())?;
    let path = resolve_relative_path(&decoded)?;
    if path.is_dir() {
        let mut items = Vec::new();
        for entry in fs::read_dir(&path).map_err(|e| e.to_string())?.flatten() {
            let p = entry.path();
            let name = p
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();
            if name.starts_with('.') {
                continue;
            }
            let rel = vault_relative_path(&p)?;
            items.push(json!({"name":name.trim_end_matches(".md"),"path":rel,"type":if p.is_dir(){"directory"}else{"file"}}));
        }
        return Ok(
            json!({"content":{"type":"directory_listing","name":path.file_name().unwrap_or_default().to_string_lossy(),"items":items}}),
        );
    }
    let raw = text(&path)?;
    if relative.ends_with(".json") {
        return serde_json::from_str(&raw).map_err(|e| e.to_string());
    }
    Ok(json!({"content":raw,"path":relative}))
}

fn entity_profile(path: &str) -> Result<Value, String> {
    let parts: Vec<_> = route(path)
        .trim_start_matches("/api/entity/")
        .splitn(2, '/')
        .collect();
    if parts.len() != 2 {
        return Err("entity type and name are required".into());
    }
    let entity_type = percent_decode_str(parts[0])
        .decode_utf8()
        .map_err(|e| e.to_string())?;
    let entity_name = percent_decode_str(parts[1])
        .decode_utf8()
        .map_err(|e| e.to_string())?;
    let mapped_type = match entity_type.to_lowercase().as_str() {
        "companion" => "Companions",
        "resident" => "Residents",
        "realm" => "Realms",
        "antagonist" => "Antagonists",
        "beast" => "Beasts",
        "companions" => "Companions",
        "residents" => "Residents",
        "realms" => "Realms",
        "antagonists" => "Antagonists",
        "beasts" => "Beasts",
        _ => return Err("invalid entity type".into()),
    };
    let base = if matches!(mapped_type, "Antagonists" | "Beasts") {
        format!("Obstacles/{mapped_type}")
    } else {
        mapped_type.to_string()
    };
    let entity_dir = resolve_relative_path(&format!("{base}/{entity_name}"))?;
    if !entity_dir.is_dir() {
        return Err("entity not found".into());
    }

    let profile_file = if mapped_type == "Realms" {
        "Realm.md"
    } else {
        "Profile.md"
    };
    let profile_path = entity_dir.join(profile_file);
    if !profile_path.is_file() {
        return Err("profile not found".into());
    }
    let content = text(&profile_path)?;
    let mut attributes = serde_json::Map::new();
    let mut sections = Vec::new();
    let mut current_title: Option<String> = None;
    let mut current_text = Vec::new();
    let mut in_frontmatter = false;
    for line in content.lines() {
        if line.starts_with("---")
            && !in_frontmatter
            && attributes.is_empty()
            && sections.is_empty()
        {
            in_frontmatter = true;
            continue;
        }
        if line.starts_with("---") && in_frontmatter {
            in_frontmatter = false;
            continue;
        }
        if in_frontmatter {
            continue;
        }
        if let Some(title) = line.strip_prefix("## ") {
            if let Some(previous) = current_title.take() {
                sections
                    .push(json!({"title": previous, "content": current_text.join("\n").trim()}));
            }
            current_title = Some(title.trim().to_string());
            current_text.clear();
        } else if let Some(attribute) = line.strip_prefix("- **") {
            if current_title.is_none() {
                if let Some((key, value)) = attribute.split_once(":**") {
                    attributes.insert(key.trim().to_string(), json!(value.trim()));
                }
            } else {
                current_text.push(line.to_string());
            }
        } else if current_title.is_some() {
            current_text.push(line.to_string());
        }
    }
    if let Some(title) = current_title {
        sections.push(json!({"title": title, "content": current_text.join("\n").trim()}));
    }

    let asset_url = |file: &str| -> String { format!("/api/vault/{base}/{entity_name}/{file}") };
    let find_asset = |names: &[&str]| -> Option<String> {
        for name in names {
            for extension in ["png", "jpg", "jpeg", "webp"] {
                let file = format!("{name}.{extension}");
                if entity_dir.join(&file).is_file() {
                    return Some(asset_url(&file));
                }
            }
        }
        None
    };
    let card_url = find_asset(&["Card"]);
    let portrait_url = find_asset(&["Portrait", "Landscape"]).or_else(|| card_url.clone());
    let card_url = card_url.or_else(|| portrait_url.clone());

    Ok(json!({
        "name": entity_name,
        "type": mapped_type,
        "attributes": attributes,
        "sections": sections,
        "portrait_url": portrait_url,
        "card_url": card_url,
        "sub_documents": [],
        "raw": content
    }))
}

fn ops() -> Result<Value, String> {
    read_json(
        "Bridge/ops_state.json",
        json!({"tasks":[],"active_tasks":[]}),
    )
}
fn canonical_task_area(area: &str) -> String {
    let value = area.trim().to_lowercase();
    match value.as_str() {
        "gauntlet" => "bureaucratic".into(),
        "outland" => "world".into(),
        _ => value,
    }
}

fn task_list(state: &Value, collection: &str, area: Option<&str>) -> Value {
    task_list_view(state, collection, area, false)
}

fn task_list_view(state: &Value, collection: &str, area: Option<&str>, include_completed: bool) -> Value {
    let tasks = state.get(collection).and_then(Value::as_array).cloned().unwrap_or_default();
    let area = area.map(canonical_task_area).filter(|a| !a.is_empty());
    json!(tasks.into_iter().filter(|t| include_completed || collection != "active_tasks" || t.get("status").and_then(Value::as_str) != Some("completed")).filter(|t| area.as_ref().map_or(true, |a|
        canonical_task_area(t.get("area").and_then(Value::as_str).unwrap_or("")) == *a
    )).collect::<Vec<_>>())
}

fn mutate_task_state(state: &mut Value, collection: &str, method: &str, id: Option<&str>, body: &Value) -> Result<Value, String> {
    let mut item = body.clone();
    if collection == "active_tasks" {
        let map = item.as_object_mut().ok_or("task body must be an object")?;
        map.retain(|key, _| matches!(key.as_str(), "id" | "text" | "area" | "status"));
        if method == "POST" { map.insert("status".into(), json!("pending")); }
    }
    if method == "POST" || method == "PUT" {
        let m = item.as_object_mut().ok_or("task body must be an object")?;
        if let Some(area) = m.get("area").filter(|v| !v.is_null()) {
            let area = area.as_str().ok_or("area must be a string")?;
            m.insert("area".into(), json!(canonical_task_area(area)));
        }
    }
    if method == "POST" {
        let supplied = item.get("id").cloned();
        let candidate = supplied.unwrap_or_else(|| json!(uuid::Uuid::new_v4().to_string()));
        let candidate_id = candidate.as_str().filter(|v| !v.is_empty()).ok_or("id must be a nonempty string")?;
        if ["tasks", "active_tasks"].iter().any(|key| state.get(*key).and_then(Value::as_array).map_or(false, |list|
            list.iter().any(|t| t.get("id").and_then(Value::as_str) == Some(candidate_id)))) {
            return Err("Duplicate task ID".into());
        }
        item.as_object_mut().unwrap().insert("id".into(), candidate);
    }
    let list = state.as_object_mut().ok_or("invalid ops state")?.entry(collection)
        .or_insert(json!([])).as_array_mut().ok_or("invalid task collection")?;
    match method {
        "POST" => {
            if collection == "tasks" { crate::recurrence::initialize(&mut item)?; }
            item.as_object_mut().unwrap().entry("status").or_insert(json!("pending"));
            list.push(item.clone());
            Ok(json!({"status":"success","task":item}))
        }
        "PUT" | "DELETE" => {
            let id = id.ok_or("task ID required")?;
            let matches: Vec<_> = list.iter().enumerate().filter(|(_, t)| t.get("id").and_then(Value::as_str) == Some(id)).map(|(i, _)| i).collect();
            if matches.len() > 1 { return Err("Ambiguous duplicate task ID; repair IDs before mutation".into()); }
            let index = *matches.first().ok_or("Task not found")?;
            if collection == "active_tasks" {
                if list[index].get("completion").is_some() { return Err("Completion history is immutable".into()); }
                if let Some(status) = item.get("status") {
                    if status != list[index].get("status").unwrap_or(&json!("pending")) { return Err("Use explicit completion transition".into()); }
                }
            }
            if method == "DELETE" {
                list.remove(index);
                return Ok(json!({"status":"success"}));
            }
            if collection == "tasks" { crate::recurrence::update(&list[index], &mut item)?; }
            let task = list[index].as_object_mut().ok_or("invalid task")?;
            for (k, v) in item.as_object().unwrap() {
                if k != "id" && !v.is_null() { task.insert(k.clone(), v.clone()); }
            }
            Ok(json!({"status":"success","task":task}))
        }
        _ => Err("unsupported task mutation".into()),
    }
}

fn mutate(collection: &str, method: &str, id: Option<&str>, body: &Value) -> Result<Value, String> {
    let mut state = ops()?;
    let result = mutate_task_state(&mut state, collection, method, id, body)?;
    write_json("Bridge/ops_state.json", &state)?;
    Ok(result)
}
pub fn request(path: &str, method: &str, body: Option<Value>) -> Result<ApiResponse, String> {
    let r = route(path);
    let body = body.unwrap_or(json!({}));
    let value = match (method, r) {
        ("POST", "/api/squad/deploy") => return deploy_squad_member(&body),
        ("POST", "/api/squad/bench") => return bench_squad_member(&body),
        ("POST", "/api/squad/vanguard") => return set_vanguard(&body),
        ("POST", "/api/combat/target") => return set_combat_target(&body),
        ("GET", "/api/combat/log") => return combat_log(path),
        ("POST", "/api/bio/adjust") => return adjust_bio(&body),
        ("GET", "/api/status") => status()?,
        ("GET", "/api/settings") => settings()?,
        ("GET", "/api/navigation") | ("GET", "/api/navigation/pillars") => navigation()?,
        ("GET", "/api/readiness") => read_json("Bridge/readiness.json", json!({}))?,
        ("GET", "/api/journal/month") => return Ok(journal_month(path)),
        ("POST", "/api/journal/entry") => return Err("Journal appends require the canonical journal bridge".into()),
        ("GET", "/api/ops") => ops()?,
        ("GET", "/api/entities") => list_entities(&query(path, "sectorId").unwrap_or_default())?,
        ("GET", "/api/holocron/weekly/manifest") => holocron_manifest()?,
        ("GET", r) if r.starts_with("/api/holocron/weekly/") && r.ends_with("/html") => {
            let wid = r.trim_start_matches("/api/holocron/weekly/").trim_end_matches("/html");
            let decoded = percent_decode_str(wid).decode_utf8().map_err(|e| e.to_string())?;
            let relative = format!("Bridge/Holocron/Weekly/{decoded}.html");
            let p = resolve_relative_path(&relative)?;
            if p.is_file() {
                let content = fs::read_to_string(&p).map_err(|e| e.to_string())?;
                return Ok(ApiResponse {
                    status: 200,
                    text: content.clone(),
                    body: json!({ "html": content }),
                });
            } else {
                return Err(format!("Holocron HTML not found: {relative}"));
            }
        }
        ("GET", r) if r.starts_with("/api/holocron/weekly/") => {
            let wid = r.trim_start_matches("/api/holocron/weekly/");
            let decoded = percent_decode_str(wid).decode_utf8().map_err(|e| e.to_string())?;
            let relative = format!("Bridge/Holocron/Weekly/{decoded}.json");
            let p = resolve_relative_path(&relative)?;
            if p.is_file() {
                read_json(&relative, json!({}))?
            } else {
                return Err(format!("Holocron cycle not found: {relative}"));
            }
        }
        ("GET", "/api/companions") => list_entities("COMPANIONS")?,
        ("GET", "/api/antagonists") => list_entities("ANTAGONISTS")?,
        ("GET", "/api/beasts") => list_entities("BEASTS")?,
        ("GET", "/api/realm/options") => realm_options()?,
        ("GET", "/api/realm/draft") => realm_draft(path)?,
        ("POST", "/api/realm/hop") => execute_realm_hop(&body)?,
        ("GET", r) if r.starts_with("/api/entity/") => entity_profile(path)?,
        ("GET", "/api/recurring") => task_list(&ops()?, "tasks", query(path, "area").as_deref()),
        ("GET", "/api/active_tasks") => task_list_view(&ops()?, "active_tasks", query(path, "area").as_deref(), query(path, "include_completed").as_deref() == Some("true")),
        ("GET", "/api/vault/") => json!({}),
        ("GET", r) if r.starts_with("/api/vault/") => {
            vault_file(r.trim_start_matches("/api/vault/"))?
        }
        ("POST", "/api/status/mission") => {
            let mut s = status()?;
            let i = body
                .get("slot_index")
                .and_then(Value::as_u64)
                .ok_or("slot_index required")? as usize;
            let mission = body
                .get("mission_name")
                .cloned()
                .ok_or("mission_name required")?;
            let a = s
                .get_mut("active_missions")
                .and_then(Value::as_array_mut)
                .ok_or("active_missions missing")?;
            if i >= a.len() {
                return Err("slot_index out of range".into());
            }
            a[i] = mission;
            let missions = a.clone();
            write_json("Bridge/status.json", &s)?;
            json!({"status":"success","active_missions":missions})
        }
        ("POST", "/api/tasks/toggle") => {
            return Err("Checkbox mutations require the canonical task bridge".into());
        }
        ("PUT", r) if r.starts_with("/api/vault/") => {
            let raw_rel = r.trim_start_matches("/api/vault/");
            let decoded = percent_decode_str(raw_rel)
                .decode_utf8()
                .map_err(|e| e.to_string())?;
            let mut p = resolve_relative_path(&decoded)?;
            if p.is_dir() {
                for candidate in ["Profile.md", "profile.md", "README.md", "readme.md"] {
                    let cand_path = p.join(candidate);
                    if cand_path.is_file() {
                        p = cand_path;
                        break;
                    }
                }
            }
            atomic(
                &p,
                body.get("content")
                    .and_then(Value::as_str)
                    .ok_or("content required")?,
            )?;
            json!({"status":"success"})
        }
        ("POST", "/api/recurring") => mutate("tasks", "POST", None, &body)?,
        ("PUT", r) if r.starts_with("/api/recurring/") => {
            mutate("tasks", "PUT", r.rsplit('/').next(), &body)?
        }
        ("DELETE", r) if r.starts_with("/api/recurring/") => {
            mutate("tasks", "DELETE", r.rsplit('/').next(), &body)?
        }
        ("POST", "/api/active_tasks") => mutate("active_tasks", "POST", None, &body)?,
        ("PUT", r) if r.starts_with("/api/active_tasks/") => {
            mutate("active_tasks", "PUT", r.rsplit('/').next(), &body)?
        }
        ("DELETE", r) if r.starts_with("/api/active_tasks/") => {
            mutate("active_tasks", "DELETE", r.rsplit('/').next(), &body)?
        }
        _ => {
            return Err(format!(
                "native Vault route not implemented: {method} {path}"
            ))
        }
    };
    Ok(response(value))
}

pub fn holocron_request(
    backend: &Path,
    path: &str,
    method: &str,
    body: Option<Value>,
) -> Result<ApiResponse, String> {
    // Revalidate sources in the shared engine, including for concluded cycles
    // and HTML. Legacy cached telemetry cannot establish current evidence.
    python_holocron(backend, path, method, body)
}

fn python_holocron(
    backend: &Path,
    path: &str,
    method: &str,
    body: Option<Value>,
) -> Result<ApiResponse, String> {
    let runtime = crate::command::resolve_python_runtime(backend, !cfg!(debug_assertions))?;
    let mut command = crate::command::hidden_command(&runtime.to_string_lossy());
    command
        .arg(backend.join("native_holocron.py"))
        .current_dir(backend)
        .env_clear();
    for key in ["PATH", "SystemRoot", "TEMP", "TMP"] {
        if let Ok(value) = std::env::var(key) {
            command.env(key, value);
        }
    }
    command
        .env("NAVIS_ROOT", root()?)
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUTF8", "1")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let mut child = command
        .spawn()
        .map_err(|e| format!("Local holocron runtime unavailable: {e}"))?;
    let input = serde_json::to_vec(&json!({
        "path": path,
        "method": method,
        "body": body.unwrap_or(json!({}))
    }))
    .map_err(|e| e.to_string())?;
    child
        .stdin
        .take()
        .ok_or("holocron stdin unavailable")?
        .write_all(&input)
        .map_err(|e| e.to_string())?;
    let output = child.wait_with_output().map_err(|e| e.to_string())?;
    if !output.status.success() {
        let err_msg = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Local holocron synthesis failed: {err_msg}"));
    }
    let envelope: Value = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("invalid holocron response: {e}"))?;
    let body = envelope
        .get("body")
        .cloned()
        .ok_or("missing holocron response body")?;
    let status = envelope
        .get("status")
        .and_then(Value::as_u64)
        .ok_or("missing holocron status")? as u16;
    let text = if let Some(html) = body.get("html").and_then(Value::as_str) {
        html.to_string()
    } else {
        serde_json::to_string(&body).map_err(|e| e.to_string())?
    };
    Ok(ApiResponse {
        status,
        body,
        text,
    })
}


#[cfg(test)]
mod tests {
    use std::fs;

    #[test]
    fn status_unavailability_does_not_become_an_earth_default() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-status-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(root.join("Bridge")).unwrap();
        let old_root = std::env::var_os("NAVIS_ROOT");
        std::env::set_var("NAVIS_ROOT", &root);
        assert!(super::status().is_err());
        for content in ["{", "[]", "{}", r#"{"squad":null}"#, r#"{"squad":[null]}"#] {
            fs::write(root.join("Bridge/status.json"), content).unwrap();
            assert!(super::status().is_err());
        }
        for content in [r#"{"squad":[]}"#, r#"{"last_updated":"2026-10-26"}"#] {
            fs::write(root.join("Bridge/status.json"), content).unwrap();
            assert!(super::status().is_ok());
        }
        match old_root { Some(value) => std::env::set_var("NAVIS_ROOT", value), None => std::env::remove_var("NAVIS_ROOT") }
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn calendar_distinguishes_unavailable_empty_and_valid_entries() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-calendar-{}", uuid::Uuid::new_v4()));
        fs::create_dir(&root).unwrap();
        let old_root = std::env::var_os("NAVIS_ROOT");
        std::env::set_var("NAVIS_ROOT", &root);
        let path = "/api/journal/month?year=2026&month=10";
        assert_eq!(super::journal_month(path).status, 503);
        fs::create_dir(root.join("Journal")).unwrap();
        let empty = super::journal_month(path);
        assert_eq!(empty.status, 200);
        assert_eq!(empty.body, json!({"availability":"available","dates":[],"year":2026,"month":10}));
        fs::write(root.join("Journal/2026"), "not a directory").unwrap();
        assert_eq!(super::journal_month(path).status, 503);
        fs::remove_file(root.join("Journal/2026")).unwrap();
        fs::create_dir_all(root.join("Journal/2026/10")).unwrap();
        for name in ["2026-10-02.md", "2026-10-01.md", "2026-10-32.md", "2026-09-01.md", "notes.md"] {
            fs::write(root.join("Journal/2026/10").join(name), "synthetic").unwrap();
        }
        fs::create_dir(root.join("Journal/2026/10/2026-10-03.md")).unwrap();
        let loaded = super::journal_month(path);
        assert_eq!(loaded.status, 200);
        assert_eq!(loaded.body["dates"], json!(["2026-10-01","2026-10-02"]));
        for query in ["year=0&month=10", "year=2026&month=13", "year=10000&month=1", "year=../Keeper&month=1"] {
            assert_eq!(super::journal_month(&format!("/api/journal/month?{query}")).status, 400);
        }
        match old_root { Some(value) => std::env::set_var("NAVIS_ROOT", value), None => std::env::remove_var("NAVIS_ROOT") }
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn holocron_reads_revalidate_in_python_instead_of_trusting_cached_files() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-holocron-evidence-{}", uuid::Uuid::new_v4()));
        let backend = root.join("backend");
        fs::create_dir_all(&backend).unwrap();
        fs::create_dir_all(root.join("Bridge/Holocron/Weekly")).unwrap();
        fs::write(root.join("Bridge/Holocron/Weekly/2026-W40.json"), r#"{"legacy":true}"#).unwrap();
        fs::write(root.join("Bridge/Holocron/Weekly/2026-W40.html"), "legacy HTML").unwrap();
        fs::write(backend.join("native_holocron.py"), "import json,sys\nr=json.load(sys.stdin)\nprint(json.dumps({'status':200,'body':{'revalidated':r['path']}}))\n").unwrap();
        let real_backend = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../backend");
        let runtime = crate::command::resolve_python_runtime(&real_backend, false).unwrap();
        let old_root = std::env::var_os("NAVIS_ROOT");
        let old_python = std::env::var_os("NAVIS_PYTHON");
        std::env::set_var("NAVIS_ROOT", &root);
        std::env::set_var("NAVIS_PYTHON", runtime);
        for path in ["/api/holocron/weekly/2026-W40", "/api/holocron/weekly/2026-W40/html", "/api/holocron/weekly/2026-W40/evidence/journal-2026-09-28"] {
            let result = super::holocron_request(&backend, path, "GET", None).unwrap();
            assert_eq!(result.body["revalidated"], path);
        }
        match old_root { Some(value) => std::env::set_var("NAVIS_ROOT", value), None => std::env::remove_var("NAVIS_ROOT") }
        match old_python { Some(value) => std::env::set_var("NAVIS_PYTHON", value), None => std::env::remove_var("NAVIS_PYTHON") }
        fs::remove_dir_all(root).unwrap();
    }

    #[cfg(windows)]
    #[test]
    fn stopping_idle_watcher_terminates_without_stdout_activity() {
        let state = super::VaultWatcherState::default();
        let mut child = crate::command::hidden_command("cmd.exe")
            .args(["/C", "ping -n 60 127.0.0.1 >nul"])
            .stdout(std::process::Stdio::piped()).spawn().unwrap();
        *state.process_job.lock().unwrap() = Some(crate::operations::attach_windows_job(&child).unwrap());
        state.stop();
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(3);
        while child.try_wait().unwrap().is_none() {
            assert!(std::time::Instant::now() < deadline, "idle watcher did not terminate");
            std::thread::sleep(std::time::Duration::from_millis(20));
        }
        state.stop(); // Already closed handles must not be reused.
        assert!(state.process_job.lock().unwrap().is_none());
    }
    use std::sync::{Mutex, OnceLock};

    use serde_json::{json, Value};

    use super::resolve_relative_path;

    #[test]
    fn task_area_identity_and_duplicate_fixtures() {
        for collection in ["tasks", "active_tasks"] {
            let mut state = json!({"tasks":[],"active_tasks":[],"unrelated":{"keep":"雪"}});
            state[collection] = json!([{"id":"imported","area":"GAUNTLET","text":"legacy"}]);
            let first = super::mutate_task_state(&mut state, collection, "POST", None, &json!({"area":" GaUnTlEt ","text":"first"})).unwrap()["task"].clone();
            let second = super::mutate_task_state(&mut state, collection, "POST", None, &json!({"area":"OUTLAND","text":"second"})).unwrap()["task"].clone();
            assert_eq!(first["area"], "bureaucratic");
            assert_eq!(second["area"], "world");
            let mut ids = std::collections::HashSet::new();
            for _ in 0..100 {
                let result = super::mutate_task_state(&mut state, collection, "POST", None, &json!({"area":"Sanctum"})).unwrap();
                let id = result["task"]["id"].as_str().unwrap();
                assert_eq!(id.len(), 36);
                assert!(ids.insert(id.to_string()));
            }
            for area in ["GAUNTLET", "bureaucratic", " Bureaucratic "] {
                assert_eq!(super::task_list(&state, collection, Some(area)).as_array().unwrap().len(), 2);
            }
            assert_eq!(super::task_list(&state, collection, None).as_array().unwrap().len(), 103);
            assert_eq!(super::task_list(&state, collection, Some(" ")).as_array().unwrap().len(), 103);
            let id = first["id"].as_str().unwrap();
            let changed = super::mutate_task_state(&mut state, collection, "PUT", Some(id), &json!({"area":"oUtLaNd","id":"replace","text":"changed"})).unwrap();
            assert_eq!(changed["task"]["id"], id);
            assert_eq!(changed["task"]["area"], "world");
            super::mutate_task_state(&mut state, collection, "DELETE", Some(id), &json!({})).unwrap();
            assert_eq!(super::task_list(&state, collection, Some("World"))[0]["id"], second["id"]);
            assert_eq!(state["unrelated"]["keep"], "雪");
            assert_eq!(state[collection][0]["id"], "imported");
            let before = state.clone();
            assert!(super::mutate_task_state(&mut state, collection, "POST", None, &json!({"id":"imported"})).is_err());
            assert_eq!(state, before);
            state[collection].as_array_mut().unwrap().extend([json!({"id":"duplicate"}),json!({"id":"duplicate"})]);
            for method in ["PUT", "DELETE"] {
                let before = state.clone();
                assert!(super::mutate_task_state(&mut state, collection, method, Some("duplicate"), &json!({"text":"bad"})).unwrap_err().contains("Ambiguous"));
                assert_eq!(state, before);
                assert!(super::mutate_task_state(&mut state, collection, method, Some("missing"), &json!({})).is_err());
            }
        }
    }

    #[test]
    fn task_routes_filter_and_persist_synthetic_vault() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-task-routes-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(root.join("Bridge")).unwrap();
        std::env::set_var("NAVIS_ROOT", &root);
        fs::write(root.join("Bridge/ops_state.json"), r#"{"tasks":[],"active_tasks":[],"keep":"fixture"}"#).unwrap();
        for route in ["/api/recurring", "/api/active_tasks"] {
            let first = super::request(route, "POST", Some(json!({"area":"Gauntlet","text":"first"}))).unwrap().body["task"].clone();
            let second = super::request(route, "POST", Some(json!({"area":"Outland","text":"second"}))).unwrap().body["task"].clone();
            if route == "/api/recurring" {
                assert!(first["last_done"].is_null());
                assert!(first["next_due"].as_str().is_some());
                let path = format!("{route}/{}", first["id"].as_str().unwrap());
                for _ in 0..2 {
                    let done = super::request(&path, "PUT", Some(json!({"frequency":"monthly", "last_done":"2024-01-31", "next_due":"2099-01-01"}))).unwrap();
                    assert_eq!(done.body["task"]["next_due"], "2024-02-29");
                    assert_eq!(super::ops().unwrap()["tasks"][0]["next_due"], "2024-02-29");
                }
                let changed = super::request(&path, "PUT", Some(json!({"frequency":"every 2 months"}))).unwrap();
                assert_eq!(changed.body["task"]["next_due"], "2024-03-31");
                let before = fs::read(root.join("Bridge/ops_state.json")).unwrap();
                assert!(super::request(&path, "PUT", Some(json!({"last_done":"2026-02-30"}))).is_err());
                assert_eq!(fs::read(root.join("Bridge/ops_state.json")).unwrap(), before);
            }
            let filtered = super::request(&format!("{route}?area=GAUNTLET"), "GET", None).unwrap();
            assert_eq!(filtered.body.as_array().unwrap().len(), 1);
            assert_eq!(filtered.body[0]["id"], first["id"]);
            let item_path = format!("{route}/{}", first["id"].as_str().unwrap());
            super::request(&item_path, "PUT", Some(json!({"area":"Outland"}))).unwrap();
            assert_eq!(super::request(&format!("{route}?area=world"), "GET", None).unwrap().body.as_array().unwrap().len(), 2);
            super::request(&item_path, "DELETE", None).unwrap();
            assert_eq!(super::request(route, "GET", None).unwrap().body[0]["id"], second["id"]);
        }
        assert_eq!(super::ops().unwrap()["keep"], "fixture");
        fs::remove_dir_all(root).unwrap();
    }

    static ENV_LOCK: OnceLock<Mutex<()>> = OnceLock::new();

    #[test]
    fn keeper_entities_list_markdown_files_and_report_missing_source() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir()
            .join(format!("navis-keeper-entities-{}", uuid::Uuid::new_v4()));
        let keeper = root.join("Keeper");
        fs::create_dir_all(&keeper).unwrap();
        fs::write(keeper.join("Ledger.md"), "synthetic keeper record").unwrap();
        fs::write(keeper.join("navis_progression.db"), b"synthetic database").unwrap();
        fs::create_dir_all(keeper.join("Nested")).unwrap();
        fs::write(keeper.join("Nested/ignored.md"), "nested fixture").unwrap();
        std::env::set_var("NAVIS_ROOT", &root);

        let entities = super::request("/api/entities?sectorId=KEEPER", "GET", None).unwrap().body;
        assert_eq!(entities, json!([{"id":"Keeper/Ledger.md","name":"Ledger","type":"file"}]));
        fs::remove_file(keeper.join("Ledger.md")).unwrap();
        assert_eq!(super::request("/api/entities?sectorId=KEEPER", "GET", None).unwrap().body, json!([]));
        fs::remove_dir_all(&keeper).unwrap();
        assert!(super::request("/api/entities?sectorId=KEEPER", "GET", None).unwrap_err().contains("Keeper source directory is unavailable"));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn atomic_write_replaces_existing_bytes_with_bom_and_unicode() {
        let root = std::env::temp_dir().join(format!("navis-atomic-success-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        let path = root.join("state.json");
        fs::write(&path, b"previous state").unwrap();
        super::atomic(&path, "{\"name\":\"Synthetic ☃\"}").unwrap();
        let bytes = fs::read(&path).unwrap();
        assert!(bytes.starts_with(&[0xEF, 0xBB, 0xBF]));
        assert_eq!(super::text(&path).unwrap(), "{\"name\":\"Synthetic ☃\"}");
        assert_eq!(fs::read_dir(&root).unwrap().count(), 1);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn failed_atomic_rename_preserves_destination_cleans_temp_and_can_retry() {
        let root = std::env::temp_dir().join(format!("navis-atomic-failure-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        let destination = root.join("state.json");
        fs::create_dir(&destination).unwrap();
        fs::write(destination.join("preserve.txt"), b"unrelated bytes").unwrap();
        assert!(super::atomic(&destination, "new state").is_err());
        assert_eq!(fs::read(destination.join("preserve.txt")).unwrap(), b"unrelated bytes");
        assert_eq!(fs::read_dir(&root).unwrap().count(), 1, "failed rename must remove staging file");
        fs::remove_dir_all(&destination).unwrap();
        super::atomic(&destination, "retry state").unwrap();
        assert_eq!(super::text(&destination).unwrap(), "retry state");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn asset_response_reads_encoded_vault_images_and_rejects_traversal() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-vault-asset-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(root.join("Companions/Ava & Echo")).expect("asset directory");
        fs::write(
            root.join("Companions/Ava & Echo/Portrait.png"),
            [1_u8, 2, 3],
        )
        .expect("image fixture");
        std::env::set_var("NAVIS_ROOT", &root);

        let (bytes, content_type) =
            super::asset_response("Companions/Ava%20%26%20Echo/Portrait.png")
                .expect("encoded image path");
        assert_eq!(bytes, [1, 2, 3]);
        assert_eq!(content_type, "image/png");
        assert!(super::asset_response("%2e%2e/secret.png").is_err());
        assert!(super::asset_response("Companions/Ava%20%26%20Echo/Missing.png").is_err());
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn asset_resolution_with_emojis_spaces_and_non_ascii_characters() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-vault-unicode-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);

        // 1. Path with emojis and spaces in folder and filename
        let emoji_dir = root.join("Companions/🛡️ Aegis ⚔️");
        fs::create_dir_all(&emoji_dir).expect("emoji directory");
        fs::write(emoji_dir.join("Portrait 🌟.png"), [10_u8, 20, 30]).expect("emoji image fixture");

        // 2. Path with multiple spaces
        let space_dir = root.join("Realms/The Outer Rim Horizon");
        fs::create_dir_all(&space_dir).expect("space directory");
        fs::write(space_dir.join("Deep Space Landscape.webp"), [40_u8, 50, 60]).expect("space image fixture");

        // 3. Path with Windows non-ASCII Unicode characters (accents, umlauts, CJK)
        let unicode_dir = root.join("Library/Lore/München Café & Forêt");
        fs::create_dir_all(&unicode_dir).expect("unicode accents directory");
        fs::write(unicode_dir.join("Château 1880.avif"), [70_u8, 80, 90]).expect("unicode avif fixture");

        let cjk_dir = root.join("Journal/2026/09/雪の国");
        fs::create_dir_all(&cjk_dir).expect("cjk directory");
        fs::write(cjk_dir.join("地図.svg"), b"<svg></svg>").expect("cjk svg fixture");

        std::env::set_var("NAVIS_ROOT", &root);

        // Test 1: Emoji raw and percent-encoded paths
        let (bytes1, mime1) = super::asset_response("Companions/🛡️ Aegis ⚔️/Portrait 🌟.png")
            .expect("raw emoji asset resolution");
        assert_eq!(bytes1, [10, 20, 30]);
        assert_eq!(mime1, "image/png");

        let (bytes1_enc, mime1_enc) = super::asset_response(
            "Companions/%F0%9F%9B%A1%EF%B8%8F%20Aegis%20%E2%9A%94%EF%B8%8F/Portrait%20%F0%9F%8C%9F.png",
        )
        .expect("percent-encoded emoji asset resolution");
        assert_eq!(bytes1_enc, [10, 20, 30]);
        assert_eq!(mime1_enc, "image/png");

        // Test 2: Multiple spaces raw and percent-encoded
        let (bytes2, mime2) = super::asset_response(
            "Realms/The Outer Rim Horizon/Deep Space Landscape.webp",
        )
        .expect("raw space asset resolution");
        assert_eq!(bytes2, [40, 50, 60]);
        assert_eq!(mime2, "image/webp");

        let (bytes2_enc, mime2_enc) = super::asset_response(
            "Realms/The%20Outer%20Rim%20Horizon/Deep%20Space%20Landscape.webp",
        )
        .expect("percent-encoded space asset resolution");
        assert_eq!(bytes2_enc, [40, 50, 60]);
        assert_eq!(mime2_enc, "image/webp");

        // Test 3: Accented and non-ASCII characters
        let (bytes3, mime3) = super::asset_response(
            "Library/Lore/München Café & Forêt/Château 1880.avif",
        )
        .expect("raw accented asset resolution");
        assert_eq!(bytes3, [70, 80, 90]);
        assert_eq!(mime3, "image/avif");

        let (bytes3_enc, mime3_enc) = super::asset_response(
            "Library/Lore/M%C3%BCnchen%20Caf%C3%A9%20%26%20For%C3%AAt/Ch%C3%A2teau%201880.avif",
        )
        .expect("percent-encoded accented asset resolution");
        assert_eq!(bytes3_enc, [70, 80, 90]);
        assert_eq!(mime3_enc, "image/avif");

        // Test 4: CJK characters and SVG mime type
        let (bytes4, mime4) = super::asset_response("Journal/2026/09/雪の国/地図.svg")
            .expect("raw cjk asset resolution");
        assert_eq!(bytes4, b"<svg></svg>");
        assert_eq!(mime4, "image/svg+xml");

        let (bytes4_enc, mime4_enc) = super::asset_response(
            "Journal/2026/09/%E9%9B%AA%E3%81%AE%E5%9B%BD/%E5%9C%B0%E5%9B%B3.svg",
        )
        .expect("percent-encoded cjk asset resolution");
        assert_eq!(bytes4_enc, b"<svg></svg>");
        assert_eq!(mime4_enc, "image/svg+xml");

        let _ = fs::remove_dir_all(&root);
    }
    #[test]
    fn rejects_parent() {
        assert!(resolve_relative_path("Bridge/../Journal/today.md").is_err());
    }
    #[test]
    fn rejects_absolute() {
        assert!(resolve_relative_path(r"C:\secret.txt").is_err());
    }

    #[test]
    fn nested_journal_file_route_returns_content() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-journal-route-{}", std::process::id()));
        let journal = root.join("Journal/2026/09");
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&journal).expect("journal directory");
        fs::write(journal.join("2026-09-21.md"), "# Journal\n\n- [ ] Test").expect("journal file");
        std::env::set_var("NAVIS_ROOT", &root);

        let response = super::request("/api/vault/Journal/2026/09/2026-09-21.md", "GET", None)
            .expect("nested journal route");
        assert_eq!(response.body["content"], "# Journal\n\n- [ ] Test");
        let entities = super::journal_entities().expect("journal entities");
        assert_eq!(entities[0]["id"], "Journal/2026/09/2026-09-21.md");
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn entity_ids_remain_vault_relative_and_loadable() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root =
            std::env::temp_dir().join(format!("navis-relative-entity-{}", std::process::id()));
        let profile = root.join("Companions/Ava & Echo/Profile.md");
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(profile.parent().expect("profile parent"))
            .expect("companion directory");
        fs::write(&profile, "# Ava & Echo\n\nTelemetry is available.").expect("profile fixture");
        std::env::set_var("NAVIS_ROOT", &root);

        let entities = super::request("/api/entities?sectorId=COMPANIONS", "GET", None)
            .expect("companion entities");
        let entity = entities
            .body
            .as_array()
            .unwrap()
            .iter()
            .find(|entity| entity.get("name").and_then(|name| name.as_str()) == Some("Ava & Echo"))
            .expect("companion entity");
        let id = entity
            .get("id")
            .and_then(|id| id.as_str())
            .expect("entity id");
        assert_eq!(id, "Companions/Ava & Echo");
        assert!(!id.contains(':'));

        let response = super::request("/api/vault/Companions/Ava & Echo/Profile.md", "GET", None)
            .expect("relative entity path loads");
        assert_eq!(
            response.body["content"],
            "# Ava & Echo\n\nTelemetry is available."
        );
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn journal_append_cannot_bypass_canonical_bridge() {
        assert!(super::request("/api/journal/entry", "POST", Some(json!({}))).is_err());
    }

    #[test]
    fn nested_operation_mission_is_listed() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root =
            std::env::temp_dir().join(format!("navis-operation-route-{}", std::process::id()));
        let mission = root.join("Operations/The Sanctum/Main/Test Area");
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&mission).expect("operation directory");
        fs::write(mission.join("Mission.md"), "# Test Area").expect("mission file");
        std::env::set_var("NAVIS_ROOT", &root);

        let entities = super::operation_entities("SANCTUM").expect("operation entities");
        assert_eq!(
            entities[0]["id"],
            "Operations/The Sanctum/Main/Test Area/Mission.md"
        );
        assert_eq!(entities[0]["name"], "Test Area");
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn entity_profile_resolves_encoded_name_and_portrait_assets() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root =
            std::env::temp_dir().join(format!("navis-entity-profile-{}", std::process::id()));
        let entity_dir = root.join("Companions/Ava & Echo");
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&entity_dir).expect("entity directory");
        fs::write(
            entity_dir.join("Profile.md"),
            "---\nignored: frontmatter\n---\n- **Class/Title:** Test Vanguard\n\n## 📜 Lore\nA profile fixture.",
        )
        .expect("profile document");
        fs::write(entity_dir.join("Portrait.png"), [1_u8, 2, 3]).expect("portrait fixture");
        fs::write(entity_dir.join("Card.png"), [4_u8, 5, 6]).expect("card fixture");
        std::env::set_var("NAVIS_ROOT", &root);

        let response = super::request("/api/entity/Companions/Ava%20%26%20Echo", "GET", None)
            .expect("entity profile route");
        assert_eq!(response.body["name"], "Ava & Echo");
        assert_eq!(response.body["attributes"]["Class/Title"], "Test Vanguard");
        assert_eq!(
            response.body["portrait_url"],
            "/api/vault/Companions/Ava & Echo/Portrait.png"
        );
        assert_eq!(
            response.body["card_url"],
            "/api/vault/Companions/Ava & Echo/Card.png"
        );
        assert_eq!(
            response.body["sections"][0]["content"],
            "A profile fixture."
        );
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn realm_options_reads_descriptions_and_excludes_recent_realms() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-realm-options-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(root.join("Realms/Current")).expect("current realm");
        fs::create_dir_all(root.join("Realms/Recent")).expect("recent realm");
        fs::create_dir_all(root.join("Realms/Available")).expect("available realm");
        fs::create_dir_all(root.join("Realms/Default")).expect("default realm");
        fs::write(
            root.join("Realms/Available/realm_data.json"),
            r#"{"description":"A bright test realm."}"#,
        )
        .expect("realm data");
        fs::create_dir_all(root.join("Bridge")).expect("bridge directory");
        fs::write(
            root.join("Bridge/status.json"),
            r#"{"current_realm":"Current"}"#,
        )
        .expect("status");
        fs::write(
            root.join("Bridge/realm_stats.json"),
            r#"{"history":["Recent"]}"#,
        )
        .expect("realm stats");
        std::env::set_var("NAVIS_ROOT", &root);

        let response = super::request("/api/realm/options", "GET", None).expect("realm options");
        assert_eq!(response.body[0]["name"], "Available");
        assert_eq!(response.body[0]["description"], "A bright test realm.");
        assert_eq!(
            response.body[0]["image"],
            "/api/vault/Realms/Available/Landscape.png"
        );
        let names: Vec<_> = response
            .body
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|v| v["name"].as_str())
            .collect();
        assert!(!names.contains(&"Current"));
        assert!(!names.contains(&"Recent"));
        assert!(!names.contains(&"Default"));
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn realm_options_returns_empty_when_no_realms_exist() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root =
            std::env::temp_dir().join(format!("navis-empty-realm-options-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(root.join("Bridge")).expect("bridge directory");
        fs::write(
            root.join("Bridge/status.json"),
            r#"{"current_realm":"Current"}"#,
        )
        .expect("status");
        std::env::set_var("NAVIS_ROOT", &root);

        let response =
            super::request("/api/realm/options", "GET", None).expect("empty realm options");
        assert_eq!(response.body, json!([]));
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn realm_selector_samples_distinct_destinations_from_the_full_set() {
        let mut next = 0;
        let selected = super::select_realm_indices(6, 3, |upper| {
            let choice = [0, 1, 2][next];
            next += 1;
            choice.min(upper - 1)
        });
        assert_eq!(selected, [0, 1, 2]);

        let mut next = 0;
        let selected_late = super::select_realm_indices(6, 3, |upper| {
            let choice = [5, 4, 3][next];
            next += 1;
            choice.min(upper - 1)
        });
        assert_eq!(selected_late, [5, 4, 3]);
        assert!(selected_late.iter().all(|index| *index >= 3));
    }

    #[test]
    fn realm_draft_selects_native_vanguard_and_companion_choices() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-realm-draft-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(root.join("Realms/Antonica")).expect("realm directory");
        fs::create_dir_all(root.join("Companions/Native")).expect("native companion");
        fs::create_dir_all(root.join("Companions/Scout")).expect("scout companion");
        fs::create_dir_all(root.join("Companions/Mage")).expect("mage companion");
        fs::create_dir_all(root.join("Bridge")).expect("bridge directory");
        fs::write(
            root.join("Realms/Antonica/realm_data.json"),
            r#"{"tags":["Fantasy"],"natives":["Native"]}"#,
        )
        .expect("realm data");
        fs::write(
            root.join("Companions/Native/companion_data.json"),
            r#"{"tags":["Fantasy"],"role":"Guide"}"#,
        )
        .expect("native data");
        fs::write(
            root.join("Companions/Scout/companion_data.json"),
            r#"{"tags":["Modern"],"role":"Scout"}"#,
        )
        .expect("scout data");
        fs::write(
            root.join("Companions/Mage/companion_data.json"),
            r#"{"tags":["Fantasy"],"role":"Mage"}"#,
        )
        .expect("mage data");
        fs::write(
            root.join("Bridge/CompanionStats.json"),
            r#"{"companions":{"Native":{"xp":12},"Scout":{"xp":2},"Mage":{"xp":4}}}"#,
        )
        .expect("companion stats");
        std::env::set_var("NAVIS_ROOT", &root);

        let response = super::request("/api/realm/draft?realm_name=Antonica", "GET", None)
            .expect("realm draft");
        assert_eq!(response.body["vanguard"]["name"], "Native");
        assert_eq!(response.body["vanguard"]["role"], "Guide");
        assert_eq!(response.body["vanguard"]["synergy"], 2);
        assert_eq!(response.body["draft_pool"][0]["name"], "Scout");
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn realm_draft_decodes_encoded_spaces_in_realm_name() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-realm-space-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(root.join("Realms/Isle of the Lost")).expect("realm directory");
        fs::write(
            root.join("Realms/Isle of the Lost/realm_data.json"),
            r##"{"tags":["#realm"],"natives":["Mal"]}"##,
        )
        .expect("realm data");
        fs::create_dir_all(root.join("Companions/Mal")).expect("native companion");
        fs::write(
            root.join("Companions/Mal/companion_data.json"),
            r##"{"tags":["#realm"],"role":"Villain"}"##,
        )
        .expect("companion data");
        fs::create_dir_all(root.join("Bridge")).expect("bridge directory");
        std::env::set_var("NAVIS_ROOT", &root);

        let response = super::request(
            "/api/realm/draft?realm_name=Isle%20of%20the%20Lost",
            "GET",
            None,
        )
        .expect("encoded realm name resolves");
        assert_eq!(response.body["vanguard"]["name"], "Mal");
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn realm_hop_updates_native_status_and_visit_history() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-realm-hop-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(root.join("Realms/Isle of the Lost")).expect("realm directory");
        fs::create_dir_all(root.join("Bridge")).expect("bridge directory");
        fs::create_dir_all(root.join("Companions/Mal")).expect("companion directory");
        fs::create_dir_all(root.join("Companions/Evie")).expect("companion directory");
        fs::create_dir_all(root.join("Companions/Carlos")).expect("companion directory");
        fs::write(
            root.join("Bridge/status.json"),
            r#"{"current_realm":"Old Realm","current_antagonist":"Keep Me"}"#,
        )
        .expect("status fixture");
        fs::write(
            root.join("Bridge/CompanionStats.json"),
            r#"{"companions":{"Mal":{"xp":12},"Keeper":{"xp":88}}}"#,
        )
        .expect("companion stats fixture");
        std::env::set_var("NAVIS_ROOT", &root);

        let response = super::request(
            "/api/realm/hop",
            "POST",
            Some(json!({
                "realm_name": "Isle of the Lost",
                "squad_names": ["Mal", "Evie", "Carlos"]
            })),
        )
        .expect("realm hop succeeds");
        assert_eq!(response.body["status"], "success");
        let status: Value = serde_json::from_str(
            &super::text(&root.join("Bridge/status.json")).expect("updated status"),
        )
        .expect("valid status JSON");
        assert_eq!(status["current_realm"], "Isle of the Lost");
        assert_eq!(status["current_antagonist"], "Keep Me");
        assert_eq!(status["squad"][0]["is_vanguard"], true);
        assert_eq!(status["squad"][0]["entry_xp"], 12);
        assert_eq!(status["keeper_entry_xp"], 88);
        let stats: Value = serde_json::from_str(
            &super::text(&root.join("Bridge/realm_stats.json")).expect("updated stats"),
        )
        .expect("valid realm stats JSON");
        assert_eq!(stats["history"][0], "Isle of the Lost");
        assert_eq!(stats["visit_counts"]["Isle of the Lost"], 1);
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn task_toggle_rejects_paths_outside_vault_and_preserves_external_file() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let base_tmp = std::env::temp_dir().join(format!("navis-toggle-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&base_tmp);
        let root = base_tmp.join("vault");
        let outside = base_tmp.join("outside");
        fs::create_dir_all(&root).expect("vault root");
        fs::create_dir_all(&outside).expect("outside dir");

        let outside_file = outside.join("tasks.md");
        let initial_bytes = b"- [ ] Outside target\n";
        fs::write(&outside_file, initial_bytes).expect("outside file");
        std::env::set_var("NAVIS_ROOT", &root);

        // 1. Directory traversal
        let res_traversal = super::request(
            "/api/tasks/toggle",
            "POST",
            Some(json!({
                "file_path": "../outside/tasks.md",
                "is_checked": true,
                "target_text": "Outside target"
            })),
        );
        assert!(res_traversal.is_err(), "traversal should be rejected");

        // 2. Encoded traversal
        let res_encoded = super::request(
            "/api/tasks/toggle",
            "POST",
            Some(json!({
                "file_path": "%2e%2e/outside/tasks.md",
                "is_checked": true,
                "target_text": "Outside target"
            })),
        );
        assert!(res_encoded.is_err(), "encoded traversal should be rejected");

        // 3. Absolute path
        let res_abs = super::request(
            "/api/tasks/toggle",
            "POST",
            Some(json!({
                "file_path": outside_file.to_string_lossy(),
                "is_checked": true,
                "target_text": "Outside target"
            })),
        );
        assert!(res_abs.is_err(), "absolute path should be rejected");

        // Verify outside file is byte-identical and untouched
        let current_bytes = fs::read(&outside_file).expect("read outside file");
        assert_eq!(current_bytes, initial_bytes, "outside file must remain byte-identical");

        let _ = fs::remove_dir_all(&base_tmp);
    }

    #[test]
    fn task_toggle_cannot_bypass_canonical_bridge() {
        let error = super::request("/api/tasks/toggle", "POST", Some(json!({}))).unwrap_err();
        assert!(error.contains("canonical task bridge"));
    }

    #[test]
    fn squad_deploy_bench_vanguard_lifecycle() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-squad-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(root.join("Bridge")).unwrap();
        fs::create_dir_all(root.join("Companions/Arwen")).unwrap();
        fs::create_dir_all(root.join("Companions/Echo")).unwrap();
        fs::create_dir_all(root.join("Companions/Rex")).unwrap();
        fs::create_dir_all(root.join("Companions/Chopper")).unwrap();
        fs::create_dir_all(root.join("Journal/2026/09")).unwrap();

        fs::write(
            root.join("Bridge/status.json"),
            "\u{feff}{\"current_realm\": \"Earth\", \"squad\": [], \"last_updated\": \"2026-09-30\"}",
        )
        .unwrap();
        fs::write(
            root.join("Bridge/CompanionStats.json"),
            "\u{feff}{\"companions\": {\"Arwen\": {\"xp\": 100, \"level\": 2}, \"Echo\": {\"xp\": 50, \"level\": 1}, \"Rex\": {\"xp\": 75, \"level\": 1}, \"Chopper\": {\"xp\": 20, \"level\": 1}}}",
        )
        .unwrap();
        fs::write(root.join("Companions/Arwen/Profile.md"), "# Arwen\n\n- **Role:** Diplomat\n").unwrap();
        fs::write(root.join("Companions/Echo/companion_data.json"), "{\"role\": \"Infiltrator\"}").unwrap();
        fs::write(root.join("Companions/Rex/Profile.md"), "# Rex\n\n- **Role:** Captain\n").unwrap();
        fs::write(root.join("Companions/Chopper/Profile.md"), "# Chopper\n\n- **Role:** Astromech\n").unwrap();

        let journal_path = root.join("Journal/2026/09/2026-09-30.md");
        fs::write(
            &journal_path,
            "\u{feff}# 2026-09-30\n\n- **🌀 Realm:** Earth\n- **🛡️ Active Squad**\n    - None\n- **👹 Antagonist:** None\n- **👾 Prime Beast:** None\n\n---\n\n## 🏰 The Sanctum\n- [ ] Sanctum task\n",
        )
        .unwrap();
        std::env::set_var("NAVIS_ROOT", &root);

        // 1. Keeper cannot be deployed
        let res_keeper = super::request("/api/squad/deploy", "POST", Some(json!({"name": "Keeper"}))).unwrap();
        assert_eq!(res_keeper.status, 400);
        assert_eq!(res_keeper.body["detail"], "Keeper cannot be deployed to squad");

        // 2. Non-existent companion
        let res_missing = super::request("/api/squad/deploy", "POST", Some(json!({"name": "Ghost"}))).unwrap();
        assert_eq!(res_missing.status, 404);

        // 3. Deploy Arwen
        let res_arwen = super::request("/api/squad/deploy", "POST", Some(json!({"name": "Arwen"}))).unwrap();
        assert_eq!(res_arwen.status, 200);
        assert_eq!(res_arwen.body["status"], "success");
        assert_eq!(res_arwen.body["squad"].as_array().unwrap().len(), 1);
        assert_eq!(res_arwen.body["squad"][0]["name"], "Arwen");
        assert_eq!(res_arwen.body["squad"][0]["role"], "Diplomat");
        assert_eq!(res_arwen.body["squad"][0]["entry_xp"], 100);

        // Journal header synced
        let jcontent = super::text(&journal_path).unwrap();
        assert!(jcontent.contains("- **🛡️ Active Squad**\n    - Arwen\n- **👹 Antagonist:** None"));
        assert!(jcontent.contains("- [ ] Sanctum task"));

        // 4. Duplicate deploy is idempotent
        let res_arwen2 = super::request("/api/squad/deploy", "POST", Some(json!({"name": "Arwen"}))).unwrap();
        assert_eq!(res_arwen2.status, 200);
        assert_eq!(res_arwen2.body["squad"].as_array().unwrap().len(), 1);
        assert!(res_arwen2.body["message"].as_str().unwrap().contains("already deployed"));

        // 5. Deploy Echo and Rex to fill squad to capacity (3)
        super::request("/api/squad/deploy", "POST", Some(json!({"name": "Echo"}))).unwrap();
        let res_rex = super::request("/api/squad/deploy", "POST", Some(json!({"name": "Rex"}))).unwrap();
        assert_eq!(res_rex.body["squad"].as_array().unwrap().len(), 3);

        // 6. Deploying 4th member without target_recall fails with 400
        let res_full = super::request("/api/squad/deploy", "POST", Some(json!({"name": "Chopper"}))).unwrap();
        assert_eq!(res_full.status, 400);
        assert_eq!(res_full.body["detail"], "SQUAD FULL: Recall a member to reserve first.");

        // 7. Deploying with Keeper as target_recall fails
        let res_swap_keeper = super::request(
            "/api/squad/deploy",
            "POST",
            Some(json!({"name": "Chopper", "target_recall": "Keeper"})),
        )
        .unwrap();
        assert_eq!(res_swap_keeper.status, 400);

        // 8. Deploying with non-squad member as target_recall fails
        let res_swap_ghost = super::request(
            "/api/squad/deploy",
            "POST",
            Some(json!({"name": "Chopper", "target_recall": "Ghost"})),
        )
        .unwrap();
        assert_eq!(res_swap_ghost.status, 400);

        // 9. Deploying with valid target_recall replaces that member
        let res_swap = super::request(
            "/api/squad/deploy",
            "POST",
            Some(json!({"name": "Chopper", "target_recall": "Arwen"})),
        )
        .unwrap();
        assert_eq!(res_swap.status, 200);
        let current_names: Vec<String> = res_swap.body["squad"]
            .as_array()
            .unwrap()
            .iter()
            .map(|m| m["name"].as_str().unwrap().to_string())
            .collect();
        assert_eq!(current_names, vec!["Echo", "Rex", "Chopper"]);

        // 10. Designate Vanguard
        let res_vg = super::request("/api/squad/vanguard", "POST", Some(json!({"name": "Chopper"}))).unwrap();
        assert_eq!(res_vg.status, 200);
        let chopper_squad = res_vg.body["squad"].as_array().unwrap();
        let chopper = chopper_squad.iter().find(|m| m["name"] == "Chopper").unwrap();
        assert_eq!(chopper["is_vanguard"], true);
        let echo = chopper_squad.iter().find(|m| m["name"] == "Echo").unwrap();
        assert_eq!(echo["is_vanguard"], false);

        // Keeper cannot be vanguard
        let res_vg_keeper = super::request("/api/squad/vanguard", "POST", Some(json!({"name": "Keeper"}))).unwrap();
        assert_eq!(res_vg_keeper.status, 400);

        // Non-squad cannot be vanguard
        let res_vg_missing = super::request("/api/squad/vanguard", "POST", Some(json!({"name": "Arwen"}))).unwrap();
        assert_eq!(res_vg_missing.status, 400);

        // 11. Bench Chopper
        let res_bench = super::request("/api/squad/bench", "POST", Some(json!({"name": "Chopper"}))).unwrap();
        assert_eq!(res_bench.status, 200);
        assert_eq!(res_bench.body["squad"].as_array().unwrap().len(), 2);

        // Keeper cannot be benched
        let res_bench_keeper = super::request("/api/squad/bench", "POST", Some(json!({"name": "Keeper"}))).unwrap();
        assert_eq!(res_bench_keeper.status, 400);

        // Bench non-squad returns 200 without changes
        let res_bench_non = super::request("/api/squad/bench", "POST", Some(json!({"name": "Chopper"}))).unwrap();
        assert_eq!(res_bench_non.status, 200);
        assert_eq!(res_bench_non.body["squad"].as_array().unwrap().len(), 2);

        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn combat_target_and_log_lifecycle() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-combat-target-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(root.join("Bridge")).unwrap();
        fs::create_dir_all(root.join("Obstacles/Antagonists/Sauron")).unwrap();
        fs::create_dir_all(root.join("Obstacles/Beasts/Dragon")).unwrap();
        fs::create_dir_all(root.join("Battle")).unwrap();
        fs::create_dir_all(root.join("Journal/2026/09")).unwrap();

        fs::write(
            root.join("Bridge/status.json"),
            "\u{feff}{\"current_realm\": \"Earth\", \"squad\": [], \"current_antagonist\": \"\", \"current_beast\": \"\", \"last_updated\": \"2026-09-30\"}",
        )
        .unwrap();
        let journal_path = root.join("Journal/2026/09/2026-09-30.md");
        fs::write(
            &journal_path,
            "\u{feff}# 2026-09-30\n\n- **🌀 Realm:** Earth\n- **🛡️ Active Squad**\n    - None\n- **👹 Antagonist:** None\n- **👾 Prime Beast:** None\n\n---\n\n## 🏰 The Sanctum\n- [ ] Task\n",
        )
        .unwrap();
        fs::write(
            root.join("Battle/Combat_Log.md"),
            "# Combat Log\n\n> Line 1\n> Line 2\n\nNote text\n> Line 3\n",
        )
        .unwrap();
        std::env::set_var("NAVIS_ROOT", &root);

        // 1. Invalid target type
        let res_invalid_type = super::request(
            "/api/combat/target",
            "POST",
            Some(json!({"type": "invalid", "name": "Sauron"})),
        )
        .unwrap();
        assert_eq!(res_invalid_type.status, 400);

        // 2. Traversal or non-existent target
        let res_traversal = super::request(
            "/api/combat/target",
            "POST",
            Some(json!({"type": "antagonist", "name": "../Other"})),
        )
        .unwrap();
        assert_eq!(res_traversal.status, 400);

        let res_missing = super::request(
            "/api/combat/target",
            "POST",
            Some(json!({"type": "antagonist", "name": "Voldemort"})),
        )
        .unwrap();
        assert_eq!(res_missing.status, 400);

        // 3. Set antagonist Sauron
        let res_ant = super::request(
            "/api/combat/target",
            "POST",
            Some(json!({"type": "antagonist", "name": "Sauron"})),
        )
        .unwrap();
        assert_eq!(res_ant.status, 200);
        assert_eq!(res_ant.body["current_status"]["current_antagonist"], "Sauron");
        let jcontent = super::text(&journal_path).unwrap();
        assert!(jcontent.contains("- **👹 Antagonist:** Sauron"));

        // 4. Set beast Dragon
        let res_beast = super::request(
            "/api/combat/target",
            "POST",
            Some(json!({"type": "beast", "name": "Dragon"})),
        )
        .unwrap();
        assert_eq!(res_beast.status, 200);
        assert_eq!(res_beast.body["current_status"]["current_beast"], "Dragon");

        // 5. Clear antagonist
        let res_clear = super::request(
            "/api/combat/target",
            "POST",
            Some(json!({"type": "antagonist", "name": ""})),
        )
        .unwrap();
        assert_eq!(res_clear.status, 200);
        assert_eq!(res_clear.body["current_status"]["current_antagonist"], "");
        let jcontent2 = super::text(&journal_path).unwrap();
        assert!(jcontent2.contains("- **👹 Antagonist:** None"));

        // 6. Combat log read
        let res_log = super::request("/api/combat/log?limit=2", "GET", None).unwrap();
        assert_eq!(res_log.status, 200);
        let logs = res_log.body["logs"].as_array().unwrap();
        assert_eq!(logs.len(), 2);
        assert_eq!(logs[0], "> Line 3");
        assert_eq!(logs[1], "> Line 2");

        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn bio_adjust_lifecycle() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-bio-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(root.join("Bridge")).unwrap();
        fs::write(
            root.join("Bridge/status.json"),
            "\u{feff}{\"current_realm\": \"Earth\", \"squad\": [], \"AP\": 10}",
        )
        .unwrap();
        fs::write(
            root.join("Bridge/CompanionStats.json"),
            "\u{feff}{\"companions\": {\"Arwen\": {\"stats\": {\"STR\": 12}, \"morale\": 5}}}",
        )
        .unwrap();
        std::env::set_var("NAVIS_ROOT", &root);

        // 1. XP adjustment rejected with 422
        let res_xp = super::request(
            "/api/bio/adjust",
            "POST",
            Some(json!({"field": "XP", "delta": 100})),
        )
        .unwrap();
        assert_eq!(res_xp.status, 422);

        // 2. Missing companion rejected with 404
        let res_missing = super::request(
            "/api/bio/adjust",
            "POST",
            Some(json!({"field": "STR", "delta": 1, "companion_name": "Ghost"})),
        )
        .unwrap();
        assert_eq!(res_missing.status, 404);

        // 3. Adjust companion STR stat
        let res_str = super::request(
            "/api/bio/adjust",
            "POST",
            Some(json!({"field": "STR", "delta": 3, "companion_name": "Arwen"})),
        )
        .unwrap();
        assert_eq!(res_str.status, 200);
        assert_eq!(res_str.body["data"]["stats"]["STR"], 15);

        // 4. Adjust companion morale
        let res_morale = super::request(
            "/api/bio/adjust",
            "POST",
            Some(json!({"field": "morale", "delta": 2, "companion_name": "Arwen"})),
        )
        .unwrap();
        assert_eq!(res_morale.status, 200);
        assert_eq!(res_morale.body["data"]["morale"], 7);

        // 5. Adjust status AP
        let res_ap = super::request(
            "/api/bio/adjust",
            "POST",
            Some(json!({"field": "AP", "delta": -4})),
        )
        .unwrap();
        assert_eq!(res_ap.status, 200);
        assert_eq!(res_ap.body["data"]["AP"], 6);

        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn holocron_navigation_entities_and_routes() {
        let _lock = ENV_LOCK.get_or_init(|| Mutex::new(())).lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-holocron-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(root.join("Bridge/Holocron/Weekly")).unwrap();
        fs::create_dir_all(root.join("Journal")).unwrap();
        fs::write(
            root.join("Bridge/settings.json"),
            json!({
                "lexicon": {
                    "pillars": {
                        "CHRONICLE": "Archives & Logs"
                    }
                }
            }).to_string(),
        ).unwrap();
        std::env::set_var("NAVIS_ROOT", &root);

        // 1. Navigation includes HOLOCRON under CHRONICLE
        let nav = super::navigation().unwrap();
        let chronicle = nav.as_array().unwrap().iter().find(|p| p["id"] == "CHRONICLE").unwrap();
        let sectors = chronicle["sectors"].as_array().unwrap();
        let holocron_sector = sectors.iter().find(|s| s["id"] == "HOLOCRON").unwrap();
        assert_eq!(holocron_sector["label"], "Weekly Holocron");
        assert_eq!(holocron_sector["icon"], "💠");

        // 2. Default entities when no manifest exists
        let entities = super::list_entities("HOLOCRON").unwrap();
        assert_eq!(entities[0]["id"], "HOLOCRON");

        // 3. Populate manifest and weekly files
        let manifest_content = json!([
            {
                "week_id": "2026-W40",
                "name": "Cycle 2026-W40",
                "is_in_flight": true,
                "precision_rate": 88.5
            }
        ]);
        fs::write(
            root.join("Bridge/Holocron/weekly_manifest.json"),
            manifest_content.to_string(),
        ).unwrap();
        fs::write(
            root.join("Bridge/Holocron/Weekly/2026-W40.json"),
            r#"{"week_id":"2026-W40","summary":{"completed_tasks":12}}"#,
        ).unwrap();
        fs::write(
            root.join("Bridge/Holocron/Weekly/2026-W40.html"),
            "<!DOCTYPE html><html><body>Holocron 2026-W40</body></html>",
        ).unwrap();

        // 4. Manifest entity listing
        let entities = super::list_entities("HOLOCRON").unwrap();
        assert_eq!(entities[0]["id"], "Holocron/2026-W40");
        assert_eq!(entities[0]["type"], "holocron");
        assert_eq!(entities[0]["precision"], 88.5);

        // 5. Request routes
        let res_manifest = super::request("/api/holocron/weekly/manifest", "GET", None).unwrap();
        assert_eq!(res_manifest.status, 200);
        assert_eq!(res_manifest.body[0]["week_id"], "2026-W40");

        let res_week = super::request("/api/holocron/weekly/2026-W40", "GET", None).unwrap();
        assert_eq!(res_week.status, 200);
        assert_eq!(res_week.body["week_id"], "2026-W40");

        let res_html = super::request("/api/holocron/weekly/2026-W40/html", "GET", None).unwrap();
        assert_eq!(res_html.status, 200);
        assert!(res_html.text.contains("Holocron 2026-W40"));

        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn vault_change_event_serialization_and_defaults() {
        let event = super::VaultChangeEvent {
            r#type: "journal".to_string(),
            path: "Journal/2026/10/2026-10-02.md".to_string(),
            timestamp: 1759461234.56,
            action: "modified".to_string(),
            full_path: Some("G:/My Drive/Navis-Vault/Journal/2026/10/2026-10-02.md".to_string()),
        };
        let val = serde_json::to_value(&event).expect("serializable");
        assert_eq!(val["type"], "journal");
        assert_eq!(val["path"], "Journal/2026/10/2026-10-02.md");
        assert_eq!(val["action"], "modified");
        assert_eq!(val["timestamp"], 1759461234.56);
        assert_eq!(
            val["full_path"],
            "G:/My Drive/Navis-Vault/Journal/2026/10/2026-10-02.md"
        );

        // Deserialization with missing optional fields defaults timestamp
        let raw = serde_json::json!({
            "type": "bridge",
            "path": "Bridge/status.json",
            "action": "created"
        });
        let de: super::VaultChangeEvent = serde_json::from_value(raw).expect("deserializable");
        assert_eq!(de.r#type, "bridge");
        assert_eq!(de.path, "Bridge/status.json");
        assert_eq!(de.action, "created");
        assert!(de.timestamp > 0.0);
        assert_eq!(de.full_path, None);
    }

    #[test]
    fn determine_event_type_classifies_vault_paths() {
        assert_eq!(super::determine_event_type("Journal/2026/10/2026-10-02.md"), "journal");
        assert_eq!(super::determine_event_type("Bridge/status.json"), "bridge");
        assert_eq!(super::determine_event_type("Keeper/navis_progression.db"), "keeper");
        assert_eq!(super::determine_event_type(r"Journal\2026\09\2026-09-30.md"), "journal");
        assert_eq!(super::determine_event_type("/Bridge/Holocron/Weekly/2026-W40.json"), "bridge");
        assert_eq!(super::determine_event_type("unknown_file.txt"), "unknown_file.txt");
    }

    #[test]
    fn parse_watcher_line_formats() {
        // EVENT: prefix format from native_operations.py
        let line_with_prefix = r#"EVENT:{"type":"journal","path":"Journal/2026/10/2026-10-02.md","timestamp":1759461234.5,"action":"modified"}"#;
        let parsed = super::parse_watcher_line(line_with_prefix).expect("valid event");
        assert_eq!(parsed.r#type, "journal");
        assert_eq!(parsed.path, "Journal/2026/10/2026-10-02.md");
        assert_eq!(parsed.action, "modified");

        // Raw JSON format
        let raw_json = r#"{"type":"bridge","path":"Bridge/status.json","action":"created"}"#;
        let parsed_raw = super::parse_watcher_line(raw_json).expect("valid raw json");
        assert_eq!(parsed_raw.r#type, "bridge");
        assert_eq!(parsed_raw.path, "Bridge/status.json");

        // Status lines and irrelevant logs return None
        assert!(super::parse_watcher_line("Starting Native Vault Watcher...").is_none());
        assert!(super::parse_watcher_line("WATCHER:READY").is_none());
        assert!(super::parse_watcher_line("").is_none());
    }
}

