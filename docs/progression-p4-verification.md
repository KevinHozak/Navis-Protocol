# Progression P4 acceptance evidence

Issue #71, parent #67; based on P3 merge 44b453f. Production Vault records were
not migrated or edited. Fixtures contain synthetic records only.

## Implementation and acceptance mapping

- Keeper totals and thresholds: Python and Rust supply the same canonical level
  progress contract; the dashboard has no independent level formula.
- Attribution: entity, source type/reference, actor, reason and correction link
  are visible; Python now decodes provenance to match native JSON.
- Recovery: separate read/write errors, explicit empty/loading states, read retry,
  manual refresh, concurrent submission guard and same-input award-ID retry.
- Refresh: successful API writes and async sync/rollover completion notify the
  dashboard; mount, status changes and focus also refresh it.
- Journal, manual and corrections: isolated Python fixtures verify repeated
  journal replay, recipient ownership, correction retries, ordering, boundaries,
  projections and totals/history after reloading the ledger service.
- Native without HTTP: Rust fixture exercises real SQLite award, identical retry,
  correction and fresh-connection history reads. Adapter fixture rejects any HTTP
  use in native mode and verifies progression IPC routing and success-only events.

## Verified 2026-09-30

- `python -m pytest backend/tests/test_progression_ledger.py -q -p no:cacheprovider
  --basetemp C:\Projects\Navis-Protocol\.p4-test-temp`: 10 passed. Run with sandbox
  escalation because ordinary pytest temp-directory access fails on this host.
- `cargo test --manifest-path frontend/src-tauri/Cargo.toml progression::tests
  -- --test-threads=1`: 1 passed, with target directory under host TEMP.
- Focused Next lint for ProgressionManifold, desktopApi and AsyncJobModal: clean.
- `node frontend/scripts/test-progression-flow.mjs`: passed web/native boundary
  and refresh behavior using synthetic responses.
- Existing desktop API boundary and native capability checks: passed.

## Historical manual checks — explicitly waived

Packaged desktop launch with FastAPI stopped, interactive journal completion to
rendered dashboard update, layout/error/retry inspection, and close/relaunch of
the packaged UI were not performed. Backend persistence and native IPC are tested,
but automated fixtures do not establish these visual/application lifecycle checks.
### Accepted disposition — reconciled 2026-11-03

The [#71 acceptance disposition](https://github.com/KevinHozak/Navis-Protocol-Private/issues/71)
dated 2026-09-30 explicitly waives those remaining manual checks and supersedes the
old instruction to keep #71/#67 open. Implementation merged in historical PR #128;
#71 and parent #67 are closed. The waiver is not a passing runtime result and does
not authorize a production Vault migration. These checks are not current closure
blockers or the next required task. No production P3 reconciliation is asserted.
