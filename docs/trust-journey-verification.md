# Integrated trust journeys - S015

S015 remains in progress. PR #21 merged at `17c23ca`, completing S010's scoped
repair. The original S009 probes describe historical defects; they are not a
current acceptance suite. This report reconciles those findings with delivered
repairs and keeps unavailable runtime acceptance explicit.

| Finding | Delivered repair | Evidence and current disposition |
| --- | --- | --- |
| T01/T02 Holocron facts and availability | S013, PR #18; S011, PR #19 | [Evidence](holocron-evidence.md), [availability](journal-availability.md). Earlier packaged source inspection, missing-source handling and exact source navigation passed. Real browser now confirms 2/2 checked items, unavailable readiness/combat/focus, and keyboard source navigation. |
| T03/T04 wrong week and silent refresh failure | S010, PR #21 | [Freshness](refresh-freshness.md). Mounted race checks and packaged 1.11.24 failure/retry passed. New real browser status failure exposed S015-F01 below. |
| T05 late journal save | S012, PR #20 | [Save contract](journal-save-verification.md). Packaged 1.11.23 source/XP recovery passed. New real browser uses a three-second post-commit response delay and proves B remains displayed while A's saved receipt arrives. |
| T06/T07 operation outcomes and retry | S014, PR #17 | [Operations](sync-operation-outcomes.md). Packaged 1.11.20 actual partial pipeline, reconnect, restart, cancel and active-close passed. Physical web counterpart remains unrun. |

## New confirmed gaps and repairs

S015-F01: the web status endpoint swallowed malformed JSON and returned HTTP 200
with an Earth/empty-squad default. The browser correctly treated that transport
as a successful read and replaced its previous source marker. Missing, unreadable,
malformed, empty-object and invalid-squad sources now return 503 without private
paths. Explicit empty squads and valid metadata-only status retain compatibility.
Native status now rejects the same unavailable shapes rather than manufacturing
an Earth default. Companion-stat projection semantics are unchanged.

S015-F02: the historical unavailable-root cache-write finding no longer reproduces
with S013's output guard: the absent root remains absent. Startup catchup still
claimed Synthesized despite no persisted artifact. It now reports unavailable
when the expected output was not persisted. This does not certify Drive races.

S015-F03: after XP recovery through the saved-source notice, an already-open
composer retained its earlier XP-pending warning. The composer now consumes the
verified completed receipt, clears that obsolete warning and closes only the
exact recovered draft. A newer draft is preserved. Mounted regression checks
exercise both the original and changed-draft cases.

## Real browser observations

The trial used dedicated loopback ports, a fresh synthetic Vault, real FastAPI
routes and the production Next renderer. FastAPI lifespan was disabled to avoid
proactive/provider daemons; this is not a lifespan or watcher acceptance claim.
The server's isolated origin configuration explicitly allowed its trial port.
A test-only wrapper delayed the journal POST response three seconds after the
canonical handler returned; no production delay or fake saved receipt was added.

After F01, malformed status produced Refresh failed with the prior UTC read time
and date-only operational marker intact. Restoring the file and retrying recovered.
Stopping only the fixture backend demonstrated offline failure; restarting it and
keyboard retry recovered while journal content remained displayed.

Saving October 26 then selecting October 27 during the delay preserved B. A's
receipt showed saved/XP pending. Keyboard Open saved journal selected October 26;
removing the empty synthetic XP projection obstruction and keyboard Retry XP
completed recovery. Read-only SQLite/journal checks found one appended entry,
one Keeper award and 12 XP; B was byte-for-byte unchanged. A subsequent checkbox
save displayed Task saved and the integrated Holocron showed 14 signed XP.

The browser Holocron distinguished missing days/unavailable readiness, focus and
combat outcomes from measured zeros. Precision inspection showed 2/2 checked
items for October 26, and keyboard source navigation opened that exact journal.
Only synthetic data was used. No provider call or personal Vault mutation occurred.

## Checks and remaining acceptance

94 isolated Python tests and 51 adapter checks plus the full frontend regression
runner passed on the repair source. 76 serial native unit tests and one parity test passed (personal-Vault probe excluded). The final 1.11.25 rebuild and selected packaged smoke passed.
Prior packaged observations above keep their original build versions; they are
not relabelled as 1.11.25 observations. Fresh runtime evidence is recorded in the
[sanitized trial record](trials/s015-trust-journeys-2026-10-27.json).

Remaining gates include physical web partial-sync/cancel/close and clean-machine
installer execution. The fresh packaged delayed-response check below passed. This host does not provide
an isolated clean Windows machine; no installer was run over the user's installed
application. Physical Drive races and production integrations remain unexercised.
Independent external review is unavailable. S015 and E002 must remain open until
retained affected acceptance passes or the user explicitly dispositions it.

## Final packaged 1.11.25 checkpoint

The first 1.11.25 checkpoint proved missing-status failure/recovery but exposed
F03. A window resize made its delayed navigation attempt inconclusive; it is not
a passing controlled-delay race. The final rebuild used fresh synthetic journals
and unmodified bundled resources (all 38 matched source). Saving with XP projection
blocked showed both pending messages. Notice recovery after removing only that
empty fixture obstruction completed, closed the original composer, removed its
obsolete warning and retained the saved checked item. Readback found one append,
one canonical row/12 XP, complete phase, unchanged B and preserved BOM/CRLF.
The fixture process was closed and its executable hash matched the release.

FileVersion/ProductVersion: 1.11.25. Executable SHA-256:
`a2a2e69e3f81a511366c51beda69ff84409ab716c91678c81156f464bf5cb8fb`.
NSIS SHA-256:
`057635d3ad363737e91bb75224a2a030d08a7f12983aba29be3e01f9bc7f1319`.
MSI/NSIS were packaged but not installed. Final native checks passed 76 unit
cases and one parity case, excluding the personal-Vault availability probe.
Source audit found no remaining actionable defect in the selected repairs;
independent external review remains unavailable. Remaining runtime gates above
continue to block full S015 acceptance and PR readiness.

## Fresh fixture follow-up

The packaged 1.11.25 delayed-save/navigation check passed on a new synthetic
Vault. All 38 bundled backend resources matched source before a test-only response
gate was added to the copied journal bridge. The gate held the response after the
canonical append completed. A fresh UI observation showed October 27 (B), with
its original content and no receipt, before releasing October 26 (A)'s response.
A's saved/XP-pending receipt then arrived while B stayed displayed. Readback found
one entry, one canonical 12-XP award, unchanged B bytes and preserved BOM/CRLF.
The projection obstruction was intentional; this check does not replace the
earlier XP recovery check. The copied bridge was restored and the app closed.

A separate fresh web fixture reached the real Sync confirmation. The browser
dialog API returned no handle, and documented CDP dialog handling timed out
during focus setup. The backend log contains no sync POST and the backup hook
was not entered. Dismissal, partial outcome and close checks remain blocked;
no passing result is inferred. Source inspection shows that running web jobs
expose a disabled Sequence Lock Active control, while native jobs expose Cancel
operation; actual web cancellation is not currently offered.

Owned fixture backend/Next process trees were stopped and their dedicated
listeners were absent afterward. Native fixture closure was verified. Closing
the temporary IAB tab was also blocked by the confirmation tooling. S015/E002
remain open and PR #22 remains draft. Clean-machine installer execution, physical
Drive races, production integrations and independent external review retain
their existing unavailable/unexercised dispositions. No production source changed.
