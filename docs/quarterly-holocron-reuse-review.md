# NAVIS-S029 helper reuse and zero-write review

Read-only source review on 2026-11-07 against local main `e0ebb6b`.
Relates to the [proposed contract and matrix](quarterly-holocron-preview-contract.md)
and [open issue](../issues/NAVIS-S029.md). **No feature implementation, helper
execution, SQLite opens, application launches, personal-Vault access or provider
calls were performed.** Existing tests were inspected as source, not rerun.
Findings below are compatibility gaps against S029, not newly reproduced defects
in the existing weekly/MCP features.

## Reuse assessment

| Existing helper | Reusable behavior | S029 mismatch / decision needed |
| --- | --- | --- |
| [`find_journal_file`](../backend/services/holocron_engine.py) | Nested dated path before flat dated path. | Uses `isfile`/existence probes and can proceed to the flat path when a preferred candidate is unsafe or not a regular file. S029 requires a discovered unreadable/unsafe preferred candidate to remain an explicit failure, not be masked. Discovery must distinguish absence from denied/unsafe candidates. |
| [`parse_daily_journal`](../backend/services/holocron_engine.py) | UTF-8-sig decoding and exact trimmed `- [x]` / `- [ ]` prefix semantics. | Opens the file itself, reads all lines, and has no size or file-identity guard. Returns zero counters for missing/unavailable input. Also extracts metadata S029 excludes. Reuse counting semantics, not this file-open path; count from one accepted bounded text snapshot. |
| [`source_path`, `journal_source`](../backend/services/holocron_evidence.py) | Root-relative source IDs, 2 MiB size check, digest and unavailable classification. | `source_path` resolves paths before containment and uses `is_symlink` for descendants, without the stronger reparse/root identity checks of shared access. Size is checked before an unbounded `read_bytes`; the file may change between those operations. Separate evidence and parser reads do not establish a single accepted snapshot. Do not use as the sole quarterly path/read boundary. |
| [`ApplicationNotePolicy`, `_snapshot`, `read_markdown_source`](../backend/services/vault_access.py) | Explicit root input, ancestor reparse checks, root identity pinning, bounded reads and before/open/after identity/size/time checks; returns content and digest from one snapshot. | Closest journal-read foundation, but current hard limit is 1 MiB, not S029's 2 MiB. Error codes intentionally collapse cases S029 distinguishes. Markdown-only resolution cannot be used for SQLite. Private helpers are not stable public interfaces. Do not globally raise limits or broaden extensions as an incidental quarterly change. |
| [`read_binary`](../backend/services/vault_io.py) | Noncreating read-only handle; Windows uses GENERIC_READ/OPEN_EXISTING/OPEN_REPARSE_POINT with shared access. Its tests cover noncreation, write refusal and short reads. | Caller must supply ancestor/path/handle checks. Public `read_markdown_source` currently calls `_snapshot` without this opener; using the stronger raw handle requires deliberate composition. Shared access permits concurrent writers; it is not an immutable snapshot or a SQLite VFS. |
| [`resolve_relative_path`](../backend/services/vault_paths.py) | Relative-path validation and lexical/realpath containment. | Containment alone is not a no-junction/no-symlink or race guarantee. Some errors include paths; map to fixed quarterly reason codes instead of forwarding text. |
| [`query_progression_telemetry`](../backend/services/holocron_engine.py) | Explicit date range, URI `mode=ro`, lowercased Keeper filter, signed sums and known-empty zero semantics. | Not a drop-in quarterly reader: required schema is not fully validated, dates are SQL string comparisons, amounts are summed/coerced before strict row validation, and no matched-row count is returned. Availability becomes available before later optional queries; broad exception handling does not establish full success or precise failure reasons. No WAL/sidecar or stable-source proof is present. |
| [`get_connection`, `init_db`](../backend/services/progression_db.py) | Canonical schema definition is useful reference material. | Runtime use is prohibited for this preview: creates Keeper directories, opens SQLite without read-only URI, runs schema initialization/migration/seed work. Missing roots/databases must never reach these functions. Do not import mutation-oriented services merely to obtain a connection. |
| Read path in [`vault_index`](../backend/services/vault_index.py) | Existing example of `mode=ro`, `query_only=ON`, `trusted_schema=OFF`, bounded source metadata and progress-handler deadlines. | It targets an index, not canonical XP, and the same module has index-building writes. Its database reads are a reference pattern, not a reusable proof of no sidecar/temp-file effects. Do not build or query an index for S029. |
| Weekly builder/export/manifest functions | Historical metric/evidence semantics and fixture patterns. | `build_weekly_holocron` can create artifacts and update manifests; HTML export can write files. `force=False` is not a no-write mode. These runtime entry points are outside S029. |

The shared `VaultPolicy.from_env` supplies MCP allow/deny roots and requires
timezone configuration. S029 instead requires an explicit CLI root and calendar
dates, without MCP configuration or broader root discovery. Prefer the explicit
application-note context for Markdown where compatible; preserve MCP policy
boundaries and never expand the global Markdown resolver to admit database files.

## Journal decisions before implementation

1. Preserve the proposed 2 MiB quarterly bound. Reusing the 1 MiB snapshot helper
   unchanged would reject otherwise in-contract sources. A narrowly parameterized
   bounded-read seam or dedicated quarterly composition must retain existing
   consumers' limits; changing the shared global constant is not the solution.
2. Separate candidate discovery from a safe accepted read. Determine absence
   without following links; do not silently treat permission errors, reparse
   points, directories or a broken preferred link as a missing date and select
   the flat copy. Emit an unreadable result where the contract requires it.
3. Derive coverage, entry counts and source identity from the same accepted bytes.
   Map `source_changed` to `changed_during_read`, encoding errors to
   `invalid_encoding`, and size rejection to `oversized_source`. Some current
   not-found errors combine policy and existence failures, so they cannot simply
   be relabeled `missing` without a justified discovery result.
4. Keep the existing prefix semantics deliberately: uppercase/custom checkboxes
   are excluded, duplicate text across days remains multiple entries, and this
   is not a new Markdown interpretation or unique-task lifecycle algorithm.

## SQLite and WAL handling

The inspected XP helper specifies a read-only SQLite connection. Its source does
not establish that every SQLite filesystem action is nonmutating, nor that a
concurrently changing DB/WAL pair matches the contract's stable-source rules.
No dedicated canonical-XP zero-write/WAL helper was found in the inspected files.
This review does not certify SQLite behavior on the host or a Drive filesystem.

Proposed bounded policy for initial S029 implementation:

| Input state | Proposed treatment / required proof |
| --- | --- |
| Missing main DB | `missing_ledger`, null totals, no SQLite open or initialization. |
| Settled compatible database without recovery work | Candidate for a read-only query with explicit root/path/identity checks and bounded work. Must pass actual native write guards and correct signed/count results before being called supported. |
| WAL/SHM present, WAL-mode header, rollback journal, or uncertain sidecar state | Conservatively return `unsafe_database_state` unless a separately demonstrated nonmutating consistent-read path covers that exact state. Rejecting these states is acceptable for this small story; silently summing only the main DB is not. |
| Live/changing DB or sidecars | `changed_during_read` or `unsafe_database_state`, null totals. No checkpoint, journal deletion, recovery, retry in writable mode or fallback to a stale snapshot. |
| Unsupported columns / invalid canonical Keeper rows | `unsupported_schema` or `invalid_ledger`; no schema repair, partial sum or coercion of questionable values into zero. Optional achievements tables remain irrelevant. |

Sidecar existence/header checks are **not** a concurrency barrier: a writer can
create or change a sidecar after a check. The future reader must either establish
the required nonmutating access/snapshot guarantees for its supported input class
or refuse it. Adding `query_only` or a SELECT authorizer is useful SQL defense,
but alone is not proof about native file operations, locking or temporary files.

Do not set `immutable=1` simply to suppress locking/sidecars on a potentially live
database. It would require an independently justified immutable input assumption;
neither a filename nor a one-time no-WAL check establishes one. Copying the DB to
disk or exporting a snapshot is also not a solution within the command's zero-
write/no-temp-file scope. A test harness may prepare a closed synthetic DB before
measurement, but the command may not prepare/repair its own input.

Before any sum, validate the required canonical columns and Keeper row values,
then apply inclusive calendar dates. The current SQL-only date predicate can
exclude malformed dates without telling the caller; S029 must state and test
its strict validation rule. Return matched-row count separately from signed sum.
One coherent accepted ledger read must supply schema validation, row validation,
count and sum; rereading them independently is not adequate snapshot evidence.

## Zero-write proof: reusable evidence versus gaps

Existing [`test_vault_io`](../backend/tests/test_vault_io.py) and
[`test_vault_mcp`](../backend/tests/test_vault_mcp.py) provide useful fixture
patterns for bounded reads, identity changes, unreadable sources and write-refusing
handles. [`test_holocron_evidence`](../backend/tests/test_holocron_evidence.py)
covers known-zero versus unavailable evidence, signed Keeper corrections and
excluded entities/dates. Several weekly tests intentionally run builders that
create caches; their success cannot be relabeled S029 zero-write acceptance.
None of these inspected tests was run or modified in this review.

The proposed matrix needs these additional proof layers:

- **Application-level effects:** fail on attempted file/directory mutation,
  writable SQLite opens, schema/repair SQL, subprocess launch and networking.
  Enforce explicit synthetic roots and reject default/environment-root discovery.
  Prevent `.pyc`, log, cache, lock and temporary-file creation, including failures.
- **Native effects:** Python `open` monkeypatches do not cover `ctypes` Windows
  file handles or SQLite's C-level I/O. Use a fixture-scoped OS/VFS-level denial
  or observation mechanism capable of seeing native attempted writes, plus
  inventories. Name the mechanism and supported platform in the evidence; do
  not claim full coverage from Python mocks alone. No tracing was performed here.
- **Content preservation:** record complete root and isolated scratch/home/temp
  inventories before/after every case, including existing DB/WAL/SHM/journal files,
  directories, hashes and relevant metadata. Native attempt guards must catch
  create-then-delete activity that final inventories cannot detect.
- **Positive-control facts:** require a known readable ledger to produce expected
  available XP under the guards. A guard that blocks all SQLite opens and returns
  unavailable has not validated the happy path. Require readable journals and
  correct partial/no-entry percentages too.
- **Permissions and concurrency:** repeat supported cases with writes denied;
  inject safe synthetic source replacement/read errors and unsafe sidecar states.
  Distinguish setup mutations from measured command effects. Record unsupported
  Windows link/permission/native tracing cases as skipped or blocked, never passed.

The command promises no intentional filesystem mutations; the OS may update
read-access metadata, as already excluded by the contract. Per-source checks do
not establish a transactionally atomic snapshot across an entire quarter.
Do not broaden that claim in a summary or test report.

## Readiness and next decision

The contract is feasible as a small CLI slice only with a dedicated quarterly
read orchestration boundary. Existing helpers are building blocks, not a proven
drop-in zero-write aggregator. No source changes, test runs or issue acceptance
completion follow from this document.

Before implementation, settle the narrow journal-reader seam and error mapping,
the explicitly supported settled-SQLite input class, and the native zero-write
verification mechanism. WAL refusal may remain an honest initial limitation;
active-WAL support must not be silently implied. Keep every acceptance item open
until its actual synthetic output and zero-write evidence are observed.
