# Guarded journal appends (S021)

Writes remain disabled unless the MCP child is launched with
`NAVIS_MCP_ENABLE_JOURNAL_APPEND=1`. This setting was not enabled on personal data.
The S020 [source-bound trial](vault-mcp-trial-results.md) adopted a controlled
read-only pilot; S021's write acceptance uses disposable fixtures. It does not
claim a personal-Drive trial or an actual Codex write-client evaluation.

## Shared authority

`services/journal_entry.py` now owns appends for the HTTP endpoint, the desktop
`native_journal_entry.py` bridge and the opt-in MCP adapter. The old Rust and HTTP
append implementations were removed. The desktop route rejects bypasses of the
Python bridge, whose new service dependencies are included in Tauri resources.
The composer retains its draft and reports a saved item with XP still pending.

The service uses the same cross-process `Battle/.completion.lock` as task toggles
and combat completion. It calls the existing RPG engine and canonical progression
ledger, preserving recipient cohorts and idempotent correction/projection rules.
It does not award a separate per-request XP event. Strict talent reconciliation
propagates failures for appends; older RPG callers retain their existing behavior.
No rollover, periodic-note creation, work/watch sync, git backup, provider or
schedule is invoked. Required ledger/projection files may be created by the XP
engine; only the journal itself is existing-file-only.

## Request and result

First use `read_note` on `Journal/YYYY/MM/YYYY-MM-DD.md` and retain its SHA-256.
Submit `append_journal_entry` with all five fields:

```json
{
  "date": "2026-10-26",
  "section": "sanctum",
  "entry": "Completed fixture work",
  "request_id": "fixture-request-00001",
  "expected_sha256": "<64 lowercase hexadecimal characters from read_note>"
}
```

The date must be a literal valid calendar date. Section is one of `sanctum`,
`domestic`, `front`, `gauntlet`, `outland`. Entry is one nonempty line, at most
10,000 characters; its leading bullet/checkbox is normalized to a completed item.
Control characters, arbitrary paths, extra properties and generic write/delete
operations are rejected. Request IDs contain 16–80 ASCII letters, digits,
underscores or hyphens. Use a fresh ID for each new intent and retain it for retries.

MCP still enforces its allowlist, exclusions, root identity, reparse-point denial,
UTF-8 and one-MiB source limit. Missing/denied journals are not created. Only an
unambiguous level-two canonical section outside fenced code is accepted; an
unclosed fence is rejected. Original bytes, BOM presence/absence, unrelated text
and CR/LF line endings survive insertion. A sibling temporary file is fsynced
and atomically replaced, followed by a fresh source read and digest check.

Successful MCP results contain `data.saved`, `data.replayed`, `request_id`, date,
path, current SHA and XP status, without echoing journal content. HTTP/desktop
retain their content response for the existing UI. `saved_xp_pending` means the
journal persisted but ledger/projection reconciliation has not completed. Keep
the same ID, original expected SHA and payload when retrying; never generate a
new ID merely because an acknowledgement was lost.

Legacy HTTP/desktop requests may omit the new fields. A deterministic payload
ID then makes retrying the same date/section/entry idempotent. This also means an
identical later entry replays the old request; revise the text for a distinct
intent. MCP always requires explicit fields. Identical normalized items already
in the selected section are rejected for a different ID.

## Persistence and recovery

Private `Battle/journal-appends/<request_id>.json` records store a payload digest,
the supplied expected hash, before/after journal digests and a phase. They do not
store the note body. Keep them for retry protection; deleting them removes that
history. They are outside the MCP note allowlist and are not returned to clients.

1. A new request validates its expected hash and writes a durable `prepared`
   intent before touching the journal.
2. Recovery from `prepared` accepts only the recorded before/after digests:
   before permits the exact insertion; after means it already persisted.
3. After read-back, `saved` permits XP-only retries using the current journal,
   preserving subsequent user edits. The engine's idempotent ledger repairs a
   failed compatibility projection without awarding the same XP twice.
4. `complete` replays without another append or XP award. Reusing an ID with a
   different normalized payload or expected hash is `request_id_conflict`.

`source_changed` means reload and reconcile the user's edit before proposing a
new intent. An interrupted I/O response can be
`append_outcome_unknown_retry_same_request`: persistence may have happened.
Retry unchanged when Drive is available.
An error/transport failure does not in general prove that nothing persisted;
retain the same request identity until the outcome has been reconciled.
If the journal changed after a crash
while the record remained `prepared`, `recovery_required` refuses to guess.
Inspect the current journal and its history locally, confirm whether the item
persisted, and use the existing date-specific RPG reconciliation if it did.
Retain the intent record and do not blindly resubmit with a new ID or rewrite
the journal from an old snapshot. This ambiguous case deliberately needs
operator reconciliation rather than an automatic overwrite.

The lock serializes cooperating writers. Hash rechecks detect ordinary edits
before replacement and read-back detects edits after it. Other editors, Drive
sync, older installed app versions and legacy sync scripts do not all take this
lock. A noncooperating writer can race in the final check/replace interval;
this is not a filesystem compare-and-swap or distributed Drive transaction.
Coordinate those writers and deploy the shared desktop bridge before enabling
the tool on real data. No personal-data enablement or installer deployment is
part of this change.

## Fixture verification

`test_journal_append_safety.py` covers BOM/no BOM, LF/CRLF/CR, Unicode, preserved
surrounding bytes, validation, stale hashes, duplicate IDs/items, two concurrent
requests, edits before replacement, interruptions before/after replacement and
before acknowledgement, owned-temp cleanup, missing/unavailable/denied sources,
unsupported encoding, pending XP with later edits, actual ledger projection
failure/retry, desktop JSON transport and real stdio opt-in calls. Existing
read-only stdio tests continue to assert exactly four tools with no mutation.
Native bridge acceptance verifies UTF-8/CRLF and persistent replay without HTTP.
