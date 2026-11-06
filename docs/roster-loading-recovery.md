# Roster loading recovery — 2026-11-05

**Result: passed in fresh isolated web and packaged 1.11.45 fixtures.** This
resolves the navigation-loading observation recorded during the talent smoke.

## Confirmed cause and repair

On baseline main `2fa89a3`, selecting Party reproduced the stuck roster. The
backend logged a successful `/api/entities?sectorId=PARTY` response and Banter Feed
content loaded, but the roster still contained only `UPLINK SYNCHRONIZING...`.
At 02:28:53 UTC on November 6 (November 5 local), rendered DOM evidence showed
an enabled filter, zero roster buttons and the loaded Banter Feed heading. This
was a stale presentation state after the request completed, not an outstanding
entity request or failed cancellation.

`EntityRail` used `AnimatePresence mode="wait"` to gate the ready list behind
the loader's exit-animation callback. The fix removes that exit gate and its
exit animations. The loading/result branches now follow the supplied request
state directly, while keeping their existing fade-in styling. Selection,
filtering, journal-calendar behavior, request cancellation and error/retry
semantics remain unchanged.

The new mounted regression uses the real Framer Motion package without a DOM or
animation driver. It failed on the original source because ready roster buttons
never appeared without an exit callback. It passes after the repair, covering
ready selection, an interrupted loading/sector change, error and retry, and
empty results. It is included in the standard frontend regression runner.

## Fresh UI verification

| Scenario | Web | Packaged desktop |
| --- | --- | --- |
| Initial Party load | Three expected roster buttons, no stale synchronizing message | Same |
| Repeated Party/Combat switching | 12 switches; correct three/two buttons each time | Six switches; correct buttons each time |
| Filter with no match, then clear | No matching items, then all three Party entries restored | Same |
| Entity selection | XP Manifold opens through its roster button | Keeper Profile opens after retry |
| Missing Keeper source | Visible error and Retry Keeper Load control, no indefinite loader | Same |
| Restore source and click Retry | Profile entry/content restored without reload | Same |

The missing-source checks temporarily renamed only each synthetic Keeper folder
and restored its original bytes. All UI actions were navigation, filtering or
read retry; no sync, rollover, talent allocation, journal completion or XP award
was performed.

The first desktop fixture encountered native-helper timeouts with a large group
of fixture-owned WebView processes. Bounded helper retries did not recover it.
Those processes were cleaned up; the helper then responded. A new independent
Vault/profile was prepared from the same release, and all packaged checks above
passed there. This retains the initial environment failure rather than counting
its attempted checks as passes. The underlying WebView buildup was not isolated
or claimed fixed by this roster presentation repair.

## Verification, isolation and cleanup

- Full frontend tests and lint passed (existing lint warnings), including the
  baseline-failing roster regression and existing navigation/API boundary tests.
- Desktop typecheck passed; **82 native unit tests and one launcher test** passed.
- Release EXE and NSIS metadata both report **1.11.45**. EXE SHA-256:
  `f24254c3c403bd9f4d7c5355b6e21255c54fb3c6e6277c758aff7ddee3cf352e`.
- Actual packaged UI used a fresh EXE copy plus 54 verified runtime resources.
  The web check used the 1.11.45 source; its unused copied EXE was 1.11.44 because
  the web fixture was prepared during native compilation.
- All 13 original files in each repaired fixture remained byte-identical after
  shutdown. Only derived caches/Holocrons and an empty completion lock were added.
- Temporary browser tabs were closed. All fixture applications, WebView children
  and web servers were stopped; final checks found **zero owned processes and
  zero listeners** on 18171/18172. Sanitized receipts/screenshots remain private.

Cloud generation stayed unconfigured and disabled. No personal Vault, live
provider call, installation or production migration was used. This verifies the
completed-request presentation defect; it does not add transport deadlines or
claim that an indefinitely stalled network request now succeeds.
