# Directive task metadata

Active and recurring create/update requests accept `description` (Markdown string),
`priority` (integer 1-4, default 4; 1 is highest), `labels` (string list), and
`due_date` (strict YYYY-MM-DD). New records default to empty descriptions and labels.
Updates preserve omitted fields; empty strings/lists clear descriptions/labels.
Active tasks allow `due_date: null` to clear their deadline.

Recurring `due_date` is an API alias for the existing persisted `next_due` schedule.
Both names are accepted; conflicting dates are rejected. Recurring update requests
cannot clear the schedule with a null `due_date`. Completion via `last_done` takes
precedence and advances the schedule, as before. Responses expose both date names;
only `next_due` is stored, preventing divergence during journal sweeps.
Legacy records and unrelated fields remain intact without a Vault migration.

The shared Python recurrence calculator supports existing presets plus `yearly`
and `every N days`, `every N weeks`, `every N months` (positive integers, singular
units also accepted). Month/year intervals clamp to the destination month's last
day. Unsupported intervals and dates beyond year 9999 are rejected.

Run regression checks with a Python environment containing the backend test dependencies:

```powershell
python -m pytest backend/tests/test_directive_metadata.py backend/tests/test_recurrence_contract.py -q
```

Tests use disposable Vault fixtures and disable network access. Native UI and task
editor enhancements are separate phases of epic #201.
