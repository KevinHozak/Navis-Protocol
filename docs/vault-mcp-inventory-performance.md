# Broad-Vault inventory and read-only pilot

Follow-up NAVIS-S025 addresses the real-Vault timeout observed after S021.
The initial 45-note pilot is preserved in [its report](vault-mcp-real-pilot.md).

## Cause and fix

A metadata-only walk found 2,160 permitted Markdown notes in approximately
0.8 seconds. The original inventory exceeded 30 seconds after opening only 418
notes: 12.9 seconds were spent opening files and 15.2 seconds repeatedly
resolving paths. These are overlapping profile totals, not additive timings.
Repeated ancestor checks and serial per-file Drive operations dominated traversal.

The inventory now validates path components and exclusions during traversal,
pins directory identities, probes **every** permitted note for readability with
eight bounded I/O workers, then revalidates directories, configured-root
coverage and the Vault root. There are at most sixteen pending probe/snapshot
results per operation. No per-call work is retained as a freshness or permission
cache. Search still inventories the complete allowed scope before and after
querying; a root filter does not hide changes elsewhere in the indexed scope.

Atomic rebuilds snapshot source content with the same bounded I/O pipeline;
only the owner thread writes SQLite. Every content snapshot keeps the shared
pre/post pathname, handle, root, link, size, encoding and digest checks. Raw
short reads are consumed completely; premature EOF fails closed. A second
inventory must still match before a generation can replace the previous one.

On Windows, the index pipeline uses read-only `OPEN_EXISTING` handles with
read/write/delete **sharing**, and `OPEN_REPARSE_POINT`. Sharing grants no write
access to this process. Path/link validation precedes source reads; the final
component is not followed as a link. Unbuffered handles avoid BufferedReader's
initial stream-position query, which was costly on this Drive. Non-Windows
systems use the ordinary read-only path. Ownership transfers from the native
handle to its descriptor exactly once, with cleanup on conversion failures.
The API semantics are documented by
[Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew).

## Honest operation budget

Optimization alone did **not** establish a ten-second guarantee for exhaustive
Drive operations. A complete diagnostic inventory took 10.5 seconds and an
atomic rebuild took 52.9 seconds. The ten-second default remains unchanged.
`NAVIS_MCP_SCAN_TIMEOUT_SECONDS` explicitly selects an integer budget of 1–120
seconds for search, mission discovery/context and the operator rebuild. The
broad pilot selects **60 seconds**, with a 90-second Codex tool timeout. Note and
journal reads retain ten seconds. Invalid budgets reject startup/rebuild rather
than silently removing the bound. OS calls remain cooperatively cancellable;
a blocked filesystem call cannot be forcibly interrupted by Python.

This is a measured I/O optimization plus an explicit budget appropriate for
exhaustive checks. It is not a claim that broad search has become instantaneous.
Sparse metadata, a stale-result TTL or skipped readability checks are not used
to make the latency look lower.

## Broader setup and verification

The retained `navis_vault_readonly` configuration covers all of `Journal`,
`Operations` and `Documentation`. A separate private index lives in
`%LOCALAPPDATA%/Navis-Protocol/vault-mcp-broad`. The former narrow index and a
pre-expansion client configuration backup remain available locally. Only this
server's environment and tool timeout changed; unrelated client settings were
verified unchanged. Journal appends remain disabled by both server environment
and the client tool allowlist/denylist. No model turn or Vault mutation is part
of the pilot.

The broader corpus contains 2,160 notes and 3,085,197 source bytes. One measured
preparation inventoried it in 9,002.528 ms and built the complete atomic index in
50,406.903 ms; the published database was 6,037,504 bytes. These are observations
on this Drive, not universal performance bounds.

The first broad replay verified 14 sources over three repetitions, with no
observed changes across all 2,160 scoped source hashes. Search took 16.9–31.6
seconds and mission/context retrieval took 8.8–15.1 seconds. A final source-bound
replay additionally exercised unfiltered search and an archived journal week.
The [source-bound sanitized report](trials/vault-mcp-broad-pilot-2026-10-27.json)
records three successful repetitions on MCP 0.4.1 and the installed Codex client.
It verified **19 unique real sources**, all seven recent journals, four archived
journals and three genuinely absent archived dates. Four mission links remained
explicitly unresolved. There were zero unexpected omissions in that selected
workflow and zero observed source-hash changes across the full scoped corpus.

| Final replay measure | Median |
| --- | --- |
| Unfiltered search over the broad index | 15,714.832 ms |
| Documentation note read | 43.747 ms |
| Recent seven-day journals | 347.187 ms |
| Archived seven-day calendar range | 301.394 ms |
| Mission with bounded context | 7,444.769 ms |

Search ranged from 15.1–16.8 seconds in the final replay. All calls completed
within the explicit 60-second scan budget. This preserves exhaustive freshness
and readability at a visible latency cost. Only the four read tools were
available, the client exited cleanly, and no model turn was requested. The
archived-date omissions were checked against direct filesystem presence; the
unresolved mission links do not count as fetched context or exhaustive recall.

Fixture regression coverage includes bounded concurrent readability probes,
unreadable nonmatches, directory/file replacement during probes, in-flight
deadlines, path/junction exclusions, stale results, failed-generation retention,
read-only native handles, cleanup, short reads and scan-budget isolation from
ordinary note deadlines. Human correction effort, desktop composer interaction,
simultaneous-client load, cold hydration and multi-device Drive races remain
outside this measured acceptance. The full-corpus source hash comparison records
observed integrity; it does not suppress or stop other Vault writers.

To explicitly rebuild the retained broad index from the repository root:

```powershell
$env:NAVIS_ROOT = 'G:\My Drive\Navis-Vault'
$env:NAVIS_MCP_TIMEZONE = 'America/Chicago'
$env:NAVIS_MCP_ALLOWED_ROOTS = '["Journal","Operations","Documentation"]'
$env:NAVIS_MCP_ENABLE_JOURNAL_APPEND = '0'
$env:NAVIS_MCP_SCAN_TIMEOUT_SECONDS = '60'
$env:NAVIS_MCP_STATE_DIR = Join-Path $env:LOCALAPPDATA 'Navis-Protocol\vault-mcp-broad'
& .tools/mcp-venv/Scripts/python.exe backend/navis_vault_index.py rebuild
```

The client must use this same root/policy/state configuration. Reconnect the
existing desktop MCP connection to load changed code/environment. The measured
pilot used a fresh actual Codex connection, without operating desktop UI.
