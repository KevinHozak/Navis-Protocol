# Issue 86: combat task completion

Use one local completion engine from FastAPI and the Tauri Python runtime bridge.
The source Markdown checkbox remains authoritative; existing RPG ledger sync owns XP.
Bind exact relative path, task line, and normalized context at link time. Reject stale,
ambiguous, missing, or unsafe sources. Persist intent before task writes, then persist
card transitions atomically, then sync XP. Retain partial operations for retry.

Acceptance mapping: both routes share the engine; durable resolution keys prevent
duplicate transitions; false resolution changes cards only; byte edits preserve BOM,
line endings and unrelated body; synthetic backend and native bridge tests cover
success, missing/checked sources and partial-write recovery.

Verification: focused pytest, native bridge transition tests, Rust formatting/checks,
and frontend lint. No live personal Vault writes are needed.

User review required: none for implementation. Review the resulting diff before merge.
