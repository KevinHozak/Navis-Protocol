mod recurrence;
mod command;
mod diagnostics;
mod lounge;
mod ollama;
mod operations;
mod p3;
mod p5;
mod progression;
mod vault;

use crate::diagnostics::startup_diagnostics;
use crate::lounge::{cancel_lounge_operation, start_lounge_operation};
use crate::operations::{
    cancel_sync_operation, emit_operation_event, start_sync_operation, SyncOperationState,
};
use crate::p5::{cancel_p5_operation, start_p5_operation};
use serde::Serialize;
use serde_json::Value;
use tauri::http::Response;

#[derive(Debug, Serialize)]
struct Healthcheck {
    runtime: &'static str,
    version: &'static str,
}

#[tauri::command]
fn healthcheck() -> Healthcheck {
    Healthcheck {
        runtime: "tauri-v2",
        version: env!("CARGO_PKG_VERSION"),
    }
}

fn allowed_vault_asset_origin(origin: &str) -> bool {
    #[cfg(windows)]
    {
        matches!(
            origin,
            "http://tauri.localhost" | "https://tauri.localhost" | "http://127.0.0.1:3000"
        )
    }
    #[cfg(not(windows))]
    {
        matches!(origin, "tauri://localhost" | "http://127.0.0.1:3000")
    }
}

#[tauri::command]
async fn lounge_request(
    path: String,
    method: Option<String>,
    body: Option<Value>,
) -> Result<lounge::ApiResponse, String> {
    tauri::async_runtime::spawn_blocking(move || {
        lounge::request(&path, method.as_deref().unwrap_or("GET"), body)
    })
    .await
    .map_err(|error| error.to_string())?
}

#[tauri::command]
async fn p5_request(
    app: tauri::AppHandle,
    path: String,
    method: Option<String>,
    body: Option<Value>,
) -> Result<p5::ApiResponse, String> {
    tauri::async_runtime::spawn_blocking(move || {
        if path.starts_with("/api/forge/") {
            return p5::forge_request(&app, &path, method.as_deref().unwrap_or("GET"), body);
        }
        if path == "/api/reid/chat"
            || path == "/api/neural/chat"
            || path == "/api/neural/warroom/chat"
        {
            if let Ok(backend) = crate::operations::backend_root(&app) {
                return p5::conversation_request(
                    &backend,
                    &path,
                    method.as_deref().unwrap_or("POST"),
                    body,
                );
            }
            return Ok(p5::unavailable("Conversation backend resources are missing. Reinstall the current Navis desktop build."));
        }
        p5::request(&path, method.as_deref().unwrap_or("GET"), body)
    })
    .await
    .map_err(|error| error.to_string())?
}

#[tauri::command]
fn progression_request(
    path: String,
    method: Option<String>,
    body: Option<Value>,
) -> Result<progression::ApiResponse, String> {
    progression::request(&path, method.as_deref().unwrap_or("GET"), body)
}

#[tauri::command]
async fn p3_request(
    app: tauri::AppHandle,
    path: String,
    method: Option<String>,
    body: Option<Value>,
) -> Result<p3::ApiResponse, String> {
    if (method.as_deref().unwrap_or("GET") == "GET" && matches!(path.as_str(), "/api/battle/state" | "/api/battle/bestiary"))
        || (method.as_deref() == Some("POST")
        && matches!(
            path.as_str(),
            "/api/battle/link" | "/api/battle/resolve" | "/api/battle/rest"
        ))
    {
        let backend = operations::backend_root(&app)?;
        return tauri::async_runtime::spawn_blocking(move || {
            p3::combat_request(&backend, &path, body)
        })
        .await
        .map_err(|e| e.to_string())?;
    }
    p3::request(&path, method.as_deref().unwrap_or("GET"), body)
}

#[tauri::command]
async fn vault_request(
    app: tauri::AppHandle,
    path: String,
    method: Option<String>,
    body: Option<Value>,
) -> Result<vault::ApiResponse, String> {
    if method.as_deref() == Some("POST") && path == "/api/tasks/toggle" {
        let backend = operations::backend_root(&app)?;
        let app_handle = app.clone();
        let task_path = body.as_ref()
            .and_then(|value| value.get("file_path"))
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string();
        return tauri::async_runtime::spawn_blocking(move || {
            let result = p3::task_toggle_request(&backend, body)?;
            if result.status >= 200 && result.status < 300 {
                let _ = vault::emit_vault_change(&app_handle, &vault::VaultChangeEvent {
                    r#type: "journal".to_string(),
                    path: task_path,
                    timestamp: vault::current_epoch_timestamp(),
                    action: "modified".to_string(),
                    full_path: None,
                });
            }
            Ok(vault::ApiResponse {status: result.status, body: result.body, text: result.text})
        }).await.map_err(|e| e.to_string())?;
    }
    if method.as_deref() == Some("POST")
        && ((path.starts_with("/api/active_tasks/") && path.ends_with("/complete"))
            || (path.starts_with("/api/recurring/") && path.ends_with("/complete")))
    {
        let backend = operations::backend_root(&app)?;
        let is_rec = path.starts_with("/api/recurring/");
        let endpoint = if is_rec { "/api/recurring/complete" } else { "/api/active_tasks/complete" };
        let prefix = if is_rec { "/api/recurring/" } else { "/api/active_tasks/" };
        let id = path.trim_start_matches(prefix).trim_end_matches("/complete");
        let id = percent_encoding::percent_decode_str(id).decode_utf8().map_err(|e| e.to_string())?.into_owned();
        let app_handle = app.clone();
        return tauri::async_runtime::spawn_blocking(move || {
            let result = p3::directive_request(&backend, endpoint, Some(serde_json::json!({"task_id": id})))?;
            if result.status >= 200 && result.status < 300 {
                let _ = vault::emit_vault_change(&app_handle, &vault::VaultChangeEvent {
                    r#type: "bridge".to_string(),
                    path: "Bridge/ops_state.json".to_string(),
                    timestamp: vault::current_epoch_timestamp(),
                    action: "modified".to_string(),
                    full_path: None,
                });
            }
            Ok(vault::ApiResponse {status: result.status, body: result.body, text: result.text})
        }).await.map_err(|e| e.to_string())?;
    }
    if path.starts_with("/api/holocron/") {
        let backend = operations::backend_root(&app)?;
        let method = method.unwrap_or_else(|| "GET".to_string());
        return tauri::async_runtime::spawn_blocking(move || {
            vault::holocron_request(&backend, &path, &method, body)
        }).await.map_err(|e| e.to_string())?;
    }
    let is_mutation = method.as_deref().map(|m| m == "POST" || m == "PUT" || m == "DELETE").unwrap_or(false);
    let app_handle = app.clone();
    let target_path = path.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let response = vault::request(&path, method.as_deref().unwrap_or("GET"), body)?;
        if is_mutation && response.status >= 200 && response.status < 300 {
            let event_type = vault::determine_event_type(&target_path);
            let _ = vault::emit_vault_change(&app_handle, &vault::VaultChangeEvent {
                r#type: event_type,
                path: target_path,
                timestamp: vault::current_epoch_timestamp(),
                action: "modified".to_string(),
                full_path: None,
            });
        }
        Ok(response)
    })
    .await
    .map_err(|error| error.to_string())?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .register_uri_scheme_protocol("vault", |_app, request| {
            let origin = request
                .headers()
                .get("Origin")
                .and_then(|value| value.to_str().ok())
                .filter(|origin| allowed_vault_asset_origin(origin));

            if request.method().as_str() == "OPTIONS" {
                let mut response = Response::builder()
                    .status(204)
                    .header("Access-Control-Allow-Methods", "GET, OPTIONS")
                    .header(
                        "Access-Control-Allow-Headers",
                        "Accept, Content-Type, X-Requested-With",
                    )
                    .header("Access-Control-Max-Age", "600");
                if let Some(origin) = origin {
                    response = response
                        .header("Access-Control-Allow-Origin", origin)
                        .header("Vary", "Origin");
                }
                return response.body(Vec::new()).unwrap();
            }

            let relative = request.uri().path().trim_start_matches('/');
            let mut response = match vault::asset_response(relative) {
                Ok((bytes, content_type)) => Response::builder()
                    .status(200)
                    .header("Content-Type", content_type)
                    .header("Cache-Control", "no-cache")
                    .body(bytes),
                Err(_) => Response::builder()
                    .status(404)
                    .header("Content-Type", "text/plain; charset=utf-8")
                    .body(Vec::new()),
            }
            .unwrap();
            if let Some(origin) = origin {
                response
                    .headers_mut()
                    .insert("Access-Control-Allow-Origin", origin.parse().unwrap());
                response
                    .headers_mut()
                    .insert("Vary", "Origin".parse().unwrap());
            }
            response
        })
        .manage(lounge::LoungeOperationState::default())
        .manage(p5::P5OperationState::default())
        .manage(SyncOperationState::default())
        .manage(vault::VaultWatcherState::default())
        .setup(|app| {
            use tauri::Manager;
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Some(state) = handle.try_state::<vault::VaultWatcherState>() {
                    let _ = vault::start_vault_watcher(handle.clone(), state);
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            healthcheck,
            ollama::polish_journal_entry,
            startup_diagnostics,
            lounge_request,
            start_lounge_operation,
            cancel_lounge_operation,
            p5_request,
            start_p5_operation,
            cancel_p5_operation,
            progression_request,
            vault_request,
            p3_request,
            emit_operation_event,
            start_sync_operation,
            cancel_sync_operation,
            vault::emit_vault_change_event,
            vault::start_vault_watcher,
            vault::stop_vault_watcher,
            vault::vault_watcher_status
        ])
        .build(tauri::generate_context!())
        .expect("failed to build Navis Protocol application")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                operations::cancel_all_sync_operations(app);
                vault::stop_all_vault_watchers(app);
            }
        })
}
