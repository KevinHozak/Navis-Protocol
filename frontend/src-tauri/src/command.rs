use std::path::{Path, PathBuf};
use std::process::Command;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

/// Create a child process without opening a Windows console window.
pub fn hidden_command(program: &str) -> Command {
    let mut command = Command::new(program);
    #[cfg(windows)]
    command.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    command
}

/// Resolve the Python interpreter shared by native Tauri subprocesses.
/// `NAVIS_PYTHON` takes precedence; otherwise development prefers the local
/// backend venv and release builds discover a supported interpreter on PATH.
pub fn resolve_python_runtime(backend: &Path, release: bool) -> Result<PathBuf, String> {
    if let Some(configured) = std::env::var_os("NAVIS_PYTHON") {
        let runtime = PathBuf::from(configured);
        if !runtime.is_file() {
            return Err(format!(
                "NAVIS_PYTHON does not point to a Python executable: {}",
                runtime.display()
            ));
        }
        validate_python_runtime(&runtime)?;
        return Ok(runtime);
    }

    let development = if !release {
        let development = backend.join(".venv").join(if cfg!(windows) {
            "Scripts/python.exe"
        } else {
            "bin/python"
        });
        Some(development)
    } else {
        None
    };

    let candidates = development.into_iter().chain(
        python_path_candidates()
            .iter()
            .filter_map(|candidate| find_on_path(candidate)),
    );
    first_supported_runtime(candidates, validate_python_runtime)
        .ok_or_else(|| "Python 3.11 or newer was not found. Install Python with the required backend packages and add it to PATH, or set NAVIS_PYTHON to its executable.".into())
}

fn first_supported_runtime(
    candidates: impl IntoIterator<Item = PathBuf>,
    validate: impl Fn(&Path) -> Result<(), String>,
) -> Option<PathBuf> {
    candidates
        .into_iter()
        .find(|runtime| runtime.is_file() && validate(runtime).is_ok())
}

fn python_path_candidates() -> &'static [&'static str] {
    &[
        "python3.14",
        "python3.13",
        "python3.12",
        "python3.11",
        "python3",
        "python",
    ]
}

fn find_on_path(program: &str) -> Option<PathBuf> {
    let path = std::env::var_os("PATH")?;
    let extensions: &[&str] = if cfg!(windows) { &[".exe", ""] } else { &[""] };
    for directory in std::env::split_paths(&path) {
        for extension in extensions {
            let candidate = directory.join(format!("{program}{extension}"));
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    None
}

/// Reject missing or unsupported interpreters before starting an operation.
pub fn validate_python_runtime(runtime: &Path) -> Result<(), String> {
    let output = hidden_command(&runtime.to_string_lossy())
        .args([
            "-c",
            "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)",
        ])
        .env_clear()
        .env("PATH", std::env::var_os("PATH").unwrap_or_default())
        .env("SystemRoot", std::env::var_os("SystemRoot").unwrap_or_default())
        .env("TEMP", std::env::var_os("TEMP").unwrap_or_default())
        .env("TMP", std::env::var_os("TMP").unwrap_or_default())
        .output()
        .map_err(|_| {
            format!(
                "Unable to start Python runtime {}. Configure NAVIS_PYTHON to Python 3.11 or newer.",
                runtime.display()
            )
        })?;
    if output.status.success() {
        Ok(())
    } else {
        Err(format!(
            "Python runtime {} is unavailable or older than 3.11. Configure NAVIS_PYTHON to Python 3.11 or newer.",
            runtime.display()
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::{first_supported_runtime, resolve_python_runtime};
    use std::sync::Mutex;

    static ENV_LOCK: Mutex<()> = Mutex::new(());

    #[test]
    fn automatic_runtime_skips_broken_and_unsupported_candidates() {
        let directory =
            std::env::temp_dir().join(format!("navis-candidates-{}", std::process::id()));
        std::fs::create_dir_all(&directory).unwrap();
        let paths: Vec<_> = ["missing", "broken", "python310", "supported", "later"]
            .iter()
            .map(|name| directory.join(name))
            .collect();
        for path in &paths[1..] {
            std::fs::write(path, b"fixture").unwrap();
        }
        let checked = std::cell::RefCell::new(Vec::new());
        let chosen = first_supported_runtime(paths.clone(), |runtime| {
            checked.borrow_mut().push(runtime.to_path_buf());
            match runtime.file_name().unwrap().to_str().unwrap() {
                "broken" => Err("Unable to start Python".into()),
                "python310" => Err("Python is older than 3.11".into()),
                _ => Ok(()),
            }
        });
        assert_eq!(chosen, Some(paths[3].clone()));
        assert_eq!(*checked.borrow(), paths[1..4]);
        std::fs::remove_dir_all(directory).unwrap();
    }

    #[test]
    fn automatic_runtime_prefers_supported_virtualenv_and_fails_without_fallback() {
        let directory =
            std::env::temp_dir().join(format!("navis-preferred-{}", std::process::id()));
        std::fs::create_dir_all(&directory).unwrap();
        let development = directory.join("venv");
        let system = directory.join("system");
        for path in [&development, &system] {
            std::fs::write(path, b"fixture").unwrap();
        }
        let candidates = [development.clone(), system];
        assert_eq!(
            first_supported_runtime(candidates.clone(), |_| Ok(())),
            Some(development)
        );
        assert_eq!(
            first_supported_runtime(candidates, |_| Err("invalid".into())),
            None
        );
        std::fs::remove_dir_all(directory).unwrap();
    }

    #[test]
    fn shared_resolver_discovers_runtime_and_honors_override() {
        let _guard = ENV_LOCK.lock().unwrap();
        let backend =
            std::env::temp_dir().join(format!("navis-python-runtime-{}", std::process::id()));
        std::fs::create_dir_all(&backend).unwrap();
        std::env::remove_var("NAVIS_PYTHON");

        let discovered = resolve_python_runtime(&backend, true)
            .expect("supported Python should be discoverable from PATH");
        let broken_venv = backend.join(".venv").join(if cfg!(windows) {
            "Scripts/python.exe"
        } else {
            "bin/python"
        });
        std::fs::create_dir_all(broken_venv.parent().unwrap()).unwrap();
        std::fs::write(&broken_venv, b"broken executable").unwrap();
        assert_eq!(resolve_python_runtime(&backend, false).unwrap(), discovered);
        std::env::set_var("NAVIS_PYTHON", &discovered);
        assert_eq!(resolve_python_runtime(&backend, true).unwrap(), discovered);

        std::env::set_var("NAVIS_PYTHON", backend.join("missing-python.exe"));
        assert!(resolve_python_runtime(&backend, true).is_err());
        std::env::remove_var("NAVIS_PYTHON");
        std::fs::remove_dir_all(backend).unwrap();
    }

    #[test]
    fn shared_resolver_rejects_an_existing_non_python_override() {
        let _guard = ENV_LOCK.lock().unwrap();
        let backend = std::env::temp_dir().join(format!(
            "navis-python-runtime-invalid-{}",
            std::process::id()
        ));
        std::fs::create_dir_all(&backend).unwrap();
        let executable = std::env::current_exe().unwrap();
        std::env::set_var("NAVIS_PYTHON", &executable);
        assert!(resolve_python_runtime(&backend, true).is_err());
        std::env::remove_var("NAVIS_PYTHON");
        std::fs::remove_dir_all(backend).unwrap();
    }
}
