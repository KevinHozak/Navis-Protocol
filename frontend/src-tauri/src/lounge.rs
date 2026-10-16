use base64::{engine::general_purpose::STANDARD, Engine as _};
use rusqlite::{params, types::ValueRef, Connection};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc, Mutex,
};
use tauri::{AppHandle, Emitter, State};

#[derive(Debug, serde::Serialize)]
pub struct ApiResponse {
    pub status: u16,
    pub body: Value,
    pub text: String,
}

#[derive(Default)]
pub struct LoungeOperationState {
    jobs: Mutex<HashMap<String, Arc<AtomicBool>>>,
}

fn operation_event(app: &AppHandle, job_id: &str, status: &str, phase: &str, message: &str) {
    let _ = app.emit(
        crate::operations::OPERATION_EVENT,
        json!({
            "job_id": job_id, "status": status, "phase": phase, "message": message
        }),
    );
}

#[tauri::command]
pub fn start_lounge_operation(
    app: AppHandle,
    state: State<'_, LoungeOperationState>,
    operation: String,
) -> Result<Value, String> {
    if !matches!(
        operation.as_str(),
        "rebuild_lounge_catalog" | "rebuild_library_index"
    ) {
        return Err("unsupported lounge operation".to_string());
    }
    let job_id = format!(
        "lounge-{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_err(|error| error.to_string())?
            .as_nanos()
    );
    let cancelled = Arc::new(AtomicBool::new(false));
    state
        .jobs
        .lock()
        .map_err(|_| "operation state unavailable")?
        .insert(job_id.clone(), cancelled.clone());
    let app_for_worker = app.clone();
    let operation_for_worker = operation.clone();
    let job_for_worker = job_id.clone();
    std::thread::spawn(move || {
        operation_event(
            &app_for_worker,
            &job_for_worker,
            "running",
            "scan",
            "Catalog maintenance started",
        );
        let result = (|| -> Result<(), String> {
            if cancelled.load(Ordering::Relaxed) {
                return Err("cancelled".to_string());
            }
            let connection = if operation_for_worker == "rebuild_lounge_catalog" {
                lounge_connection()?
            } else {
                library_connection()?
            };
            if let Some(connection) = connection {
                let table = if operation_for_worker == "rebuild_lounge_catalog" {
                    "MediaItems"
                } else {
                    "library_vectors"
                };
                let mut statement = connection
                    .prepare(&format!("SELECT rowid FROM {table}"))
                    .map_err(|error| error.to_string())?;
                let mut rows = statement.query([]).map_err(|error| error.to_string())?;
                let mut scanned = 0u64;
                while rows.next().map_err(|error| error.to_string())?.is_some() {
                    scanned += 1;
                    if cancelled.load(Ordering::Relaxed) {
                        return Err("cancelled".to_string());
                    }
                    if scanned % 100 == 0 {
                        operation_event(
                            &app_for_worker,
                            &job_for_worker,
                            "running",
                            "scan",
                            &format!("Scanned {scanned} catalog rows"),
                        );
                    }
                }
                connection
                    .execute_batch("PRAGMA optimize;")
                    .map_err(|error| error.to_string())?;
            }
            Ok(())
        })();
        match result {
            Ok(()) => operation_event(
                &app_for_worker,
                &job_for_worker,
                "completed",
                "finalize",
                "Catalog maintenance complete",
            ),
            Err(error) if error == "cancelled" => operation_event(
                &app_for_worker,
                &job_for_worker,
                "cancelled",
                "cancel",
                "Catalog maintenance cancelled",
            ),
            Err(error) => operation_event(
                &app_for_worker,
                &job_for_worker,
                "failed",
                "finalize",
                &error,
            ),
        }
    });
    Ok(json!({"status":"accepted", "job_id":job_id, "operation":operation}))
}

#[tauri::command]
pub fn cancel_lounge_operation(
    state: State<'_, LoungeOperationState>,
    job_id: String,
) -> Result<Value, String> {
    let jobs = state
        .jobs
        .lock()
        .map_err(|_| "operation state unavailable")?;
    let token = jobs.get(&job_id).ok_or("operation not found")?;
    token.store(true, Ordering::Relaxed);
    Ok(json!({"status":"cancellation_requested", "job_id":job_id}))
}
fn root() -> PathBuf {
    std::env::var("NAVIS_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(r"G:\My Drive\Navis-Vault"))
}

fn lounge_connection() -> Result<Option<Connection>, String> {
    let path = root().join("Lounge").join("lounge.db");
    if !path.exists() {
        return Ok(None);
    }
    Connection::open(path)
        .map(Some)
        .map_err(|error| error.to_string())
}

fn library_connection() -> Result<Option<Connection>, String> {
    let vault_root = crate::operations::configured_vault_root()
        .map_err(|_| "library_vault_unavailable".to_string())?;
    let path = vault_root.join("Library").join("Library_Intelligence.db");
    if !path.is_file() {
        return Err("library_database_missing".to_string());
    }
    Connection::open_with_flags(
        path,
        rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY | rusqlite::OpenFlags::SQLITE_OPEN_URI,
    )
    .map(Some)
    .map_err(|_| "library_database_unreadable".to_string())
}

fn response(body: Value) -> ApiResponse {
    ApiResponse {
        status: 200,
        text: body.to_string(),
        body,
    }
}

fn library_response(result: Result<Value, String>) -> ApiResponse {
    match result {
        Ok(body) => response(body),
        Err(code) => {
            let code = match code.as_str() {
                "library_vault_unavailable"
                | "library_database_missing"
                | "library_database_unreadable" => code,
                _ => "library_schema_invalid".to_string(),
            };
            let status = if code == "library_database_missing"
                || code == "library_database_unreadable"
                || code == "library_vault_unavailable"
            {
                503
            } else {
                500
            };
            let body = json!({"detail":{"code":code}});
            ApiResponse {
                status,
                text: body.to_string(),
                body,
            }
        }
    }
}

fn media_type(value: &str) -> String {
    match value.to_ascii_lowercase().as_str() {
        "movies" => "Movie".to_string(),
        "tv" => "TV Show".to_string(),
        "youtube" => "YouTube".to_string(),
        "books" => "Book".to_string(),
        "audio" => "Audio".to_string(),
        "games" => "Game".to_string(),
        other => other.to_string(),
    }
}

fn local_poster(id: &str) -> Option<String> {
    let safe: String = id
        .chars()
        .filter(|character| !r#"\\/*?:"<>|"#.contains(*character))
        .collect();
    let path = root()
        .join("Lounge")
        .join("posters")
        .join(format!("{safe}.jpg"));
    let bytes = std::fs::read(path).ok()?;
    Some(format!("data:image/jpeg;base64,{}", STANDARD.encode(bytes)))
}

fn media(path: &str) -> Result<Value, String> {
    let Some(connection) = lounge_connection()? else {
        return Ok(json!({"total_items": 0, "items": []}));
    };
    let type_filter = query(path, "type");
    let sql = "SELECT m.id, m.type, m.title, m.creator, m.series, m.overview, m.release_year,
        m.duration_mins, m.rating, m.poster_url, m.status, m.source, m.date_added,
        m.date_completed, GROUP_CONCAT(g.name, '|')
        FROM MediaItems m LEFT JOIN MediaGenres mg ON m.id = mg.media_id
        LEFT JOIN Genres g ON mg.genre_id = g.id";
    let mut sql = sql.to_string();
    if type_filter.is_some() {
        sql.push_str(" WHERE m.type = ?1");
    }
    sql.push_str(" GROUP BY m.id ORDER BY m.date_added DESC, m.date_completed DESC");
    let mut statement = connection
        .prepare(&sql)
        .map_err(|error| error.to_string())?;
    let mut rows = if let Some(filter) = type_filter {
        statement
            .query(params![media_type(&filter)])
            .map_err(|error| error.to_string())?
    } else {
        statement.query([]).map_err(|error| error.to_string())?
    };
    let mut items = Vec::new();
    while let Some(row) = rows.next().map_err(|error| error.to_string())? {
        let id: String = row.get(0).map_err(|error| error.to_string())?;
        let mut item = json!({
            "id": id, "type": row.get::<_, Option<String>>(1).ok().flatten(),
            "title": row.get::<_, Option<String>>(2).ok().flatten(),
            "creator": row.get::<_, Option<String>>(3).ok().flatten(),
            "series": row.get::<_, Option<String>>(4).ok().flatten(),
            "overview": row.get::<_, Option<String>>(5).ok().flatten(),
            "release_year": row.get::<_, Option<i64>>(6).ok().flatten(),
            "duration_mins": row.get::<_, Option<i64>>(7).ok().flatten(),
            "rating": row.get::<_, Option<f64>>(8).ok().flatten(),
            "poster_url": row.get::<_, Option<String>>(9).ok().flatten(),
            "status": row.get::<_, Option<String>>(10).ok().flatten(),
            "source": row.get::<_, Option<String>>(11).ok().flatten(),
            "date_added": row.get::<_, Option<String>>(12).ok().flatten(),
            "date_completed": row.get::<_, Option<String>>(13).ok().flatten(),
            "genres": row.get::<_, Option<String>>(14).ok().flatten().map(|value| value.split('|').map(str::to_string).collect::<Vec<_>>()).unwrap_or_default()
        });
        if item
            .get("poster_url")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .is_empty()
        {
            if let Some(poster) = local_poster(&id) {
                item["poster_url"] = Value::String(poster);
            }
        }
        items.push(item);
    }
    Ok(json!({"total_items": items.len(), "items": items}))
}

fn library_timestamp(row: &rusqlite::Row<'_>, column: usize) -> rusqlite::Result<Value> {
    let value = match row.get_ref(column)? {
        ValueRef::Null => Value::Null,
        ValueRef::Integer(value) => json!(value),
        ValueRef::Real(value) if value.is_finite() => json!(value),
        ValueRef::Text(value) => json!(String::from_utf8_lossy(value).into_owned()),
        ValueRef::Real(_) | ValueRef::Blob(_) => Value::Null,
    };
    Ok(value)
}

fn library_dashboard() -> Result<Value, String> {
    let connection = library_connection()?.ok_or_else(|| "library_database_missing".to_string())?;
    let total: i64 = connection
        .query_row(
            "SELECT COUNT(DISTINCT file_path) FROM library_vectors",
            [],
            |row| row.get(0),
        )
        .map_err(|_| "library_schema_invalid".to_string())?;
    let mut categories_statement = connection.prepare("SELECT category, COUNT(DISTINCT file_path) FROM library_vectors WHERE category IS NOT NULL AND category != '' GROUP BY category ORDER BY COUNT(DISTINCT file_path) DESC LIMIT 12").map_err(|error| error.to_string())?;
    let categories = categories_statement
        .query_map([], |row| {
            Ok(json!({"name": row.get::<_, String>(0)?, "count": row.get::<_, i64>(1)?}))
        })
        .map_err(|error| error.to_string())?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|error| error.to_string())?;
    let mut recent_statement = connection.prepare("SELECT category, file_path, MAX(last_modified) FROM library_vectors GROUP BY file_path ORDER BY MAX(last_modified) DESC LIMIT 15").map_err(|error| error.to_string())?;
    let recent_documents = recent_statement.query_map([], |row| {
        let file_path: String = row.get(1)?;
        let name = std::path::Path::new(&file_path).file_stem().and_then(|value| value.to_str()).unwrap_or(&file_path).to_string();
        Ok(json!({"id": file_path, "name": name, "category": row.get::<_, Option<String>>(0)?.unwrap_or_else(|| "Uncategorized".to_string()), "path": file_path, "last_modified": library_timestamp(row, 2)?}))
    }).map_err(|error| error.to_string())?.collect::<Result<Vec<_>, _>>().map_err(|error| error.to_string())?;
    Ok(
        json!({"total_documents": total, "categories": categories, "recent_documents": recent_documents}),
    )
}

fn library_search(path: &str) -> Result<Value, String> {
    let connection = library_connection()?.ok_or_else(|| "library_database_missing".to_string())?;
    let query_value = query(path, "q").unwrap_or_default();
    let category = query(path, "category").unwrap_or_default();
    let pattern = format!("%{}%", query_value);
    let category_pattern = format!("%{}%", category);
    let mut statement = connection.prepare("SELECT category, file_path, MAX(last_modified) FROM library_vectors WHERE (?1 = '' OR chunk_text LIKE ?2 OR file_path LIKE ?2) AND (?3 = '' OR category LIKE ?4) GROUP BY file_path ORDER BY MAX(last_modified) DESC LIMIT 50").map_err(|error| error.to_string())?;
    let rows = statement.query_map(params![query_value, pattern, category, category_pattern], |row| {
        let file_path: String = row.get(1)?;
        let name = std::path::Path::new(&file_path).file_stem().and_then(|value| value.to_str()).unwrap_or(&file_path).to_string();
        Ok(json!({"id": file_path, "name": name, "category": row.get::<_, Option<String>>(0)?.unwrap_or_else(|| "Uncategorized".to_string()), "path": file_path, "last_modified": library_timestamp(row, 2)?}))
    }).map_err(|error| error.to_string())?;
    Ok(json!({"results": rows.collect::<Result<Vec<_>, _>>().map_err(|error| error.to_string())?}))
}

fn decode_query(value: &str) -> String {
    let mut output = String::new();
    let bytes = value.as_bytes();
    let mut index = 0;
    while index < bytes.len() {
        if bytes[index] == b'%' && index + 2 < bytes.len() {
            if let Ok(decoded) = u8::from_str_radix(&value[index + 1..index + 3], 16) {
                output.push(decoded as char);
                index += 3;
                continue;
            }
        }
        output.push(if bytes[index] == b'+' {
            ' '
        } else {
            bytes[index] as char
        });
        index += 1;
    }
    output
}
fn query(path: &str, key: &str) -> Option<String> {
    path.split('?').nth(1)?.split('&').find_map(|part| {
        let (name, value) = part.split_once('=')?;
        (name == key).then(|| decode_query(value))
    })
}

pub fn request(path: &str, method: &str, _body: Option<Value>) -> Result<ApiResponse, String> {
    if method != "GET" {
        return Err(format!("native lounge route is read-only: {method} {path}"));
    }
    let route = path.split('?').next().unwrap_or(path);
    let body = match route {
        "/api/v1/lounge/media" => media(path)?,
        "/api/v1/library/dashboard" => return Ok(library_response(library_dashboard())),
        "/api/v1/library/search" => return Ok(library_response(library_search(path))),
        _ => {
            return Err(format!(
                "native lounge route not implemented: {method} {path}"
            ))
        }
    };
    Ok(response(body))
}

#[cfg(test)]
mod tests {
    static LIBRARY_ROOT_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());
    #[test]
    fn unsupported_methods_and_routes_fail_before_opening_storage() {
        for method in ["POST", "PUT", "DELETE", "PATCH"] {
            let error = super::request("/api/v1/lounge/media", method, None).unwrap_err();
            assert!(error.contains("read-only"));
        }
        let error = super::request("/api/v1/lounge/unknown", "GET", None).unwrap_err();
        assert!(error.contains("not implemented"));
    }

    #[test]
    fn media_type_mapping_matches_web_contract() {
        assert_eq!(super::media_type("youtube"), "YouTube");
        assert_eq!(super::media_type("books"), "Book");
    }
    #[test]
    fn native_catalog_queries_work_without_backend() {
        let _guard = LIBRARY_ROOT_LOCK
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let original = std::env::var_os("NAVIS_ROOT");
        let root =
            std::env::temp_dir().join(format!("navis-lounge-offline-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join("Lounge/posters")).expect("lounge dirs");
        std::fs::create_dir_all(root.join("Library")).expect("library dir");
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge dir");
        std::fs::create_dir_all(root.join("Journal")).expect("journal dir");
        let lounge = rusqlite::Connection::open(root.join("Lounge/lounge.db")).expect("lounge db");
        lounge.execute_batch("CREATE TABLE MediaItems (id TEXT PRIMARY KEY, type TEXT, title TEXT, creator TEXT, series TEXT, overview TEXT, release_year INTEGER, duration_mins INTEGER, rating REAL, poster_url TEXT, status TEXT, source TEXT, date_added TEXT, date_completed TEXT); CREATE TABLE Genres (id INTEGER PRIMARY KEY, name TEXT); CREATE TABLE MediaGenres (media_id TEXT, genre_id INTEGER); INSERT INTO MediaItems VALUES ('book-1','Book','Native Book','Keeper','','',2026,10,5.0,'','completed','test','2026-09-20',NULL);").expect("lounge schema");
        std::fs::write(
            root.join("Lounge/posters/book-1.jpg"),
            [0xFF, 0xD8, 0xFF, 0xD9],
        )
        .expect("poster");
        let library = rusqlite::Connection::open(root.join("Library/Library_Intelligence.db"))
            .expect("library db");
        library.execute_batch("CREATE TABLE library_vectors (category TEXT, file_path TEXT, last_modified TEXT, chunk_index INTEGER, chunk_text TEXT); INSERT INTO library_vectors VALUES ('Notes','Library/Notes/Example.md','2026-09-20',0,'native search fixture');").expect("library schema");
        std::env::set_var("NAVIS_ROOT", &root);

        let media =
            super::request("/api/v1/lounge/media?type=books", "GET", None).expect("media route");
        let search =
            super::request("/api/v1/library/search?q=native", "GET", None).expect("search route");
        assert_eq!(media.body["total_items"], 1);
        assert!(media.body["items"][0]["poster_url"]
            .as_str()
            .unwrap_or_default()
            .starts_with("data:image/jpeg;base64,"));
        assert_eq!(search.body["results"][0]["name"], "Example");
        let _ = std::fs::remove_dir_all(root);
        match original {
            Some(value) => std::env::set_var("NAVIS_ROOT", value),
            None => std::env::remove_var("NAVIS_ROOT"),
        }
    }

    #[test]
    fn library_reports_failures_and_recovers_without_backend() {
        let _guard = LIBRARY_ROOT_LOCK
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let root =
            std::env::temp_dir().join(format!("navis-library-fixture-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join("Library")).expect("library dir");
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge dir");
        std::fs::create_dir_all(root.join("Journal")).expect("journal dir");
        let original = std::env::var_os("NAVIS_ROOT");
        std::env::set_var("NAVIS_ROOT", &root);

        let missing = super::request("/api/v1/library/dashboard", "GET", None).unwrap();
        assert_eq!(missing.status, 503);
        assert_eq!(missing.body["detail"]["code"], "library_database_missing");
        assert!(!missing.text.contains(root.to_string_lossy().as_ref()));

        let path = root.join("Library/Library_Intelligence.db");
        std::fs::write(&path, "not sqlite").expect("malformed fixture");
        let malformed = super::request("/api/v1/library/dashboard", "GET", None).unwrap();
        assert_eq!(malformed.status, 500);
        assert_eq!(malformed.body["detail"]["code"], "library_schema_invalid");

        std::fs::remove_file(&path).expect("remove malformed fixture");
        let db = rusqlite::Connection::open(&path).expect("sqlite fixture");
        db.execute_batch("CREATE TABLE library_vectors (category TEXT, file_path TEXT, last_modified REAL, chunk_text TEXT);").expect("empty schema");
        drop(db);
        let empty = super::request("/api/v1/library/dashboard", "GET", None).unwrap();
        assert_eq!(empty.status, 200);
        assert_eq!(empty.body["total_documents"], 0);
        assert_eq!(empty.body["categories"].as_array().unwrap().len(), 0);

        let db = rusqlite::Connection::open(&path).expect("sqlite fixture");
        db.execute("INSERT INTO library_vectors VALUES ('Notes','Library/Notes/fixture.md',1791454200.5,'safe synthetic phrase')", []).expect("fixture data");
        drop(db);
        let dashboard = super::request("/api/v1/library/dashboard", "GET", None).unwrap();
        assert_eq!(dashboard.status, 200);
        assert_eq!(dashboard.body["total_documents"], 1);
        assert_eq!(dashboard.body["categories"][0]["name"], "Notes");
        assert_eq!(
            dashboard.body["recent_documents"][0]["last_modified"].as_f64(),
            Some(1791454200.5)
        );
        let search = super::request("/api/v1/library/search?q=safe", "GET", None).unwrap();
        assert_eq!(search.status, 200);
        assert_eq!(search.body["results"][0]["id"], "Library/Notes/fixture.md");
        assert_eq!(
            search.body["results"][0]["last_modified"].as_f64(),
            Some(1791454200.5)
        );
        let category =
            super::request("/api/v1/library/search?category=Notes", "GET", None).unwrap();
        assert_eq!(category.body["results"].as_array().unwrap().len(), 1);

        std::fs::remove_dir_all(&root).ok();
        match original {
            Some(value) => std::env::set_var("NAVIS_ROOT", value),
            None => std::env::remove_var("NAVIS_ROOT"),
        }
    }
}
