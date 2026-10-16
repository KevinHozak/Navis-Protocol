# Recurring mandate schedule contract

All runtimes store `last_done` and `next_due` as ISO calendar dates (YYYY-MM-DD),
not UTC timestamps. The journal day starts at **03:00 local wall-clock time**.
Before 03:00, use the preceding calendar date. Subtract a calendar day, not three
elapsed hours: those differ during DST transitions.

The browser supplies its journal date as `next_due` on creation and `last_done`
on completion. This keeps hosted web storage independent of the server timezone.
For direct API/native creation without `next_due`, use the runtime's local journal
day; callers in a different timezone should supply their date explicitly. Native
creation ignores supplied `last_done`: new mandates have never been completed.
Creation saves `last_done: null` and is due immediately on that journal day unless
an explicit initial `next_due` is supplied. The board displays **Last: Never**.

| Frequency (trimmed, case insensitive) | Interval |
| --- | --- |
| daily | 1 calendar day |
| weekly | 7 calendar days |
| bi-weekly, every 2 weeks | 14 calendar days |
| every 3 weeks | 21 calendar days |
| monthly | 1 calendar month |
| bimonthly, every 2 months | 2 calendar months |
| quarterly | 3 calendar months |
| seasonal | 6 calendar months |

Month advancement retains the completion's day number, clamping to the target
month's final day when necessary (Jan 31 -> Feb 28, or Feb 29 in a leap year).
The next completion is a fresh anchor; Feb 28 -> Mar 28. There is no sticky
month-end rule. Unknown frequencies and invalid dates fail before persistence.

Completion derives `next_due` from `last_done`, so repeated completion on the
same date is idempotent and an accompanying `next_due` cannot override it.
Changing frequency recomputes from an existing completion; an uncompleted task
keeps its initial due date. A standalone due-date update is an explicit override.
The journal sweep uses the journal's recorded date, even when sweeping later,
and the same Python interval helper as CRUD. No XP ledger changes are involved.
Existing records are not migrated automatically; schedules are corrected when
completed or their frequency is updated.

Verification uses the shared synthetic `tests/recurrence-contract.json` vectors,
Python CRUD/sweep fixtures, native persisted route fixtures and a Chicago browser
date test. It never requires the personal Vault, live rollover or providers.

```text
python -m pytest backend/tests/test_recurrence_contract.py backend/tests/test_task_identity.py
node frontend/scripts/test-recurrence-contract.mjs
cargo test --offline --no-default-features --manifest-path frontend/src-tauri/Cargo.toml recurrence
cargo test --offline --no-default-features --manifest-path frontend/src-tauri/Cargo.toml task_
```
