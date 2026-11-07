# Navis-Protocol roadmap

Reconciled on **2026-11-07** through merged main `acd603a` (PRs #53–#55), the
local issue store and tracked acceptance records. The November 3 legacy GitHub
issue snapshot is retained, not a renewed live backlog query. See the
[dated audit and status reconciliation](roadmap-acceptance-audit.md). Implemented, verified,
waived and operator-only limits are separate states. Historical test counts do not
certify the current application or a personal-Vault migration.

## Current backlog

All **32 local records** (four epics and 28 stories) remain done at this review.
Both GitHub issue backlogs had no open issues in the November 3 snapshot after
#245/#246 closeout; their live state was not rechecked here. Closed legacy issues with
unchecked original checklists are not automatically unfinished work: inspect their
completion/disposition sections. No new issue is created by this roadmap.

| Delivered scope | Evidence and retained boundary |
| --- | --- |
| E001: bounded AI workflows (S001–S008) | [Final S008 evidence](s008-workflow-simplifications.md). Briefs, reviewed notes, decision review and narrow controls are delivered. S007 human rehearsal was waived; human time savings and long-term reuse remain unmeasured. |
| E002: trustworthy status (S009–S015) | [Trust journeys and accepted limits](trust-journey-verification.md). Selected web/packaged journeys passed; installer/clean-machine and physical Drive/production integration limits were explicitly accepted as untested. |
| E003: Vault MCP (S016–S021, S025–S026) | [Controlled read-only adoption](vault-mcp-real-workflow.md), [guarded append contract](vault-mcp-journal-appends.md). Personal MCP writes remain disabled; fixture append delivery is not production-write adoption. |
| E004: task state (S022–S024) | [Shared states](task-status-semantics.md), [timestamps](task-completion-times.md), [Completed today](completed-today.md). Isolated web/native acceptance passed with documented runtime limits. |
| S027: shared Vault retrieval | [Architecture](architecture.md) and [issue](../issues/NAVIS-S027.md). Shared domain reads preserve transport-specific access rules; no MCP network hop is required inside the app. |
| S028: configured text routing | [Provider inventory/configuration](openrouter-text-generation.md). OpenRouter is the shared default but **cloud and background generation remain disabled until explicitly configured**. No live quality or personal-data transmission acceptance is implied. |
| Portal S028 native Forge integration | [PR #53](https://github.com/KevinHozak/Navis-Protocol/pull/53) merged at `96b9c14`; [Protocol 1.11.47 / Portal 0.2.22 qualification](portal-s028-qualification.md#current-protocol-11147--portal-0222-qualification) records isolated composed lifecycle, cancellation, privacy and billing checks. Explicit Portal selection/consent remains required; no live provider, installed upgrade or production GUI startup acceptance is implied. |
| Recovery harness and offline policy | [PR #54](https://github.com/KevinHozak/Navis-Protocol/pull/54) merged at `8299c4c`; [investigation](webview-process-investigation.md) and [reusable harness](packaged-recovery-harness.md) separate process shutdown, per-launch UI outcomes and 43 offline policy cases. The original buildup remains unexplained; no reproduced app fix or universal recovery guarantee is claimed. |
| Workflow semantic validation | [PR #55](https://github.com/KevinHozak/Navis-Protocol/pull/55) merged at `acd603a`; [actionlint and pre-push checks](packaged-recovery-harness.md#semantic-validation-before-publication) and linked Windows CI verify workflow semantics, 9 pre-push checks and 43 offline cases on the published PR head. These are static/policy checks, not renewed packaged UI qualification. |
| #246: version in native title | PR #44 merged at `7edf1ff`; [direct/launcher packaged evidence](desktop-window-version.md), issue closed. |
| #245: Projects overview | PR #45 merged at `6f3f69f`; [web/native acceptance](projects-overview.md), issue closed. Bounded GitHub CLI account reads, not per-browser account linking. |

## Existing foundations: implemented versus remaining scope

| Capability | Current source/evidence | Remaining boundary |
| --- | --- | --- |
| Sync/rollover and recovery | [S014 resource-directory smoke](desktop-release.md#targeted-s014-release-fixture-evidence---2026-10-27) and S015 selected journeys cover success/partial failure, reconnect/review, cancel/close/restart and unavailable roots. | Installed-package/clean-machine and physical integration limits remain accepted untested boundaries; do not label all packaged smoke unperformed. |
| Canonical XP ledger/dashboard | Python/native ledger and refresh contracts delivered; #67/#71 closed. [P4 disposition](progression-p4-verification.md) records the user's explicit manual-check waiver. | Waived checks were not passed and are not closure blockers. Personal historical reconciliation is separately authorized operator work, not a pending automatic migration. |
| Interactive map/telemetry | Validated nodes, realm navigation and optional measured telemetry consumers; [web/native lifecycle evidence and repairs](map-telemetry-lifecycle-smoke.md) passed in 1.11.40 fixtures after PR #47. | No in-repository measured-coordinate producer was found; omitted positions must stay unavailable. Installer and production coordinate integration are not certified by synthetic UI smoke. |
| Combat/task completion | Shared completion authority and durable retry/XP behavior; [packaged Execute/Retry/Cancel/relaunch smoke](combat-packaged-recovery-smoke.md) passed in fresh 1.11.40 fixtures. | Canonical XP exactly once, journal/card persistence and cleanup verified. Installer, clean-machine discovery and physical Drive interruption remain untested. |
| Tactical combat and Bestiary | [Round/AP/shield rules](combat-tactical-rules.md), [elements](combat-elements.md), [squad synergies](combat-synergies.md), [Bestiary analytics/trophies](combat-bestiary.md), and [reviewed single-enemy setup](combat-encounter-setup.md) exist. Legacy epic #183 is closed. | Setup uses existing validated Beast profiles, explicit preview/confirmation and recovery guards. Multi-enemy selection, enemy editing, abandonment/restart and deck rebuilding are outside this bounded change. No full tactical-game completion is claimed. |
| Talents | [Schema/parity](talent-p1-verification.md), [node graph](talent-p2-verification.md), [modifiers](talent-p3-verification.md), [allocation lifecycle](talent-allocation-lifecycle-smoke.md), and [pointer repair/rerun](talent-pointer-activation.md) exist; #193 and children are closed. | Pointer and keyboard allocation, prerequisite unlocking, persistence and the selected shield perk passed in fresh web/packaged 1.11.44 fixtures. Clean-machine and broad human usability remain unqualified. |
| Reactive updates | Python watcher/event bus, `/api/events/stream`, native watcher/events and client invalidation are implemented; #188 and children are closed. | This is not a universal Drive consistency or uninterrupted push-delivery guarantee. |
| Squad management | Native deploy/bench/vanguard routes and tests exist alongside web routes. | The earlier claim that these native mutations were absent is superseded. No new squad redesign is selected. |
| Forge/Reid/War Room | Python runtime bridges exist in native P5; [current text provider boundary](openrouter-text-generation.md) supersedes historical local-only defaults. [PR #53 qualification](portal-s028-qualification.md) adds isolated native Portal Forge lifecycle and accounting evidence. | Live provider quality/spend, rich personal-Vault context, production GUI startup and installed upgrade are not certified by the composed fixtures; cloud generation stays disabled. |
| Journal composer/Holocron | [Save verification](journal-save-verification.md), [freshness](refresh-freshness.md), S006/S008 and S028 supply scoped packaged/browser evidence. | Do not describe these selected journeys as globally awaiting first packaged smoke; physical races and installer limits remain separate. |

## Completed bounded follow-ups

The [map lifecycle smoke and repairs](map-telemetry-lifecycle-smoke.md) passed after
merged PR #47. The subsequent [packaged combat recovery smoke](combat-packaged-recovery-smoke.md)
passed Execute, retry after actual app relaunch and Cancel, with journal/card/XP
integrity and process cleanup. These records supersede the original audit's absence
of evidence for those selected journeys. Cloud generation remains disabled.

Reviewed encounter setup/selection merged in PR #49; its scope and verification
are recorded in [encounter setup](combat-encounter-setup.md).
The subsequent [encounter-to-Bestiary lifecycle smoke](combat-bestiary-lifecycle-smoke.md)
verified two UI-driven victories, exact-once history/XP and reload/relaunch
integrity in fresh web and packaged fixtures. The initial run exposed a missing
native Beasts Codex dashboard entry and overlapping metrics in narrow web cards.
Both were repaired in 1.11.43, and fresh UI-driven lifecycle reruns passed in both
runtimes, including native dossier navigation, reload/relaunch persistence and
exact-once history/XP. Rendered web metric containment passed at 1024, 1280 and
1600 pixel widths. No confirmed gap remains in this selected lifecycle scope.
Waived progression work, production XP migration, installer exercises, live
integrations and AI configuration are not implied follow-ups.

The [talent lifecycle smoke](talent-allocation-lifecycle-smoke.md) subsequently
passed allocation, prerequisite unlocking, browser refresh/native relaunch and
Mindful Clarity's shield effect in fresh 1.11.43 fixtures. Direct SVG-node pointer
attempts initially did not reliably activate under automation; keyboard and the
native tooltip button worked. The subsequent [pointer investigation and repair](talent-pointer-activation.md)
confirmed detail-panel interception and off-center decorative SVG transforms.
Fresh web/packaged 1.11.44 checks passed pointer allocation, keyboard guards,
persistence and the same combat perk. This resolves the selected pointer gap;
the separate navigation-loading observation was investigated next.

The [roster-loading repair](roster-loading-recovery.md) reproduced an enabled
filter and loaded content beside a stale synchronizing skeleton after a successful
entity response. Removing the exit-animation gate resolved the presentation race.
Fresh web/packaged 1.11.45 switching, filtering and missing-source/retry checks
passed, alongside a real-Framer-Motion regression that failed on baseline.
The initial fixture's WebView process buildup was investigated separately in the
[process and recovery record](webview-process-investigation.md). Eight sequential
normal-close cycles and three forced-close cycles did not establish persistent
accumulation. The visible follow-up loaded System HUD and Party in all three
cycles; cycle 2's initial Combat observation was interrupted and its later normal
launch recheck does not retroactively certify post-crash completion. The original
cause remains unknown; no broader transport or clean-machine guarantee is implied.

[PR #54](https://github.com/KevinHozak/Navis-Protocol/pull/54) delivered a
self-contained synthetic-Vault harness with elapsed shutdown samples and explicit
UI outcomes/history. One normal-close and one forced-close/relaunch validation
passed; all original generated-Vault files were preserved and no owned processes
remained. Its 43 offline regressions subsequently repaired harness policy guards,
not a reproduced Navis process defect. The initial workflow was rejected before
tests started; step-scoped runner-path evaluation fixed that configuration error.

[PR #55](https://github.com/KevinHozak/Navis-Protocol/pull/55) added checksum-pinned
actionlint provisioning and offline semantic/rejection checks, plus a scoped
pre-push gate that validates each affected pushed commit. On published head
`6828cc7`, [Windows push CI](https://github.com/KevinHozak/Navis-Protocol/actions/runs/42386550110)
verified actionlint, all 9 pre-push selection checks and all 43 recovery policy
cases; [PR CI](https://github.com/KevinHozak/Navis-Protocol/actions/runs/42386576491)
also passed on the test merge. No Navis launch, personal Vault access or provider
call was part of these checks. Tool provisioning is a separate public download;
validation itself is offline. No new runtime tests were run in this reconciliation.

## Current task selection

No unfinished local story or reproduced application defect is selected by this
review. The original audit's map, combat, encounter and talent follow-ups have
dated completion evidence above; they are not pending first-run checks. Broader
product work needs an explicitly selected outcome and acceptance scope. Waived
checks, accepted installer/physical-integration limits, personal-Vault adoption
and provider configuration remain separate boundaries, not automatic new tasks.

## Unselected broader directions

Batch card-art pipelines, gallery ingestion, annual/quarterly analytics, multiverse
decision tracking, broader creative-project matrices, live objective pinning,
ambient soundscapes/dynamic backgrounds and richer health/training visualizers remain
product directions, not confirmed active defects or newly authorized implementation.
Existing assets, entity reads, telemetry, trophy derivation and sector UIs do not
establish those entire workflows. Scope and evidence must precede a new story.
