use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, ExitStatus, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tauri::{AppHandle, Emitter, Manager, State};

pub const OPERATION_EVENT: &str = "navis://operation";
pub const NATIVE_OPERATIONS: &[&str] = &["sync", "rollover"];
const MAX_DIAGNOSTIC_BYTES: usize = 4096;
#[cfg(unix)]
const TERMINATE_GRACE: Duration = Duration::from_secs(2);

#[derive(Clone, Default)]
pub struct SyncOperationState {
    pub jobs: Arc<Mutex<HashMap<String, Arc<AtomicBool>>>>,
}

impl SyncOperationState {
    fn register(&self, id: String) -> Result<Arc<AtomicBool>, String> {
        let cancel = Arc::new(AtomicBool::new(false));
        let mut jobs = self.jobs.lock().map_err(|_| "operation state unavailable")?;
        if !jobs.is_empty() {
            return Err("an operation is already running".into());
        }
        jobs.insert(id, cancel.clone());
        Ok(cancel)
    }

    fn remove(&self, id: &str) {
        if let Ok(mut jobs) = self.jobs.lock() {
            jobs.remove(id);
        }
    }

    fn cancel_all(&self) {
        if let Ok(jobs) = self.jobs.lock() {
            for cancel in jobs.values() {
                cancel.store(true, Ordering::Release);
            }
        }
    }
}

pub(crate) fn backend_root(app: &AppHandle) -> Result<PathBuf, String> {
    let development = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("backend");
    if backend_entrypoint_exists(&development) {
        return Ok(development);
    }

    let bundled = app
        .path()
        .resource_dir()
        .map_err(|error| format!("unable to locate application resources: {error}"))?
        .join("backend");
    if backend_entrypoint_exists(&bundled) {
        return Ok(bundled);
    }

    Err("Navis sync backend resource is missing. Reinstall the application or use a complete development checkout.".into())
}

fn backend_entrypoint_exists(backend: &Path) -> bool {
    backend.join("native_operations.py").is_file()
        && backend.join("services").join("__init__.py").is_file()
        && backend.join("services").join("sync_engine.py").is_file()
}

pub(crate) fn configured_vault_root() -> Result<PathBuf, String> {
    // The desktop launch path may not inherit interactive shell variables. Match
    // the established Navis Vault default used by the native read adapters.
    let root = std::env::var_os("NAVIS_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(r"G:\My Drive\Navis-Vault"));
    if !root.is_dir() {
        return Err(format!(
            "NAVIS_ROOT is not an available directory: {}",
            root.display()
        ));
    }
    if !root.join("Bridge").is_dir() || !root.join("Journal").is_dir() {
        return Err(format!(
            "NAVIS_ROOT is missing required Bridge or Journal directories: {}",
            root.display()
        ));
    }
    Ok(root)
}

fn emit(app: &AppHandle, job_id: &str, status: &str, phase: &str, message: impl Into<String>) {
    let _ = app.emit(
        OPERATION_EVENT,
        serde_json::json!({"job_id":job_id,"status":status,"phase":phase,"message":message.into()}),
    );
}

fn redact_diagnostic(input: &str) -> String {
    let mut result = input.to_string();
    for key in [
        "NAVIS_ROOT",
        "NAVIS_VAULT_ROOT",
        "NAVIS_PYTHON",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "API_KEY",
        "TOKEN",
        "PASSWORD",
        "SECRET",
    ] {
        let mut cursor = 0;
        while let Some(relative) = result[cursor..].to_ascii_uppercase().find(key) {
            let start = cursor + relative;
            let after_key = start + key.len();
            if let Some((separator_offset, separator)) = result[after_key..]
                .char_indices()
                .find(|(_, c)| *c == '=' || *c == ':')
            {
                if separator_offset <= 2 {
                    let value_start = after_key + separator_offset + separator.len_utf8();
                    let value_end = result[value_start..]
                        .find(['\r', '\n', ' ', ',', ';'])
                        .map_or(result.len(), |n| value_start + n);
                    result.replace_range(value_start..value_end, "[REDACTED]");
                    cursor = value_start + "[REDACTED]".len();
                } else {
                    cursor = after_key;
                }
            } else {
                cursor = after_key;
            }
            if cursor >= result.len() {
                break;
            }
        }
    }
    result
}

fn remember_tail(tail: &Arc<Mutex<String>>, line: &str) {
    if let Ok(mut value) = tail.lock() {
        value.push_str(&redact_diagnostic(line));
        value.push('\n');
        if value.len() > MAX_DIAGNOSTIC_BYTES {
            let mut start = value.len() - MAX_DIAGNOSTIC_BYTES;
            while !value.is_char_boundary(start) {
                start += 1;
            }
            value.drain(..start);
        }
    }
}

fn drain_stream<R: std::io::Read + Send + 'static>(
    reader: R,
    tail: Arc<Mutex<String>>,
    progress: Option<Arc<dyn Fn(String) + Send + Sync>>,
) -> std::thread::JoinHandle<Result<(), String>> {
    std::thread::spawn(move || {
        let mut reader = BufReader::new(reader);
        let mut line = String::new();
        loop {
            line.clear();
            match reader.read_line(&mut line) {
                Ok(0) => return Ok(()),
                Ok(_) => {
                    if line.len() > MAX_DIAGNOSTIC_BYTES {
                        let omitted = line.len() - MAX_DIAGNOSTIC_BYTES;
                        let mut start = omitted;
                        while !line.is_char_boundary(start) {
                            start += 1;
                        }
                        let bounded = format!(
                            "[output truncated: {omitted} bytes omitted]{}",
                            &line[start..]
                        );
                        let bounded = bounded.trim_end_matches(['\r', '\n']);
                        if !bounded.is_empty() {
                            remember_tail(&tail, bounded);
                            if let Some(progress) = &progress {
                                progress(redact_diagnostic(bounded));
                            }
                        }
                        continue;
                    }
                    let line = line.trim_end_matches(['\r', '\n']);
                    if line.is_empty() {
                        continue;
                    }
                    remember_tail(&tail, line);
                    if let Some(progress) = &progress {
                        progress(redact_diagnostic(line));
                    }
                }
                Err(error) => return Err(error.to_string()),
            }
        }
    })
}

#[cfg(unix)]
fn configure_process_tree(command: &mut Command) {
    use std::os::unix::process::CommandExt;
    command.process_group(0);
}

#[cfg(windows)]
fn configure_process_tree(_command: &mut Command) {}

#[cfg(windows)]
fn attach_windows_job(child: &Child) -> Result<isize, String> {
    use std::os::windows::io::AsRawHandle;
    use windows_sys::Win32::System::JobObjects::{
        AssignProcessToJobObject, JobObjectExtendedLimitInformation, SetInformationJobObject,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    };
    use windows_sys::Win32::System::JobObjects::{
        CreateJobObjectW, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    };
    let job = unsafe { CreateJobObjectW(std::ptr::null(), std::ptr::null()) };
    if job.is_null() {
        return Err("unable to create process job object".into());
    }
    let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = unsafe { std::mem::zeroed() };
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    let configured = unsafe {
        SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            &info as *const _ as *const _,
            std::mem::size_of_val(&info) as u32,
        )
    };
    let assigned = unsafe { AssignProcessToJobObject(job, child.as_raw_handle() as _) };
    if configured == 0 || assigned == 0 {
        unsafe {
            windows_sys::Win32::Foundation::CloseHandle(job);
        }
        return Err("unable to supervise child process tree".into());
    }
    Ok(job as isize)
}

#[cfg(windows)]
fn terminate_tree(child: &mut Child, job: Option<isize>) {
    if let Some(job) = job {
        unsafe {
            windows_sys::Win32::System::JobObjects::TerminateJobObject(job as _, 1);
        }
    } else {
        let _ = child.kill();
    }
}

#[cfg(unix)]
fn terminate_tree(child: &mut Child, _job: Option<isize>) {
    let pid = child.id() as i32;
    unsafe {
        libc::kill(-pid, libc::SIGTERM);
    }
    let deadline = Instant::now() + TERMINATE_GRACE;
    while Instant::now() < deadline {
        if child.try_wait().ok().flatten().is_some() {
            return;
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    unsafe {
        libc::kill(-pid, libc::SIGKILL);
    }
}

#[cfg(not(any(unix, windows)))]
fn terminate_tree(child: &mut Child, _job: Option<isize>) {
    let _ = child.kill();
}

fn supervise(
    mut command: Command,
    cancel: &AtomicBool,
    progress: Arc<dyn Fn(String) + Send + Sync>,
) -> Result<ExitStatus, String> {
    command.stdout(Stdio::piped()).stderr(Stdio::piped());
    configure_process_tree(&mut command);
    let mut child = command
        .spawn()
        .map_err(|error| format!("spawn error: {error}"))?;
    #[cfg(windows)]
    let process_job = match attach_windows_job(&child) {
        Ok(job) => Some(job),
        Err(error) => {
            let _ = child.kill();
            let _ = child.wait();
            return Err(format!("spawn supervision error: {error}"));
        }
    };
    #[cfg(not(windows))]
    let process_job: Option<isize> = None;

    let tail = Arc::new(Mutex::new(String::new()));
    let (Some(stdout), Some(stderr)) = (child.stdout.take(), child.stderr.take()) else {
        terminate_tree(&mut child, process_job);
        let _ = child.wait();
        return Err("read error: stdout or stderr pipe unavailable".into());
    };
    let out_reader = drain_stream(stdout, tail.clone(), Some(progress));
    let err_reader = drain_stream(stderr, tail.clone(), None);
    let mut cancelled = false;
    let waited = loop {
        if cancel.load(Ordering::Acquire) {
            cancelled = true;
            terminate_tree(&mut child, process_job);
            break child
                .wait()
                .map_err(|error| format!("cancellation reap error: {error}"));
        }
        match child.try_wait() {
            Ok(Some(status)) => break Ok(status),
            Err(error) => {
                terminate_tree(&mut child, process_job);
                let _ = child.wait();
                break Err(format!("child wait error: {error}"));
            }
            Ok(None) => std::thread::sleep(Duration::from_millis(50)),
        }
    };
    let reader_results = (|| {
        let stdout_result = out_reader
            .join()
            .map_err(|_| "stdout reader panicked".to_string())?;
        let stderr_result = err_reader
            .join()
            .map_err(|_| "stderr reader panicked".to_string())?;
        stdout_result?;
        stderr_result?;
        Ok::<(), String>(())
    })();
    #[cfg(windows)]
    if let Some(job) = process_job {
        unsafe {
            windows_sys::Win32::Foundation::CloseHandle(job as _);
        }
    }
    if let Err(error) = reader_results {
        return Err(format!("read error: {error}"));
    }
    let status = waited?;
    if cancelled {
        return Err("cancelled".into());
    }
    if !status.success() {
        let diagnostic = tail
            .lock()
            .map(|value| value.trim().to_string())
            .unwrap_or_default();
        return Err(if diagnostic.is_empty() {
            format!("native operation exited with {status}")
        } else {
            format!("native operation exited with {status}: {diagnostic}")
        });
    }
    Ok(status)
}

fn run_operation(
    command: Command,
    cancel: Arc<AtomicBool>,
    progress: Arc<dyn Fn(String) + Send + Sync>,
) -> Result<(), String> {
    supervise(command, &cancel, progress).map(|_| ())
}

pub fn cancel_all_sync_operations(app: &AppHandle) {
    if let Some(state) = app.try_state::<SyncOperationState>() {
        state.cancel_all();
    }
}

#[tauri::command]
pub fn start_sync_operation(
    app: AppHandle,
    state: State<'_, SyncOperationState>,
    operation: String,
    request_id: Option<String>,
) -> Result<Value, String> {
    if !NATIVE_OPERATIONS.contains(&operation.as_str()) {
        return Err("unsupported native synchronization operation".into());
    }
    let backend = backend_root(&app)?;
    let vault_root = configured_vault_root()?;
    let runtime = crate::command::resolve_python_runtime(&backend, !cfg!(debug_assertions))?;
    let generated_id = format!(
        "native-{}-{}",
        operation,
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_err(|error| error.to_string())?
            .as_nanos()
    );
    let job_id = request_id.unwrap_or(generated_id);
    if job_id.is_empty() || job_id.len() > 96 || !job_id.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_') {
        return Err("invalid operation identity".into());
    }
    let cancel = state.register(job_id.clone())?;
    let state = state.inner().clone();
    let app2 = app.clone();
    let job2 = job_id.clone();
    let operation2 = operation.clone();
    std::thread::spawn(move || {
        emit(
            &app2,
            &job2,
            "running",
            "start",
            format!("Starting native {operation2} sequence"),
        );
        let mut command = crate::command::hidden_command(&runtime.to_string_lossy());
        command
            .arg("-u")
            .arg(backend.join("native_operations.py"))
            .arg(&operation2)
            .current_dir(&backend)
            .env_clear();
        for key in ["PATH", "SystemRoot", "TEMP", "TMP"] {
            if let Ok(value) = std::env::var(key) {
                command.env(key, value);
            }
        }
        command
            .env("NAVIS_OPERATION_ID", &job2)
            .env("NAVIS_ROOT", &vault_root)
            .env("PYTHONPATH", &backend)
            .env("PYTHONIOENCODING", "utf-8");
        let progress_app = app2.clone();
        let progress_job = job2.clone();
        let progress: Arc<dyn Fn(String) + Send + Sync> =
            Arc::new(move |line| emit(&progress_app, &progress_job, "running", "progress", line));
        let result = run_operation(command, cancel, progress);
        match result {
            Ok(()) => emit(
                &app2,
                &job2,
                "completed",
                "finalize",
                "Native operation completed",
            ),
            Err(error) if error == "cancelled" => emit(
                &app2,
                &job2,
                "cancelled",
                "cancel",
                "Native operation cancelled",
            ),
            Err(error) => emit(&app2, &job2, "failed", "finalize", error),
        }
        state.remove(&job2);
    });
    Ok(serde_json::json!({"status":"accepted","job_id":job_id,"operation":operation}))
}

#[tauri::command]
pub fn cancel_sync_operation(
    state: State<'_, SyncOperationState>,
    job_id: String,
) -> Result<Value, String> {
    let jobs = state
        .jobs
        .lock()
        .map_err(|_| "operation state unavailable")?;
    let token = jobs.get(&job_id).ok_or("operation not found")?;
    token.store(true, Ordering::Release);
    Ok(serde_json::json!({"status":"cancellation_requested","job_id":job_id}))
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OperationEvent {
    pub job_id: String,
    pub status: String,
    pub phase: String,
    pub message: String,
    #[serde(default)]
    pub output: Option<String>,
    #[serde(default)]
    pub result: Option<Value>,
}

#[tauri::command]
pub fn emit_operation_event(app: AppHandle, event: OperationEvent) -> Result<(), String> {
    if event.job_id.trim().is_empty() {
        return Err("job_id is required".to_string());
    }
    if event.phase.trim().is_empty() {
        return Err("phase is required".to_string());
    }
    if event.message.trim().is_empty() {
        return Err("message is required".to_string());
    }
    app.emit(OPERATION_EVENT, event)
        .map_err(|error| format!("failed to emit operation event: {error}"))
}

#[cfg(test)]
mod tests {
    use super::{
        backend_entrypoint_exists, configured_vault_root, drain_stream, redact_diagnostic,
        run_operation, OperationEvent, SyncOperationState, NATIVE_OPERATIONS,
    };
    use std::path::Path;
    use std::path::PathBuf;
    use std::process::Command;
    use std::sync::{atomic::AtomicBool, Arc, Mutex};
    use std::time::{Duration, Instant};
    static ENV_LOCK: Mutex<()> = Mutex::new(());

    #[test]
    fn native_sync_boundary_only_accepts_supported_mutations() {
        assert_eq!(NATIVE_OPERATIONS, &["sync", "rollover"]);
        assert!(!NATIVE_OPERATIONS.contains(&"backup"));
    }
    #[test]
    fn operation_event_defaults_optional_fields() {
        let event: OperationEvent = serde_json::from_value(serde_json::json!({"job_id":"job-1","status":"running","phase":"sync","message":"Synchronizing"})).expect("valid operation event");
        assert_eq!(event.output, None);
        assert_eq!(event.result, None);
    }
    #[test]
    fn backend_resource_requires_entrypoint_and_engine() {
        let root = fixture("backend");
        std::fs::create_dir_all(root.join("services")).unwrap();
        std::fs::write(root.join("native_operations.py"), "").unwrap();
        assert!(!backend_entrypoint_exists(&root));
        std::fs::write(root.join("services/__init__.py"), "").unwrap();
        assert!(!backend_entrypoint_exists(&root));
        std::fs::write(root.join("services/sync_engine.py"), "").unwrap();
        assert!(backend_entrypoint_exists(&root));
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn vault_root_defaults_to_available_navis_vault_when_unset() {
        let _guard = ENV_LOCK.lock().unwrap();
        let configured = std::env::var_os("NAVIS_ROOT");
        std::env::remove_var("NAVIS_ROOT");
        let default_root = PathBuf::from(r"G:\My Drive\Navis-Vault");
        if default_root.is_dir()
            && default_root.join("Bridge").is_dir()
            && default_root.join("Journal").is_dir()
        {
            assert_eq!(configured_vault_root().unwrap(), default_root);
        } else {
            assert!(configured_vault_root().is_err());
        }

        let root = fixture("vault");
        std::fs::create_dir_all(root.join("Bridge")).unwrap();
        std::env::set_var("NAVIS_ROOT", &root);
        assert!(configured_vault_root().is_err());
        std::fs::create_dir_all(root.join("Journal")).unwrap();
        assert_eq!(configured_vault_root().unwrap(), root);
        match configured {
            Some(value) => std::env::set_var("NAVIS_ROOT", value),
            None => std::env::remove_var("NAVIS_ROOT"),
        }
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn operation_state_registers_and_cleans_job_ids() {
        let state = SyncOperationState::default();
        let cancel = state.register("job".into()).unwrap();
        assert!(!cancel.load(std::sync::atomic::Ordering::Relaxed));
        state.remove("job");
        assert!(state.jobs.lock().unwrap().is_empty());
    }
    #[test]
    fn diagnostics_redact_secrets_and_bound_tail_size() {
        assert_eq!(redact_diagnostic("API_KEY=secret"), "API_KEY=[REDACTED]");
        let tail = Arc::new(Mutex::new(String::new()));
        super::remember_tail(&tail, &"x".repeat(10_000));
        assert!(tail.lock().unwrap().len() <= super::MAX_DIAGNOSTIC_BYTES);
    }

    #[test]
    fn diagnostic_tail_bounds_multibyte_utf8_and_keeps_latest_line() {
        let tail = Arc::new(Mutex::new(String::new()));
        super::remember_tail(&tail, &"🛰️".repeat(2000));
        super::remember_tail(&tail, "latest synthetic diagnostic");
        let text = tail.lock().unwrap();
        assert!(text.len() <= super::MAX_DIAGNOSTIC_BYTES);
        assert!(text.ends_with("latest synthetic diagnostic\n"));
        assert!(!text.contains('\u{fffd}'));
    }

    #[test]
    fn diagnostics_redact_repeated_case_insensitive_secret_assignments() {
        let line = "token=first,TOKEN:second; api_key=third\nSafe diagnostic";
        assert_eq!(redact_diagnostic(line),
            "token=[REDACTED],TOKEN:[REDACTED]; api_key=[REDACTED]\nSafe diagnostic");
    }
    #[test]
    fn both_streams_are_drained_concurrently_for_large_output() {
        let dir = fixture("large-output");
        let script = dir.join("child.py");
        std::fs::write(&script, "import sys\nfor i in range(12000):\n print('out-' + str(i))\n print('err-' + str(i), file=sys.stderr)\n").unwrap();
        let command = python_command(&script);
        let cancel = AtomicBool::new(false);
        let progress = Arc::new(|_: String| {});
        let started = Instant::now();
        assert!(run_operation(command, Arc::new(cancel), progress).is_ok());
        assert!(started.elapsed() < Duration::from_secs(20));
        std::fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn delayed_output_and_nonzero_exit_return_useful_redacted_diagnostic() {
        let dir = fixture("delayed");
        let script = dir.join("child.py");
        std::fs::write(&script, "import sys,time\nprint('starting', flush=True)\ntime.sleep(.15)\nprint('API_KEY=hidden', file=sys.stderr, flush=True)\nsys.exit(7)\n").unwrap();
        let lines = Arc::new(Mutex::new(Vec::new()));
        let observed = lines.clone();
        let progress = Arc::new(move |line: String| observed.lock().unwrap().push(line));
        let error = run_operation(
            python_command(&script),
            Arc::new(AtomicBool::new(false)),
            progress,
        )
        .unwrap_err();
        assert!(error.contains("exited with"));
        assert!(error.contains("API_KEY=[REDACTED]"));
        assert!(lines.lock().unwrap().iter().any(|line| line == "starting"));
        std::fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn spawn_failure_is_distinguished() {
        let error = run_operation(
            Command::new(fixture("missing").join("absent")),
            Arc::new(AtomicBool::new(false)),
            Arc::new(|_: String| {}),
        )
        .unwrap_err();
        assert!(error.starts_with("spawn error:"));
    }
    #[test]
    fn cancellation_terminates_child_and_reaps_it() {
        let dir = fixture("cancel");
        let script = dir.join("child.py");
        std::fs::write(
            &script,
            "import time\nprint('ready', flush=True)\ntime.sleep(30)\n",
        )
        .unwrap();
        let cancel = Arc::new(AtomicBool::new(false));
        let cancel2 = cancel.clone();
        let progress = Arc::new(move |line: String| {
            if line == "ready" {
                cancel2.store(true, std::sync::atomic::Ordering::Release);
            }
        });
        let started = Instant::now();
        let error = run_operation(python_command(&script), cancel, progress).unwrap_err();
        assert_eq!(error, "cancelled");
        assert!(started.elapsed() < Duration::from_secs(5));
        std::fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn read_error_is_reported_by_stream_drain() {
        let tail = Arc::new(Mutex::new(String::new()));
        let thread = drain_stream(std::io::Cursor::new(Vec::<u8>::new()), tail, None);
        assert!(thread.join().unwrap().is_ok());
    }
    fn python_command(script: &Path) -> Command {
        let mut command =
            Command::new(std::env::var_os("NAVIS_TEST_PYTHON").unwrap_or_else(|| "python".into()));
        command.arg(script);
        command
    }
    fn fixture(name: &str) -> PathBuf {
        let path = std::env::temp_dir().join(format!(
            "navis-operations-{name}-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&path).unwrap();
        path
    }
}
