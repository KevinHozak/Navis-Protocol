use serde::Serialize;
use std::fs::{self, OpenOptions};
use std::path::{Path, PathBuf};

#[derive(Debug, Serialize)]
pub struct DiagnosticCheck {
    pub id: String,
    pub label: String,
    pub severity: String,
    pub ok: bool,
    pub message: String,
}

#[derive(Debug, Serialize)]
pub struct DiagnosticsReport {
    pub runtime: String,
    pub version: String,
    pub navis_root: String,
    pub overall_ok: bool,
    pub checks: Vec<DiagnosticCheck>,
}

fn check(
    id: &str,
    label: &str,
    severity: &str,
    ok: bool,
    message: impl Into<String>,
) -> DiagnosticCheck {
    DiagnosticCheck {
        id: id.into(),
        label: label.into(),
        severity: severity.into(),
        ok,
        message: message.into(),
    }
}

fn configured_root() -> PathBuf {
    crate::operations::configured_vault_root()
        .unwrap_or_else(|_| PathBuf::from(r"G:\\My Drive\\Navis-Vault"))
}

fn required_file(root: &Path, relative: &str, checks: &mut Vec<DiagnosticCheck>) {
    let path = root.join(relative);
    let (ok, message) = match fs::metadata(&path) {
        Ok(metadata) if metadata.is_file() => (true, "Available".to_string()),
        Ok(_) => (false, "Path exists but is not a file".to_string()),
        Err(error) => (false, format!("Unavailable: {error}")),
    };
    checks.push(check(
        &format!("required:{relative}"),
        &format!("Required Vault file: {relative}"),
        "error",
        ok,
        message,
    ));
}

#[tauri::command]
pub fn startup_diagnostics() -> DiagnosticsReport {
    let root = configured_root();
    let mut checks = vec![check(
        "webview",
        "Embedded WebView runtime",
        "error",
        true,
        "Tauri has started; the embedded Windows WebView is available",
    )];
    let root_exists = root.is_dir();
    checks.push(check(
        "vault-root",
        "Configured NAVIS_ROOT",
        "error",
        root_exists,
        if root_exists {
            "Directory is available"
        } else {
            "Directory is missing or unavailable"
        },
    ));

    if root_exists {
        required_file(&root, "Bridge/status.json", &mut checks);
        required_file(&root, "Bridge/ops_state.json", &mut checks);
        let companions = root.join("Companions");
        checks.push(check(
            "companions",
            "Companions directory",
            "error",
            companions.is_dir(),
            if companions.is_dir() {
                "Available"
            } else {
                "Missing Companions directory"
            },
        ));
        let writable = OpenOptions::new()
            .write(true)
            .open(root.join("Bridge/status.json"))
            .is_ok();
        checks.push(check(
            "vault-permissions",
            "Vault write permission",
            "error",
            writable,
            if writable {
                "Bridge/status.json can be opened for writing"
            } else {
                "Bridge/status.json cannot be opened for writing"
            },
        ));
        let bridge = root.join("Bridge");
        let stale_lock = fs::read_dir(&bridge)
            .ok()
            .into_iter()
            .flatten()
            .filter_map(Result::ok)
            .any(|entry| entry.path().extension().is_some_and(|ext| ext == "lock"));
        checks.push(check(
            "stale-locks",
            "Vault lock files",
            "warning",
            !stale_lock,
            if stale_lock {
                "A lock file may indicate an interrupted operation"
            } else {
                "No lock files found"
            },
        ));
        let failed_migration = fs::read_dir(&bridge)
            .ok()
            .into_iter()
            .flatten()
            .filter_map(Result::ok)
            .any(|entry| {
                entry
                    .file_name()
                    .to_string_lossy()
                    .contains("migration_failed")
            });
        checks.push(check(
            "migrations",
            "Migration markers",
            "error",
            !failed_migration,
            if failed_migration {
                "A failed migration marker requires recovery before writes"
            } else {
                "No failed migration marker found"
            },
        ));
    }
    let overall_ok = checks
        .iter()
        .all(|item| item.ok || item.severity != "error");
    DiagnosticsReport {
        runtime: "tauri-v2".into(),
        version: env!("CARGO_PKG_VERSION").into(),
        navis_root: root.display().to_string(),
        overall_ok,
        checks,
    }
}
