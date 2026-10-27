# Journal save verification

S012 repairs S009 finding T05: an append result for journal A must not overwrite
the displayed content, loaded-record identity or selected date after navigation
to B. The canonical append service and existing checkbox/task safeguards remain
the persistence authority; no second write or XP ledger is introduced.

`services/journal_entry.py` owns durable request identity, serialized append,
atomic bytes, authoritative snapshot readback and the separate XP completion
phase. Its verified response identifies the saved date, canonical relative path,
request ID, content digest, saved content and XP status. The frontend validates
that receipt against the submitted date/path before acknowledging success.

The page callback uses current selection refs rather than the submit-time view.
It refreshes the same currently selected Journal/date through the existing
guarded read path, rather than injecting an older receipt snapshot. A failed
display refresh is labelled separately from the already verified save.
A saved-source notice survives navigation and opens the actual source through the
existing read flow. A composer is tied to its journal identity so another record
can have its own draft while an earlier append finishes.

Transport loss, server recovery errors, malformed responses and receipt identity
mismatches are labelled unverified, with read-only journal review. They do not
claim no bytes were committed, discard the draft or automatically resubmit.
An unresolved request is retained in memory across navigation and restored as
the draft only when its original journal is opened for review and explicit retry.
Known pre-commit argument/section errors retain the draft and identify an unsaved
entry. Manual exact retries preserve the canonical service's deterministic
date/section/normalized-entry request identity.

When readback proves the entry saved but XP projection is pending, the source
notice says so and retains the exact submitted request for explicit XP recovery.
The service's existing durable phase prevents another append or duplicate award.
A failed recovery does not retract the earlier verified save. The checkbox XP
notice now requires an actual pending object; two absent IDs cannot display a
false pending-save message.

This is a scoped UI/receipt repair. Existing backend readback, crash recovery,
projection retry, byte-preservation and XP authority checks are retained. S010
refresh/selection and S015 broader runtime journeys remain separate.

## Verification - 2026-10-27

Mounted production Home, composer, receipt helper and source notice run with
controlled web/native transport doubles and lightweight navigation/view shells.
The tests navigate from A to B during a deferred save and verify B's content and
draft survive, A's receipt opens A, pending XP uses the exact submitted request,
failed XP recovery does not retract the saved entry, and mismatched receipts are
unverified. They also cover lost responses without automatic replay, restoration
of unresolved drafts only to their source, a failed display refresh after a
verified save, newer authoritative content, same-frame submit suppression and
known pre-commit rejection. This does not claim a physical delayed-response race.

44 isolated Python checks passed for append/readback/recovery and existing task
and canonical XP invariants. The new post-replace mismatch fixture leaves one
committed item, reports recovery_required, and reconciles the exact request once;
the other journal and original BOM/CRLF content remain unchanged. Existing real
ledger projection-failure tests prove recovery does not duplicate XP. 51 adapter
tests and the full frontend regression runner passed. Native verification passed
75 serial unit tests and one parity test, excluding the personal-Vault probe.
Ruff, frontend lint with existing warnings and whitespace checks passed.

The latest source notice and unresolved draft are scoped to the current cockpit
session and are not persisted across reload. Recovery after reload requires the
original entry to be resubmitted to the canonical service's durable request record;
no browser draft store or receipt-history workflow is introduced. Separate physical web-browser, clean-machine
installation and personal-Vault/provider checks remain unclaimed under S015.

## Packaged release fixture - 1.11.23

The final release executable reports FileVersion/ProductVersion 1.11.23. All 38
bundled backend resources matched source. In an isolated synthetic Vault, saving
October 26 and navigating to October 27 preserved the latter journal and showed
the original saved date with pending XP. The notice buttons were accessible above
the IPC badge; opening the saved source loaded October 26 and its checked entry.
After removing only the synthetic projection obstruction, explicit XP recovery
completed with exactly one appended entry, one canonical XP row and 12 XP.
Original pending content and BOM/CRLF were preserved; the other journal was
unchanged. The fixture app was closed and its executable hash matched the release.

Release executable SHA-256:
`cc93f330c36c652760fadb91f1129ac34ed38aa1cfdd2a9644a5f3d8cf5b37b9`.
NSIS installer SHA-256:
`d1b67467954cdc64857fef497e36ffe59f6e8d5930fd37bedf6345530e2a2dcb`.
The installer was packaged, not installed. No personal Vault/provider was used.
