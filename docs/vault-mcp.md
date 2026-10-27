# Standalone Vault MCP server

S017–S018 implement a local **stdio** process, independent of Obsidian, FastAPI and
the Tauri application. Advertised tools are `read_note` and `search_vault`.
Journal and mission tools are S019. Client adoption is S020;
no write tools are enabled. See the [access contract](vault-mcp-contract.md).

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
generation ID and per-file metadata/digests. Before and after each search, the
server inventories allowed Markdown files and checks metadata, root coverage and
read access. Added, removed, renamed or changed files, changed roots/exclusions,
or previously missing directories appearing invalidate the generation. Matching
files are re-read and digest-checked before snippets are returned.

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
`index_stale` and `internal_error`.

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

No HTTP port, credential, shell tool, model call, automatic sync, XP update or
journal write is exposed. stdout carries only protocol frames. The dedicated
child disables SDK logging because malformed frames may otherwise log private
arguments; stderr contains only static startup/runtime codes. Normal calls are
silent. A client can still send retrieved text to its model/provider; the MCP
process does not control client retention or disclosure.

Each client owns its child process. Closing stdin/disconnecting stops the child;
reconnecting launches a fresh one. Calls have a 10-second cooperative deadline
and run outside the protocol loop, with a four-worker admission limiter. On a
deadline, the response is an error and the loop remains available. An already
blocked OS read cannot be forcibly interrupted by Python thread cancellation;
the client may terminate the child if graceful shutdown stalls, then restart.
No detached worker service is launched.

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

Run with the isolated interpreter:

```powershell
& .tools/mcp-venv/Scripts/python.exe -m pytest backend/tests/test_vault_index.py backend/tests/test_vault_mcp.py backend/tests/test_task_toggle_safety.py backend/tests/test_journal_entry.py -q
```

This verifies the server transport and shared HTTP behavior. It does not certify
Codex or Claude Desktop configuration, personal Drive availability, cross-client
adoption, real-Vault search quality or any write-integrity gate. Those remain S019–S021.

SDK references consulted with Firecrawl on 2026-10-26:
[low-level server](https://py.sdk.modelcontextprotocol.io/advanced/low-level-server/),
[tools](https://py.sdk.modelcontextprotocol.io/servers/tools/), and
[package metadata](https://pypi.org/project/mcp/2.3.0/).
Search semantics follow [SQLite FTS5](https://www.sqlite.org/fts5.html), consulted
with Firecrawl during S018: literal quoted phrases, unicode61 and rank ordering.
