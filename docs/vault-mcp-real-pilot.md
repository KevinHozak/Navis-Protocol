# Real-Vault read-only pilot — 2026-10-27

This is the initial restricted-scope record. NAVIS-S025 subsequently fixed the
serial inventory bottlenecks and expanded the retained connection to all three
roots; see the [broader pilot](vault-mcp-inventory-performance.md) for current
scope, explicit scan budget and source-bound measurements.

**Decision: retain the configured, scoped read-only pilot.** The real Vault was
read through MCP 0.4.0 using the installed desktop-bundled Codex app-server
0.164.0-alpha.11.1. This follows merged PR #12 and closes S021's implementation;
it does not enable journal appends or complete the broader usability evaluation.
The [sanitized report](trials/vault-mcp-real-pilot-2026-10-27.json) contains counts
and timings, with private note text, source names and content digests omitted.

## Configuration

The persistent Codex entry is `navis_vault_readonly`, using the absolute isolated
MCP interpreter and standalone server script in this checkout. It sets
`NAVIS_MCP_ENABLE_JOURNAL_APPEND=0`, allows exactly `read_note`, `search_vault`,
`get_journal_range`, `get_mission`, and explicitly denies `append_journal_entry`.
The timezone is `America/Chicago`.

The permitted scope is October 2026 journals, Documentation, and one existing
canonical mission directory. Its private name is retained only in local
configuration. Broader Journal and Operations access is outside this pilot's
configured scope and will be denied rather than reported as an empty result.

The search index is under `%LOCALAPPDATA%/Navis-Protocol/vault-mcp`, outside both
the Vault and checkout. Its inherited ACL was checked for broad user access:
none was present. The index contains private content and must remain local.
The same directory contains a private pre-change Codex configuration backup and
pilot metadata. No raw note bodies were saved in pilot logs or repository files.

Registration used the installed `codex mcp add` command. Its serialization
removed an existing `node_repl.args` field; the pilot detected that difference,
restored only that missing field from the backup, and verified that all unrelated
configuration values were preserved before completing the new entry's controls.

Configuration follows the [official MCP guide](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
To load it in an already-running desktop connection, restart the server through
Settings → MCP servers and check `/mcp`. This run verified a fresh actual Codex
client connection using the persisted entry; it did not operate the desktop
settings/composer UI or claim that this already-running chat refreshed its tools.

## Measured retrieval

An initial inventory of the broad Journal/Operations/Documentation policy
exceeded a 30-second inventory deadline before publishing an index. That is a
real scale/Drive-cost finding. The server's normal read-call deadline remains
10 seconds; it was not increased to hide the failure. A narrower policy was
selected and then used consistently for indexing and client configuration.

The scoped corpus contained **45 Markdown notes, 138,052 source bytes**. Initial
inventory took **1,339.878 ms** and the complete atomic index build took
**4,037.833 ms**. The published database was **315,392 bytes**. The Codex
connection and discovery took **1,923.1 ms**.

Three repetitions exercised project-documentation keyword search, a source
note read, a seven-day journal range (October 20–26), and a canonical mission
with related context. Returned paths, whole-source byte digests and physical
excerpts were independently checked against direct reads in memory. This is a
retrieval/provenance check, not a human interpretation or answer-quality test.

| Observation | Result |
| --- | --- |
| Unique real sources verified | 14 |
| Search matches per repetition | 5 |
| Journal dates per repetition | 7 present, 0 missing |
| Mission context per repetition | 1 related note; 4 explicit unresolved links |
| Unexpected omissions in the selected workflow | 0 |
| Scoped source hashes changed during setup/pilot | 0 |
| Available tools | Exactly the four read tools |
| Client exit | Clean, code 0 |
| Median search call | 1,679.256 ms |
| Median note read | 41.591 ms |
| Median seven-day journal retrieval | 431.082 ms |
| Median mission/context retrieval | 945.178 ms |

The unresolved links were preserved as unresolved metadata; they were not
silently treated as fetched context. Their private targets and text were not
logged. The report's omission count applies to the checked search results,
selected date range and returned mission sources; it does not claim complete
retrieval of unavailable/out-of-scope linked material or exhaustive search recall.

Only initialization, ephemeral read-only context creation, MCP status and direct
MCP tool RPCs were permitted. No `turn/start`, hosted model generation or journal,
XP, rollover, backup or sync operation was requested. Other servers/plugins were
disabled only for that probe process. The fresh context had no persisted history
path, and the probe preserved the persistent configuration it loaded.

## Remaining evaluation

- Investigate broad-policy inventory cost before expanding search coverage;
  the successful measurements apply to this 45-note scope.
- Review the four unresolved mission links before widening related-note access.
- Collect user feedback and human correction/setup effort. Those measures
  remain unmeasured; automated execution time is not a substitute.
- Verify an interactive desktop connection when loading this server into normal
  use. Claude Desktop and personal journal writes remain outside verified scope.

No Vault files were changed by the pilot. Persistent setup consists of the
local Codex entry and private index. Rebuild the index explicitly with its exact
registered policy after allowed notes change; stale search fails closed while
direct reads remain available. To stop the pilot, disable this server in MCP
settings. Do not remove or rewrite unrelated Codex server configuration.
