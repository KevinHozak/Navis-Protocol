# Tasks-P4 checkbox mutation contract

Issue: #150. Both HTTP and the desktop Python bridge use `services/task_toggle.py`.

Requests must include `expected_content`, the exact decoded UTF-8 source snapshot (without BOM). Vault reads expose `source_content` separately from web display image rewriting. Missing snapshots, changed revisions, stale lines, and ambiguous text-only targets return a conflict without a checkbox write. Line numbers must match exact task text. Mutations serialize with canonical combat/directive completion using the cross-process Vault completion lock, recheck bytes before atomic replacement, and retain BOM, line endings, sections, and unrelated text.

Success returns authoritative content, `saved`, `modified`, and `xp_status`. Dated journal files reconcile their own date through canonical daily XP, including negative corrections when unchecked. Other files return `not_applicable`. XP failure after persistence returns HTTP 200 with `saved_xp_pending`; the UI preserves saved content and offers Retry XP using the saved snapshot. Replays run reconciliation even when the checkbox is unchanged; the canonical ledger applies only source deltas. Lost responses trigger a read-back. Rapid clicks are ignored while a mutation is pending. Native packages include the bridge and shared service; direct legacy native checkbox writes fail closed.

## Verification

- 22 backend tests passed: checkbox contract, existing path safety, canonical progression ledger. Fixtures are temporary Vaults and databases.
- Frontend regression suite passed, including executed handler tests for authoritative responses, rapid clicks, XP pending, conflict and status refresh failure.
- 2 affected Rust tests passed with `TAURI_CONFIG` pointing `frontendDist` to existing public test assets. The fresh worktree has no production frontend export.
- Version metadata synchronized to 1.6.6.

Commands: `PYTHONPATH=backend python -m pytest backend/tests/test_checkbox_contract.py backend/tests/test_task_toggle_safety.py backend/tests/test_progression_ledger.py`; `node frontend/scripts/test-regressions.mjs`; `cargo test --manifest-path frontend/src-tauri/Cargo.toml --lib task_toggle --offline` with the test asset override.

Compiled WebView2 interaction and a production installer build remain unverified. External editors and Drive sync do not share the application mutation lock; physical multi-device race behavior was not exercised.

The fresh worktree lacks the generated Husky bootstrap, frontend lint dependencies and the backend Ruff module. Those lint checks were unavailable; the commit uses a one-command hook bypass after the listed passing tests.
