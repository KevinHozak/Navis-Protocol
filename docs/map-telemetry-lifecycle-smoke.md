# Map telemetry lifecycle smoke — 2026-11-03

Partial agent-operated run against documentation commit `64c8ef9`; application source unchanged from main `6f3f69f`. This is not a passing acceptance record. The user stopped Computer Use with physical Escape before completion; no further UI actions were taken.

The original run below is retained as historical evidence. See the separate repair/rerun section at the end for the later authorized continuation.

Fresh synthetic Vaults and WebView profile: `.tools/map-smoke-20261103/web` and `direct`. Web used loopback ports 18151/18152, backend lifespan disabled. Packaged runtime was 1.11.39, executable SHA-256 `9bd49ad51bbcfd106f7b5295f64960b9503dda692b4cb331b2d2538c23ae8ad7`; all 53 copied resource files matched source with line-ending normalization. No personal Vault, sync, rollover, paid provider or model configuration was used. Cloud key/config variables were removed and generation remained disabled.

## Observed results

| Check | Web | Packaged |
| --- | --- | --- |
| Player/antagonist/beast coordinates and labels | Passed | Passed |
| Replace player position (100,180) with (850,100), remove old marker | Passed visually | Passed visually |
| Clear both threats and squad; remove markers and show omission reasons | Passed | Passed |
| Stale, future, malformed coordinates | Passed omission text | Passed omission text |
| Missing optional telemetry | Passed, all positions unavailable | Passed, all positions unavailable |
| Out-of-bounds player | Not observed before next case | Passed omission text |
| Matching deployed squad | **Failed** | **Failed** |
| Small viewport 800×600 | **Failed**: legend/destinations below visible area; scrolling did not reveal them | Not completed |
| Keyboard map destination | Enter invoked draft callback, but stable draft view not established | Interrupted before action |
| Moongate hop, old-realm clearing, missing destination background | Not completed | Not completed |
| Full five-minute unchanged-status expiry | Started; interrupted before final observation | Started; interrupted before final observation |

The four regression commands passed: `test:map-telemetry`, `test:map-node-validation`, `test:map-realm-navigation`, `test:moongate-loading`. They do not override runtime failures.

## Confirmed repair targets

1. Status APIs require squad objects (for example `{name: "Reid"}`), but `resolveMapTelemetry` compares telemetry member-name strings directly against those objects. `SectorView` passes the status unchanged. Valid telemetry `members: ["Reid"]` therefore renders “Position belongs to another squad” in both apps. Existing unit fixtures use a squad string array and miss the actual API shape. Normalize squad names at the consumer boundary and add coverage using the real status shape.
2. The map layout clips its legend and destination controls at 800×600; the normal 1280×720 web view also placed these below the visible map. Scrolling over the map did not reveal them. Bound the canvas layout while retaining reachable text and keyboard controls, then rerun both runtime gates.

Cold Next compilation and initial scene loading eventually completed; they are not classified as product failures. An initial synthetic squad string array was rejected by both status APIs and corrected to valid objects before the runtime findings above. No application repair or new release was performed. Keep follow-up evidence separate from the roadmap reconciliation PR.

## Authorized repair and fresh rerun — release 1.11.40

The subsequent user request authorized repairs and another isolated run. These changes are uncommitted on local main and are separate from PR #46.

- Normalize actual squad object names while retaining exact membership/order checks and support for legacy name arrays. Regression coverage includes valid API objects, replacement, count/order mismatch, null and missing names.
- Give the canvas a bounded 16:9 host and allow the surrounding map view to scroll, retaining the legend and destination controls. Keep the scene callback stable across parent refreshes.
- Carry a map destination through the selected entity because the parent remounts SectorView during navigation. Load the draft in the new instance rather than losing it with the outgoing map.

Release executable version metadata is 1.11.40. SHA-256: `07a3b275a9e7ae95838a3630db068d4c6379437e55f401bcfddcd1cabc487889`. NSIS SHA-256: `e04223ef501bbe1e1b0ccd5266dbdf4214cab127a09b28137abe075a7a2ffc2f`. All 53 packaged Python resources matched source. Private preparation/build receipt fingerprint: `b8a77d65b2cfadc85d68d74ee8e60c341e085e10af4d844334d75aab08325925`.

Fresh synthetic runs used `.tools/map-fixed-20261103/web`, `direct`, and `direct2` with separate WebView profiles. Web ports were 18155/18156. No personal Vault or live integrations were used; OpenRouter key/configuration were removed and cloud generation stayed disabled. Companion art was deliberately absent; Mars also lacked its map background. Only disposable fixture status/journal/visit history and generated caches were eligible for app writes.

Validation observed so far:

- Full frontend suite and lint passed (existing lint warnings retained). All five targeted map/loading/navigation commands passed.
- Production export, native release and NSIS build passed. Native tests passed with **81/81** plus the launcher test when run with fixture Python, synthetic default root and `--test-threads=1`. Initial parallel runs failed from process-wide environment races and poisoned locks; they are not recorded as passes.
- Matching squad markers passed in web and packaged UI. Web also passed changed squad omission, moved coordinates, independent threat clearing, stale/future/malformed/out-of-bounds and missing data.
- Web 800×600 and native 1100×700 client-size views exposed readable legend/destination controls through scrolling. Native Tab focus reached Mars with visible focus indication and Enter opened its stable draft. Web keyboard activation also passed.
- Actual Moongate hops to Mars passed in both runtimes with Reid/Lune/Tress. Web confirmed Earth markers disappeared and a missing-image diagnostic retained the Earth destination. Native missing-image/expiry follow-up remains pending until recorded below.
- Web idle expiry passed: the source timestamp remained `2026-11-03T19:56:18.948869+00:00`, last successful UI read remained `19:56:45.717 UTC`, and all four details changed to stale after the five-minute source threshold without refresh. Native final idle interval began with unchanged source at `2026-11-03T20:05:16.302335+00:00`.

The first native window disappeared during a sizing-menu attempt. A second fresh fixture completed the supported minimum-size check using its outer frame. One later capture stalled; the helper was reset once and the same returned fixture window was recovered. No UI results from the stalled capture are claimed.

### Final observations and limits

Packaged idle expiry **passed** after the full five-minute threshold: all four details became “Position is stale”, while the last successful read remained `20:05:16.385 UTC`. The source SHA-256 remained `118698a180a15a94ddc7872d83ac92a8c31e0f13fde2e98b8bced650435d0187`, identical to the interval start. A subsequent synthetic Mars status showed all four previous-realm positions omitted, the explicit missing `Overworld.png` HTTP 404/retry diagnostic and the Earth destination. This completes the previously interrupted expiry and packaged missing-art checks.

Additional native invalid/moved repetitions were attempted after these passes but **not observed**: the helper returned “Computer Use helper already has an active request” and stayed busy on a bounded retry after two seconds. Do not transfer the original 1.11.39 omission/movement results into a new 1.11.40 native pass. Those branches passed on the final web source and in automated tests; native matching-squad, minimum-size access, keyboard draft, actual hop, old-realm omission, missing-art fallback and full idle expiry have direct 1.11.40 evidence. No new native product failure was established by helper contention.

Fixture preservation checks passed: only deliberate status edits and the web hop's journal header changed among original files. The original journal body/task text remained intact. Added files were generated caches/Holocrons, realm visit history and the web journal backup. Cleanup status is recorded after process readback below. No fixes were committed, pushed or added to PR #46 during this request.

Cleanup completed: the owned web/native process trees and orphaned fixture WebViews were stopped, with **zero remaining owned fixture processes** on readback. The agent-created web tab was closed and temporary viewport override reset. Final preservation checks reported no unexpected original-file changes in any of the three fresh fixtures. The separate roadmap branch remains at `64c8ef90aadcfdf4e54251721685c5ff5fcf396c`.

## Final packaged completion — 2026-11-03

The user authorized helper recovery, fresh packaged checks and a separate fixes PR. Resetting the JavaScript session restored the native helper's lightweight inventory; a fresh returned window under `.tools/map-fixed-20261103/final-native` was selected. No helper executable, custom protocol or system settings were changed.

The executable still matched the verified 1.11.40 SHA-256 above, all 53 resources matched, and the shared build receipt confirmed identical source and synchronized versions. No rebuild or additional version allocation was needed. Cloud credentials/configuration were removed from the fixture environment; no cloud generation or personal Vault access occurred.

All previously blocked packaged cases now **passed** on this source:

| Case | Observed result |
| --- | --- |
| Movement | Player moved from (100,180) to (850,100); old player marker disappeared and other markers remained. |
| Stale/future/malformed/out-of-bounds | Player stale, antagonist future, beast malformed and squad outside bounds were omitted with their specific reasons. |
| Changed squad | Previous squad position omitted while player and threat markers remained. |
| Independent antagonist clearing | Antagonist omitted; beast, player and squad retained their positions. |
| Independent beast clearing | Beast omitted; antagonist, player and squad retained their positions. |
| Missing optional telemetry | All four positions unavailable. |
| Both threats and squad cleared | No active target for either threat and no deployed squad; player position retained. |

Freshly written timestamps can precede the wrapper's next one-second clock tick. Retention checks were observed after that tick; the brief future-time guard was not mistaken for a missing retained marker. Private text observations and movement screenshot are retained in `.tools/map-final-*`. Combined with the earlier same-source web/packaged expiry, navigation, realm-hop and minimum-size checks, this completes the scoped lifecycle gate.

Final fixture cleanup passed after process-exit readback: no matching app/Python/WebView processes remained. Original files were unchanged apart from intentional `Bridge/status.json` edits; only generated weekly Holocron files were added. The completed fixes and evidence are published separately from the roadmap reconciliation, with its branch still at `64c8ef9`.
