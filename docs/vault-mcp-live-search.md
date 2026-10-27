# Live scoped-search timeout (S026)

The current-chat Documentation search returned `deadline_exceeded` after PR #13.
A later live retry succeeded in **31,250 ms**, so the observed failure was
variable. Its cause was excessive work for the requested scope: the SQL root
filter narrowed results, while both freshness passes still opened all 2,160
indexed notes. The selected Documentation subtree contained only 17 notes.

MCP 0.4.2 bounds both freshness passes to an explicit search root. On the real
Vault, a direct candidate check returned the same query in 778 ms and performed
34 Documentation readability probes, without probing Journal or Operations notes.

## Coverage contract

- Omitting `root` retains whole-policy validation, `index_state: current`, and
  the existing exhaustive scan budget. Large unfiltered queries retain their
  I/O cost and may still encounter an OS/deadline failure.
- Providing `root` validates the complete requested subtree before and after
  querying, including unreadable nonmatches. Results report
  `index_state: current_for_scope`, `requested_root`, `validated_roots` and
  `unvalidated_roots`. `allowed_roots` still describes the configured policy;
  `missing_roots` then describes the validated scope only.
- For example, a Documentation search declares Documentation validated and
  Journal/Operations unvalidated. An unrelated journal edit does not invalidate
  those Documentation results, and those results never claim global freshness.
- In-scope edits, additions, removals, permission failures and post-query changes
  still reject results. Matching source bytes/digests, global index/policy
  identity, exclusions, file/response limits and both inventory passes remain.
- File-prefix filters validate the containing allowed directory. Case-insensitive
  root matching retains actual filesystem spelling; case aliases are discovered
  and rechecked within a bounded metadata walk. Directory/alias changes during
  the query fail closed. No TTL, permission cache or stale excerpt is used.

No schema migration or private-index rebuild is needed for this query change.
The existing configured 60-second scan budget and write-disable controls remain.

## Verification

The affected Python suite passed **217 tests**, with one POSIX case-alias test
skipped on Windows. It covers scoped/unfiltered freshness, unrelated I/O
avoidance, unreadable nonmatches, edits/additions/removals, post-query changes,
Unicode/case and filename-root handling, missing scopes, path/link restrictions,
read-only transport, indexing, retrieval and shared journal/XP regressions.

A fresh actual desktop-bundled Codex app-server 0.164.0-alpha.11.1 connection
using the persisted `navis_vault_readonly` entry discovered MCP 0.4.2 and exactly
four read tools. The [sanitized report](trials/vault-mcp-live-scope-2026-10-27.json)
binds these measurements to normalized source hashes. Three source-verified searches took **291.153, 250.172 and
247.663 ms**. The third used a lowercase root to check canonical casing. Returned
digests and physical excerpts matched direct reads in memory. The private index
was unchanged, the client exited cleanly and no model turn was requested.

After the user restarted only `navis_vault_readonly`, this chat advertised the
new scoped-search contract. Three actual current-chat searches passed in
**284, 247 and 226 ms**, including a lowercase-root query. Each returned one
match with `current_for_scope`, Documentation validated and Journal/Operations
unvalidated. This completes the previously pending post-restart acceptance.
Runtime configuration reloads queue a refresh for loaded threads; see the
[official app-server guide](https://learn.chatgpt.com/docs/app-server).
No desktop UI automation, unrelated server restart, Vault write or additional
provider/model call was performed.
