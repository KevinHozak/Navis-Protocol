# Sync and rollover outcomes (S014)

S009 findings T06/T07 are delivered in [audit PR #16](https://github.com/KevinHozak/Navis-Protocol/pull/16).
This implementation changes user-initiated sync/rollover outcome reporting and
recovery. It does not run any operation against personal data or enable MCP writes.

## Shared authority and states

Web routes and the native entrypoint use `services/operation_outcomes.py` around
the existing sync engine. Known engine boundaries explicitly start work, XP,
watch-history, backup, sweep, journal initialization, index/readiness, banter,
biometrics, Holocron and cache phases. Errors caught inside engine phases are
reported; the adapter also conservatively recognizes legacy returned error and
warning strings. Missing merge targets retain their source work and mark failure.

Each phase has `status` (not_run/running/completed/failed/skipped/unknown) and
`persistence` (not_attempted/may_have_committed/confirmed). Completed means the
phase returned without a reported error, not that every input was independently
revalidated. Confirmed means a specific journal write or Git commit returned;
it is not proof that every effect in that phase committed. Multi-file journal
and index/readiness phases are aggregates, not rollback transactions.

Overall status is completed, partial or failed. Partial explicitly allows saved
effects and failed steps together. Rollover does not begin after a failed backup
sequence. Downstream phases remain not_run; no automatic per-step retry is added.
Fixture-disabled integrations appear skipped rather than being claimed executed.

## Durable evidence and overlap

Static outcome records are atomically saved under `Bridge/.navis_operations/`
before phase effects. Records contain identifiers, timestamps, phase labels and
statuses, not note bodies, external source paths or provider credentials. A
process-held OS lock plus local thread guard serializes cooperating web/native
sync/rollover operations. Repeated request IDs return the retained outcome and
never replay the sequence; conflicting kinds and reserved/unsafe IDs are rejected.
The UI retains request identity after an ambiguous submission. Locks are released
by the OS on process exit; an unlocked running receipt is reported interrupted
with unknown in-flight effects rather than presumed success or rollback.

Receipts and locks are excluded from backup staging in both production and
fixture Git paths. They are local operating state, not a journal/XP authority or
a replacement for backups. Preserve receipts when recovering this runtime; loss
of receipts also loses request replay evidence. Do not delete them to bypass an
unresolved outcome. No automatic retention pruning is introduced.

The lock covers these cooperating operations, not arbitrary editors, other
machines, old runtimes or standalone legacy engine callers. Existing underlying
journal concurrency/integrity limitations remain; this layer does not certify
Drive-wide distributed locking or transactional rollover.

## API and interface

- POST `/api/sync` or `/api/journal/rollover` accepts optional `request_id` and
  `run_async=true`; retry an uncertain submission with the exact same ID.
- GET `/api/ops/jobs/{id}` reads the persisted outcome after memory/process loss;
  generic legacy job polling remains supported through the web memory fallback.
- GET `/api/ops/latest` retrieves the latest sync/rollover record for review.
- POST `/api/ops/jobs/{id}/review` acknowledges operator review under the same
  lock. It does not rerun steps, award XP, repair journals or turn failures into
  successful phases. Acknowledgement while a write is active is rejected.

The modal lists phase outcomes, confirmed saves and uncertain persistence.
Reconnect status performs GETs only. Confirm review requires explicit user
confirmation and only records that review. Another operation is blocked after
an unreviewed partial/interrupted outcome. If a new request was blocked or lacks
a receipt, the modal can display the prior outcome explicitly; it does not invoke
the new request's completion callback based on an older success. Non-sync native
job completion remains event-compatible. Native status reconnects are bounded
when no saved record is available; status-unavailable is not labelled write failure.

Before confirming review, inspect the failed/unknown phases and the authoritative
saved journals/XP/backup state; reconcile uncertain effects manually using their
existing recovery tools. Then close the modal and start a new operation only when
appropriate. This is a new user action, not an automatic resume or rollback.
If the UI is unavailable, with the correct root/runtime configured:

```powershell
.tools/mcp-venv/Scripts/python.exe backend/native_operations.py review JOB_ID
# Only after reviewing the saved changes:
.tools/mcp-venv/Scripts/python.exe backend/native_operations.py review JOB_ID --acknowledge
```

## Verification boundary

Disposable fixtures cover saved-before-error, interrupted process, same-ID replay,
conflicting identities, cross-process overlap, root mismatch, corrupt state,
unavailable Vault, HTTP/native durable readback, retained unmerged work and review
without replay. Mounted React tests cover web/native partial outcomes, read-only
reconnect, confirmed review, old-outcome isolation, generic native completion and
cancellation with request IDs. Native library tests exercise the Python status
bridge including rejecting a GET acknowledgement and preserving journal bytes.

The prior native success fixture used an unmatched work-section heading and
mistakenly relied on retained work being reported successful. It now supplies a
valid heading and checks both the merged journal and purged source; a separate
fixture verifies missing-target partial failure preserves unmerged work.

Packaged WebView2 interaction, cross-device Drive races, installer/resource
execution and actual production integrations remain unverified under S015.
The known missing-watchdog test is explicitly excluded, not passed. This change
does not repair S013 factual Holocron metrics or the other S009 findings. Version
1.11.19 is prepared for these app changes; no installer is produced by this work.


## Local verification - 2026-10-27

81 affected Python tests passed (27.55 seconds); the existing watcher test was
excluded because watchdog is unavailable, not counted as passed. The seven mounted
operation scenarios, 49 complete-adapter tests and the full frontend regression
runner passed. 71 serial Rust library tests passed, with only the personal-Vault
availability probe excluded. Backend Ruff and frontend lint passed (existing
frontend warnings). The desktop frontend production build passed after a targeted
retry for sandbox EPERM on .next output creation. No installer or packaged UI was
run. S009's unrelated two failing Holocron-manifest tests are unchanged; this does
not certify the whole repository suite. Source-level delivery review found no
remaining actionable finding in the selected changes; independent external review
is unavailable. A separate S014 PR is authorized and depends on audit PR #16.

S009 reproduction probes describe the audit baseline at 279a614. Their T06/T07
cases are historical observations, not passing acceptance tests for this repaired
source. Use the S014 operation tests for current recovery acceptance.
