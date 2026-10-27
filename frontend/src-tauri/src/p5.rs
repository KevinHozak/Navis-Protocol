use serde_json::{json, Value};
use std::collections::HashMap;
use std::hash::{Hash, Hasher};
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc, Mutex,
};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::{AppHandle, Emitter, State};

#[derive(Debug, serde::Serialize)]
pub struct ApiResponse {
    pub status: u16,
    pub body: Value,
    pub text: String,
}

fn response(status: u16, body: Value) -> ApiResponse {
    ApiResponse {
        status,
        text: body.to_string(),
        body,
    }
}
fn root() -> PathBuf {
    crate::operations::configured_vault_root()
        .unwrap_or_else(|_| PathBuf::from(r"G:\My Drive\Navis-Vault"))
}
pub(crate) fn unavailable(message: &str) -> ApiResponse {
    response(
        503,
        json!({"status":"unavailable","code":"native_dependency_unavailable","message":message}),
    )
}

const MAX_BANTER_THREADS_PER_RUN: usize = 3;
const USABLE_THREAD_MAX_AGE_SECONDS: f64 = 24.0 * 60.0 * 60.0;

fn banter_db(root: &PathBuf) -> PathBuf {
    let settings_path = root.join("Bridge").join("settings.json");
    let configured = std::fs::read_to_string(settings_path)
        .ok()
        .and_then(|text| serde_json::from_str::<Value>(&text).ok())
        .and_then(|settings| {
            settings
                .pointer("/paths/chronicle_db")?
                .as_str()
                .map(PathBuf::from)
        });
    configured.unwrap_or_else(|| root.join("Journal").join("Chronicle.db"))
}

fn timestamp() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs_f64())
        .unwrap_or_default()
}

fn party_names(status: &Value) -> Vec<String> {
    status
        .get("squad")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|member| member.get("name").and_then(Value::as_str))
        .map(str::trim)
        .filter(|name| !name.is_empty())
        .map(str::to_string)
        .collect()
}

fn read_banter_status(root: &PathBuf) -> Result<Value, &'static str> {
    let path = root.join("Bridge").join("status.json");
    let text = std::fs::read_to_string(&path).map_err(|error| match error.kind() {
        std::io::ErrorKind::NotFound => "Squad status is missing. Restore Bridge/status.json in the configured Vault, then retry.",
        std::io::ErrorKind::InvalidData => "Squad status is malformed. Repair Bridge/status.json in the configured Vault, then retry.",
        _ => "Squad status could not be read. Check Vault access and retry.",
    })?;
    let text = text.strip_prefix('\u{feff}').unwrap_or(&text);
    let status = serde_json::from_str::<Value>(text)
        .map_err(|_| "Squad status is malformed. Repair Bridge/status.json in the configured Vault, then retry.")?;
    if !status.is_object() || !status.get("squad").is_some_and(Value::is_array) {
        return Err("Squad status has an invalid squad field. Repair Bridge/status.json, then retry.");
    }
    Ok(status)
}

fn valid_chain(chain: &Value, participants: &[String]) -> bool {
    let Some(turns) = chain.as_array() else {
        return false;
    };
    if turns.len() != participants.len() {
        return false;
    }
    let speakers: Vec<&str> = turns
        .iter()
        .filter_map(|turn| {
            let speaker = turn.get("speaker")?.as_str()?;
            let text = turn.get("text")?.as_str()?;
            (!text.trim().is_empty()).then_some(speaker)
        })
        .collect();
    speakers.len() == participants.len()
        && speakers
            .iter()
            .copied()
            .collect::<std::collections::HashSet<_>>()
            .len()
            == participants.len()
        && speakers
            .iter()
            .map(|speaker| (*speaker).to_string())
            .eq(participants.iter().cloned())
}

fn usable_recent_thread(conn: &rusqlite::Connection, realm: &str, participants: &[String]) -> bool {
    let Ok(mut statement) = conn.prepare(
        "SELECT chain FROM banter_threads WHERE realm=?1 AND participants=?2 AND timestamp>=?3 ORDER BY timestamp DESC",
    ) else { return false };
    let participant_key = sorted_participant_key(participants);
    let Ok(rows) = statement.query_map(
        rusqlite::params![
            realm,
            participant_key,
            timestamp() - USABLE_THREAD_MAX_AGE_SECONDS
        ],
        |row| row.get::<_, String>(0),
    ) else {
        return false;
    };
    let found = rows.flatten().any(|chain| {
        serde_json::from_str::<Value>(&chain).is_ok_and(|value| valid_chain(&value, participants))
    });
    found
}

fn read_utf8(path: PathBuf) -> String {
    std::fs::read_to_string(path).unwrap_or_default()
}

fn section(content: &str, heading: &str, fallback: &str) -> String {
    let Some(start) = content.find(heading).map(|index| index + heading.len()) else {
        return fallback.to_string();
    };
    let rest = content[start..].trim_start_matches(['\r', '\n', ' ', '\t']);
    let end = rest
        .find("\n##")
        .into_iter()
        .chain(rest.find("\n---"))
        .min()
        .unwrap_or(rest.len());
    rest[..end].trim().to_string()
}

fn local_ollama_generate(prompt: &str) -> Result<String, String> {
    let base_url =
        std::env::var("NAVIS_OLLAMA_URL").unwrap_or_else(|_| "http://localhost:11434".into());
    let endpoint = base_url
        .strip_prefix("http://")
        .unwrap_or_default()
        .trim_end_matches('/');
    let Some((host, port)) = endpoint.split_once(':') else {
        return Err(
            "Native Ollama URL must use a local HTTP endpoint such as http://localhost:11434."
                .into(),
        );
    };
    if !matches!(host, "localhost" | "127.0.0.1") || port.contains('/') {
        return Err(
            "Native local generation currently supports the local Ollama endpoint only.".into(),
        );
    }
    let port = port
        .parse::<u16>()
        .map_err(|_| "Native Ollama URL has an invalid port.".to_string())?;
    let model = std::env::var("NAVIS_OLLAMA_MODEL").unwrap_or_else(|_| "Kimiko-20B:latest".into());
    let timeout = std::env::var("NAVIS_OLLAMA_TIMEOUT")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(90)
        .clamp(1, 600);
    let payload = serde_json::to_vec(&json!({
        "model": model,
        "prompt": prompt,
        "stream": false,
        "keep_alive": "1h",
        "options": {"temperature": 0.75, "num_predict": 2048}
    }))
    .map_err(|_| "Could not encode the local banter request.".to_string())?;
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let mut stream =
        TcpStream::connect_timeout(&address, Duration::from_secs(5)).map_err(|_| {
            "Local Ollama is unavailable. Start Ollama and verify the configured model.".to_string()
        })?;
    stream
        .set_read_timeout(Some(Duration::from_secs(timeout)))
        .map_err(|_| "Could not configure the local Ollama connection.".to_string())?;
    stream
        .set_write_timeout(Some(Duration::from_secs(30)))
        .map_err(|_| "Could not configure the local Ollama connection.".to_string())?;
    let request = format!(
        "POST /api/generate HTTP/1.1\r\nHost: {host}:{port}\r\nContent-Type: application/json\r\nAccept: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        payload.len()
    );
    stream
        .write_all(request.as_bytes())
        .and_then(|_| stream.write_all(&payload))
        .and_then(|_| stream.flush())
        .map_err(|_| "Could not send the local banter request.".to_string())?;
    let mut raw = Vec::new();
    stream
        .read_to_end(&mut raw)
        .map_err(|_| "Local Ollama timed out or returned an incomplete response.".to_string())?;
    let Some(header_end) = raw.windows(4).position(|window| window == b"\r\n\r\n") else {
        return Err("Local Ollama returned an invalid HTTP response.".into());
    };
    let headers = String::from_utf8_lossy(&raw[..header_end]);
    let status = headers
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .and_then(|code| code.parse::<u16>().ok())
        .unwrap_or(503);
    if !(200..300).contains(&status) {
        return Err(format!("Local Ollama returned HTTP {status}."));
    }
    let body = &raw[header_end + 4..];
    let decoded = if headers.lines().any(|line| {
        line.to_ascii_lowercase().starts_with("transfer-encoding:")
            && line.to_ascii_lowercase().contains("chunked")
    }) {
        super::ollama::decode_chunked_for_p5(body)
            .ok_or_else(|| "Local Ollama returned malformed chunked data.".to_string())?
    } else {
        body.to_vec()
    };
    let response: Value = serde_json::from_slice(&decoded)
        .map_err(|_| "Local Ollama returned malformed output.".to_string())?;
    response
        .get("response")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|text| !text.is_empty())
        .map(str::to_string)
        .ok_or_else(|| "Local Ollama returned an empty response.".to_string())
}

fn generate_banter(root: &PathBuf, requested_count: usize) -> ApiResponse {
    let status = match read_banter_status(root) {
        Ok(status) => status,
        Err(detail) => return response(503, json!({"detail":detail})),
    };
    let realm = status
        .get("current_realm")
        .and_then(Value::as_str)
        .unwrap_or("Unknown");
    let participants = party_names(&status);
    if participants.len() < 2
        || participants
            .iter()
            .map(|name| name.to_lowercase())
            .collect::<std::collections::HashSet<_>>()
            .len()
            != participants.len()
    {
        return response(
            422,
            json!({"detail":"At least two uniquely named active squad members are required."}),
        );
    }
    let db_path = banter_db(root);
    let conn = match rusqlite::Connection::open(&db_path) {
        Ok(conn) => conn,
        Err(_) => {
            return response(
                503,
                json!({"detail":"Banter history storage is unavailable."}),
            )
        }
    };
    if usable_recent_thread(&conn, realm, &participants) {
        return response(
            200,
            json!({"status":"success","message":"A usable current squad thread is already available."}),
        );
    }
    let count = requested_count.clamp(1, MAX_BANTER_THREADS_PER_RUN);
    let realm_file = root.join("Realms").join(realm).join("Realm.md");
    let realm_content = read_utf8(realm_file);
    let realm_brief = section(
        &realm_content,
        "## 🗣️ Environmental Briefing",
        &realm_content.chars().take(800).collect::<String>(),
    );
    let companion_root = root.join("Companions");
    let mut protocols = Vec::new();
    for name in &participants {
        let first = name.split_whitespace().next().unwrap_or(name);
        let profile = [
            companion_root.join(first).join("Profile.md"),
            companion_root.join(name).join("Profile.md"),
        ]
        .into_iter()
        .find(|path| path.is_file())
        .unwrap_or_else(|| companion_root.join(first).join("Profile.md"));
        let content = read_utf8(profile);
        let protocol = section(&content, "## 🗣️ Banter Protocol", "Standard behavior.");
        protocols.push(format!("NAME: {name}\nPERSONALITY PROTOCOL:\n{protocol}"));
    }
    let names_json = serde_json::to_string(&participants).unwrap_or_else(|_| "[]".into());
    let mut persisted = 0;
    for _ in 0..count {
        let prompt = format!(
            "Act as a role-playing game storyteller. Location: {realm}.\n\nSetting:\n{realm_brief}\n\nParty member protocols:\n{}\n\nWrite one immersive line for each member, once each, in this exact order: {names_json}. Avoid modern military and science-fiction jargon. Keep persona constraints. Speak of the journey and surroundings. Refer to the user as Keeper. Return only a JSON array of objects with string fields speaker and text.",
            protocols.join("\n-----\n")
        );
        let generated = match local_ollama_generate(&prompt) {
            Ok(text) => text,
            Err(error) => return response(503, json!({"detail":error})),
        };
        let json_text = generated
            .find('[')
            .zip(generated.rfind(']'))
            .map(|(start, end)| &generated[start..=end]);
        let chain = json_text.and_then(|text| serde_json::from_str::<Value>(text).ok());
        let Some(chain) = chain.filter(|chain| valid_chain(chain, &participants)) else {
            return response(
                503,
                json!({"detail":"Local Ollama returned malformed banter or an incomplete party thread."}),
            );
        };
        if let Err(_) = persist_banter(&conn, realm, &participants, &chain) {
            return response(
                503,
                json!({"detail":"Could not persist the generated banter thread."}),
            );
        }
        persisted += 1;
    }
    response(
        200,
        json!({"status":"success","message":format!("Generated {persisted} local squad banter thread(s).")}),
    )
}

fn persist_banter(
    conn: &rusqlite::Connection,
    realm: &str,
    participants: &[String],
    chain: &Value,
) -> rusqlite::Result<()> {
    conn.execute_batch("CREATE TABLE IF NOT EXISTS banter_threads (id INTEGER PRIMARY KEY AUTOINCREMENT, realm TEXT, participants TEXT, chain TEXT, timestamp REAL, thread_hash TEXT UNIQUE); CREATE INDEX IF NOT EXISTS idx_realm ON banter_threads(realm);")?;
    let chain_text = chain.to_string();
    let first_text = chain
        .as_array()
        .and_then(|turns| turns.first())
        .and_then(|turn| turn.get("text"))
        .and_then(Value::as_str)
        .unwrap_or_default();
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    first_text.hash(&mut hasher);
    let hash = format!("{:016x}", hasher.finish());
    conn.execute("BEGIN IMMEDIATE", [])?;
    let participant_key = sorted_participant_key(participants);
    let mut statement =
        conn.prepare("SELECT chain FROM banter_threads WHERE realm=?1 AND participants=?2")?;
    let existing: Vec<String> = statement
        .query_map(rusqlite::params![realm, participant_key], |row| row.get(0))?
        .flatten()
        .collect();
    if existing.iter().any(|saved| {
        serde_json::from_str::<Value>(saved)
            .ok()
            .and_then(|value| {
                value
                    .as_array()
                    .and_then(|turns| turns.first())
                    .and_then(|turn| turn.get("text"))
                    .and_then(Value::as_str)
                    .map(str::to_string)
            })
            .is_some_and(|saved_text| saved_text == first_text)
    }) {
        conn.execute("ROLLBACK", [])?;
        return Ok(());
    }
    conn.execute(
        "INSERT OR IGNORE INTO banter_threads (realm,participants,chain,timestamp,thread_hash) VALUES (?1,?2,?3,?4,?5)",
        rusqlite::params![realm, participant_key, chain_text, timestamp(), hash],
    )?;
    conn.execute(
        "DELETE FROM banter_threads WHERE id IN (SELECT id FROM banter_threads WHERE realm=?1 AND participants=?2 ORDER BY timestamp DESC LIMIT -1 OFFSET 10)",
        rusqlite::params![realm, participant_key],
    )?;
    conn.execute("COMMIT", [])?;
    Ok(())
}

fn sorted_participant_key(participants: &[String]) -> String {
    let mut sorted = participants.to_vec();
    sorted.sort();
    sorted.join(",")
}

fn banter_history(root: &PathBuf) -> ApiResponse {
    let status = match read_banter_status(root) {
        Ok(status) => status,
        Err(detail) => return response(503, json!({"detail":detail})),
    };
    let names = party_names(&status);
    let db_path = banter_db(root);
    if !db_path.is_file() {
        return response(200, json!([]));
    }
    let conn = match rusqlite::Connection::open(db_path) {
        Ok(conn) => conn,
        Err(_) => return response(503, json!({"detail":"Banter history storage is unavailable. Check Vault access and retry."})),
    };
    let has_banter_table: bool = match conn.query_row(
        "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'banter_threads')",
        [],
        |row| row.get(0),
    ) {
        Ok(exists) => exists,
        Err(_) => return response(503, json!({"detail":"Banter history could not be read. Check the Chronicle database and retry."})),
    };
    if !has_banter_table {
        return response(200, json!([]));
    }
    let mut statement = match conn.prepare(
        "SELECT realm,participants,chain,timestamp FROM banter_threads ORDER BY id DESC LIMIT 50",
    ) {
        Ok(statement) => statement,
        Err(_) => return response(503, json!({"detail":"Banter history could not be read. Check the Chronicle database and retry."})),
    };
    let rows = match statement.query_map([], |row| {
        Ok((
            row.get::<_, String>(0)?,
            row.get::<_, String>(1)?,
            row.get::<_, String>(2)?,
            row.get::<_, f64>(3)?,
        ))
    }) {
        Ok(rows) => rows,
        Err(_) => return response(503, json!({"detail":"Banter history could not be read. Check the Chronicle database and retry."})),
    };
    let mut seen = std::collections::HashSet::new();
    let mut messages = Vec::new();
    for row in rows {
        let (realm, participants, serialized, stamp) = match row {
            Ok(row) => row,
            Err(_) => return response(503, json!({"detail":"Banter history contains unreadable records. Check the Chronicle database and retry."})),
        };
        if !participants.split(',').all(|name| {
            names
                .iter()
                .any(|active| active.eq_ignore_ascii_case(name.trim()))
        }) {
            continue;
        }
        let Ok(Value::Array(chain)) = serde_json::from_str::<Value>(&serialized) else {
            continue;
        };
        for turn in chain.iter().rev() {
            let Some(speaker) = turn.get("speaker").and_then(Value::as_str) else {
                continue;
            };
            let Some(text) = turn.get("text").and_then(Value::as_str) else {
                continue;
            };
            if text.trim().is_empty() || !seen.insert(speaker.to_string()) {
                continue;
            }
            let role = companion_role(&root.join("Companions"), speaker);
            let avatar_dir = companion_directory(&root.join("Companions"), speaker);
            let avatar = format!(
                "/api/vault/Companions/{}/Portrait.png",
                percent_encoding::utf8_percent_encode(
                    &avatar_dir,
                    percent_encoding::NON_ALPHANUMERIC
                )
            );
            messages.push(json!({"sender":speaker,"role":role,"text":text,"avatar":avatar,"realm":realm,"timestamp":stamp}));
        }
    }
    messages.reverse();
    response(200, json!(messages))
}

fn companion_directory(root: &PathBuf, speaker: &str) -> String {
    if root.join(speaker).is_dir() {
        return speaker.into();
    }
    speaker
        .split_whitespace()
        .next()
        .unwrap_or(speaker)
        .to_string()
}

fn companion_role(root: &PathBuf, speaker: &str) -> String {
    let persona = std::fs::read_to_string(
        root.join(companion_directory(root, speaker))
            .join("Persona.json"),
    )
    .ok()
    .and_then(|text| serde_json::from_str::<Value>(&text).ok());
    persona
        .and_then(|value| {
            value
                .get("role")
                .and_then(Value::as_str)
                .map(str::to_string)
        })
        .unwrap_or_else(|| "Companion".into())
}

fn latest_history() -> Value {
    let dir = root().join("Reflection Chamber").join("Fridr Hall");
    let Some(path) = std::fs::read_dir(dir).ok().and_then(|entries| {
        entries
            .flatten()
            .map(|e| e.path())
            .filter(|p| p.extension().and_then(|x| x.to_str()) == Some("md"))
            .max_by_key(|p| std::fs::metadata(p).and_then(|m| m.modified()).ok())
    }) else {
        return json!([]);
    };
    let text = std::fs::read_to_string(path).unwrap_or_default();
    let mut messages = Vec::new();
    for line in text.lines() {
        let line = line.trim();
        if let Some(value) = line.strip_prefix("**[") {
            if let Some((stamp, rest)) = value.split_once("] Keeper:**") {
                messages.push(json!({"role":"user","content":format!("[{stamp}] {rest}")}));
            }
            if let Some((stamp, rest)) = value.split_once("] Reid:**") {
                messages.push(json!({"role":"reid","content":format!("[{stamp}] {rest}")}));
            }
        }
    }
    Value::Array(messages)
}

fn biometrics(path: &str) -> ApiResponse {
    let db = root().join("Keeper").join("FitbitChronicle.db");
    if !db.exists() {
        return unavailable("FitbitChronicle.db is not available in the configured Vault");
    }
    let conn = match rusqlite::Connection::open(db) {
        Ok(v) => v,
        Err(e) => return response(500, json!({"status":"error","message":e.to_string()})),
    };
    let route = path.split('?').next().unwrap_or(path);
    let (table, order, limit) = match route {
        "/api/v1/biometrics/vitals/latest" => ("daily_vitals", "date DESC", 1),
        "/api/v1/biometrics/vitals/history" => ("daily_vitals", "date DESC", 7),
        "/api/v1/biometrics/exercises/recent" => ("exercise_logs", "date DESC", 5),
        _ => {
            return response(
                404,
                json!({"status":"error","message":"unsupported biometrics route"}),
            )
        }
    };
    let mut stmt = match conn.prepare(&format!("SELECT * FROM {table} ORDER BY {order} LIMIT ?1")) {
        Ok(v) => v,
        Err(e) => return response(503, json!({"status":"unavailable","message":e.to_string()})),
    };
    let names: Vec<String> = stmt
        .column_names()
        .iter()
        .map(|v| (*v).to_string())
        .collect();
    let rows = stmt
        .query_map([limit], |row| {
            let mut item = serde_json::Map::new();
            for (i, name) in names.iter().enumerate() {
                let value: Result<String, _> = row.get(i);
                item.insert(
                    name.clone(),
                    value.map(Value::String).unwrap_or(Value::Null),
                );
            }
            Ok(Value::Object(item))
        })
        .ok()
        .map(|rows| rows.flatten().collect::<Vec<_>>())
        .unwrap_or_default();
    if route.ends_with("latest") {
        rows.first()
            .cloned()
            .map_or_else(|| unavailable("No vitals found"), |v| response(200, v))
    } else {
        response(200, Value::Array(rows))
    }
}

#[derive(Default)]
pub struct P5OperationState {
    pub jobs: Mutex<HashMap<String, Arc<AtomicBool>>>,
}
const ALLOWED: &[(&str, &str)] = &[
    ("backup", "Engine/sync/backup_protocol.py"),
    ("apply_xp", "Engine/rpg/apply_xp.py"),
    ("daily_rollover", "Engine/sync/daily_rollover.py"),
    ("sync_bridge", "Engine/sync/sync_bridge.py"),
];

fn emit(app: &AppHandle, job: &str, status: &str, phase: &str, message: &str) {
    let _ = app.emit(
        crate::operations::OPERATION_EVENT,
        json!({"job_id":job,"status":status,"phase":phase,"message":message}),
    );
}

#[tauri::command]
pub fn start_p5_operation(
    app: AppHandle,
    state: State<'_, P5OperationState>,
    operation: String,
) -> Result<Value, String> {
    let (_, relative) = ALLOWED
        .iter()
        .find(|(id, _)| *id == operation)
        .ok_or("unsupported operation")?;
    let vault_root = crate::operations::configured_vault_root()?;
    let script = vault_root.join(relative.replace('/', std::path::MAIN_SEPARATOR_STR));
    if !script.starts_with(&vault_root) {
        return Err("operation path escaped Vault root".into());
    }
    if !script.exists() {
        return Err(format!("approved operation is unavailable: {relative}"));
    }
    let backend = crate::operations::backend_root(&app)?;
    let runtime = crate::command::resolve_python_runtime(&backend, !cfg!(debug_assertions))?;
    let job = format!(
        "p5-{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_err(|e| e.to_string())?
            .as_nanos()
    );
    let cancelled = Arc::new(AtomicBool::new(false));
    state
        .jobs
        .lock()
        .map_err(|_| "operation state unavailable")?
        .insert(job.clone(), cancelled.clone());
    let app2 = app.clone();
    let job2 = job.clone();
    std::thread::spawn(move || {
        emit(
            &app2,
            &job2,
            "running",
            "start",
            "Approved operation started",
        );
        let mut command = crate::command::hidden_command(&runtime.to_string_lossy());
        command.arg(script).env_clear();
        for key in ["PATH", "SystemRoot", "TEMP", "TMP"] {
            if let Ok(value) = std::env::var(key) {
                command.env(key, value);
            }
        }
        command
            .env("NAVIS_ROOT", &vault_root)
            .env("PYTHONIOENCODING", "utf-8");
        let result = command.spawn().and_then(|mut child| loop {
            if cancelled.load(Ordering::Relaxed) {
                let _ = child.kill();
                let _ = child.wait();
                return Ok(None);
            }
            match child.try_wait()? {
                Some(status) => return Ok(Some(status)),
                None => std::thread::sleep(std::time::Duration::from_millis(100)),
            }
        });
        if cancelled.load(Ordering::Relaxed) {
            emit(
                &app2,
                &job2,
                "cancelled",
                "cancel",
                "Cancellation requested",
            );
        } else {
            match result {
                Ok(Some(output)) if output.success() => emit(
                    &app2,
                    &job2,
                    "completed",
                    "finalize",
                    "Approved operation completed",
                ),
                Ok(Some(output)) => emit(
                    &app2,
                    &job2,
                    "failed",
                    "finalize",
                    &format!("Approved operation exited with code {:?}", output.code()),
                ),
                Ok(None) => emit(&app2, &job2, "cancelled", "cancel", "Operation cancelled"),
                Err(error) => emit(
                    &app2,
                    &job2,
                    "failed",
                    "finalize",
                    &format!("Approved operation failed: {error}"),
                ),
            }
        }
    });
    Ok(json!({"status":"accepted","job_id":job,"operation":operation}))
}

#[tauri::command]
pub fn cancel_p5_operation(
    state: State<'_, P5OperationState>,
    job_id: String,
) -> Result<Value, String> {
    let jobs = state
        .jobs
        .lock()
        .map_err(|_| "operation state unavailable")?;
    let token = jobs.get(&job_id).ok_or("operation not found")?;
    token.store(true, Ordering::Relaxed);
    Ok(json!({"status":"cancellation_requested","job_id":job_id}))
}

/// Shared Forge service: private concepts travel on stdin, never argv or logs.
pub fn forge_request(app: &AppHandle, path: &str, method: &str, body: Option<Value>) -> Result<ApiResponse, String> {
    let action = match (method, path) {
        ("POST", "/api/forge/submit") => "submit",
        ("POST", "/api/forge/approve") => "approve",
        ("POST", "/api/forge/discard") => "discard",
        _ => return Ok(response(400, json!({"detail":"Unsupported Forge action."}))),
    };
    let backend = match crate::operations::backend_root(app) {
        Ok(value) => value,
        Err(_) => return Ok(unavailable("Forge backend resources are unavailable.")),
    };
    let runtime = match crate::command::resolve_python_runtime(&backend, !cfg!(debug_assertions)) {
        Ok(value) => value,
        Err(_) => return Ok(unavailable("Forge requires Python 3.11+ and backend dependencies.")),
    };
    let mut command = crate::command::hidden_command(&runtime.to_string_lossy());
    command.args(["-m", "services.forge_service", action]).current_dir(backend).env_clear();
    for key in ["PATH", "SystemRoot", "TEMP", "TMP", "NAVIS_OLLAMA_URL", "NAVIS_OLLAMA_MODEL", "NAVIS_OLLAMA_TIMEOUT", "NAVIS_AI_PROVIDER", "GOOGLE_API_KEY", "GEMINI_API_KEY"] {
        if let Ok(value) = std::env::var(key) { command.env(key, value); }
    }
    command.env("NAVIS_ROOT", root()).env("PYTHONIOENCODING", "utf-8")
        .stdin(std::process::Stdio::piped()).stdout(std::process::Stdio::piped()).stderr(std::process::Stdio::null());
    let mut child = match command.spawn() {
        Ok(value) => value,
        Err(_) => return Ok(unavailable("Forge runtime could not start.")),
    };
    if let Some(mut input) = child.stdin.take() {
        let payload = body.unwrap_or_else(|| json!({})).to_string();
        if payload.len() > 65536 || input.write_all(payload.as_bytes()).is_err() {
            let _ = child.kill(); let _ = child.wait();
            return Ok(response(400, json!({"detail":"Invalid Forge request."})));
        }
    }
    let output = child.wait_with_output().map_err(|_| "Forge runtime did not complete.")?;
    let result: Value = match serde_json::from_slice(&output.stdout) {
        Ok(value) => value,
        Err(_) => return Ok(unavailable("Forge runtime unavailable. Verify backend dependencies and local model.")),
    };
    Ok(response(result["http_status"].as_u64().unwrap_or(503) as u16, result["body"].clone()))
}

fn find_backend() -> Option<PathBuf> {
    if let Ok(root) = std::env::var("NAVIS_BACKEND_DIR").map(PathBuf::from) {
        if root.exists() {
            return Some(root);
        }
    }
    let candidate = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("backend");
    if candidate.exists() {
        return Some(candidate);
    }
    None
}

// Classify stderr without exposing paths, credentials, or private input.
fn conversation_output(stdout: &[u8], stderr: &[u8], success: bool) -> ApiResponse {
    if !success {
        let diagnostic = String::from_utf8_lossy(stderr);
        let message = if diagnostic.contains("ModuleNotFoundError") || diagnostic.contains("ImportError") {
            "Conversation Python dependencies are missing. Install backend requirements in the NAVIS_PYTHON interpreter (including aiohttp), then restart Navis."
        } else {
            "Conversation runtime exited unexpectedly. Verify NAVIS_PYTHON and backend dependencies, then restart Navis."
        };
        return unavailable(message);
    }
    let result: Value = match serde_json::from_slice(stdout) {
        Ok(value) => value,
        Err(_) => return unavailable("Conversation runtime returned an invalid or empty response. Reinstall the current build, verify Python dependencies, and retry."),
    };
    let status = match result["http_status"].as_u64() {
        Some(value) if (200..=599).contains(&value) && result["body"].is_object() => value as u16,
        _ => return unavailable("Conversation runtime returned an invalid response envelope. Reinstall the current build and retry."),
    };
    if status < 300 && !result["body"]["response"].is_string() {
        return unavailable("Conversation runtime returned no message. Check the configured local model and retry.");
    }
    response(status, result["body"].clone())
}

/// Shared Conversation service for Reid, Neural Bridge, and War Room.
pub fn conversation_request(
    backend: &std::path::Path,
    path: &str,
    method: &str,
    body: Option<Value>,
) -> Result<ApiResponse, String> {
    let action = match (method, path) {
        ("POST", "/api/reid/chat") => "reid_chat",
        ("POST", "/api/neural/chat") => "neural_chat",
        ("POST", "/api/neural/warroom/chat") => "warroom_chat",
        _ => return Ok(response(400, json!({"detail":"Unsupported conversation action."}))),
    };
    if !backend.join("services/conversation_runtime.py").is_file()
        || !backend.join("services/conversation_service.py").is_file()
        || !backend.join("services/reid_agent.py").is_file() {
        return Ok(unavailable("Conversation backend files are missing. Reinstall the current Navis desktop build or use a complete development checkout."));
    }
    let runtime = match crate::command::resolve_python_runtime(backend, !cfg!(debug_assertions)) {
        Ok(value) => value,
        Err(_) => return Ok(unavailable("Conversation requires Python 3.11+. Set NAVIS_PYTHON to a supported interpreter with aiohttp installed, then restart Navis.")),
    };
    let mut command = crate::command::hidden_command(&runtime.to_string_lossy());
    command.args(["-m", "services.conversation_runtime", action]).current_dir(backend).env_clear();
    for key in [
        "PATH",
        "SystemRoot",
        "TEMP",
        "TMP",
        "NAVIS_OLLAMA_URL",
        "NAVIS_OLLAMA_MODEL",
        "NAVIS_OLLAMA_TIMEOUT",
        "NAVIS_AI_PROVIDER",
        "NAVIS_REID_NOTE_FILES",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
    ] {
        if let Ok(value) = std::env::var(key) { command.env(key, value); }
    }
    command.env("NAVIS_ROOT", root()).env("PYTHONIOENCODING", "utf-8")
        .stdin(std::process::Stdio::piped()).stdout(std::process::Stdio::piped()).stderr(std::process::Stdio::piped());
    let mut child = match command.spawn() {
        Ok(value) => value,
        Err(_) => return Ok(unavailable("Conversation runtime could not start. Verify NAVIS_PYTHON and restart Navis.")),
    };
    if let Some(mut input) = child.stdin.take() {
        let payload = body.unwrap_or_else(|| json!({})).to_string();
        if payload.len() > 65536 || input.write_all(payload.as_bytes()).is_err() {
            let _ = child.kill(); let _ = child.wait();
            return Ok(response(400, json!({"detail":"Invalid conversation request."})));
        }
    }
    let output = match child.wait_with_output() {
        Ok(value) => value,
        Err(_) => return Ok(unavailable("Conversation runtime did not complete. Restart Navis and retry.")),
    };
    let parsed = conversation_output(&output.stdout, &output.stderr, output.status.success());
    let status = parsed.status;
    let body_val = parsed.body;
    let text = if path == "/api/neural/warroom/chat" {
        body_val.get("response").and_then(Value::as_str).unwrap_or(&body_val.to_string()).to_string()
    } else {
        body_val.to_string()
    };
    Ok(ApiResponse {
        status,
        body: body_val,
        text,
    })
}

pub fn request(path: &str, method: &str, _body: Option<Value>) -> Result<ApiResponse, String> {
    let route = path.split('?').next().unwrap_or(path);
    match (method, route) {
        ("GET", "/api/neural/banter/history") => Ok(banter_history(&root())),
        ("POST", "/api/neural/banter/generate") => {
            let count = path.split_once('?').and_then(|(_, query)| {
                query.split('&').find_map(|part| {
                    let (key, value) = part.split_once('=')?;
                    (key == "count").then(|| value.parse::<usize>().ok()).flatten()
                })
            }).unwrap_or(1);
            Ok(generate_banter(&root(), count))
        }
        ("GET", "/api/reid/history") => Ok(response(200, json!({"status":"success","history":latest_history()}))),
        ("GET", r) if r.starts_with("/api/v1/biometrics/") => Ok(biometrics(path)),
        ("GET", "/api/neural/warroom/history") => {
            let hist_path = root().join("Bridge").join("warroom_history.json");
            let data: Value = std::fs::read_to_string(&hist_path)
                .ok()
                .and_then(|t| serde_json::from_str(&t).ok())
                .unwrap_or_else(|| json!([]));
            Ok(response(200, data))
        }
        ("POST", "/api/neural/warroom/clear") => {
            let bridge_dir = root().join("Bridge");
            let _ = std::fs::create_dir_all(&bridge_dir);
            let hist_path = bridge_dir.join("warroom_history.json");
            let _ = std::fs::write(&hist_path, "[]");
            Ok(response(200, json!({"status": "success"})))
        }
        ("POST", "/api/reid/chat")
        | ("POST", "/api/neural/chat")
        | ("POST", "/api/neural/warroom/chat") => {
            if let Some(backend) = find_backend() {
                conversation_request(&backend, route, method, _body)
            } else {
                Ok(unavailable("Conversation backend resources are unavailable."))
            }
        }
        _ => Err(format!("native P5 route not implemented: {method} {path}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn conversation_output_handles_failures_and_recovery() {
        for output in [b"".as_slice(), b"not json", b"{}", b"{\"http_status\":200,\"body\":{}}"] {
            assert_eq!(conversation_output(output, b"private secret", true).status, 503);
        }
        let missing = conversation_output(b"", b"ModuleNotFoundError: secret", false);
        assert!(missing.text.contains("dependencies"));
        assert!(!missing.text.contains("secret"));
        let crashed = conversation_output(b"{}", b"private prompt", false);
        assert!(!crashed.text.contains("private prompt"));
        let unavailable_model = br#"{"http_status":503,"body":{"detail":"Install configured local model."}}"#;
        assert_eq!(conversation_output(unavailable_model, b"", true).status, 503);
        let recovered = br#"{"http_status":200,"body":{"response":"Ready"}}"#;
        assert_eq!(conversation_output(recovered, b"", true).body["response"], "Ready");
    }

    #[test]
    fn only_approved_operations_are_registered() {
        assert!(ALLOWED.iter().any(|(id, _)| *id == "backup"));
        assert!(!ALLOWED.iter().any(|(id, _)| *id == "rm"));
    }
    #[test]
    fn unavailable_response_redacts_provider_details() {
        let v = unavailable("provider unavailable");
        assert_eq!(v.status, 503);
        assert!(!v.text.contains("API_KEY"));
    }

    #[test]
    fn warroom_history_and_clear_work_with_synthetic_vault() {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time")
            .as_nanos();
        let root = std::env::temp_dir().join(format!("navis-warroom-test-{}-{nonce}", std::process::id()));
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge dir");
        std::fs::create_dir_all(root.join("Journal")).expect("journal dir");
        let initial_history = json!([
            {"role": "user", "content": "Test entry"},
            {"role": "assistant", "content": "Understood."}
        ]);
        std::fs::write(root.join("Bridge").join("warroom_history.json"), initial_history.to_string()).expect("write");
        std::env::set_var("NAVIS_ROOT", &root);

        let res = request("/api/neural/warroom/history", "GET", None).expect("history route");
        assert_eq!(res.status, 200);
        assert_eq!(res.body.as_array().map(Vec::len), Some(2));

        let clear_res = request("/api/neural/warroom/clear", "POST", None).expect("clear route");
        assert_eq!(clear_res.status, 200);

        let empty_res = request("/api/neural/warroom/history", "GET", None).expect("history route after clear");
        assert_eq!(empty_res.status, 200);
        assert_eq!(empty_res.body.as_array().map(Vec::len), Some(0));

        let _ = std::fs::remove_dir_all(root);
        std::env::remove_var("NAVIS_ROOT");
    }

    #[test]
    fn conversation_routes_redact_secrets_when_provider_unavailable() {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time")
            .as_nanos();
        let root = std::env::temp_dir().join(format!("navis-conv-test-{}-{nonce}", std::process::id()));
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge dir");
        std::fs::create_dir_all(root.join("Journal")).expect("journal dir");
        std::fs::write(root.join("Bridge").join("status.json"), r#"{"squad":[],"current_realm":"Unknown"}"#).expect("write");
        std::env::set_var("NAVIS_ROOT", &root);
        std::env::set_var("NAVIS_OLLAMA_URL", "http://127.0.0.1:54321");
        std::env::set_var("NAVIS_OLLAMA_TIMEOUT", "1");
        std::env::set_var("GEMINI_API_KEY", "super_secret_test_key_12345");

        let cases = [
            ("POST", "/api/reid/chat", json!({"message": "Hello Reid"})),
            ("POST", "/api/neural/chat", json!({"message": "Hello Bridge"})),
            ("POST", "/api/neural/warroom/chat", json!({"message": "Hello War Room"})),
        ];
        for (method, path, body) in cases {
            if path == "/api/neural/warroom/chat" {
                // War Room validates its active squad before calling a provider.
                let empty = request(path, method, Some(body.clone())).expect("empty squad validation");
                assert_eq!(empty.status, 400);
                std::fs::write(root.join("Bridge/status.json"), r#"{"squad":[{"name":"Fixture Companion"}],"current_realm":"Unknown"}"#).expect("valid squad fixture");
            }
            let result = request(path, method, Some(body)).expect("route should be handled");
            assert_eq!(result.status, 503, "{method} {path}");
            assert_eq!(result.body["code"], "native_dependency_unavailable");
            assert!(!result.text.contains("super_secret_test_key_12345"));
            assert!(!result.text.contains("GEMINI_API_KEY"));
        }

        let _ = std::fs::remove_dir_all(root);
        std::env::remove_var("NAVIS_ROOT");
        std::env::remove_var("NAVIS_OLLAMA_URL");
        std::env::remove_var("NAVIS_OLLAMA_TIMEOUT");
        std::env::remove_var("GEMINI_API_KEY");
    }

    #[test]
    fn banter_validation_requires_the_full_party_in_order() {
        let party = vec!["Aster".to_string(), "Rowan".to_string()];
        let valid = json!([
            {"speaker":"Aster","text":"The path is quiet."},
            {"speaker":"Rowan","text":"For now."}
        ]);
        let reversed = json!([
            {"speaker":"Rowan","text":"For now."},
            {"speaker":"Aster","text":"The path is quiet."}
        ]);
        let incomplete = json!([{"speaker":"Aster","text":"The path is quiet."}]);
        assert!(valid_chain(&valid, &party));
        assert!(!valid_chain(&reversed, &party));
        assert!(!valid_chain(&incomplete, &party));
    }

    #[test]
    fn configured_banter_section_stops_at_next_heading() {
        let content = "intro\n## 🗣️ Banter Protocol\nSpeak warmly.\n## Other\nIgnore this.";
        assert_eq!(
            section(content, "## 🗣️ Banter Protocol", "fallback"),
            "Speak warmly."
        );
    }

    #[test]
    fn banter_storage_is_idempotent_and_sorts_party_key() {
        let conn = rusqlite::Connection::open_in_memory().expect("memory database");
        let party = vec!["Rowan".to_string(), "Aster".to_string()];
        let chain = json!([
            {"speaker":"Rowan","text":"A quiet trail."},
            {"speaker":"Aster","text":"I agree."}
        ]);
        persist_banter(&conn, "Mosswood", &party, &chain).expect("first insert");
        persist_banter(&conn, "Mosswood", &party, &chain).expect("duplicate is harmless");
        let count: i64 = conn
            .query_row("SELECT COUNT(*) FROM banter_threads", [], |row| row.get(0))
            .expect("count");
        let stored_party: String = conn
            .query_row("SELECT participants FROM banter_threads", [], |row| {
                row.get(0)
            })
            .expect("party");
        assert_eq!(count, 1);
        assert_eq!(stored_party, "Aster,Rowan");
    }

    #[test]
    fn missing_banter_history_does_not_create_a_database() {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time")
            .as_nanos();
        let root = std::env::temp_dir().join(format!(
            "navis-banter-history-{}-{nonce}",
            std::process::id()
        ));
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge directory");
        std::fs::create_dir_all(root.join("Journal")).expect("journal directory");
        std::fs::write(root.join("Bridge").join("status.json"), r#"{"squad":[]}"#)
            .expect("status file");

        let result = banter_history(&root);

        assert_eq!(result.status, 200);
        assert_eq!(result.body, json!([]));
        assert!(!root.join("Journal").join("Chronicle.db").exists());
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn existing_chronicle_without_banter_table_is_empty_history() {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time")
            .as_nanos();
        let root = std::env::temp_dir().join(format!(
            "navis-banter-history-no-table-{}-{nonce}",
            std::process::id()
        ));
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge directory");
        std::fs::create_dir_all(root.join("Journal")).expect("journal directory");
        std::fs::write(
            root.join("Bridge").join("status.json"),
            r#"{"squad":[{"name":"Aster"},{"name":"Rowan"}]}"#,
        )
        .expect("status file");
        let conn = rusqlite::Connection::open(root.join("Journal").join("Chronicle.db"))
            .expect("Chronicle database");
        conn.execute("CREATE TABLE journal_entries (id INTEGER PRIMARY KEY)", [])
            .expect("journal table");
        drop(conn);

        let result = banter_history(&root);

        assert_eq!(result.status, 200);
        assert_eq!(result.body, json!([]));

        let conn = rusqlite::Connection::open(root.join("Journal").join("Chronicle.db"))
            .expect("Chronicle database");
        conn.execute("DROP TABLE journal_entries", [])
            .expect("remove journal table");
        conn.execute("CREATE TABLE banter_threads (id INTEGER PRIMARY KEY)", [])
            .expect("malformed banter table");
        drop(conn);

        let malformed_result = banter_history(&root);
        assert_eq!(malformed_result.status, 503);
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn banter_status_accepts_utf8_bom_and_empty_squad() {
        let root = std::env::temp_dir().join(format!("navis-banter-status-bom-{}", std::process::id()));
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge directory");
        std::fs::write(root.join("Bridge/status.json"), b"\xef\xbb\xbf{\"squad\":[]}").expect("status file");
        let status = read_banter_status(&root).expect("BOM status is valid");
        assert_eq!(party_names(&status), Vec::<String>::new());
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn banter_status_reports_missing_unreadable_and_malformed_files() {
        let root = std::env::temp_dir().join(format!("navis-banter-status-errors-{}", std::process::id()));
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge directory");
        assert!(read_banter_status(&root).unwrap_err().contains("missing"));
        std::fs::write(root.join("Bridge/status.json"), "not-json").expect("malformed status");
        assert!(read_banter_status(&root).unwrap_err().contains("malformed"));
        std::fs::remove_file(root.join("Bridge/status.json")).expect("remove status");
        std::fs::create_dir(root.join("Bridge/status.json")).expect("unreadable status path");
        assert!(read_banter_status(&root).unwrap_err().contains("could not be read"));
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn empty_or_duplicate_active_squad_is_distinct_from_unavailable_status() {
        let root = std::env::temp_dir().join(format!("navis-banter-empty-squad-{}", std::process::id()));
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge directory");
        std::fs::write(root.join("Bridge/status.json"), r#"{"squad":[],"current_realm":"Mosswood"}"#).expect("status file");
        let result = generate_banter(&root, 1);
        assert_eq!(result.status, 422);
        assert!(result.body["detail"].as_str().unwrap().contains("two uniquely named"));
        std::fs::write(root.join("Bridge/status.json"), r#"{"squad":[{"name":"Aster"},{"name":" aStEr "}],"current_realm":"Mosswood"}"#).expect("duplicate status file");
        assert_eq!(generate_banter(&root, 1).status, 422);
        let _ = std::fs::remove_dir_all(root);
    }
}
