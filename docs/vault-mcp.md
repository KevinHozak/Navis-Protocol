# Standalone Vault MCP server

S017–S019 implement a local **stdio** process, independent of Obsidian, FastAPI and
the Tauri application. Advertised tools are `read_note`, `search_vault`,
`get_journal_range` and `get_mission`. The S020
[trial report](vault-mcp-trial-results.md) adopts a controlled read-only pilot on
the verified desktop-bundled Codex runtime; desktop UI setup and real-Vault scale
remain unverified. S021 adds an explicitly enabled journal append tool; the
default tool set remains read-only. See [guarded appends](vault-mcp-journal-appends.md)
and the [access contract](vault-mcp-contract.md).

The [2026-10-27 real-Vault pilot](vault-mcp-real-pilot.md) subsequently configured
a restricted read-only Codex connection and verified real source provenance.
Its measured scope is 45 notes; broad-policy inventory exceeded its deadline.
See that report for the retained configuration, scope and remaining human checks.
The subsequent [inventory fix and broader pilot](vault-mcp-inventory-performance.md)
expanded the retained read-only connection to 2,160 notes across Journal,
Operations and Documentation, using an explicit 60-second scan budget.

## Install and launch

Use Python 3.11+ and a dedicated virtual environment. Run from the repository
root on Windows:

```powershell
python -m venv .tools/mcp-venv
& .tools/mcp-venv/Scripts/python.exe -m pip install -r backend/requirements-mcp.txt
$env:NAVIS_ROOT = 'G:\My Drive\Navis-Vault'
$env:NAVIS_MCP_TIMEZONE = 'America/Chicago'
& .tools/mcp-venv/Scripts/python.exe backend/navis_vault_mcp.py
```

The process waits for newline-delimited MCP JSON-RPC on stdin. This is not an
interactive terminal application. A local MCP client should launch the absolute
interpreter path with the absolute script path as its argument, supplying the
environment variables below. No client configuration was installed by S017.
The SDK is pinned to `mcp==2.3.0`; `tzdata==2026.5` supplies IANA zones on Windows.
Install test-only dependencies from `backend/requirements-test.txt` in an isolated
environment when running regressions, not in the portal's runtime environment.

| Variable | Behavior |
| --- | --- |
| `NAVIS_ROOT` | Required absolute existing readable Vault directory. No fallback or directory creation. |
| `NAVIS_MCP_TIMEZONE` | Required valid IANA timezone. Used for future journal tools; explicit note lines have no date conversion. |
| `NAVIS_MCP_ALLOWED_ROOTS` | Optional JSON array of relative directories. Default: `["Journal","Operations","Codex","Documentation"]`. Empty or malformed configuration is rejected. Maximum 32 roots, each at most 1,024 characters. |
| `NAVIS_MCP_DENIED_PATHS` | Optional JSON array of relative subtrees or files to exclude. Default `[]`. Denials override allowed roots. Same count/path limits as allowed roots. |
| `NAVIS_MCP_STATE_DIR` | Required for search/rebuild: absolute private directory outside both the Vault and checkout, containing `vault-index.db`. It must not be an ancestor of either root. Direct note reads work without it. |
| `NAVIS_MCP_ENABLE_JOURNAL_APPEND` | Only the exact value `1` advertises/enables `append_journal_entry`. Unset by default. Requires an existing allowed journal, expected SHA and stable request ID. See the guarded-write guide before opting in. |
| `NAVIS_MCP_SCAN_TIMEOUT_SECONDS` | Optional integer 1–120, default 10. Explicit budget for exhaustive search/mission discovery and the operator rebuild command. The broad real-Vault pilot uses 60; note/journal reads retain their ten-second limit. Set the client's tool timeout higher than this scan budget. |

Missing individual allowed directories are returned in coverage; unreadable/linked directories
produce an error. Reads never create them. Root replacement or disappearance
fails closed. Restore the original root to recover, or restart to accept a
deliberately changed root identity/configuration.

## Build and refresh the private search index

Run the operator command explicitly, using the same roots/exclusions as the MCP
client. The MCP server never creates or refreshes an index during a tool call:

```powershell
$env:NAVIS_MCP_STATE_DIR = Join-Path $env:LOCALAPPDATA 'Navis-Protocol\vault-mcp'
& .tools/mcp-venv/Scripts/python.exe backend/navis_vault_index.py rebuild
```

This example inherits the configured `NAVIS_ROOT`, timezone and access policy
from the launch instructions. The command creates the state directory if absent,
builds a temporary SQLite FTS5 database there, and atomically replaces the last
complete generation only after a second source-inventory check. Failed builds
retain the prior database. It never changes Vault files. The directory contains
private note text: use a location restricted to your OS account (Windows inherits
the selected directory's ACLs; POSIX requires an owner-only state directory).
Do not put it in a shared/synced folder. Symlink/junction state paths are denied.
An interrupted process may leave a private temporary file; it is never treated
as a published generation.

Each generation records a schema/policy/root fingerprint, build time, opaque
generation ID and per-file metadata/digests. Search without `root` inventories
all configured Markdown roots before and after the query and reports `current`
only when that complete inventory matches. With an explicit `root`, both passes
validate that subtree and report `current_for_scope`, `validated_roots` and
`unvalidated_roots`. Missing-root coverage then applies to the validated scope;
other roots are not certified fresh. Added, removed, renamed, changed or unreadable
files within that scope still fail closed. Policy/index identity remains global,
and matching files are re-read and digest-checked before snippets are returned.
See [live scoped-search verification](vault-mcp-live-search.md).

`index_unavailable` means a missing, corrupt or unsupported database/configured
state location; `index_stale` means it no longer matches the current source or
policy. Neither returns snippets. After resolving the source/configuration
problem, run `rebuild` again. A valid current index with no matches returns a
successful empty list. Unreadable sources return `source_unreadable`, and an
unavailable root returns `vault_unavailable` even if an old index exists.
Direct `read_note` remains usable with a missing or stale index.

Bounds apply to both rebuild and search: 20,000 notes, 50,000 directory entries,
64 MiB of source bytes, 1 MiB per note and a 10-second cooperative work deadline.
Reaching a bound fails explicitly; incomplete coverage is not presented as no
matches. SQLite queries also have a progress deadline. State databases over
256 MiB are rejected. Normal filesystem edits are detected by metadata; deliberate
same-size/mtime edits of non-matching files and adversarial changes by another
process with the same OS access are outside this freshness guarantee. Matching
files always undergo a byte-digest comparison. Search latency/adoption on the
personal Vault remains an S020 trial, not a performance claim here.

## Tool and results

`get_journal_range` accepts inclusive `start_date`/`end_date` in strict
YYYY-MM-DD format, optional exact `section`, and `max_chars_per_day` (default
4,000, maximum 8,000). The range is at most 31 days. Dates resolve literally to
`Journal/YYYY/MM/YYYY-MM-DD.md`; the configured timezone is returned without
applying the recurring-task 03:00 cutoff or converting dates through host time.

The response lists chronological `journals` with source metadata and per-note
truncation/continuation, plus explicit `missing_dates`. The Journal directory
must be readable; a missing year/month/day is ordinary absence, while denied,
linked or unreadable paths remain errors. A missing selected section is
`section_not_found`, not a missing day. No journal is created. When the aggregate
byte budget fills, `continuation.next_date` identifies the first unprocessed
date: start a new range there, retaining the original end date. Per-day content
may also be truncated by the shared 200-line/byte limit; use that day's
`read_note` continuation for the remaining content. Empty journals retain empty
content with null source line ranges.

`get_mission` accepts exactly one of `name` or canonical `path`. Name lookup
uses exact directory names under
`Operations/<region>/{Main,Side}/<name>/Mission.md`; optional exact `region` and
`mission_type` narrow that lookup. Path lookup requires that canonical structure
and cannot be combined with name/region/type. `related_limit` defaults to 3 and
is bounded to 0–5. Names and regions are individual path components, not fuzzy
searches. Both Main and Side missions are supported, without building the
portal's sector cache.

Multiple matching missions return MCP `isError` with `ambiguous_mission`, a
bounded list of allowed relative `candidates` (maximum 20), and a candidate
`truncated` flag. Nothing is selected automatically. No matching allowed mission
is `not_found`. A missing/unreadable Operations area during name discovery is
`source_unreadable`; a missing explicit mission path is `not_found`. Discovery
is bounded by the shared deadline and 50,000 inspected directory entries.

Mission responses include the selected mission's source excerpt (at most 8,000
characters), source-linked `related` notes (at most 2,000 characters each),
`unresolved_links` and `related_truncated`. All excerpts also retain shared
line/byte limits and continuation metadata. Related context comes only from
recognized Markdown links or Obsidian wiki links in the **returned mission
excerpt**, excluding fenced/inline code. Anchors/aliases do not change the
linked note read. Simple Markdown targets, including angle-bracket targets with
spaces, are recognized; this is not a full CommonMark reference-link parser.

Path links are checked relative to the mission folder and Vault root; different
allowed matches are ambiguous. Bare note names are matched across a bounded,
live allowed-file inventory without requiring an index. Ambiguous links are
reported unresolved. Denied/missing/external links disclose no additional target
in the unresolved metadata, only a recognized-link index and safe code. No
external URL is fetched, and related notes' own links are never expanded. Duplicate
and self links are not read twice. `related_truncated` reports omitted recognized
links; a truncated mission excerpt may contain additional uninspected links.
Setting `related_limit: 0` avoids related-note inventory/reads entirely.

`search_vault` accepts `query` (1–512 characters), optional allowed relative
`root`, and `limit` (default 10, maximum 20). Whitespace-separated keyword terms
are ANDed; double quotes group a phrase. FTS5 unicode61 tokenization handles case
and punctuation; raw FTS/SQL operators are not accepted as operators. For example,
`red OR blue` requires the literal words red, OR and blue; `"red blue"` requires
that token phrase. Empty/unclosed quotes and tokenless terms are rejected.

Matches are ordered by FTS relevance and relative path. Each includes a live
snippet of at most 500 characters, relative path, exact physical line range and
starting column, nearest heading, original-byte digest and modification time.
Coverage includes `index_state: current`, generation and indexed-at time. Results
are bounded by the shared byte budget; `truncated` reports further matches or
response-budget omissions. There is no search cursor: narrow the query/root or
use `read_note` for more context. A snippet can show the first matching term
without showing every ANDed term elsewhere in that note.

`read_note` accepts `path`, optional `section`, `start_line` (default 1),
`start_column` (default 0) and `max_lines` (default 100, maximum 200). The section
is exact ATX Markdown heading text, without the `#` prefix. Its subtree ends at
the next heading of equal or lesser depth. Headings inside fenced code do not
count. Repeated matching headings require a line-based read instead.

`start_line` always identifies a physical source line; `start_column` is a
zero-based Unicode character offset within that line. Pass the returned
`continuation` fields into the next call to resume long lines without data loss.
Do not concatenate different source revisions: compare `sha256` across pages
and restart if the note changed. Section selection intersects the requested
line range. Empty notes/reads past EOF return null line ranges and no continuation.

Successful envelopes contain `status`, `data`, `coverage`, `truncated` and
`continuation`. Source data includes the relative path, excerpt, physical line
range, heading, UTC modification time and SHA-256 of the original bytes. UTF-8
with an optional BOM is accepted; original content and CR/LF endings are retained.
The server reads at most 1 MiB per file and fits both text and structured results
under 64 KiB serialized. Large excerpts are paged; oversized coverage metadata
returns `response_too_large` rather than silently omitting access limits.

Tool errors have MCP `isError: true` and a safe `error.code`/`retryable` envelope.
Unknown tools are `unknown_tool`; extra fields, wrong types and invalid limits
are `invalid_argument`. Malformed protocol frames are handled by the SDK, separate
from tool errors. Unavailable Vaults are not reported as empty notes. Other
errors include `not_found`, `source_unreadable`, `source_changed`,
`unsupported_encoding`, `file_too_large`, `section_not_found`,
`deadline_exceeded`, `inventory_limit_exceeded`, `index_unavailable`,
`index_stale`, `ambiguous_mission` and `internal_error`.

## Access and process ownership

Only ordinary allowed `.md` files can be read or indexed. Shared path containment is in
`backend/services/vault_paths.py`; the HTTP wrapper preserves its existing
responses. The MCP policy adds allow/deny roots, hidden/secret/config/backup
exclusions, Windows device/short-name alias rejection and symlink/junction/reparse
point denial, including all ancestors of the configured root. All paths are
checked again after opening. A denial and a missing note both return `not_found`.
The policy is designed for a trusted local filesystem; it is not isolation from
another process with the same OS account racing filesystem changes. It does not
detect secrets embedded inside otherwise allowed notes. Configure exclusions
before connecting a client to personal data.

No HTTP port, credential, shell tool, model call or automatic sync is exposed.
Default read tools never write journals or XP. The opt-in append tool reconciles
the existing XP ledger after a confirmed save. stdout carries only protocol frames. The dedicated
child disables SDK logging because malformed frames may otherwise log private
arguments; stderr contains only static startup/runtime codes. Normal calls are
silent. A client can still send retrieved text to its model/provider; the MCP
process does not control client retention or disclosure.

Each client owns its child process. Closing stdin/disconnecting stops the child;
reconnecting launches a fresh one. Read calls have a 10-second cooperative deadline
and run outside the protocol loop, with a four-worker admission limiter. On a
deadline, the response is an error and the loop remains available. An already
blocked OS read cannot be forcibly interrupted by Python thread cancellation;
the client may terminate the child if graceful shutdown stalls, then restart.
No detached worker service is launched.
An enabled mutation waits for its worker instead of abandoning a writer at the
read deadline. A blocked Drive operation can delay it; after terminating a child,
retry the exact same append request ID, expected hash and payload.

## Verified scope

Disposable-fixture acceptance uses a real Windows stdio child: initialization,
tool listing, note reads, unknown tools/fields, Vault disappearance, ping after
errors, EOF shutdown and fresh-process reconnect. Policy tests cover traversal,
drives/UNC, device aliases, denied roots, real symlinks/junctions, encoding,
oversized files, edited-during-read metadata, sections and lossless Unicode
continuation. In-memory SDK checks cover deadline recovery. Fixtures retain
their original bytes; logs are checked for synthetic private/credential markers.

S018 additionally verifies literal keyword/phrase retrieval, fresh/no-match versus
stale/unavailable states, failed-generation retention, source-span provenance,
excluded text absence from SQLite, Unicode snippet budgets and real CLI/stdio
searches. It also fixes plural credential/secret-name exclusions and preserves
heading names such as C# and headings after fenced code.

S019 adds fixture acceptance for inclusive month/year/leap-day ranges, maximum
calendar dates, missing journals versus denied/unreadable paths, range byte
pagination, source continuations, Main/Side missions, duplicate names, bounded
ambiguous candidates, internal-only related notes, Unicode paths, no recursion
and real stdio retrieval without an index. Fixture journals, XP-state sentinels
and other existing Vault bytes remain unchanged. Internal path handling now
protects literal percent escapes without inflating Unicode paths through URL
encoding before applying character-count bounds.

Run with the isolated interpreter:

```powershell
& .tools/mcp-venv/Scripts/python.exe -m pytest backend/tests/test_vault_retrieval.py backend/tests/test_vault_index.py backend/tests/test_vault_mcp.py backend/tests/test_task_toggle_safety.py backend/tests/test_journal_entry.py -q
```

This verifies the server transport and shared HTTP behavior. It does not certify
Codex or Claude Desktop configuration, personal Drive availability, cross-client
adoption, real-Vault retrieval quality or any write-integrity gate. S020 separately verifies
the actual Codex MCP runtime on synthetic data, without installing a permanent
connection; human usability and production behavior remain unmeasured.

SDK references consulted with Firecrawl on 2026-10-26:
[low-level server](https://py.sdk.modelcontextprotocol.io/advanced/low-level-server/),
[tools](https://py.sdk.modelcontextprotocol.io/servers/tools/), and
[package metadata](https://pypi.org/project/mcp/2.3.0/).
Search semantics follow [SQLite FTS5](https://www.sqlite.org/fts5.html), consulted
with Firecrawl during S018: literal quoted phrases, unicode61 and rank ordering.
