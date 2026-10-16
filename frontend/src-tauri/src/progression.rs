use rusqlite::{params, Connection, OptionalExtension, TransactionBehavior};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

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

fn connection() -> Result<Connection, String> {
    let vault = root();
    if !vault.is_dir() {
        return Err(format!("Navis Vault is unavailable at {}", vault.display()));
    }
    let dir = vault.join("Keeper");
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let conn = Connection::open(dir.join("navis_progression.db")).map_err(|e| e.to_string())?;
    conn.busy_timeout(std::time::Duration::from_secs(30))
        .map_err(|e| e.to_string())?;
    conn.execute_batch(
        "PRAGMA foreign_keys=ON;
         CREATE TABLE IF NOT EXISTS xp_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, amount INTEGER NOT NULL, details TEXT);
         CREATE TABLE IF NOT EXISTS achievements (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, description TEXT, date_achieved TEXT, category TEXT);
         CREATE TABLE IF NOT EXISTS xp_ledger (
           award_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, amount INTEGER NOT NULL,
           source_type TEXT NOT NULL, source_ref TEXT NOT NULL, source_event_at TEXT NOT NULL,
           local_date TEXT NOT NULL, rule_version TEXT NOT NULL, provenance TEXT NOT NULL,
           created_at TEXT NOT NULL, correction_of TEXT, reason TEXT, details TEXT NOT NULL DEFAULT '',
           FOREIGN KEY(correction_of) REFERENCES xp_ledger(award_id));
         CREATE INDEX IF NOT EXISTS idx_xp_ledger_entity_date ON xp_ledger(entity_id, local_date DESC, created_at DESC);
         CREATE TABLE IF NOT EXISTS xp_source_state (
           entity_id TEXT NOT NULL, source_type TEXT NOT NULL, source_ref TEXT NOT NULL,
           amount INTEGER NOT NULL, last_award_id TEXT NOT NULL, provenance TEXT NOT NULL,
           local_date TEXT NOT NULL, PRIMARY KEY(entity_id,source_type,source_ref));
         CREATE TABLE IF NOT EXISTS progression_schema (version INTEGER NOT NULL);
         CREATE TABLE IF NOT EXISTS xp_reconciliation_lock (singleton INTEGER PRIMARY KEY CHECK(singleton=1), run_id TEXT NOT NULL);
         CREATE TABLE IF NOT EXISTS talent_nodes (
           id TEXT PRIMARY KEY, branch TEXT NOT NULL,
           tier INTEGER NOT NULL, prerequisites TEXT NOT NULL DEFAULT '[]',
           max_rank INTEGER NOT NULL DEFAULT 1, perk_key TEXT NOT NULL,
           name TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '');
         CREATE TABLE IF NOT EXISTS talent_allocations (
           entity_id TEXT NOT NULL, node_id TEXT NOT NULL,
           rank INTEGER NOT NULL, allocated_at TEXT NOT NULL,
           PRIMARY KEY(entity_id, node_id),
           FOREIGN KEY(node_id) REFERENCES talent_nodes(id));
         CREATE INDEX IF NOT EXISTS idx_talent_allocations_entity ON talent_allocations(entity_id);
         INSERT INTO progression_schema(version) SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM progression_schema);
         INSERT OR IGNORE INTO talent_nodes (id, branch, tier, prerequisites, max_rank, perk_key, name, description) VALUES
           ('focus_deep_work', 'Focus', 1, '[]', 3, 'focus_deep_work_multiplier', 'Deep Work Flow', 'Enhances focus depth and execution endurance during single-task sessions.'),
           ('focus_clarity', 'Focus', 2, '[\"focus_deep_work\"]', 2, 'focus_stamina_boost', 'Mindful Clarity', 'Reduces cognitive fatigue and extends focus stamina during extended deep work.'),
           ('martial_momentum', 'Martial', 1, '[]', 3, 'high_velocity_xp_bonus', 'High-Velocity Striker', '+10% XP yield on High-Velocity Front combat operations and rapid task completions.'),
           ('martial_tenacity', 'Martial', 2, '[\"martial_momentum\"]', 2, 'reduced_rollover_penalty', 'Unyielding Tenacity', 'Mitigates friction, morale loss, and rollover penalties from overdue objectives.'),
           ('kinetic_vitality', 'Kinetic', 1, '[]', 3, 'kinetic_stamina_efficiency', 'Kinetic Vitality', 'Boosts physical endurance, energy reserves, and daily health habit tracking.'),
           ('kinetic_surge', 'Kinetic', 2, '[\"kinetic_vitality\"]', 1, 'daily_outland_surge', 'Outland Surge', 'Awards surge bonus rewards and stamina replenishment upon conquering physical expeditions.'),
           ('lore_archivist', 'Lore', 1, '[]', 3, 'library_harvest_bonus', 'Master Archivist', 'Boosts wisdom and XP yields when harvesting or transmuting research scrolls.'),
           ('lore_synthesis', 'Lore', 2, '[\"lore_archivist\"]', 2, 'neural_arbiter_synergy', 'Holocron Synthesis', 'Amplifies cognitive telemetry synthesis, arbiter insights, and intelligence archives.');
         UPDATE progression_schema SET version = 2 WHERE version < 2;",
    )
    .map_err(|e| e.to_string())?;
    Ok(conn)
}

fn response(body: Value, status: u16) -> ApiResponse {
    ApiResponse {
        status,
        text: body.to_string(),
        body,
    }
}

fn query_value(path: &str, key: &str) -> Option<String> {
    path.split('?').nth(1)?.split('&').find_map(|pair| {
        let (name, value) = pair.split_once('=')?;
        (name == key).then(|| value.to_string())
    })
}

fn level(total: i64) -> i64 {
    (0.5 + (0.25 + 2.0 * total as f64 / 1000.0).max(0.0).sqrt())
        .floor()
        .max(1.0) as i64
}

fn query_xp(path: &str) -> Result<Value, String> {
    let entity = query_value(path, "entity_id").unwrap_or_else(|| "keeper".into());
    let limit = query_value(path, "limit")
        .and_then(|v| v.parse::<i64>().ok())
        .unwrap_or(100)
        .clamp(1, 1000);
    let conn = connection()?;
    let total: i64 = conn
        .query_row(
            "SELECT COALESCE(SUM(amount),0) FROM xp_ledger WHERE entity_id=?1",
            [&entity],
            |r| r.get(0),
        )
        .map_err(|e| e.to_string())?;
    let unresolved: i64 = conn
        .query_row("SELECT COUNT(*) FROM xp_logs", [], |r| r.get(0))
        .map_err(|e| e.to_string())?;
    let mut stmt = conn.prepare("SELECT award_id,entity_id,amount,source_type,source_ref,source_event_at,local_date,rule_version,provenance,created_at,correction_of,reason,details FROM xp_ledger WHERE entity_id=?1 ORDER BY local_date DESC,created_at DESC,award_id DESC LIMIT ?2").map_err(|e| e.to_string())?;
    let rows = stmt.query_map(params![entity, limit], |r| Ok(json!({
        "award_id":r.get::<_,String>(0)?, "entity_id":r.get::<_,String>(1)?, "amount":r.get::<_,i64>(2)?,
        "source_type":r.get::<_,String>(3)?, "source_ref":r.get::<_,String>(4)?,
        "source_event_at":r.get::<_,String>(5)?, "local_date":r.get::<_,String>(6)?, "date":r.get::<_,String>(6)?,
        "rule_version":r.get::<_,String>(7)?, "provenance":serde_json::from_str::<Value>(&r.get::<_,String>(8)?).unwrap_or(Value::Null),
        "created_at":r.get::<_,String>(9)?, "correction_of":r.get::<_,Option<String>>(10)?,
        "reason":r.get::<_,Option<String>>(11)?, "details":r.get::<_,String>(12)?
    }))).map_err(|e| e.to_string())?;
    let mut history = rows
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())?;
    for row in &mut history {
        if row["details"].as_str().unwrap_or("").is_empty() {
            row["details"] = row["reason"]
                .as_str()
                .filter(|reason| !reason.is_empty())
                .map(|reason| json!(reason))
                .unwrap_or_else(|| row["source_type"].clone());
        }
    }
    let current_level = level(total);
    let base = 500 * current_level * (current_level - 1);
    let next = 500 * (current_level + 1) * current_level;
    Ok(
        json!({"entity_id":entity,"total_xp":total,"level":current_level,"current_level_xp":base,"next_level_xp":next,"xp_into_level":total-base,"xp_for_next_level":next-base,"progress_percent":((total-base) as f64 * 100.0 / (next-base) as f64).clamp(0.0,100.0),"legacy_history_unresolved":unresolved>0,"history":history}),
    )
}

fn required_string(body: &Value, key: &str) -> Result<String, String> {
    body.get(key)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .map(str::to_string)
        .ok_or_else(|| format!("{key} required"))
}

fn record_award(body: &Value) -> Result<Value, String> {
    let award_id = required_string(body, "award_id")?;
    let entity_id = required_string(body, "entity_id")?;
    let source_type = required_string(body, "source_type")?;
    let source_ref = required_string(body, "source_ref")?;
    let source_event_at = required_string(body, "source_event_at")?;
    let local_date = required_string(body, "local_date")?;
    let rule_version = required_string(body, "rule_version")?;
    let amount = body
        .get("amount")
        .and_then(Value::as_i64)
        .ok_or("amount must be a signed integer")?;
    if entity_id != "keeper"
        && !entity_id
            .strip_prefix("companion:")
            .map(|v| !v.trim().is_empty())
            .unwrap_or(false)
    {
        return Err("entity_id must be keeper or companion:<stable-name>".into());
    }
    if chrono_date_invalid(&local_date) {
        return Err("local_date must use YYYY-MM-DD".into());
    }
    if !timestamp_has_timezone(&source_event_at) {
        return Err("source_event_at must be an ISO-8601 timestamp with timezone".into());
    }
    let reason = body
        .get("reason")
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim()
        .to_string();
    if source_type == "manual_adjustment" && reason.is_empty() {
        return Err("manual adjustments require an attributed reason".into());
    }
    let provenance_value = body.get("provenance").cloned().unwrap_or_else(|| json!({}));
    if !provenance_value.is_object() {
        return Err("provenance must be a JSON object".into());
    }
    if source_type == "manual_adjustment"
        && provenance_value
            .get("actor")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|v| !v.is_empty())
            .is_none()
    {
        return Err("manual adjustments require provenance.actor attribution".into());
    }
    let correction_of = body
        .get("correction_of")
        .and_then(Value::as_str)
        .map(str::to_string);
    if correction_of.is_some() != (source_type == "correction") {
        return Err("corrections must use source_type=correction and correction_of".into());
    }
    let details = body
        .get("details")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let provenance = provenance_value.to_string();
    let mut conn = connection()?;
    let tx = conn
        .transaction_with_behavior(TransactionBehavior::Immediate)
        .map_err(|e| e.to_string())?;
    let reconciliation_lock: Option<String> = tx
        .query_row(
            "SELECT run_id FROM xp_reconciliation_lock WHERE singleton=1",
            [],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| e.to_string())?;
    if reconciliation_lock.is_some() {
        return Err("XP reconciliation is applying or recovering; retry after it completes".into());
    }
    if let Some(original) = &correction_of {
        let owner: Option<String> = tx
            .query_row(
                "SELECT entity_id FROM xp_ledger WHERE award_id=?1",
                [original],
                |r| r.get(0),
            )
            .optional()
            .map_err(|e| e.to_string())?;
        if owner.as_deref() != Some(entity_id.as_str()) {
            return Err("correction_of must identify an existing award for the same entity".into());
        }
    }
    let created_at = chrono_now();
    let inserted = tx.execute(
        "INSERT OR IGNORE INTO xp_ledger(award_id,entity_id,amount,source_type,source_ref,source_event_at,local_date,rule_version,provenance,created_at,correction_of,reason,details) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13)",
        params![award_id,entity_id,amount,source_type,source_ref,source_event_at,local_date,rule_version,provenance,created_at,correction_of,if reason.is_empty(){None}else{Some(reason.clone())},details],
    ).map_err(|e| e.to_string())?;
    let created = inserted == 1;
    if !created {
        let existing: (String,i64,String,String,String,String,String,String,Option<String>,Option<String>,String) = tx.query_row("SELECT entity_id,amount,source_type,source_ref,source_event_at,local_date,rule_version,provenance,correction_of,reason,details FROM xp_ledger WHERE award_id=?1", [&award_id], |r| Ok((r.get(0)?,r.get(1)?,r.get(2)?,r.get(3)?,r.get(4)?,r.get(5)?,r.get(6)?,r.get(7)?,r.get(8)?,r.get(9)?,r.get(10)?))).map_err(|e| e.to_string())?;
        let same = existing
            == (
                entity_id.clone(),
                amount,
                source_type.clone(),
                source_ref.clone(),
                source_event_at.clone(),
                local_date.clone(),
                rule_version.clone(),
                provenance.clone(),
                correction_of.clone(),
                if reason.is_empty() {
                    None
                } else {
                    Some(reason.clone())
                },
                details.clone(),
            );
        if !same {
            return Err("award_id already exists with conflicting content".into());
        }
    }
    tx.commit().map_err(|e| e.to_string())?;
    project_entity(&entity_id).map_err(|e| {
        format!("ledger committed; compatibility projection failed (retry to repair): {e}")
    })?;
    Ok(json!({"created":created,"award_id":award_id,"entity_id":entity_id}))
}

fn chrono_date_invalid(value: &str) -> bool {
    let parts: Vec<_> = value.split('-').collect();
    if parts.len() != 3 || parts[0].len() != 4 || parts[1].len() != 2 || parts[2].len() != 2 {
        return true;
    }
    match (
        parts[0].parse::<u32>(),
        parts[1].parse::<u32>(),
        parts[2].parse::<u32>(),
    ) {
        (Ok(y), Ok(m), Ok(d)) => m < 1 || m > 12 || d < 1 || d > days_in_month(y, m),
        _ => true,
    }
}
fn timestamp_has_timezone(value: &str) -> bool {
    if !value.contains('T') {
        return false;
    }
    if value.ends_with('Z') {
        return true;
    }
    let bytes = value.as_bytes();
    if bytes.len() < 25 {
        return false;
    }
    let suffix = &bytes[bytes.len() - 6..];
    (suffix[0] == b'+' || suffix[0] == b'-')
        && suffix[1..3].iter().all(u8::is_ascii_digit)
        && suffix[3] == b':'
        && suffix[4..6].iter().all(u8::is_ascii_digit)
}
fn days_in_month(year: u32, month: u32) -> u32 {
    match month {
        2 => {
            if year % 4 == 0 && (year % 100 != 0 || year % 400 == 0) {
                29
            } else {
                28
            }
        }
        4 | 6 | 9 | 11 => 30,
        _ => 31,
    }
}
fn chrono_now() -> String {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let days = (now / 86_400) as i64;
    let seconds = now % 86_400;
    let z = days + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let mut year = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = mp + if mp < 10 { 3 } else { -9 };
    year += if month <= 2 { 1 } else { 0 };
    format!(
        "{year:04}-{month:02}-{day:02}T{:02}:{:02}:{:02}Z",
        seconds / 3600,
        (seconds % 3600) / 60,
        seconds % 60
    )
}

fn atomic_write(path: &Path, content: &str) -> Result<(), String> {
    let parent = path.parent().ok_or("projection has no parent directory")?;
    fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    let temp = path.with_extension(format!("tmp-{}", std::process::id()));
    fs::write(&temp, content).map_err(|e| e.to_string())?;
    if path.exists() {
        let backup = path.with_extension(format!("bak-{}", std::process::id()));
        if backup.exists() {
            fs::remove_file(&backup).map_err(|e| e.to_string())?;
        }
        fs::rename(path, &backup).map_err(|e| format!("cannot preserve old projection: {e}"))?;
        if let Err(err) = fs::rename(&temp, path) {
            let _ = fs::rename(&backup, path);
            let _ = fs::remove_file(&temp);
            return Err(err.to_string());
        }
    } else {
        fs::rename(&temp, path).map_err(|e| e.to_string())?;
    }
    Ok(())
}

fn project_entity(entity_id: &str) -> Result<(), String> {
    let root = root();
    let conn = connection()?;
    let total: i64 = conn
        .query_row(
            "SELECT COALESCE(SUM(amount),0) FROM xp_ledger WHERE entity_id=?1",
            [entity_id],
            |r| r.get(0),
        )
        .map_err(|e| e.to_string())?;
    let mut rows_stmt = conn.prepare("SELECT local_date,amount,details,source_type,reason FROM xp_ledger WHERE entity_id=?1 ORDER BY local_date,created_at,award_id").map_err(|e| e.to_string())?;
    let rows = rows_stmt
        .query_map([entity_id], |r| {
            Ok((
                r.get::<_, String>(0)?,
                r.get::<_, i64>(1)?,
                r.get::<_, String>(2)?,
                r.get::<_, String>(3)?,
                r.get::<_, Option<String>>(4)?,
            ))
        })
        .map_err(|e| e.to_string())?;
    let entries = rows
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())?;
    drop(rows_stmt);
    drop(conn);
    let name = if entity_id == "keeper" {
        "Keeper".to_string()
    } else {
        entity_id
            .strip_prefix("companion:")
            .ok_or("invalid companion entity_id")?
            .to_string()
    };
    let stats_path = root.join("Bridge/CompanionStats.json");
    let mut stats: Value = serde_json::from_slice(
        &fs::read(&stats_path).map_err(|e| format!("CompanionStats.json unavailable: {e}"))?,
    )
    .map_err(|e| format!("CompanionStats.json invalid: {e}"))?;
    let companion = stats
        .pointer_mut(&format!(
            "/companions/{}",
            name.replace('~', "~0").replace('/', "~1")
        ))
        .ok_or_else(|| format!("entity {name:?} is absent from CompanionStats.json"))?;
    // Preserve unresolved legacy totals until the separately scoped P3 migration.
    companion["ledger_xp"] = json!(total);
    companion["ledger_level"] = json!(level(total));
    atomic_write(
        &stats_path,
        &serde_json::to_string_pretty(&stats).map_err(|e| e.to_string())?,
    )?;

    let xp_path = if entity_id == "keeper" {
        root.join("Keeper/XP.md")
    } else {
        root.join("Companions").join(&name).join("XP.md")
    };
    let old = fs::read_to_string(&xp_path).unwrap_or_default();
    let start = "<!-- NAVIS XP LEDGER START -->";
    let end = "<!-- NAVIS XP LEDGER END -->";
    let mut block = format!(
        "{start}\n**Canonical total: {total} XP (Level {})**\n\n",
        level(total)
    );
    for (date, amount, details, source_type, reason) in entries {
        let label = if details.is_empty() {
            reason.unwrap_or(source_type)
        } else {
            details
        };
        block.push_str(&format!("- **{date}:** {amount:+} XP ({label})\n"));
    }
    block.push_str(end);
    let content = if let Some(i) = old.find(start) {
        if let Some(rel_end) = old[i..].find(end) {
            format!("{}{}{}", &old[..i], block, &old[i + rel_end + end.len()..])
        } else {
            format!("{}\n\n{}\n", old.trim_end(), block)
        }
    } else {
        format!("{}\n\n{}\n", old.trim_end(), block)
    };
    atomic_write(&xp_path, &content)?;
    Ok(())
}

fn achievements() -> Result<Value, String> {
    let conn = connection()?;
    let mut stmt = conn.prepare("SELECT id,code,name,description,date_achieved,category FROM achievements ORDER BY category,date_achieved DESC").map_err(|e| e.to_string())?;
    let rows = stmt.query_map([], |r| Ok(json!({"id":r.get::<_,i64>(0)?,"code":r.get::<_,String>(1)?,"name":r.get::<_,String>(2)?,"description":r.get::<_,Option<String>>(3)?.unwrap_or_default(),"date_achieved":r.get::<_,Option<String>>(4)?,"category":r.get::<_,Option<String>>(5)?.unwrap_or_else(||"Uncategorized".into())}))).map_err(|e| e.to_string())?;
    Ok(Value::Array(
        rows.collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?,
    ))
}

fn parse_prereqs(raw: &str) -> Value {
    let trimmed = raw.trim();
    if trimmed.starts_with('[') {
        if let Ok(val) = serde_json::from_str::<Value>(trimmed) {
            if val.is_array() {
                return val;
            }
        }
    }
    let parts: Vec<Value> = trimmed
        .split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(|s| json!(s))
        .collect();
    Value::Array(parts)
}

fn prereq_satisfied(prereq: &Value, alloc_map: &HashMap<String, i64>) -> bool {
    if let Some(req_node) = prereq.as_str() {
        return alloc_map.get(req_node).copied().unwrap_or(0) >= 1;
    }
    if let Some(obj) = prereq.as_object() {
        let req_node = obj.get("node_id").and_then(Value::as_str).unwrap_or("");
        let min_rank = obj.get("min_rank").and_then(Value::as_i64).unwrap_or(1);
        return alloc_map.get(req_node).copied().unwrap_or(0) >= min_rank;
    }
    true
}

fn query_talents(path: &str) -> Result<Value, String> {
    let entity = query_value(path, "entity_id").unwrap_or_else(|| "keeper".into());
    if entity != "keeper"
        && !entity
            .strip_prefix("companion:")
            .map(|v| !v.trim().is_empty())
            .unwrap_or(false)
    {
        return Err("entity_id must be keeper or companion:<stable-name>".into());
    }
    let conn = connection()?;
    let total_xp: i64 = conn
        .query_row(
            "SELECT COALESCE(SUM(amount), 0) FROM xp_ledger WHERE entity_id=?1",
            [&entity],
            |r| r.get(0),
        )
        .map_err(|e| e.to_string())?;
    let current_level = level(total_xp);

    let mut alloc_stmt = conn
        .prepare("SELECT entity_id, node_id, rank, allocated_at FROM talent_allocations WHERE entity_id=?1 ORDER BY allocated_at ASC")
        .map_err(|e| e.to_string())?;
    let alloc_rows = alloc_stmt
        .query_map([&entity], |r| {
            Ok(json!({
                "entity_id": r.get::<_, String>(0)?,
                "node_id": r.get::<_, String>(1)?,
                "rank": r.get::<_, i64>(2)?,
                "allocated_at": r.get::<_, String>(3)?,
            }))
        })
        .map_err(|e| e.to_string())?;
    let allocations: Vec<Value> = alloc_rows.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())?;

    let mut alloc_map: HashMap<String, i64> = HashMap::new();
    for a in &allocations {
        if let (Some(node_id), Some(rank)) = (a["node_id"].as_str(), a["rank"].as_i64()) {
            alloc_map.insert(node_id.to_string(), rank);
        }
    }
    let total_allocated_ranks: i64 = alloc_map.values().sum();
    let available_points: i64 = (current_level - total_allocated_ranks).max(0);

    let mut node_stmt = conn
        .prepare("SELECT id, branch, tier, prerequisites, max_rank, perk_key, name, description FROM talent_nodes ORDER BY branch ASC, tier ASC, id ASC")
        .map_err(|e| e.to_string())?;
    let node_rows = node_stmt
        .query_map([], |r| {
            let id: String = r.get(0)?;
            let branch: String = r.get(1)?;
            let tier: i64 = r.get(2)?;
            let prereqs_raw: String = r.get(3)?;
            let max_rank: i64 = r.get(4)?;
            let perk_key: String = r.get(5)?;
            let name: String = r.get(6)?;
            let description: String = r.get(7)?;
            let prereqs = parse_prereqs(&prereqs_raw);
            let current_rank = alloc_map.get(&id).copied().unwrap_or(0);
            let unlocked = prereqs
                .as_array()
                .map(|arr| arr.iter().all(|p| prereq_satisfied(p, &alloc_map)))
                .unwrap_or(true);
            Ok(json!({
                "id": id,
                "branch": branch,
                "tier": tier,
                "prerequisites": prereqs,
                "max_rank": max_rank,
                "perk_key": perk_key,
                "name": name,
                "description": description,
                "current_rank": current_rank,
                "unlocked": unlocked,
            }))
        })
        .map_err(|e| e.to_string())?;
    let nodes: Vec<Value> = node_rows.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())?;

    Ok(json!({
        "entity_id": entity,
        "level": current_level,
        "current_level": current_level,
        "total_xp": total_xp,
        "total_allocated_ranks": total_allocated_ranks,
        "available_points": available_points,
        "allocations": allocations,
        "nodes": nodes,
    }))
}

fn query_talent_nodes() -> Result<Value, String> {
    let conn = connection()?;
    let mut stmt = conn
        .prepare("SELECT id, branch, tier, prerequisites, max_rank, perk_key, name, description FROM talent_nodes ORDER BY branch ASC, tier ASC, id ASC")
        .map_err(|e| e.to_string())?;
    let rows = stmt
        .query_map([], |r| {
            let prereqs_raw: String = r.get(3)?;
            Ok(json!({
                "id": r.get::<_, String>(0)?,
                "branch": r.get::<_, String>(1)?,
                "tier": r.get::<_, i64>(2)?,
                "prerequisites": parse_prereqs(&prereqs_raw),
                "max_rank": r.get::<_, i64>(4)?,
                "perk_key": r.get::<_, String>(5)?,
                "name": r.get::<_, String>(6)?,
                "description": r.get::<_, String>(7)?,
            }))
        })
        .map_err(|e| e.to_string())?;
    let nodes: Vec<Value> = rows.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())?;
    Ok(Value::Array(nodes))
}

fn allocate_talent(body: &Value) -> Result<Value, String> {
    let entity_id = body
        .get("entity_id")
        .and_then(Value::as_str)
        .unwrap_or("keeper")
        .trim()
        .to_string();
    if entity_id != "keeper"
        && !entity_id
            .strip_prefix("companion:")
            .map(|v| !v.trim().is_empty())
            .unwrap_or(false)
    {
        return Err("entity_id must be keeper or companion:<stable-name>".into());
    }
    let node_id = required_string(body, "node_id")?;
    let requested_rank = match body.get("rank") {
        Some(Value::Number(n)) => {
            let r = n.as_i64().ok_or("rank must be a positive integer")?;
            if r <= 0 {
                return Err("rank must be a positive integer".into());
            }
            Some(r)
        }
        Some(Value::Null) | None => None,
        _ => return Err("rank must be a positive integer".into()),
    };

    let mut conn = connection()?;
    let tx = conn
        .transaction_with_behavior(TransactionBehavior::Immediate)
        .map_err(|e| e.to_string())?;

    let reconciliation_lock: Option<String> = tx
        .query_row(
            "SELECT run_id FROM xp_reconciliation_lock WHERE singleton=1",
            [],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| e.to_string())?;
    if reconciliation_lock.is_some() {
        return Err("XP reconciliation is applying or recovering; retry after it completes".into());
    }

    let node: Option<(String, i64, String, i64, String)> = tx
        .query_row(
            "SELECT branch, tier, prerequisites, max_rank, perk_key FROM talent_nodes WHERE id=?1",
            [&node_id],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?, r.get(4)?)),
        )
        .optional()
        .map_err(|e| e.to_string())?;
    let (_branch, _tier, prereqs_raw, max_rank, _perk_key) = match node {
        Some(n) => n,
        None => return Err(format!("Talent node '{node_id}' does not exist")),
    };

    let mut alloc_map: HashMap<String, (i64, String)> = HashMap::new();
    {
        let mut alloc_stmt = tx
            .prepare("SELECT node_id, rank, allocated_at FROM talent_allocations WHERE entity_id=?1")
            .map_err(|e| e.to_string())?;
        let alloc_rows = alloc_stmt
            .query_map([&entity_id], |r| {
                Ok((r.get::<_, String>(0)?, r.get::<_, i64>(1)?, r.get::<_, String>(2)?))
            })
            .map_err(|e| e.to_string())?;

        for row in alloc_rows {
            let (nid, rank, date) = row.map_err(|e| e.to_string())?;
            alloc_map.insert(nid, (rank, date));
        }
    }

    let current_rank = alloc_map.get(&node_id).map(|(r, _)| *r).unwrap_or(0);
    let target_rank = requested_rank.unwrap_or(current_rank + 1);

    let total_allocated_ranks: i64 = alloc_map.values().map(|(r, _)| *r).sum();
    let total_xp: i64 = tx
        .query_row(
            "SELECT COALESCE(SUM(amount), 0) FROM xp_ledger WHERE entity_id=?1",
            [&entity_id],
            |r| r.get(0),
        )
        .map_err(|e| e.to_string())?;
    let current_level = level(total_xp);
    let available_points = (current_level - total_allocated_ranks).max(0);

    // Idempotency: already at target rank
    if target_rank == current_rank {
        let existing_date = alloc_map.get(&node_id).map(|(_, d)| d.clone()).unwrap_or_else(chrono_now);
        return Ok(json!({
            "status": "success",
            "entity_id": entity_id,
            "node_id": node_id,
            "allocated_rank": current_rank,
            "ranks_added": 0,
            "available_points": available_points,
            "total_allocated_ranks": total_allocated_ranks,
            "current_level": current_level,
            "allocated_at": existing_date,
        }));
    }

    if target_rank < current_rank {
        return Err(format!("Cannot decrease talent rank (current rank is {current_rank})"));
    }

    if target_rank > max_rank {
        return Err(format!(
            "Requested rank {target_rank} exceeds max rank {max_rank} for node '{node_id}'"
        ));
    }

    // Prerequisite check
    let prereqs = parse_prereqs(&prereqs_raw);
    if let Some(arr) = prereqs.as_array() {
        for p in arr {
            if let Some(req_node) = p.as_str() {
                if alloc_map.get(req_node).map(|(r, _)| *r).unwrap_or(0) < 1 {
                    return Err(format!("Prerequisite node '{req_node}' is not unlocked"));
                }
            } else if let Some(obj) = p.as_object() {
                let req_node = obj.get("node_id").and_then(Value::as_str).unwrap_or("");
                let min_rank = obj.get("min_rank").and_then(Value::as_i64).unwrap_or(1);
                if alloc_map.get(req_node).map(|(r, _)| *r).unwrap_or(0) < min_rank {
                    return Err(format!("Prerequisite node '{req_node}' is not unlocked"));
                }
            }
        }
    }

    let points_needed = target_rank - current_rank;
    if available_points < points_needed {
        return Err(format!(
            "Insufficient talent points: requires {points_needed}, but only {available_points} available"
        ));
    }

    let now = chrono_now();
    tx.execute(
        "INSERT INTO talent_allocations (entity_id, node_id, rank, allocated_at)
         VALUES (?1, ?2, ?3, ?4)
         ON CONFLICT(entity_id, node_id) DO UPDATE SET rank=excluded.rank, allocated_at=excluded.allocated_at",
        params![entity_id, node_id, target_rank, now],
    )
    .map_err(|e| e.to_string())?;
    tx.commit().map_err(|e| e.to_string())?;

    let new_total_allocated = total_allocated_ranks + points_needed;
    let new_available = available_points - points_needed;

    Ok(json!({
        "status": "success",
        "entity_id": entity_id,
        "node_id": node_id,
        "allocated_rank": target_rank,
        "ranks_added": points_needed,
        "available_points": new_available,
        "total_allocated_ranks": new_total_allocated,
        "current_level": current_level,
        "allocated_at": now,
    }))
}

pub fn request(path: &str, method: &str, body: Option<Value>) -> Result<ApiResponse, String> {
    let route = path.split('?').next().unwrap_or(path);
    let value = match (method, route) {
        ("GET", "/api/v1/progression/xp") => query_xp(path)?,
        ("GET", "/api/v1/progression/achievements") => achievements()?,
        ("GET", "/api/v1/progression/talents") => query_talents(path)?,
        ("GET", "/api/v1/progression/talents/nodes") => query_talent_nodes()?,
        ("POST", "/api/v1/progression/xp") => record_award(&body.unwrap_or(json!({})))?,
        ("POST", "/api/v1/progression/talents/allocate") => allocate_talent(&body.unwrap_or(json!({})))?,
        ("POST", "/api/v1/progression/xp/corrections") => {
            let b = body.unwrap_or(json!({}));
            if b.get("source_type").and_then(Value::as_str) != Some("correction")
                || b.get("correction_of").and_then(Value::as_str).is_none()
            {
                return Err("corrections require source_type=correction and correction_of".into());
            }
            record_award(&b)?
        }
        _ => {
            return Err(format!(
                "native progression route not implemented: {method} {path}"
            ))
        }
    };
    Ok(response(value, 200))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;
    static ENV_LOCK: Mutex<()> = Mutex::new(());

    #[test]
    fn native_manual_award_matches_the_shared_ledger_contract() {
        let _lock = ENV_LOCK.lock().unwrap();
        let fixture =
            std::env::temp_dir().join(format!("navis-progression-native-{}", std::process::id()));
        let _ = fs::remove_dir_all(&fixture);
        fs::create_dir_all(fixture.join("Bridge")).unwrap();
        fs::create_dir_all(fixture.join("Keeper")).unwrap();
        fs::write(
            fixture.join("Bridge/CompanionStats.json"),
            r#"{"companions":{"Keeper":{"xp":0,"level":1}}}"#,
        )
        .unwrap();
        std::env::set_var("NAVIS_ROOT", &fixture);
        let award = json!({"award_id":"native-test-1","entity_id":"keeper","amount":12,"source_type":"manual_adjustment","source_ref":"manual/native-test-1","source_event_at":"2026-09-28T12:00:00Z","local_date":"2026-09-28","rule_version":"xp-v1","provenance":{"actor":"Keeper"},"reason":"native fixture","details":"native fixture"});
        let first = request("/api/v1/progression/xp", "POST", Some(award.clone())).unwrap();
        let second = request("/api/v1/progression/xp", "POST", Some(award)).unwrap();
        assert_eq!(first.body["created"], true);
        assert_eq!(second.body["created"], false);
        let read = request("/api/v1/progression/xp?entity_id=keeper", "GET", None).unwrap();
        assert_eq!(read.body["total_xp"], 12);
        assert_eq!(read.body["history"][0]["award_id"], "native-test-1");
        assert_eq!(read.body["level"], 1);
        assert_eq!(read.body["next_level_xp"], 1000);
        assert_eq!(read.body["xp_into_level"], 12);
        assert_eq!(read.body["history"][0]["provenance"]["actor"], "Keeper");
        let correction = json!({"award_id":"native-correction","entity_id":"keeper","amount":-2,"source_type":"correction","source_ref":"manual/native-test-1/correction","source_event_at":"2026-09-29T12:00:00Z","local_date":"2026-09-29","rule_version":"xp-v1","provenance":{"actor":"Keeper"},"reason":"correct native fixture","details":"correct native fixture","correction_of":"native-test-1"});
        request("/api/v1/progression/xp/corrections", "POST", Some(correction.clone())).unwrap();
        let retry = request("/api/v1/progression/xp/corrections", "POST", Some(correction)).unwrap();
        assert_eq!(retry.body["created"], false);
        // Requests open fresh SQLite connections, including the restarted read.
        let restarted = request("/api/v1/progression/xp", "GET", None).unwrap();
        assert_eq!(restarted.body["total_xp"], 10);
        assert_eq!(restarted.body["history"][0]["correction_of"], "native-test-1");
        assert_eq!(restarted.body["history"].as_array().unwrap().len(), 2);
        std::env::remove_var("NAVIS_ROOT");
        let _ = fs::remove_dir_all(&fixture);
    }

    #[test]
    fn native_talent_allocation_and_prerequisites_enforced() {
        let _lock = ENV_LOCK.lock().unwrap();
        let fixture =
            std::env::temp_dir().join(format!("navis-talents-native-{}", std::process::id()));
        let _ = fs::remove_dir_all(&fixture);
        fs::create_dir_all(fixture.join("Bridge")).unwrap();
        fs::create_dir_all(fixture.join("Keeper")).unwrap();
        fs::write(
            fixture.join("Bridge/CompanionStats.json"),
            r#"{"companions":{"Keeper":{"xp":0,"level":1}}}"#,
        )
        .unwrap();
        std::env::set_var("NAVIS_ROOT", &fixture);

        // 1. Initial talent state: level 1 with 0 spent ranks has 1 available point
        let state = request("/api/v1/progression/talents", "GET", None).unwrap();
        assert_eq!(state.body["entity_id"], "keeper");
        assert_eq!(state.body["level"], 1);
        assert_eq!(state.body["available_points"], 1);
        assert_eq!(state.body["total_allocated_ranks"], 0);

        // 2. Prerequisite check: focus_clarity requires focus_deep_work
        let prereq_fail = request(
            "/api/v1/progression/talents/allocate",
            "POST",
            Some(json!({"node_id": "focus_clarity", "rank": 1})),
        );
        assert!(prereq_fail.is_err());
        assert!(prereq_fail.unwrap_err().contains("Prerequisite node 'focus_deep_work' is not unlocked"));

        // 3. Allocate focus_deep_work rank 1
        let alloc1 = request(
            "/api/v1/progression/talents/allocate",
            "POST",
            Some(json!({"node_id": "focus_deep_work", "rank": 1})),
        )
        .unwrap();
        assert_eq!(alloc1.body["status"], "success");
        assert_eq!(alloc1.body["allocated_rank"], 1);
        assert_eq!(alloc1.body["ranks_added"], 1);
        assert_eq!(alloc1.body["available_points"], 0);
        assert_eq!(alloc1.body["total_allocated_ranks"], 1);

        // 4. Idempotent retry: allocating same rank returns success with ranks_added = 0
        let retry = request(
            "/api/v1/progression/talents/allocate",
            "POST",
            Some(json!({"node_id": "focus_deep_work", "rank": 1})),
        )
        .unwrap();
        assert_eq!(retry.body["status"], "success");
        assert_eq!(retry.body["allocated_rank"], 1);
        assert_eq!(retry.body["ranks_added"], 0);
        assert_eq!(retry.body["available_points"], 0);

        // 5. Insufficient points: Keeper is level 1, points available is 0
        let point_fail = request(
            "/api/v1/progression/talents/allocate",
            "POST",
            Some(json!({"node_id": "focus_clarity", "rank": 1})),
        );
        assert!(point_fail.is_err());
        assert!(point_fail.unwrap_err().contains("Insufficient talent points"));

        // 6. Award XP to reach level 2 (needs >= 1000 XP)
        let award = json!({
            "award_id": "xp-lvl-2",
            "entity_id": "keeper",
            "amount": 1050,
            "source_type": "manual_adjustment",
            "source_ref": "manual/xp-lvl-2",
            "source_event_at": "2026-10-01T12:00:00Z",
            "local_date": "2026-10-01",
            "rule_version": "xp-v1",
            "provenance": {"actor": "Keeper"},
            "reason": "Level up for talent allocation test",
            "details": "Level up"
        });
        request("/api/v1/progression/xp", "POST", Some(award)).unwrap();

        // Check new state: level 2, available points = 2 - 1 = 1
        let state2 = request("/api/v1/progression/talents", "GET", None).unwrap();
        assert_eq!(state2.body["level"], 2);
        assert_eq!(state2.body["available_points"], 1);

        // 7. Now allocating focus_clarity succeeds because prerequisite is met and point is available
        let alloc2 = request(
            "/api/v1/progression/talents/allocate",
            "POST",
            Some(json!({"node_id": "focus_clarity", "rank": 1})),
        )
        .unwrap();
        assert_eq!(alloc2.body["status"], "success");
        assert_eq!(alloc2.body["allocated_rank"], 1);
        assert_eq!(alloc2.body["ranks_added"], 1);
        assert_eq!(alloc2.body["available_points"], 0);
        assert_eq!(alloc2.body["total_allocated_ranks"], 2);

        // 8. Max rank check: focus_clarity max_rank is 2; requesting rank 3 should fail
        let max_fail = request(
            "/api/v1/progression/talents/allocate",
            "POST",
            Some(json!({"node_id": "focus_clarity", "rank": 3})),
        );
        assert!(max_fail.is_err());
        assert!(max_fail.unwrap_err().contains("exceeds max rank"));

        std::env::remove_var("NAVIS_ROOT");
        let _ = fs::remove_dir_all(&fixture);
    }
}
