# Tauri P3 verification record

P3 native workflows are designed to run from the Tauri command boundary without a FastAPI process. The compatibility adapter continues to use HTTP in web/dev mode.

## Evidence

- `frontend/src-tauri/src/p3.rs` provides native battle state, link, resolve, rest, mission listing, and sector-cache routes
- `frontend/src-tauri/src/progression.rs` provides native XP history, XP logging, and achievements routes through the existing SQLite database
- `frontend/src-tauri/src/vault.rs` provides native mission selection and task persistence routes
- `frontend/src-tauri/src/operations.rs` emits typed `navis://operation` events
- `frontend/src-tauri/tests/fixtures/p3_parity.json` records representative Python/native response contracts
- `p3::tests::native_routes_work_without_backend_server` exercises native battle and mission routes directly with no server
- `parity_contracts::native_and_python_contract_fixtures_match` compares the representative contracts

## Required checks

```text
cargo fmt --manifest-path frontend/src-tauri/Cargo.toml -- --check
cargo test --manifest-path frontend/src-tauri/Cargo.toml
npm run lint                 # from frontend
npm run build:desktop       # from frontend; Windows spawn EPERM may affect the local type-check worker
```

The final manual smoke check is performed with the backend process stopped and the Tauri app running against `NAVIS_ROOT`.

Combat task P3 now additionally exercises the Rust `combat_request` subprocess
bridge and HTTP compatibility routes with synthetic journals and persisted
recovery checkpoints. See [combat task verification](combat-task-verification.md)
for exact automated evidence and the packaged-app smoke checks still not run.
