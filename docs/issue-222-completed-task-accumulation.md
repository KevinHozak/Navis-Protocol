# Issue #222: completed task accumulation

## Reproduction and responsible writers

Synthetic tests reproduced three defects in the pre-fix source:

- `directive_completion.complete`: completing a directive already present as
  an unchecked journal item inserted a second checked item and retained the
  pending occurrence. This service is shared by the web completion routes and
  the desktop `native_directive.py` bridge.
- `sync_engine.sync_active_tasks`: sweeping a checked Operations/Tasks.md item
  already recorded in the destination section appended it again. Restoring the
  source after a restart reproduced another append.
- The same sweep treated a completed longer task label as completion of a
  recurring task whose label was its prefix, advancing the wrong schedule.

These reproduce source defects; the original personal-Vault report has not
been reproduced live. No personal history was edited or cleaned up.

## Change

Completion now reuses a unique exact checklist occurrence within the target
section, retains its location and list formatting, and attaches canonical
directive provenance. An absent occurrence is inserted once. Ambiguous existing
occurrences and conflicting provenance fail for review without rewriting the
journal. Existing duplicates are not deleted automatically.

The legacy sweep uses the same section-aware merge. It saves journal evidence
atomically before removing source items, so interruption and restart can retry
without adding another completion. Both writers create recoverable backups and
preserve BOM presence, CRLF, and unrelated content. Recurrence sweep matching
requires the complete task label, allowing the canonical provenance suffix.
The canonical daily XP calculation and ledger policy remain unchanged.

## Verification

Focused suites: `test_completed_task_accumulation.py`,
`test_directive_completion.py`, `test_sync_work_journal.py`,
`test_recurrence_contract.py`, and `test_native_operations.py`.

Final result: **73 passed**. `git diff --check` passed. Tests used Python 3.14
with temporary storage inside this worktree; the primary backend virtualenv
lacks pytest. Windows asyncio tests ran outside the filesystem sandbox because
its loopback socket restriction stalled the in-process web route tests.

Coverage includes the three failing reproductions, web completion and desktop
completion subprocesses, repeat completion with unchanged bytes and exactly 12
Keeper XP, backup read-back, unrelated sections with identical task labels,
ambiguous history, interruption after journal save but before source cleanup,
and native rollover/sync across separate process launches. Rollover preserves
completed one-off history, excludes a weekly mandate not yet due, and injects
one genuinely due daily mandate. Existing recurrence interval and completion
tests verify subsequent due dates.

The PR audit identified partial-heading extraction for Domestic and
Bureaucratic operation folders. The sweep now captures the entire heading on
one line. Added regressions verify both longer headings, CRLF/BOM preservation,
identical labels in unrelated sections, source cleanup, and repeat execution.

All fixtures are synthetic. Packaged desktop UI behavior and the reported live
trigger remain unverified. Native repeat-run fixtures exclude their unrelated
untracked work-log/XP outputs from fixture Git; the backup routine's handling
of unstaged untracked files is a separate pre-existing limitation.
