# Task area and identity contract

Both recurring and active task APIs use trimmed lowercase area keys. `Gauntlet`
and `Bureaucratic` map to `bureaucratic`; `Outland` and `World` map to `world`.
Other names (including Sanctum, Domestic and Front) retain their lowercase key.
Reads normalize both the requested area and legacy stored values. Missing or
blank filters return all records. Creates and area updates save canonical keys.
Area boards may continue sending their existing aliases.

New tasks receive full UUID v4 IDs. Existing IDs are never migrated on read or
update. Native imports may supply a unique nonempty string ID; collisions are
rejected across both collections. Updates cannot change an ID. An ID matching
multiple records in a collection makes update/delete fail before writing:
FastAPI returns HTTP 409, and the native bridge reports an explicit ambiguity
error. Repair duplicated IDs deliberately before retrying; no bulk deletion is
performed. Missing IDs return HTTP 404 or a native Task not found error.

Verification uses disposable state, never the personal Vault:

```text
python -m pytest backend/tests/test_task_identity.py
cargo test --manifest-path frontend/src-tauri/Cargo.toml task_area_identity
```
