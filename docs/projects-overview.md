# Projects overview (#245)

Command → Projects lists repositories accessible to the server/native host's
currently signed-in GitHub CLI account. Install the official GitHub CLI and sign
in on that host before use. No credential entry or OAuth/token export is added
to the browser. The existing Navis HTTP authentication boundary protects the
endpoint; this is a personal-instance server-account integration, not per-browser
GitHub account linking or a multi-user authorization system.

`GET /api/projects` and the packaged native adapter use one shared Python service.
Its fixed read-only GraphQL query goes through `gh api --hostname github.com`.
Discovery includes owner, collaborator and organization-member affiliations,
ordered by push time, with at most two 50-repository pages and a 12-second timeout
per CLI invocation. A visible limit notice distinguishes bounded discovery from
a complete account inventory. Requests have no caller-controlled command, query,
host or credentials. No repository checkout, mutation, AI call or Vault write is
part of the service.

Rows expose description, visibility, archive state, separate open issue and PR
counts, repository/list links and the default branch's latest commit summary/date.
Counts are not inferred from REST's combined issue/PR total. Missing counts stay
unavailable, empty repositories can lack a default-branch commit, and partial
GraphQL results retain usable rows with a warning. Nodes without viewer permission
are omitted. Links are constructed only from validated GitHub repository names and
commit IDs; descriptions and summaries are rendered as text.

There is no persistent repository cache. Refresh and account/transport failures
clear the old snapshot so a previous account's private cards are not retained.
Only a successful current response receives a refreshed time. Rate limit/auth/
timeout failures show a safe diagnostic and manual Refresh, without raw CLI error
bodies, automatic retries, token values or cached private results. A failed later
discovery page fails the snapshot closed; partial fields within a verified response
can still be displayed. No background polling is introduced.

## Verification - 2026-11-03

- 12 Projects backend tests passed: separate counts, links, partial/denied nodes,
  bounded/empty discovery, account changes, timeout/auth/malformed output, fixed
  CLI host/query, HTTP auth and copied packaged adapter with no Vault writes.
- Mounted Projects tests passed loading, partial results, links, empty state,
  auth failure/private-card clearing and unmount races. Full frontend suite and
  lint passed; 81 native tests passed serially. The existing standalone-view
  structural check was updated to include Projects alongside Holocron/Roadmap.
- The live read-only CLI query returned 11 repositories without partial errors;
  only aggregate counts were reported. No private repository snapshot was saved
  into this repository or displayed in the synthetic UI fixtures.
- Release/NSIS 1.11.39 built; executable ProductVersion verified as 1.11.39.
  All 53 Python resources matched source before copied-fixture instrumentation.
  Executable SHA-256: `9bd49ad51bbcfd106f7b5295f64960b9503dda692b4cb331b2d2538c23ae8ad7`.
- Fresh packaged UI used a copied provider transport stub returning synthetic
  GitHub data. Real Command navigation, cards, count/list/commit URLs, dates,
  refreshed time, partial notice, empty discovery, failure and recovery passed.
  Each original synthetic Vault file stayed byte-identical; only deterministic
  Holocron caches were added. Owned fixture app/WebView/web processes were closed.
- The live isolated HTTP endpoint returned two synthetic partial repository rows;
  web startup added only a sector cache and preserved its original fixture files.

**Retained gate:** real browser UI smoke is unverified. The in-app browser helper
repeatedly timed out/reset; the alternate browser connector was unavailable.
Native window discovery also initially timed out, then recovered after tests and
fixture cleanup. Its completed packaged checks do not substitute for browser UI
acceptance. Publish a draft until that gate is resolved or explicitly deferred.
No clean-machine installation or independent external review is claimed.

Cloud generation remains disabled. Fixture launches selected disabled OpenRouter
and removed its key/config values. No inference or personal-Vault access was used.
The standalone #246 title change remains separate delivery history.
