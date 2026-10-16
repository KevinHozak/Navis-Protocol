# XP history reconciliation

The per-entity `xp_ledger` in `Keeper/navis_progression.db` is canonical. Legacy `xp_logs` rows have no entity identity, `CompanionStats.json` has totals without defensible event dates, and historical XP Markdown can overlap those stores. Reconciliation therefore inventories all sources but imports only entries explicitly reviewed in a version 1 mapping manifest. Unmapped, duplicate, stale, or uncertain history stays unchanged and unresolved.

## Dry run

`migrate_xp.py` is read-only by default. It does not initialize a missing database or rewrite any Vault file. It reports aggregate source counts and totals, possible duplicates, missing store/entity coverage, ambiguous source counts, and proposed mappings. It omits journal text and Markdown line contents.

```powershell
$env:NAVIS_ROOT = 'C:\path\to\isolated-vault-fixture'
backend\.venv\Scripts\python.exe backend\scripts\migrate_xp.py --report C:\path\to\xp-dry-run.json
```

The report lists possible duplicate candidates with matching dates and amounts for review. These are never automatically collapsed because same-day entries may be distinct awards. A dry run with `--manifest` validates mappings and shows their proposed entities, amounts, and award IDs without changing files.

## Reviewed mapping manifest

The manifest is local operator input and should not contain copied journal text. It supports three explicit source identities:

- `xp_logs:<row id>` for one legacy SQLite row. Its amount and date must match the database exactly. The row itself does not identify an entity.
- `markdown:<Vault-relative XP.md path>:<line number>` for a parsed dated XP bullet outside the canonical projection block. Set `source_line_hash` to the fingerprint from a local review tool or construct it as SHA-256 of the exact UTF-8 line. The amount, date, entity inferred from the file path, and fingerprint must still match at apply time.
- `companion_stats:<entity id>` for an explicitly reviewed opening balance. The amount must match the old `xp` field and the manifest must supply a defensible entity and local date. A total alone is insufficient evidence and must remain unresolved.

Each mapping supplies `award_id`, `entity_id`, signed integer `amount`, timezone-qualified `source_event_at`, `local_date`, and `provenance`. Optional fields are `source_type` (defaults to `legacy_import`), `rule_version`, `reason`, and `details`. Use `source_type: "manual_adjustment"` only when the source is verified as a manual award, and include its `reason` and `provenance.actor`. Source IDs and award IDs must be unique. Mappings cannot change source amounts or dates, guess a Markdown line after it changes, or map one source twice. Possible same-day overlaps are reported by date and amount even if details differ. If a reviewed group is intentionally being imported as more than one distinct award, every newly imported member must include `provenance.identity_review: "distinct_award"`. An already imported source remains recorded in ledger provenance, so a later run cannot silently import an overlapping source as a second award.

Example shape:

```json
{
  "version": 1,
  "mappings": [
    {
      "source_id": "xp_logs:17",
      "award_id": "legacy:reviewed-row-17",
      "entity_id": "keeper",
      "amount": 12,
      "source_event_at": "2026-01-03T12:00:00Z",
      "local_date": "2026-01-03",
      "provenance": {"actor": "reviewer", "review_ref": "local-case-17"}
    }
  ]
}
```

## Apply, verification, and rollback

Apply only after the isolated fixture scenarios pass and every mapping has evidence. Provide a new backup directory. Applying to the configured `NAVIS_ROOT` requires the explicit `--allow-configured-vault` flag; never use that flag for fixture work.

```powershell
backend\.venv\Scripts\python.exe backend\scripts\migrate_xp.py `
  --root C:\path\to\isolated-vault-fixture `
  --manifest C:\path\to\reviewed-manifest.json `
  --apply `
  --backup-dir C:\path\to\xp-backup
```

Before changing data, the tool creates a SQLite online backup and exact copies of the JSON/Markdown projections it may rewrite, then verifies each backup. The manifest records file hashes and a logical SQLite digest. Apply uses a SQLite immediate transaction, stores version/checkpoint state, inserts append-only ledger events idempotently, refreshes affected projections, and verifies final per-entity totals. The database lock blocks Python and Tauri XP writers during apply and projection recovery.

If apply is interrupted after the ledger commit, its lock remains in place so other XP writers fail clearly. Rerun with the same manifest; the tool reuses the verified backup and checkpoint, repairs projections, verifies totals, and releases the lock. An unchanged completed manifest is an idempotent no-op. A different manifest cannot take over an active recovery.

For a verified rollback, stop the Navis services first, then use the run ID printed by apply:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\migrate_xp.py `
  --root C:\path\to\isolated-vault-fixture `
  --rollback xp-reconcile-v1-<manifest-hash>
```

Rollback verifies every backup and the restored copy. It restores the pre-migration database and affected projections, including removing a projection file the migration created only when its contents still match the recorded post-migration digest. It refuses to overwrite a store changed after migration. Keep the backup directory until the migrated totals and projections have been reviewed.

The configured personal Vault is not part of repository tests. Run the migration and rollback scenarios against isolated representative fixtures first; keep reports and source-level evidence local.
