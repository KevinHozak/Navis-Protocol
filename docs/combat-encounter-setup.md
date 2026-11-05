# Reviewed encounter setup

Combat Theater offers one existing Beast per encounter. Selection loads a
read-only preview; a separate confirmation starts the fight. Dismissing the
preview does not write anything. This does not generate enemies or use AI.

Enemy definitions come from `Codex/Beasts/<name>/Combat.json`, falling back to
`Obstacles/Beasts/<name>/Combat.json` only when the name has no Codex directory.
The same precedence applies to unavailable definitions. Paths must resolve
inside the Vault. Required fields are positive integer `hp` and non-negative
integer `attack`; booleans are rejected. Optional `intent_pattern` defaults to
`["Strike"]` and accepts Strike, Charge and Debuff. Affinity and vulnerabilities
use the existing elemental-profile rules. Missing or invalid definitions appear
as unavailable; setup does not guess their combat stats.

Example synthetic profile:

```json
{"hp":20,"attack":4,"intent_pattern":["Charge","Strike"],
 "affinity":"Physical","vulnerabilities":{"Digital":2}}
```

Starting state is turn 1, Keeper HP 100, base AP 2, and the reviewed enemy at full
HP. Existing squad/talent effects still apply when the battle engine hydrates
and resolves rounds. The preview labels AP as base AP for this reason.

HTTP and packaged desktop use `services.encounter_setup` through the shared
combat dispatcher:

- `GET /api/battle/encounters`: choices, unavailable reasons and setup blocker.
- `POST /api/battle/encounter/preview`: `enemy_id`, returning the encounter and
  a digest binding the preview to the current battle state and combat definition.
- `POST /api/battle/encounter`: `enemy_id` and `preview_token`. The service
  revalidates under the existing combat lock before an atomic battle-state save.

Client-supplied stats and paths cannot override the selected definition. A
changed battle or definition requires another preview. Repeating the same saved
confirmation returns the existing encounter without restarting it, including
after a lost response or relaunch.

Setup requires existing combat cards and battle state. Pending recovery, linked
maneuvers, and unfinished encounters block a new fight. Won or defeated
encounters may be replaced after review. Setup preserves card piles, completed
resolution history, journals and XP; it replaces only the encounter and removes
the previous round's display summary. Each new encounter gets a distinct history
ID for the existing round-history projection.

Limits: single Beast only; no enemy editor, random encounter generation,
abandon/restart flow, deck rebuilding, health carry-over, or cloud generation.
Existing round hydration continues to read current elemental profiles and squad
effects, as it did before setup was added.

## Verification

Automated checks cover shared/HTTP/native validation, preview without writes,
stale definitions and battle state, confirmation replay, pending recovery,
invalid stats, missing cards, active encounters, linked maneuvers, completed
encounter replacement and Execute/Cancel integration. Mounted UI checks cover
selection, review, dismissal, errors, double-submit protection and blocked setup.

### Fresh runtime smoke — 2026-11-03

Four independent synthetic Vaults were used under the ignored
`.tools/encounter-smoke-20261103` directory. No personal Vault was used. All
fixture processes removed cloud credentials/configuration, left the OpenRouter
provider unconfigured and made no live generation calls.

| Check | Web | Packaged Windows x64 1.11.41 |
| --- | --- | --- |
| Existing configured enemy selectable; incomplete definition unavailable | Passed | Passed, including keyboard selection |
| Preview HP 20, attack 4, Charge → Strike, Keeper HP 100, base AP 2 | Passed | Passed |
| Dismissal preserves all 10 original fixture files; no encounter created | Passed | Passed |
| Definition changed to attack 5 after preview; old confirmation rejected | Passed | Passed |
| New preview shows attack 5; explicit confirmation starts encounter | Passed | Passed |
| Active encounter blocks replacement | Passed | Passed |
| Reload/relaunch retains enemy, turn 1, HP, cards and history ID | Passed, page reload | Passed, actual process relaunch with fresh WebView profile |
| Separate fresh fixture with pending XP recovery blocks setup | Passed | Passed |
| Pending record and all 10 original files preserved | Passed | Passed |

Successful creation changed only battle state, plus the combat definition that
the operator deliberately edited for the stale-preview check. Journals and
companion stats remained byte-identical, card piles stayed unchanged, and the
XP ledger contained zero rows. Existing dashboard/cache reads produced only
derived sector-cache, weekly-Holocron and empty progression-DB files. Those are
separate from setup's own read-only preview behavior, which is checked without
other dashboard reads in the automated suite.

The first forced-stop desktop relaunch left a windowless process using the old
WebView profile. It was stopped, then the same executable and saved fixture
Vault were relaunched with a new WebView profile. The encounter retained history
ID `9cee76e6-6f0e-4622-84bd-367d7091a8f6`; the web encounter retained
`b7032618-173e-40f9-bbde-4fc30e662d94`. A same-profile graceful-relaunch or
installer/clean-machine claim is not made by this check.

Owned fixture applications, WebView children and loopback servers were stopped;
temporary browser tabs were closed. Fixture data, logs and screenshots remain
ignored local evidence. Automated results: 51 setup cases plus 74 completion
cases across shared/HTTP/native paths, the full frontend suite (53 transport
unit cases plus the regression scripts), lint with existing warnings only,
and 81 native tests plus one launcher test passed.

### Original desktop build and packaging report — 2026-11-03

- Repository: `C:\Projects\Navis-Protocol`, branch `main`, uncommitted changes.
- Declared version: **1.11.41**; Windows x64 release built and verified.
- Executable: `frontend/src-tauri/target/release/navis-protocol.exe`, 28,303,360
  bytes; FileVersion and ProductVersion both 1.11.41.
- Installer: `frontend/src-tauri/target/release/bundle/nsis/Navis Protocol_1.11.41_x64-setup.exe`,
  19,300,452 bytes; FileVersion and ProductVersion both 1.11.41. Built, not installed.
- `tauri.conf.json`, Cargo.toml, the app Cargo.lock entry, package.json and both
  package-lock root versions are synchronized at 1.11.41. The runtime window
  title also showed 1.11.41. All 54 packaged backend resources matched source.
- EXE SHA-256: `8ccf51eb477f1ced4f66dcc1efa59e8ad0df6eb992b2c487ffec3d8d38564a24`.
- NSIS SHA-256: `671f3c39b532b3fda6fc123401a6531e0f913b5fd19a3ce122e48c2ba8d2cf3d`.
- Source fingerprint: `ca815e0cb2e7f75c1c1e696c46fa82c8292c093160ada41056e44d63c7caaead`.
  Build receipt identifiers remain in private local evidence.

This original build preceded the separately authorized delivery below. No
installer execution or cloud configuration was performed.

### Delivery rebuild — 2026-11-05

The shared preparation record had advanced to an unbuilt 1.11.42 in another
checkout. The canonical checkout was explicitly reconciled to that version,
preserving historical receipts and adding the new packaged encounter service
to the runtime source profile. The other checkout and the unrelated untracked
`BASE/` directory were preserved.

Release 1.11.42 rebuilt successfully in the canonical checkout. Both the EXE
and NSIS installer report FileVersion and ProductVersion 1.11.42; all six managed
version fields match. All 54 bundled backend resources matched source. A new
synthetic Vault and WebView profile verified dashboard startup, the 1.11.42
window title and IPC online. Packaged catalog and preview calls both returned
200 and left Vault bytes unchanged when run with exclusive fixture ownership.
An earlier comparison overlapped with dashboard background writes; it was
rerun after stopping the fixture application. All ten original fixture files
were unchanged and no fixture processes remained after cleanup.

Delivery checks passed: 125 backend setup/completion cases, scoped Ruff, the
full frontend suite, lint with existing warnings only, desktop typechecking,
81 native tests plus one launcher test,
publication-path guards, and redacted staged/full-history secret scans. The
original full web/desktop journey evidence above remains applicable to unchanged
encounter code; this rebuild's new runtime check is startup and packaged
read-only selection/preview, rather than a repeated full journey trial.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `frontend/src-tauri/target/release/navis-protocol.exe` | 28,303,360 | `af821e2a18b849e8c4f75efad462e7eaf4de6c6a6dc1d73451a9b5526f9c9b40` |
| `frontend/src-tauri/target/release/bundle/nsis/Navis Protocol_1.11.42_x64-setup.exe` | 19,302,648 | `bb32e22c6c5dfa52ed5002d493f7722db7fddafc5e4617339a4842fd99bf5de6` |

Prepared source fingerprint:
`ff4526a4940c1545f82d978488e5c813b645285d60dff46cde5a754485116a41`.
Build receipt identifiers remain in private local evidence.
Cloud generation remains disabled; the installer was built, not installed.
