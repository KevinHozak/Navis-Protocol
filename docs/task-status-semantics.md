# Shared task status contract (S022)

The picker exposes Pending, In progress, Deferred, Cancelled and Done in journals,
area task/recurring boards and the central Tasks cockpit. It uses a labelled native
select, pending/error/saved feedback and focus restoration after persistence.
Completed directives can be shown and reopened; this is not the S024 Completed
today view. Timestamp presentation and broader timestamp policy remain S023.

| Status | Journal checkbox | Completion / recurrence effect |
| --- | --- | --- |
| Pending | `[ ]` | Open/reopen; no reschedule |
| In progress | `[ ]` | No completion or reschedule |
| Deferred | `[ ]` | No completion or implied due-date change |
| Cancelled | `[ ]` | Not successful completion; does not cancel a recurring series |
| Done | `[x]` | Existing canonical completion and daily XP reconciliation |

Legacy blank/x/X checkboxes remain valid. Rich journal status uses an invisible
`<!-- navis-task:UUID:status -->` suffix on the same line; UUID is 32 lower-case hex
characters. The stable identity is Vault-relative file plus UUID. The line/text
and exact expected file content must still agree; missing, stale or ambiguous
targets and duplicated markers are rejected. A legacy row gets an identity only
when a status is explicitly selected. Source text, section, order, nested notes,
BOM and newline style stay in place. This does not migrate other checkbox dialects.
Managed operation-file rows are excluded from the legacy collection sweep, so
sync cannot move the original entry. Unrelated legacy sweep behavior is unchanged.

`POST /api/tasks/toggle` accepts `task_status` with the existing file/text/line and
`expected_content` fields. Legacy `is_checked` is supported; contradictory fields
are rejected. Every save reads back source content. HTTP and Tauri both execute
`services.task_toggle.toggle`; Tauri has no independent status writer. Lost-response
retries with an old snapshot conflict and reload; retries with the read-back
snapshot are idempotent. Only checked rows contribute task XP. Noncompletion
status edits cannot create a daily award; existing daily source totals can be
reconciled downward or retried after projection failure without duplicate awards.

Active directives retain their existing `id`, with `status` set to pending,
in_progress, deferred, cancelled or the legacy completed value for Done. Recurring
mandates retain series identity and schedule fields; `occurrence_status` stores
the operational journal date and status. An old occurrence status does not cancel
the next occurrence. Done uses the existing directive completion writer and its
`navis-directive` journal marker, saved phases and canonical XP source. Existing
legacy completion buttons and combat completion continue through their canonical
paths. Reopening a task does not undo a historical combat resolution.

The existing `/api/active_tasks/{id}/complete` and `/api/recurring/{id}/complete`
routes additionally accept `{task_status, expected_task}`. The full canonical
record snapshot is compared under the shared Vault completion lock; augmented UI
fields are not submitted. Tauri forwards the same body to native_directive.py.
The default active-task GET still omits completed directives; the picker views use
`include_completed=true` when reopening is available. Saved feedback follows a
confirmed status readback, not an optimistic choice.

Reopening keeps completion provenance in `completion_history`, unchecks only the
unique linked journal row, reconciles that journal's XP, and retains the marker.
Recurring reopening restores the schedule captured before that completion;
unknown legacy schedules/completions require provenance review. Recompletion
reuses the same occurrence marker without appending another log item. New recurring
occurrences archive the previous completion. Reopening has a durable recovery
phase; after an interruption reload and retry the same status. Pending completion
recovery must finish through Done before another status is selected. A transient
Saved / XP pending option keeps that state explicit.

Verification uses disposable Vaults only. Automated tests cover HTTP/native bridge
roundtrips, stale and duplicate targets, preserved bytes/notes, readback, canonical
XP reconciliation, reopening recovery, recurring schedules, no-collection behavior
and mounted board/cockpit controls. Packaged and physical browser observations are
recorded separately in the S022 trial record; source/adapter tests do not substitute
for those observations. No personal Vault mutation or production integration is
part of this acceptance.

## Verification checkpoint

The [sanitized S022 trial](trials/s022-task-status-2026-10-27.json) records passing
real web and packaged 1.11.26 status, completion, reopening and cancellation
checks. Both fixtures ended with byte-identical journals, 12 net XP after reopening,
one retained completion history item and unchanged recurring due dates. BOM,
CRLF, attached notes and each original task occurrence were preserved. Fixture
windows/processes and dedicated web listeners were cleaned up.

The packaged check found a missing native_directive.py bundle entrypoint; it is
now included and covered by a resource regression. All 39 final bundled backend
resources matched source. The earlier missing-entrypoint attempt is not counted
as passing. One existing injected combat-recovery test failed once; its isolated
rerun and the complete 174-case affected suite passed afterward. The trial retains
that observation without assigning an unverified cause. Two additional packaging
and concurrent-edit tests passed, as did 51 frontend adapters/full regressions,
76 native unit tests and one parity test. The personal-Vault probe was excluded.

Primary-agent source review found no remaining actionable issue in the selected
changes. Independent external review remains unavailable. This checkpoint does
not certify a clean-machine installation, production migration or live integration.
