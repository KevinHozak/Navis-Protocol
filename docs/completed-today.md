# Completed today (S024)

The read-only view is opened from Directives → Completed today. It uses calendar
midnight-to-midnight in the top-level `Bridge/settings.json` IANA `timezone`, with
America/Chicago fallback. This is separate from Navis's 03:00 operational journal
rollover. UTC instants are converted into that local calendar day, so DST days can
have 23 or 25 hours. The UI shows the date and zone returned by the reader.

`GET /api/tasks/completed-today` runs the same `services.completed_today.build`
projection on HTTP and through the packaged native read bridge. Python `tzdata`
is declared for Windows zone support. No mutation service, journal sweep,
progression database, XP calculation, recurrence advancement or Vault lock is
initialized by this reader. The native read subprocess disables bytecode writes.
Reading, filtering and refreshing do not write to the Vault.

## Coverage and provenance

All Markdown under `Journal/` is scanned, including older journal files whose
tasks were completed today. Original operation headers determine grouping;
unrecognized headers remain Unassigned. Every row links through the existing
journal-navigation callback to its original file, with the source line displayed.
Task labels, notes, journal positions and file bytes are never rewritten.

Timestamped rows are explicit canonical completion evidence: checked rows with
S023 completion metadata, or checked directive occurrences with a unique valid
canonical completion instant in ops_state. Active and recurring records are
provenance lookups, never a second list of projected task copies. Recurrence
history can supply the original instant for an older occurrence. Current
reopening/pending phases are excluded. A recompleted row uses its current instant,
not one extra row per archived instant. Cancelled, deferred, in-progress and
pending states are excluded.

Journal UUID identity is scoped by original file. Directive markers carry global
occurrence identity. Distinct same-text rows remain distinct; duplicate/ambiguous
identities and copied directive representations are reported as partial coverage,
rather than guessed together or counted twice. Conflicting journal/canonical times
are also reported, and unstable sources are discarded from that snapshot.
Frontmatter, fenced examples and comment blocks are not task evidence.

Unchecked history and file modification/sync times do not establish completion.
Checked rows without trustworthy completion time appear separately only when
their canonical journal file date matches today's local calendar date. This
**Journal-day evidence** may include activity logs and is never counted as
Completed today. No text heuristic silently classifies historical activity logs
as completed tasks. Canonical timestamp metadata records an explicit Done action;
unmarked checks remain unknown-time evidence.

## Availability and refresh

The reader returns complete, empty, partial or unavailable status. Missing Journal
sources are unavailable; unreadable, malformed, changing, linked or bounded-out
sources produce coverage details, never an unexplained empty list. Parsing is
limited to 8,000 files, 2 MiB per source, 64 MiB of journal bytes and 1,000 rows per
request. Hitting a limit is explicit partial coverage, not exhaustive success.
Symlinks/junctions are not followed. Invalid/missing timezone configuration falls
back to Chicago; unavailable zone support is reported as unavailable.

File size/mtime are used only to detect concurrent edits, never as completion
times. Journal/ops/settings changes during the read invalidate affected evidence.
No global transaction or production-wide exhaustive scan is claimed. The UI
clears stale rows during loading and errors, filters locally, refreshes on Vault
events and at least once per minute, and rejects superseded/unmounted responses.
Unsupported client timezone formatting fails explicitly rather than displaying
the wrong zone. Source navigation opens the original journal without a write.

## Verification

Synthetic automated checks cover older origins, grouping, same-text identities,
directive provenance, replay/reopening, legacy separation, midnight/DST, refresh,
source callbacks, unavailable/partial states and byte-for-byte read-only behavior
through HTTP and the native Python bridge. Native and physical web/packaged
checks are recorded separately; source assertions are not runtime acceptance.

The S024 [verification record](trials/s024-completed-today.json) records 247
affected Python tests, the full frontend suite and 77 native tests passing.
Actual web and fresh packaged Tauri grouping, filtering, older-source navigation,
reopening and refresh passed. Four completions became three after reopening,
with one distinct same-text Outland row remaining. Unknown-time activity evidence
stayed separate and unreadable-source coverage remained explicit.
Release 1.11.28 and its installer have matching metadata and 42 source-matching
backend resources. This is not clean-machine installation certification.

The resumed run's Windows helper responded without application/helper source
repair; the earlier timeout cause remains unconfirmed. Native and web fixtures
ran sequentially; the web session loaded after initial compilation and reload.
Whole-Vault byte checks passed for 13 native files before the intentional edit,
16 after dashboard cache writes settled, and 11/14 web files before/after its
intentional edit. Command navigation refreshed three existing Holocron cache
files, invalidating the first post-edit native baseline; the isolated completion
view Refresh then preserved every byte. Source journal, XP and recurrence reads
remained unchanged. All owned fixture processes and dedicated listeners were
cleaned up. The verification record retains earlier failed/blocked observations.

Windows Python installations need the declared `tzdata==2026.5` dependency from
`backend/requirements.txt`; without zone data the reader reports unavailable.
