# S020 read-only retrieval trial — 2026-10-26

**Decision: adopt a controlled read-only pilot on the verified Codex runtime.**
All predefined fixture gates passed. This does not install a permanent client
connection, establish human preference, certify personal-Vault performance or
enable writes. S021 remains a separate guarded-write implementation and
verification gate.

The [rubric](vault-mcp-trial-rubric.md) was written before measurement. The
[sanitized machine report](trials/vault-mcp-s020.json) binds results to normalized
source hashes and observed runtime versions. The [runner](../backend/scripts/vault_mcp_trial.py)
is repeatable and does not request a model turn.

## Actual client and scope

The installed **desktop-bundled Codex app-server 0.164.0-alpha.11.1** connected
to Navis MCP 0.3.0, discovered all four read-only tools, and executed the three
retrieval workflows through Codex's own `mcpServer/tool/call` API. This is an
actual Codex MCP-client connection, not an SDK-only protocol simulation.

The runner used temporary command-line configuration, disabled the user's other
configured MCP servers/plugins in that process, and opened an ephemeral,
read-only technical context. Its returned history path was null. No `turn/start`
request was sent; the RPC allowlist permits only initialization, ephemeral
context creation, discovery and direct MCP calls. The client exited normally,
temporary fixture data was removed, and the persistent Codex configuration hash
was unchanged. No real Vault content, credentials or raw client stderr is in the
committed evidence.

| Client/surface | Observation | Supported scope |
| --- | --- | --- |
| Desktop-bundled Codex app-server 0.164.0-alpha.11.1 | Connected; four tools discovered; all workflows executed. | Verified local MCP runtime on this synthetic corpus. |
| Running desktop settings/composer UI | Not exercised or reconfigured. | No UI-installation or active-chat tool-availability claim. |
| Separately installed Codex CLI 0.162.1 | Version inspected; not the measured client. | No compatibility claim from that inventory alone. |
| Claude Desktop | Not exercised. Claude Code inventory is not Desktop verification. | Unverified and outside the supported adoption scope; no cross-client claim. |

Python was 3.14.8, SQLite 3.50.4, on Windows (`win32`). The experimental Codex RPC
schema was generated from the installed desktop executable before probing it.
Future client/runtime updates require a fresh connection check.

## Comparison

The corpus contained a fictional past decision, seven dated journals, a canonical
mission and its linked context, plus distractor and XP-state sentinel files.
The three workflows required ten unique sources in total: one decision, seven journal
sections, one mission and one context note. An independent golden manifest
checked paths, original-byte digests, physical line ranges and required content.
Oracle tests deliberately corrupt paths, digests, excerpts, line references and
day coverage to verify that incorrect evidence is rejected.

The baseline used `rg` discovery followed by direct file reads, canonical dated
journal reads and explicit mission/context reads. The candidate used
`search_vault`, `read_note`, `get_journal_range` and `get_mission`. The routes ran
in alternating order for five repetitions; validation occurred outside the
timed retrieval interval. The baseline is the practical direct file/search
workflow, not the old skill index whose limitations were recorded in S016.

| Measure | Direct file/search | Codex MCP |
| --- | --- | --- |
| Median whole-workflow retrieval | 89.991 ms | 506.678 ms |
| Nearest-rank p95 (maximum of five) | 98.831 ms | 524.515 ms |
| Required sources correct | 10 per repetition | 10 per repetition |
| Unexpected evidence omissions | 0 | 0 |

MCP was slower on this fixture, while remaining below the predefined two-second
warm-workflow gate. Adoption is for a consistent, bounded, source-linked access
boundary; these measurements do not demonstrate a speed improvement or answer
quality advantage. There was no human or language-model interpretation task.

## Freshness, integrity and operating effort

- Initial private index build: **357.248 ms**. Codex client connection/discovery:
  **3,327.289 ms**, measured separately from retrieval.
- After the runner deliberately edited the synthetic decision, search returned
  `index_stale` without an excerpt. Explicit rebuild plus retry recovered the new
  evidence in **597.045 ms**, representing two operator actions.
- Human correction time is **not measured**. No incorrect retrieval result
  required an evidence correction; the recovery timing above is a scripted
  freshness exercise, not human task time.
- File hashes were unchanged after all ten-source comparisons. After recovery,
  only the deliberately edited decision differed. Journals and XP-state
  sentinels were unchanged. Only read tools were advertised/called.
- Ongoing maintenance requires a private state directory and explicit rebuilds
  after source/policy changes. Direct note/journal/mission reads remain available
  when search is stale. Real-Vault rebuild cost, Drive hydration and human setup
  effort are unknown.
- Dependency installation was already completed during earlier implementation;
  it is not included in these setup timings. An initial launcher override-key
  quoting error was diagnosed and corrected before the accepted run; it was not
  a Navis-server failure. Exploratory measurements were not pooled with the
  final source-bound run.

## Repeat and operate

Install the declared isolated MCP/test dependencies as described in the
[operating guide](vault-mcp.md). Select the absolute executable path of the
intended desktop-bundled Codex runtime and verify its `--version`. Set
`$codexClient` to that path and `$trialDirectory` to a private directory outside
the checkout and personal Vault, then run:

```powershell
& .tools/mcp-venv/Scripts/python.exe backend/scripts/vault_mcp_trial.py --codex-executable $codexClient --work-directory $trialDirectory --report (Join-Path $trialDirectory 'result.json')
```

The runner creates only its own disposable fixture subtree/private index. It
does not register a permanent server, call a model or read the personal Vault.
Its report records the exact executable version and source identity. CLI
overrides with dotted existing server/plugin IDs are rejected rather than
guessed. Review a changed runtime/schema before extending the RPC allowlist.

For a subsequent user-approved personal-Vault pilot, follow the operating guide
to select allowed roots/exclusions and private state, build the index, then add
the absolute interpreter/script and those environment variables through the
desktop MCP settings or CLI. Restart the connection and independently verify
the tool list. That persistent configuration step was not performed by this
trial. Retain direct file access as a fallback while evaluating maintenance and
human correction effort. Retrieved text can reach the configured client's model;
local stdio is not a client-retention guarantee.

Official configuration reference consulted through Firecrawl:
[MCP in local Codex clients](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
It documents stdio commands, environment variables and client configuration.
The exact experimental RPC methods used here came from the installed binary's
generated schema, not an assumed web API contract.
