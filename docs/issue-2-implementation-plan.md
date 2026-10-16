# Issue #2 implementation plan

## Scope

Port Reid/neural, biometrics, Forge, and approved operational jobs behind typed Tauri commands and observable events. Keep AI provider access behind a native adapter; renderer input must never select arbitrary executables, paths, or secrets.

## Acceptance mapping

- Native Reid/neural, biometrics, Forge, and operations routes use typed native commands/events or structured unavailable responses.
- Operations use fixed allowlists, Vault-root working directories, filtered environments, cancellation, bounded output, and exit diagnostics.
- Forge remains two-step: blueprint first, explicit approval before writes.
- Missing Vault databases and providers degrade safely.
- Tests cover route allowlists, event validation, cancellation, failure recovery, and secret redaction.

## Verification

- `cargo fmt --manifest-path frontend/src-tauri/Cargo.toml -- --check`
- `cargo test --manifest-path frontend/src-tauri/Cargo.toml`
- `npm run lint` from `frontend`
- `git diff --check`
