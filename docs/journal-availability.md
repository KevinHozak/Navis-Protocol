# Journal and Holocron availability

S011 finishes S009 finding T02 after S013's shared Holocron evidence work.
Command readiness and task-board empty/zero handling already exist and are
preserved. No global conversion of zero values to errors is introduced.

## Calendar contract

`GET /api/journal/month?year=YYYY&month=M` has matching web/native semantics:

| State | Contract and display |
| --- | --- |
| Loading | Visible loading state; unverified date selection disabled. |
| Readable Journal with no matching entries | HTTP 200, `availability: available`, requested year/month and `dates: []`; “No journal entries this month.” Missing year/month directories are valid empty history if the Journal source can be read. |
| Readable dated entries | HTTP 200 with sorted real dates in the selected month; directories, symlinks, unrelated names and invalid dates are excluded. |
| Missing/inaccessible Journal, obstructed directory or failed enumeration | HTTP 503 with generic `journal_unavailable` detail; no successful empty result or private path. |
| Invalid date parameters | HTTP 400 (malformed typed HTTP parameters may use FastAPI 422); no filesystem traversal. |
| Backend/dependency failure, malformed response or timeout | Unavailable state and Retry dates; no empty-success label. An unsupported native 501 is explicitly labelled. |
| Failed same-month refresh | Prior dates remain labelled as previously loaded; selection pauses until a successful retry. |

Month requests have cancellation and revision guards. A late result cannot
replace a newer month's dates or mark its request complete. Switching months
does not reuse another month's cached date set. Retry performs reads only;
rollover remains a separate explicit operation with its existing confirmation.

## Holocron contract

S013 already distinguishes missing/corrupt XP, signed Keeper zero, missing days,
partial coverage and unsupported historical metrics. S011 adds parser-level
availability so a successful fingerprint read cannot hide a later parser failure.
Unreadable or invalid UTF-8 journals do not count as readable days or contribute
zeros. Daily and sector measurements with no readable source are null; a readable
pending-only checklist still yields measured 0%, and a readable empty canonical
Keeper ledger still yields 0 XP. UI and standalone HTML retain these distinctions.

Existing evidence inspection and relative journal navigation are reused. No
personal Vault mutations, live provider calls or unrelated freshness repairs are
part of this work. S010's broader Holocron week-response/selector races remain
separate from the calendar request guard required for this availability contract.

## Verification - 2026-10-27

50 affected Python tests passed, with the eight calendar/availability fixtures
rerun after the final canonical filename filter and HTML assertions. These cover
missing and obstructed calendar sources, failed enumeration, invalid parameters,
real empty history, parser failure after successful fingerprint reads, corrupt XP
storage, a pending-only 0% day and a canonical zero-XP ledger. Web requests use an
in-process FastAPI client with external sockets disabled.

51 desktop adapter tests and the full frontend regression runner passed. Mounted
calendar checks exercise loading, HTTP/transport failure, unsupported native
responses, malformed bodies, timeouts, retries, retained-date selection guards,
real entries, valid empty months and out-of-order month responses. Native Rust
verification passed 75 serial unit tests and one parity integration test; the
personal-Vault default-root probe is excluded. Ruff, frontend lint with existing
warnings and whitespace checks passed. Packaged fixture observations follow.

Separate physical web-browser, clean-machine installation, real Drive-lock timing
and personal-Vault/provider checks are not claimed. Those broader runtime journeys
remain under S015; no independent external review is implied by these checks.

## Packaged fixture acceptance - 1.11.22

Windows release packaging produced MSI and NSIS installers. Executable
FileVersion and ProductVersion both read 1.11.22; all five managed version files
are synchronized. All 38 mapped backend resources match current source bytes.
The copied executable ran outside the source backend with an isolated synthetic
Vault and WebView profile.

The native calendar displayed an unavailable warning and Retry dates when Journal
was missing. Creating an empty Journal and clicking Retry replaced that warning
with the valid empty-month message. A pending-only October 27 entry appeared after
navigating to November and back, and selecting it loaded the exact journal with
its task still unchecked. The packaged Python bridge returned unavailable
precision/sector counts with no readable days, then measured 0% and one readable
day after the entry was added; its readable empty Keeper ledger remained 0 XP.
The fixture app was closed after smoke. No sync, rollover or provider was invoked.

Executable SHA-256: `feed20e1ebdc646b4e2b8fe2b183dcb5873ef38df904b50e56b7f3140ae506e4`.
NSIS SHA-256: `f2026f3ba9cff855f0af1a7b41b52cfdb640daf2ac1468d4da263de1ad518a7c`.

The pre-existing global pending-XP toast was present in the sparse fixture and is
not counted as an S011 calendar result. Broader save/progression recovery remains
outside this narrowed T02 repair. HTML zero/unavailable behavior was checked
programmatically, not through a physical download dialog.
