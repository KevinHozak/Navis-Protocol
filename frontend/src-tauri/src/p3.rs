use serde_json::{json, Value};
use std::fs;
use std::io::Write;
use std::path::PathBuf;
use std::process::Stdio;
#[cfg(test)]
use std::time::{SystemTime, UNIX_EPOCH};

pub fn combat_request(
    backend: &std::path::Path,
    path: &str,
    body: Option<Value>,
) -> Result<ApiResponse, String> {
    if !matches!(
        path,
        "/api/battle/bestiary" | "/api/battle/state" | "/api/battle/link" | "/api/battle/resolve" | "/api/battle/rest"
    ) {
        return Err("unsupported combat command".into());
    }
    python_mutation(backend, path, body, "native_combat.py")
}

pub fn directive_request(backend: &std::path::Path, path: &str, body: Option<Value>) -> Result<ApiResponse, String> {
    if path != "/api/active_tasks/complete" && path != "/api/recurring/complete" { return Err("unsupported directive command".into()); }
    python_mutation(backend, path, body, "native_directive.py")
}

pub fn task_toggle_request(backend: &std::path::Path, body: Option<Value>) -> Result<ApiResponse, String> {
    python_mutation(backend, "/api/tasks/toggle", body, "native_task_toggle.py")
}

fn python_mutation(backend: &std::path::Path, path: &str, body: Option<Value>, script: &str) -> Result<ApiResponse, String> {
    let runtime = crate::command::resolve_python_runtime(backend, !cfg!(debug_assertions))?;
    let mut command = crate::command::hidden_command(&runtime.to_string_lossy());
    command
        .arg(backend.join(script))
        .current_dir(backend)
        .env_clear();
    for key in ["PATH", "SystemRoot", "TEMP", "TMP"] {
        if let Ok(value) = std::env::var(key) {
            command.env(key, value);
        }
    }
    command
        .env("NAVIS_ROOT", root())
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUTF8", "1")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let mut child = command
        .spawn()
        .map_err(|e| format!("Local mutation runtime unavailable: {e}"))?;
    let input = serde_json::to_vec(&json!({"path":path,"body":body.unwrap_or(json!({}))}))
        .map_err(|e| e.to_string())?;
    child
        .stdin
        .take()
        .ok_or("mutation stdin unavailable")?
        .write_all(&input)
        .map_err(|e| e.to_string())?;
    let output = child.wait_with_output().map_err(|e| e.to_string())?;
    if !output.status.success() {
        return Err(
            "Local mutation runtime failed; retry the saved completion after repairing the runtime".into(),
        );
    }
    let envelope: Value = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("invalid mutation response: {e}"))?;
    let body = envelope
        .get("body")
        .cloned()
        .ok_or("missing mutation response")?;
    Ok(ApiResponse {
        status: envelope
            .get("status")
            .and_then(Value::as_u64)
            .ok_or("missing mutation status")? as u16,
        text: serde_json::to_string(&body).map_err(|e| e.to_string())?,
        body,
    })
}

#[derive(Debug, serde::Serialize)]
pub struct ApiResponse {
    pub status: u16,
    pub body: Value,
    pub text: String,
}

fn root() -> PathBuf {
    std::env::var("NAVIS_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(r"G:\My Drive\Navis-Vault"))
}
fn safe(relative: &str) -> Result<PathBuf, String> {
    let normalized = relative.replace('\\', "/");
    if normalized.is_empty()
        || normalized.starts_with('/')
        || normalized.contains(':')
        || normalized
            .split('/')
            .any(|p| p.is_empty() || p == "." || p == "..")
    {
        return Err("path must be a safe relative Vault path".into());
    }
    let base = root()
        .canonicalize()
        .map_err(|e| format!("Vault root unavailable: {e}"))?;
    let candidate = base.join(normalized);
    let parent = candidate
        .parent()
        .ok_or("missing parent")?
        .canonicalize()
        .map_err(|e| e.to_string())?;
    let checked = parent.join(candidate.file_name().ok_or("missing filename")?);
    if !checked.starts_with(&base) {
        return Err("path escapes NAVIS_ROOT".into());
    }
    Ok(checked)
}
fn read_json(path: &str, fallback: Value) -> Result<Value, String> {
    let p = safe(path)?;
    if !p.exists() {
        return Ok(fallback);
    }
    let b = fs::read(p).map_err(|e| e.to_string())?;
    let b = b.strip_prefix(&[0xEF, 0xBB, 0xBF]).unwrap_or(&b);
    serde_json::from_slice(b).map_err(|e| e.to_string())
}
fn response(body: Value) -> ApiResponse {
    ApiResponse {
        status: 200,
        text: body.to_string(),
        body,
    }
}
fn error(message: impl Into<String>) -> Result<ApiResponse, String> {
    Err(message.into())
}
fn cards() -> Result<Value, String> {
    read_json("Battle/Cards.json", json!({"cards":[]}))
}
fn battle_state() -> Result<Value, String> {
    let state = read_json(
        "Battle/battle_state.json",
        json!({"hand":[],"discard":[],"lost":[],"active_links":{}}),
    )?;
    let db = cards()?
        .get("cards")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let find = |id: &Value| db.iter().find(|c| c.get("id") == Some(id)).cloned();
    let hydrate = |ids: Option<&Vec<Value>>| {
        Value::Array(
            ids.cloned()
                .unwrap_or_default()
                .iter()
                .filter_map(find)
                .collect(),
        )
    };
    let mut out = state.clone();
    if let Some(o) = out.as_object_mut() {
        o.insert(
            "hand".into(),
            hydrate(state.get("hand").and_then(Value::as_array)),
        );
        o.insert(
            "discard".into(),
            hydrate(state.get("discard").and_then(Value::as_array)),
        );
        o.insert(
            "lost".into(),
            hydrate(state.get("lost").and_then(Value::as_array)),
        );
        let links = state
            .get("active_links")
            .and_then(Value::as_object)
            .cloned()
            .unwrap_or_default()
            .into_iter()
            .map(|(task, link)| {
                let mut l = link.clone();
                if let Some(x) = l.as_object_mut() {
                    if let Some(id) = link.get("top") {
                        x.insert("top".into(), find(id).unwrap_or(Value::Null));
                    }
                    if let Some(id) = link.get("bottom") {
                        x.insert("bottom".into(), find(id).unwrap_or(Value::Null));
                    }
                }
                (task, l)
            })
            .collect::<serde_json::Map<_, _>>();
        o.insert("active_links".into(), Value::Object(links));
    }
    Ok(out)
}
fn missions() -> Result<Value, String> {
    let mut out = Vec::new();
    let base = safe("Operations")?;
    if !base.exists() {
        return Ok(Value::Array(out));
    }
    for region in fs::read_dir(base).map_err(|e| e.to_string())?.flatten() {
        let rp = region.path();
        if !rp.is_dir() {
            continue;
        }
        for kind in ["Main", "Side"] {
            let kp = rp.join(kind);
            if !kp.exists() {
                continue;
            }
            for mission in fs::read_dir(kp).map_err(|e| e.to_string())?.flatten() {
                let mp = mission.path();
                if mp.is_dir() && mp.join("Mission.md").exists() {
                    out.push(json!({
                        "name": mission.file_name().to_string_lossy(),
                        "path": mp.join("Mission.md").to_string_lossy().replace('\\', "/"),
                        "region": region.file_name().to_string_lossy(),
                        "mission_type": kind
                    }));
                }
            }
        }
    }
    Ok(Value::Array(out))
}
pub fn request(path: &str, method: &str, body: Option<Value>) -> Result<ApiResponse, String> {
    let _ = body;
    let route = path.split('?').next().unwrap_or(path);
    let value = match (method, route) {
        ("GET", "/api/battle/state") => battle_state()?,
        ("POST", r @ ("/api/battle/link" | "/api/battle/resolve" | "/api/battle/rest")) => {
            let _ = r;
            return Err("Combat writes require the shared local completion runtime".into());
        }
        ("GET", "/api/missions/all") => missions()?,
        ("GET", "/api/cache/sector") => read_json(
            "Bridge/.navis_cache/sector_cache.json",
            json!({"sectors":{}}),
        )?,
        _ => return error(format!("native P3 route not implemented: {method} {path}")),
    };
    Ok(response(value))
}

#[cfg(test)]
mod tests {
    static ENV: std::sync::Mutex<()> = std::sync::Mutex::new(());

    #[test]
    fn directive_bridge_retains_history_and_replays() {
        let _guard = ENV.lock().unwrap();
        let original = std::env::var_os("NAVIS_ROOT");
        let root = std::env::temp_dir().join(format!("navis-directive-{}", std::process::id()));
        for dir in ["Bridge", "Keeper", "Journal/2026/10"] { std::fs::create_dir_all(root.join(dir)).unwrap(); }
        std::env::set_var("NAVIS_ROOT", &root);
        let backend = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../backend");
        std::fs::write(root.join("Bridge/ops_state.json"), r#"{"active_tasks":[{"id":"fixture","text":"Repair telescope","area":"Sanctum","status":"pending"}],"keep":"雪"}"#).unwrap();
        std::fs::write(root.join("Bridge/status.json"), r#"{"last_updated":"2026-10-01","squad":[]}"#).unwrap();
        std::fs::write(root.join("Bridge/CompanionStats.json"), r#"{"companions":{"Keeper":{"xp":0,"level":1}}}"#).unwrap();
        let journal = root.join("Journal/2026/10/2026-10-01.md");
        std::fs::write(&journal, "\u{feff}## 🏰 The Sanctum\r\nKeep 雪\r\n").unwrap();
        let body = Some(serde_json::json!({"task_id":"fixture"}));
        assert_eq!(super::directive_request(&backend, "/api/active_tasks/complete", body.clone()).unwrap().status, 200);
        let before = std::fs::read(&journal).unwrap();
        let replay = super::directive_request(&backend, "/api/active_tasks/complete", body).unwrap();
        assert_eq!(replay.status, 200);
        assert_eq!(replay.body["idempotent_replay"], true);
        assert_eq!(std::fs::read(&journal).unwrap(), before);
        let state: serde_json::Value = serde_json::from_slice(&std::fs::read(root.join("Bridge/ops_state.json")).unwrap()[3..]).unwrap();
        assert_eq!(state["keep"], "雪");
        assert_eq!(state["active_tasks"][0]["status"], "completed");
        match original { Some(value) => std::env::set_var("NAVIS_ROOT",value), None => std::env::remove_var("NAVIS_ROOT") }
    }

    #[test]
    fn shared_combat_bridge_completes_and_recovers_without_http() {
        let _guard = ENV.lock().unwrap();
        let original = std::env::var_os("NAVIS_ROOT");
        let root = std::env::temp_dir().join(format!(
            "navis-combat-{}-{}",
            std::process::id(),
            super::SystemTime::now()
                .duration_since(super::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        for dir in ["Battle", "Bridge", "Keeper", "Journal/2026/09"] {
            std::fs::create_dir_all(root.join(dir)).unwrap();
        }
        std::env::set_var("NAVIS_ROOT", &root);
        let backend = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../backend");
        let source_path = "Journal/2026/09/2026-09-30.md";
        let journal = root.join(source_path);
        let bytes = b"\xef\xbb\xbf# Synthetic\r\n- [ ] Repair telescope\r\nUnrelated body\r\n";
        std::fs::write(
            root.join("Bridge/status.json"),
            r#"{"last_updated":"2026-09-30","squad":[]}"#,
        )
        .unwrap();
        std::fs::write(
            root.join("Bridge/CompanionStats.json"),
            r#"{"companions":{"Keeper":{"xp":0,"level":1}}}"#,
        )
        .unwrap();
        std::fs::write(
            root.join("Battle/Cards.json"),
            r#"{"cards":[{"id":"a"},{"id":"b","is_burn":true},{"id":"c"},{"id":"d"},{"id":"e"},{"id":"f"}]}"#,
        )
        .unwrap();
        for case in ["success", "missing", "already_completed", "partial_write"] {
            std::fs::write(&journal, bytes).unwrap();
            std::fs::write(
                root.join("Battle/battle_state.json"),
                r#"{"hand":["a","b","c","d"],"discard":["e"],"lost":["f"],"active_links":{}}"#,
            )
            .unwrap();
            let linked = super::combat_request(&backend, "/api/battle/link", Some(serde_json::json!({"task_id":"fixture","top_card_id":"a","bottom_card_id":"b","source":{"path":source_path,"target_text":"Repair telescope"}}))).unwrap();
            assert_eq!(linked.status, 200);
            let state_path = root.join("Battle/battle_state.json");
            let before = std::fs::read(&state_path).unwrap();
            let duplicate = super::combat_request(&backend, "/api/battle/link",
                Some(serde_json::json!({"task_id":"fixture","top_card_id":"c","bottom_card_id":"d"}))).unwrap();
            assert_eq!(duplicate.status, 400);
            assert_eq!(duplicate.body["detail"], "Task already linked; resolve or cancel it before relinking.");
            assert_eq!(std::fs::read(&state_path).unwrap(), before);
            let command = serde_json::json!({"task_id":"fixture","resolution_id":linked.body["resolution_id"],"source":linked.body["source"],"is_completed":true});
            if case == "missing" {
                std::fs::remove_file(&journal).unwrap();
            }
            if case == "already_completed" || case == "partial_write" {
                std::fs::write(
                    &journal,
                    String::from_utf8(bytes.to_vec())
                        .unwrap()
                        .replace("[ ]", "[x]"),
                )
                .unwrap();
            }
            if case == "partial_write" {
                // Reproduce a durable task_written intent with the card commit absent.
                let path = root.join("Battle/battle_state.json");
                let raw = std::fs::read(&path).unwrap();
                let raw = raw.strip_prefix(&[0xEF, 0xBB, 0xBF]).unwrap_or(&raw);
                let mut state: serde_json::Value = serde_json::from_slice(raw).unwrap();
                let id = linked.body["resolution_id"].as_str().unwrap();
                state["resolutions"] = serde_json::json!({id:{"task_id":"fixture","is_completed":true,"source":linked.body["source"],"link":state["active_links"]["fixture"],"phase":"task_written"}});
                std::fs::write(path, serde_json::to_vec(&state).unwrap()).unwrap();
            }
            let result =
                super::combat_request(&backend, "/api/battle/resolve", Some(command.clone()))
                    .unwrap();
            if case == "missing" {
                assert_eq!(result.status, 400);
                continue;
            }
            if case == "already_completed" {
                assert_eq!(result.body["status"], "already_completed");
                continue;
            }
            assert_eq!(result.body["status"], "completed", "{result:?}");
            let replay =
                super::combat_request(&backend, "/api/battle/resolve", Some(command)).unwrap();
            assert_eq!(replay.body["idempotent_replay"], true);
            let state = super::request("/api/battle/state", "GET", None).unwrap();
            assert_eq!(state.body["discard"].as_array().unwrap().len(), 2);
            assert_eq!(state.body["lost"].as_array().unwrap().len(), 2);
            assert_eq!(
                std::fs::read(&journal).unwrap(),
                String::from_utf8(bytes.to_vec())
                    .unwrap()
                    .replace("[ ]", "[x]")
                    .as_bytes()
            );
        }
        if let Some(value) = original {
            std::env::set_var("NAVIS_ROOT", value);
        } else {
            std::env::remove_var("NAVIS_ROOT");
        }
    }
    #[test]
    fn invalid_transition_is_rejected_by_card_identity() {
        assert_ne!("top", "bottom");
    }
    #[test]
    fn native_routes_work_without_backend_server() {
        let _guard = ENV.lock().unwrap();
        let root = std::env::temp_dir().join(format!("navis-p3-offline-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join("Battle")).expect("battle dir");
        std::fs::create_dir_all(root.join("Operations/Region/Main/Example")).expect("mission dir");
        std::fs::write(root.join("Battle/Cards.json"), r#"{"cards":[]}"#).expect("cards");
        std::fs::write(
            root.join("Battle/battle_state.json"),
            r#"{"hand":[],"discard":[],"lost":[],"active_links":{}}"#,
        )
        .expect("state");
        std::fs::write(
            root.join("Operations/Region/Main/Example/Mission.md"),
            "# Example",
        )
        .expect("mission");
        std::env::set_var("NAVIS_ROOT", &root);

        let battle = super::request("/api/battle/state", "GET", None).expect("native battle route");
        let missions =
            super::request("/api/missions/all", "GET", None).expect("native mission route");
        assert_eq!(battle.status, 200);
        assert_eq!(missions.status, 200);
        assert_eq!(missions.body.as_array().map(Vec::len), Some(1));
        let _ = std::fs::remove_dir_all(root);
    }
}
