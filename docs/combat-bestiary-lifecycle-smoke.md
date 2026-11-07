# Encounter-to-Bestiary lifecycle smoke — 2026-11-05

**Current result: passed after the 1.11.43 repairs below.** The original
1.11.42 run was partial: the web data lifecycle passed, including recovery from one
Windows sharing error, with a narrow-panel readability defect recorded below.
Packaged combat, ledger/history integrity and same-profile graceful relaunch
passed in that original run, while a native navigation parity gap blocked its
Bestiary analytics UI. The repair section supersedes that original partial result.

## Runtime and isolation

- Source: merged main `79fad773204a05d4cb1a652026d14ef7429513c8` (PR #49).
- Packaged Windows release: **1.11.42**, EXE SHA-256
  `af821e2a18b849e8c4f75efad462e7eaf4de6c6a6dc1d73451a9b5526f9c9b40`.
  All 54 copied backend resources matched source with line-ending normalization.
- Two independent synthetic Vaults and WebView/browser profiles under ignored
  `.tools/bestiary-lifecycle-20261105/{web,native}`. Four cards and two tasks were
  seeded; neither encounters nor task/card links were pre-created.
- Web listeners used only loopback ports 18171/18172, with FastAPI lifespan jobs
  disabled. Packaged checks used the copied release and its bundled Python
  services, without an HTTP backend.
- Cloud key/configuration variables were removed. OpenRouter stayed unconfigured;
  no model/key/budget setup, paid calls, personal Vault access, sync or rollover.

## Journeys and durable read-back

All encounter selection, preview, confirmation, card selection, binding and
Execute actions were performed through the actual UI. After the first victory,
the UI created another encounter using the two remaining cards. The web page
was reloaded between fights. Desktop was closed normally, verified to have zero
remaining fixture processes, and relaunched with the **same Vault and same
WebView profile** before the second fight. The new encounter stayed at turn 1,
Keeper HP 100 and enemy HP 8, preserving the previous victory and card piles.

| Assertion | Web | Packaged desktop |
| --- | --- | --- |
| Reviewed creation and UI card binding/Execute for both fights | Passed | Passed |
| First victory: one recorded round, one slaying, First Slaying trophy | Passed after one recovery retry | Passed without retry |
| Replacement after victory gets a distinct history ID | Passed | Passed |
| First history and remaining cards survive reload/relaunch | Passed, page reload | Passed, graceful same-profile process relaunch |
| Final history: two encounters, two wins, two slayings, no defeats/unresolved recorded encounters | Passed | Passed through packaged shared API and read-only SQLite |
| Highest turn damage 8, win rate 100%, one First Slaying trophy label | Passed in UI and read-back | Passed in shared API; analytics UI blocked below |
| Canonical XP rows: 12 then 2, total 14 | Passed | Passed |
| Replays add no XP, rounds, slayings or trophies | Passed | Passed |

The daily XP rule grants a 10-XP base once plus 2 per checked task. The fixture's
initial expectation of 12 for each completion was corrected against that rule;
the application's 12-then-2 result was correct. No elemental/talent bonuses were
configured. Final hands were empty, all four cards appeared once in discard,
lost piles and active links were empty, and all completion phases were complete.

The first web execution reported `WinError 5` during atomic replacement of
`battle_state.json`. The saved phase was `battle_committed`: task/card/round state
was committed, while XP and Bestiary history had not yet been recorded. One UI
Retry completed the saved operation. It produced exactly one round and one XP
award, including after subsequent API replay. The cause of the transient sharing
failure was not established; this run does not certify error-free Windows saves.

After UI completion, separate HTTP/packaged-adapter replays used the saved
resolution keys. Journal, battle state and stats bytes were unchanged, as were
ledger and round row counts and the full Bestiary projection. Those supplemental
API replays are not described as additional UI clicks.

## Confirmed native UI gap

Codex → Beasts does not expose the **Beasts Codex** dashboard entry in packaged
desktop. Initially the minimal fixture lacked `Obstacles/Beasts`, producing an
entity-loading error. Adding the directory removed that error. A second
diagnostic populated `Obstacles/Beasts/Sentinel/Profile.md` with the synthetic
profile: the roster then opened the Sentinel dossier, but still offered no
Bestiary analytics dashboard entry. The packaged Bestiary API itself returned
the correct persisted results throughout.

Source inspection agrees with the observed UI: native
[`list_entities`](../frontend/src-tauri/src/vault.rs) has no Codex virtual-board
entry for BEASTS and returns only directory entries. The
[web entity route](../backend/main.py) prepends
`{id: "CODEX_BOARD", name: "Beasts Codex", type: "virtual"}`. The shared
[`CodexBestiaryView`](../frontend/src/components/CodexBestiaryView.js) is therefore
reachable through normal web navigation, while that native route selects an
entity dossier instead.

The final web screenshot at a 1280×720 viewport also shows a readability defect:
the center panel's Bestiary card is narrow enough for the Encounters label and
its value to collide. The view's viewport-based three-column grid and nested
two-column metrics do not account for the available center-panel width. Values
were correct in the accessibility tree and ledger, but this is not a clean
visual-layout pass.

Next bounded repair: restore the native Beasts Codex dashboard entry, preserve
ordinary Beast dossier navigation and existing history, make metric labels and
values readable in narrow center panels, and rerun visible Bestiary checks in
fresh web/packaged fixtures. No application repair or new story was created as
part of this smoke-only task.

## Integrity and cleanup

Each baseline covered 12 original files. Only battle state, companion XP
projection and the target journal changed; the other nine stayed byte-identical.
The journal retained its BOM/CRLF and unrelated body, with only the two task
checkboxes and supported completion metadata changed. Added files were expected
combat backups, progression database/XP projection, derived caches/Holocrons,
and the explicitly added diagnostic native Beast profile. Bestiary reads after
shutdown changed no Vault bytes.

Both fixture applications, WebView children and web servers were stopped. Final
verification found **zero fixture processes and zero listeners** on 18171/18172.
The temporary browser tab was closed. Private fixture results/screenshots remain
ignored evidence. No application source changes, rebuild, commit or publication occurred.

Separately, the explicitly authorized unused `BASE/portal-s028-review/target`
cache was removed after absolute-path, cache-only-content, reparse-point and
active-use checks: **3,330 files / 1,011,629,285 bytes**. `BASE/` no longer exists.

## Repair and fresh rerun — 1.11.43

The native navigation route now prepends the virtual Beasts Codex dashboard,
including when the optional Obstacles/Beasts source is absent or empty. Existing
dossiers remain available in order. The enemy-choice route stays separate and
does not receive the virtual dashboard. An unavailable Vault still reports an
error. The shared Bestiary cards now size columns from the available panel width,
with bounded metric tracks and wrapping labels/values.

Fresh independent web and packaged fixtures repeated the full two-encounter
lifecycle using UI preview, confirmation, binding and Execute. Both passed:

| Check | Web | Packaged desktop |
| --- | --- | --- |
| First victory and visible Bestiary | 1 encounter/win/slaying; First Slaying once | Same; dashboard opens without Obstacles present |
| Second reviewed encounter | Distinct history ID; full HP and preserved card piles | Same |
| Persistence before second victory | Browser reload retains active encounter and prior history/XP | Graceful app close, complete process exit and same-profile relaunch retain state |
| Final visible analytics | 2 encounters/wins/slayings, 0 defeats/unresolved, 100% win rate, best damage 8 | Same |
| XP and replay | 12 then 2 XP; two ledger/round rows; replay adds nothing | Same |
| Dossier navigation | Existing shared navigation unchanged | Added synthetic Sentinel dossier remains reachable beside dashboard; dashboard return works |

No retry was needed for either repaired lifecycle run. Native analytics showed
the same totals before and after adding a synthetic dossier; original profile,
history and XP files were retained. A new native regression test additionally
covers missing/empty/populated folders, ordering, unavailable Vaults and keeping
the dashboard out of `/api/beasts` choices.

At web viewports **1024×768, 1280×720 and 1600×900**, rendered metric cells had no
horizontal overflow, and text-range rectangles stayed within their respective
cells. Visual inspection at 1280×720 confirmed labels and values no longer
overlap. Packaged desktop metrics were readable at the restored 1602×1032 window.

Verification: full frontend tests and lint passed (existing lint warnings);
desktop typecheck passed; **82 native unit tests plus one launcher test** passed;
**133 focused backend tests** passed; release build produced Windows x64 EXE and
NSIS artifacts with version **1.11.43**. The first sandboxed native test attempt
stalled in its synthetic Python subprocess; the owned attempt was stopped and
the unchanged suite passed with the required process permissions in 35.29s.
Packaged EXE SHA-256:
`95052a93ae7aa879c96fa33826da5d9ae6be8e13ca9dde9ad059df890cd6a873`.

Post-shutdown integrity checks again found only battle state, companion XP and
the target journal changed among 12 baseline files; the other nine were
byte-identical. BOM/CRLF and unrelated journal text survived. Bestiary reads
changed no Vault bytes. Added files were derived progression/cache/Holocron
outputs, combat backups and the explicitly added synthetic dossier.

Both fixtures and WebView/server children were stopped, the browser tab closed,
and viewport override reset. Private JSON results, geometry measurements and
screenshots are retained outside the tracked delivery. Cloud generation stayed
unconfigured and disabled; no personal Vault, live integration, paid generation
or installer execution was used. These limits remain separate from the passing
isolated lifecycle acceptance.
