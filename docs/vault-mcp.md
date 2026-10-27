# Standalone Vault MCP server

S017 implements a local **stdio** process, independent of Obsidian, FastAPI and
the Tauri application. The only advertised tool is `read_note`. Search/index
management is S018; journal and mission tools are S019. Client adoption is S020;
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

The future `NAVIS_MCP_STATE_DIR` is not used by this read-only implementation:
there is no index or other persistent adapter state yet. Missing individual
allowed directories are returned in coverage; unreadable/linked directories
produce an error. Reads never create them. Root replacement or disappearance
fails closed. Restore the original root to recover, or restart to accept a
deliberately changed root identity/configuration.

## Tool and results

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
`deadline_exceeded` and `internal_error`.

## Access and process ownership

Only ordinary allowed `.md` files can be read. Shared path containment is in
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

Run with the isolated interpreter:

```powershell
& .tools/mcp-venv/Scripts/python.exe -m pytest backend/tests/test_vault_mcp.py backend/tests/test_task_toggle_safety.py backend/tests/test_journal_entry.py -q
```

This verifies the server transport and shared HTTP behavior. It does not certify
Codex or Claude Desktop configuration, personal Drive availability, cross-client
adoption, search quality or any write-integrity gate. Those remain S018–S021.

SDK references consulted with Firecrawl on 2026-10-26:
[low-level server](https://py.sdk.modelcontextprotocol.io/advanced/low-level-server/),
[tools](https://py.sdk.modelcontextprotocol.io/servers/tools/), and
[package metadata](https://pypi.org/project/mcp/2.3.0/).
