# Task completion times (S023)

A canonical transition from unchecked to Done records a timezone-aware UTC instant
with the successful checkbox write. Journal rows store an invisible
`<!-- navis-completion:{"completed_at":"ISO instant","history":[]} -->` comment.
The checkbox, timestamp and history share the same atomic file replacement, BOM,
newline style and source position. Task labels and attached notes remain intact.
The metadata reader rejects malformed or duplicate comments; source comparisons
ignore only this metadata. Combat source fingerprints also ignore completion
metadata so recoverable card resolution can validate its original source.

Journal, directive, recurring and combat writers use the same timestamp helper.
Directive `completed_at` and `completion.completed_at` mirror the saved journal
instant. Existing reliable offset-bearing instants remain valid. An idempotent
Done retry preserves the first instant, including recovery after XP failure.
Reopening archives the instant, clears the current time and reconciles XP through
the existing canonical path. Recompletion records a new instant on the same row;
directive completion history retains the earlier provenance. Recurring dates keep
separate occurrence markers and archive the prior occurrence's completion.

An already checked legacy/manual row has **Completion time unknown** unless it
already has reliable completion metadata. A later sync, import, replay or file
modification time cannot manufacture an exact completion instant. The legacy
collection helper deliberately does not stamp copied completions. Completion time
is distinct from XP source-event time, import time and the operational journal date.
Pending XP does not change the original persisted completion instant.

The journal and task pickers show known instants in the IANA zone in
`Bridge/settings.json`'s top-level `timezone`, with `America/Chicago` fallback for
missing, invalid or unavailable configuration. Settings are loaded through the
same API on web and Tauri at page startup; reload after changing that setting.
No browser/Windows timezone is used for completion-time formatting. The UI uses
an accessible `<time dateTime="original instant">`, local date, seconds and zone
abbreviation. Legacy date-only or naive values remain explicitly unknown.

Calendar midnight changes the displayed date. Navis's existing 03:00 journal
rollover and authoritative `Bridge/status.json.last_updated` continue to choose
the journal/recurrence occurrence, independently of its exact completion instant.
At fall DST, the two 01:30 instants display CDT and CST respectively; at spring
DST, formatting skips from 01:59:59 CST to 03:00:00 CDT. UTC storage is monotonic
across these wall-clock changes and never guesses an ambiguous local offset.

Verification uses synthetic clocks and disposable Vaults for midnight/DST,
unknown legacy, recurring occurrence history, reopening/recompletion, replay,
concurrent-edit preservation, failed XP recovery and web/native bridge parity.
Physical browser and packaged Tauri observations are recorded separately.
S024's Completed today aggregation remains separate work.

## Verification checkpoint

The [sanitized trial](trials/s023-completion-times-2026-10-27.json) retains the
passing 232-case affected suite, frontend regressions, 76 serial native unit
cases and real web configured-zone/reopening observations. It also retains initial
failures and repairs. Packaged timestamp UI acceptance remains pending after the
window-discovery helper failed through its documented recovery. Cleanup observed
an unexpectedly large descendant process tree of unconfirmed cause; the final
fixture roots, window and dedicated listeners were absent. This delivery remains
a draft until the packaged UI check passes. Independent external review is
unavailable; primary-agent source review found no further S023 source finding.
