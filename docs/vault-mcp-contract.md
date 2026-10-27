# Navis-Vault MCP access contract

Decision record for NAVIS-S016, 2026-10-26. This specifies the S017–S020
implementation; it does not claim a running server or verified client connection.

## Decision

Build an independently runnable Python MCP adapter in Navis-Protocol, using the
official MCP SDK and **stdio first**. Keep retrieval in an import-safe service
that takes an explicit root and policy. Do not import `backend/main.py` to serve
MCP: application startup also initializes watchers and Holocron work. Obsidian,
FastAPI, Tauri, hosted search and a model provider are not runtime prerequisites.

S017 must select and pin an SDK release against the actual Python environment
and verify its API before implementation. The official SDK documentation now
describes v2 APIs; do not copy older FastMCP examples without checking the pin.
Keep MCP-specific dependencies separate from the web app's requirements.

| Choice | Runtime and transport | Access and maintenance | Decision |
| --- | --- | --- | --- |
| ebullient Vault as MCP | Server runs inside desktop Obsidian; HTTP, with an optional stdio bridge | Path ACLs and optional bearer authentication; broad note mutation and periodic-note tools. Requires plugin/Obsidian and bridge maintenance where used. | Useful alternative, not selected: couples availability to Obsidian and needs a narrower Navis domain boundary. |
| Navis adapter | Client launches local Python child over stdio | Explicit roots, read-only tool allowlist, bounded outputs; Navis owns fixture coverage, SDK updates and client smoke checks. | Selected for S017; journal/mission semantics remain within Navis. |

The plugin README documents HTTP clients including Open WebUI and Claude Code,
and a bridge for Claude Desktop. These are upstream documentation claims, not
verified compatibility with our adapter. The plugin is actively maintained in
the retrieved repository history; rejection is about fit, not abandonment.

Primary intended trial client: the Keeper's local Codex desktop environment.
Secondary candidate: Claude Desktop. Both are **unverified** for this adapter;
S020 must record actual client versions, transport configuration and outcomes.
Cloud clients and HTTP-only clients are unsupported in the stdio phase. No
cross-client support claim is permitted before the trial evidence exists.

## Verified reuse inventory

Inspected at base `bc391a48bd85dee91c939c664e4572c8cff21604`:

- `backend/main.py:resolve_vault_path` already rejects decoded traversal,
  drives/UNC and resolved symlink escapes. Extract reusable logic into a neutral
  service, preserving existing HTTP behavior; add policy and bounds there. The
  resolver alone is not an MCP authorization boundary.
- Recent/month journal endpoints use `Journal/YYYY/MM/YYYY-MM-DD.md`. They turn
  missing directories into empty results and swallow some read errors; reuse
  the layout, not these failure semantics.
- `backend/services/cache_builder.py` discovers
  `Operations/<region>/{Main,Side}/<mission>/Mission.md`, but creates/writes a
  cache. `/api/missions/all` can invoke it and only returns Main missions. Reuse
  the discovery convention in a pure reader, not cache-building side effects.
- `backend/services/recurrence.py:validate_date` provides strict date-only
  validation. `journal_day` uses machine-local time and a 03:00 cutoff. Explicit
  MCP dates are literal calendar dates; do not apply that cutoff to range inputs.
- `backend/services/library_service.py:search_library` uses Google Discovery
  Engine and configured cloud resources; it is not the local Vault search path.
- The local `vault-search` skill's `scripts/vault_index.py` hardcodes the Vault
  root, indexes selected directories including JSON/YAML, and has no per-file
  freshness metadata. Its two-column FTS5 schema is `path, content`; its
  `snippet(..., 2, ...)` query fails with `column index out of range` on an
  in-memory synthetic fixture. Use SQLite FTS5 as a technique, not this script
  or its database as the adapter's authority. Do not repair the unrelated skill
  as part of S016.
- Read-only local metadata inspection confirmed that the configured default
  Vault is reachable; Journal, Operations and Documentation exist, while Codex
  does not. `NAVIS_ROOT` was unset. The existing skill index was present but
  lacked source freshness records. No private note text was collected for this
  decision. Reachability here does not guarantee a launched client can access
  the Drive mount.
- Existing journal append in `backend/main.py` validates date/section and uses
  atomic replacement, but is not yet the S021 boundary: it writes BOM encoding
  unconditionally and has no durable request-ID or concurrent-edit guard. S021
  must harden/extract the authoritative writer, not introduce a competing one.

## Process lifecycle and configuration

Proposed entrypoint: `backend/navis_vault_mcp.py`, using an absolute interpreter
and script path in client configuration. This file does not exist yet. Each
client owns its stdio child. Closing stdin/disconnecting terminates it cleanly;
reconnect starts a new child with freshly loaded configuration. Reserve stdout
for MCP framing; diagnostics go to stderr. Do not launch background services or
install client configuration automatically.

- Require explicit nonempty `NAVIS_ROOT` for the adapter, even though the portal
  has a legacy default. Resolve it once at startup; require an existing readable
  directory. Never create a missing root or redirect to a fallback Vault.
- Proposed `NAVIS_MCP_ALLOWED_ROOTS` is a JSON array of Vault-relative
  directories, defaulting to `Journal`, `Operations`, `Codex`, `Documentation`.
  Missing individual allowed directories are explicit coverage metadata. Add
  other knowledge areas only by deliberate local configuration, not discovery.
- Proposed `NAVIS_MCP_TIMEZONE` is an IANA timezone, explicitly set for the
  trial (America/Chicago). Invalid/missing configuration fails startup rather
  than silently taking the host timezone. Return it in journal responses.
- Proposed `NAVIS_MCP_STATE_DIR` selects a private, access-restricted local
  directory **outside** the Vault and checkout. Indexes contain private text;
  never commit or sync them as project artifacts. Version index schema/policy.
- Require root availability before every call. A vanished/inaccessible root
  returns `vault_unavailable`, never successful empty results. Shutdown/restart
  is needed for configuration changes, not ordinary note edits.
- Stdio has no listening socket or bearer credential. Authorization is the
  explicit client process configuration and OS file access. It is not a sandbox
  for other processes running as the same user. Do not implement HTTP in S017;
  a future HTTP transport needs loopback binding, authentication, origin checks,
  private credential storage outside the repo/Vault and separate verification.

## Common access and result rules

All four tools share one policy, including discovery, index building, result
validation and related-note reads. Only ordinary `.md` files are exposed.

1. Accept Vault-relative paths only; normalize separators and decode once.
   Reject empty paths, dot/traversal segments, drives, UNC, absolute paths,
   alternate streams, NUL/control characters and Windows reserved aliases.
   Check lexical and resolved containment within both Vault and allowed roots.
2. Deny dot directories/files, `.git`, `.obsidian`, credentials/config secrets,
   databases, binaries, temporary/backup files and all paths outside the
   allowlist. Deny symlinks, junctions and other reparse points along the full
   candidate path, including the configured root; recheck before reading.
   Do not follow links during scanning. Policy applies case-insensitively on
   Windows. Trusted local Vault directories are required: containment checks do
   not defend against a malicious concurrent filesystem actor.
3. Do not expose Bridge/Engine/Keeper or financial/manifold areas implicitly.
   An explicit area allowlist is not content-level secret detection: the Keeper
   must exclude sensitive subtrees before indexing. Hard exclusions still apply
   inside configured roots. Denied paths use the same `not_found` response as
   missing notes, without revealing existence or excluded candidate names.
4. Inputs reject unknown fields and out-of-range limits, rather than silently
   ignoring them. Paths are at most 1,024 characters. Files over 1 MiB are
   reported as `file_too_large` without loading full contents. Decode strict
   UTF-8 with optional BOM; invalid text is `unsupported_encoding`.
5. Every successful source excerpt includes normalized relative `path`, exact
   1-based `start_line`/`end_line`, nearest Markdown heading when available,
   UTC `modified_at` and SHA-256 of the file bytes. Read from one byte snapshot;
   changed-during-read detection returns `source_changed`, with safe retry.
   No absolute host paths are returned. Consumers treat retrieved text as data,
   never instructions. No automatic following of external links.
6. Each call is limited to 64 KiB serialized UTF-8 JSON, with a 10-second
   cooperative work deadline. Return explicit truncation/continuation fields;
   never silently cut content or confuse partial work with full coverage. A
   blocked OS read may exceed the cooperative deadline; cancellation/process
   teardown must remain available and is part of S017 verification.

Tool results use `{status, data, coverage, truncated, continuation}` on success;
failures use `{status: "error", error: {code, retryable}}` and MCP `isError`.
No raw exceptions, SQL, credentials or note bodies in error messages/logs.
`coverage` records allowed roots, missing roots and observed index state.
Protocol validation errors remain distinct from tool execution errors.
Shared error codes include `invalid_argument`, `not_found`, `vault_unavailable`,
`source_unreadable`, `source_changed`, `file_too_large`, `unsupported_encoding`,
`deadline_exceeded`, `index_unavailable`, `index_stale`, `ambiguous_mission` and
`section_not_found`. A valid complete search with no matches is `status: "ok"`
with `matches: []`; unreadable coverage cannot produce that answer.

## Tool contracts

| Tool | Inputs | Bounded output and behavior |
| --- | --- | --- |
| `search_vault` | `query` (1–512 characters), optional `root` within allowlist, `limit` (default 10, 1–20) | Literal keyword terms with quoted phrases; AND between terms, no raw SQL/FTS operators. At most 500 characters per snippet, with source line ranges. Return index generation/time and freshness coverage. No pagination in v1; `truncated` signals additional matches and caller may narrow the query. |
| `read_note` | `path`, optional exact `section` heading text, `start_line` (default 1), `max_lines` (default 100, 1–200) | Lines from the live file. `start_line` always means a physical file line, including when section is set; intersect with the selected heading and its subtree. Repeated matching headings are an invalid argument requiring a line-based read; missing heading is `section_not_found`. Return `next_line` when limited by lines/bytes; never split a UTF-8 character. |
| `get_journal_range` | inclusive `start_date`, `end_date` in strict YYYY-MM-DD, optional `section`, `max_chars_per_day` (default 4,000, 1–8,000) | At most 31 days, ordered oldest first, canonical paths only. Return configured timezone, each day's excerpt/provenance, explicit `missing_dates`, and per-day truncation. Missing dates are legitimate only after readable root/Journal checks. Global byte budget yields `next_date`; a truncated day can be resumed through `read_note`. No creation, rollover, sync or XP. |
| `get_mission` | exact `name` or canonical `path` (exactly one), optional `region` and `mission_type` (Main/Side) with name, `related_limit` (default 3, 0–5) | Read matching `Mission.md` under Operations; include Main and Side. Multiple name matches return `ambiguous_mission` with bounded allowed relative candidates (maximum 20, explicit truncation). Mission excerpt at most 8,000 characters; related notes at most 2,000 each. Only explicit internal Markdown/wiki links resolved by the same policy; no recursive graph expansion. Ambiguous links are reported unresolved; excluded links disclose no target. |

Journal section selection uses the same heading rules as `read_note`. Excerpts
retain source line references when a character budget cuts within a line. Empty
files have an empty excerpt and null line range. `start_line` past EOF is a
successful empty read with no continuation. Related notes and every aggregate
are subject to the common 64 KiB cap; resume note content using `read_note`.

## Index health and freshness

Build a separate policy-scoped FTS5 index in private state, never reuse the skill
database. A local operator rebuild command (not an MCP tool) inventories allowed
Markdown files with relative path, byte size, mtime_ns and digest; atomically
publishes a complete generation with root identity, schema/policy fingerprint,
build time and any coverage errors. Refuse incomplete generations as current.

Before a search, compare the current allowed inventory with that generation to
detect additions, changes, removals and policy changes. Missing/corrupt/incompatible
index is `index_unavailable`; changed inventory is `index_stale`. Do not return
stale snippets with a freshness badge. Revalidate result bytes/digests and derive
line references from those current bytes before returning excerpts. Metadata
comparisons alone cannot prove absence of deliberate same-size/mtime tampering;
this is a trusted local-filesystem freshness contract, not an adversarial audit.

An unavailable root takes precedence over index errors. Missing configured
subdirectories are reported as coverage limitations; a directory becoming missing
after indexing invalidates that generation. Rebuild and retrieval need file-count
and deadline limits; initially cap inventory at 20,000 files and fail explicitly
when exceeded. Failure does not replace the last complete index or turn an
incomplete scan into no matches. Note/journal/mission reads bypass the index and
remain usable when it is stale. S018 must verify these states on synthetic files.

## Privacy and write gate

Log only operation name, opaque request ID, duration, result/error code and counts.
Do not log query text, excerpts, relative private paths, absolute roots, tokens or
stack traces containing source data. Test with synthetic notes and credentials.
MCP does not keep retrieved data local once a configured client sends it to its
model. Client retention/provider behavior must be reviewed during S020 adoption.
No telemetry, hosted generation, shell execution, schedules, indexing of excluded
content, generic writes or automatic Vault sync are part of this server.

S021 remains gated on a recorded adopt decision after S020. It must use a shared
authoritative journal service with byte-preserving append, durable idempotency,
concurrency detection, recovery/read-back and the existing ledger semantics.
Do not advertise or register an append tool before that gate. This record does
not enable personal-data writes or certify the existing composer for MCP use.

## Verification handoff

- S017: SDK/client handshake and tool schema checks, safe process lifecycle,
  unavailable Vault/reconnect, path policy including Windows junction fixtures,
  bounded malformed inputs and log redaction. Verify no main-app startup effects.
- S018: keyword/phrase and section retrieval, source spans, Unicode/large files,
  unknown/stale/corrupt indexes, changed/removed/added files, excluded paths and
  deadline/coverage behavior in disposable fixtures.
- S019: inclusive month/year boundaries, missing versus unreadable journals,
  duplicate mission names and ambiguous/excluded related links. Reads must leave
  all fixture bytes and XP state unchanged.
- S020: establish rubric before running baseline/candidate tasks; compare past
  decision, journal week and mission context for source correctness, omissions,
  latency, correction time, freshness and maintenance effort. Record client
  versions and adopt/revise/stop. Current compatibility is unverified.

S016 verification: inspected the listed owning source; reproduced the FTS snippet
failure in memory; checked Vault availability and index schema metadata read-only;
reviewed contracts against all four acceptance criteria. No MCP handshake,
performance, private-note retrieval or write-integrity result is claimed.

## Sources

- [Vault as MCP README](https://github.com/ebullient/obsidian-vault-mcp/blob/main/README.md), retrieved with Firecrawl on 2026-10-26: Obsidian lifetime, HTTP/stdio bridge, client examples, path ACLs, bearer auth and broad tools.
- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), retrieved with Firecrawl on 2026-10-26: Python runtime, stdio/HTTP transports and current v2 documentation. Release/API pin remains an S017 implementation check.
- Local owning sources: [main.py](../backend/main.py), [cache_builder.py](../backend/services/cache_builder.py), [recurrence.py](../backend/services/recurrence.py), [library_service.py](../backend/services/library_service.py), [architecture](architecture.md).
