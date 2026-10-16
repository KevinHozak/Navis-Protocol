# Issue 149: active directive completion

Mark Done sends POST /api/active_tasks/{id}/complete. Both HTTP and the native
Rust bridge call services.directive_completion.complete; native execution uses
the existing allowlisted local Python runtime rather than hosted HTTP.

Completion retains the active_tasks record with completed status, timestamp,
source journal, stable task marker, XP rule, and recovery phase. Active reads hide
completed records. Ordinary DELETE remains available for pending directives;
completion history cannot be edited or deleted through task CRUD.

The configured status.last_updated selects the journal date, matching the
existing daily XP policy. A recognized pillar and an existing journal section
are required. Completion inserts one checked entry and calls the canonical
daily ledger; it does not add a separate per-directive XP award. Retries use the
saved date and marker, and the canonical daily source retains its award cohort.
Missing evidence or projections leave a recoverable operation on the active list.
Legacy completed directives are not automatically backfilled or awarded.

Validation uses temporary synthetic Vaults: HTTP route, Rust/Python bridge,
interrupted XP sync, replay, encoding, duplicate identities, immutable completion
history, intentional deletion, canonical ledger and frontend click/error/retry.
No real rollover, provider requests, or private Vault modifications are required.
