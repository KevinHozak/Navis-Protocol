# Navis-Protocol roadmap

Reconciled on **2026-11-03** against merged main `6f3f69f`, the local issue store,
legacy GitHub issue dispositions and tracked acceptance records. See the
[audit, evidence and next task](roadmap-acceptance-audit.md). Implemented, verified,
waived and operator-only limits are separate states. Historical test counts do not
certify the current application or a personal-Vault migration.

## Current backlog

All **32 local records** (four epics and 28 stories) are done. Both GitHub issue
backlogs have no open issues after #245/#246 closeout. Closed legacy issues with
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
| Talents | [Schema/parity](talent-p1-verification.md), [node graph](talent-p2-verification.md), [modifiers](talent-p3-verification.md) exist; #193 and children are closed. | These records primarily map implementation and automated coverage, not a clean-machine or human usability result. Do not re-list the entire tree as planned. |
| Reactive updates | Python watcher/event bus, `/api/events/stream`, native watcher/events and client invalidation are implemented; #188 and children are closed. | This is not a universal Drive consistency or uninterrupted push-delivery guarantee. |
| Squad management | Native deploy/bench/vanguard routes and tests exist alongside web routes. | The earlier claim that these native mutations were absent is superseded. No new squad redesign is selected. |
| Forge/Reid/War Room | Python runtime bridges exist in native P5; [current text provider boundary](openrouter-text-generation.md) supersedes historical local-only defaults. | Configured live quality/spend and the separate Portal accounting contract remain outside this audit; cloud generation stays disabled. |
| Journal composer/Holocron | [Save verification](journal-save-verification.md), [freshness](refresh-freshness.md), S006/S008 and S028 supply scoped packaged/browser evidence. | Do not describe these selected journeys as globally awaiting first packaged smoke; physical races and installer limits remain separate. |

## Completed bounded follow-ups

The [map lifecycle smoke and repairs](map-telemetry-lifecycle-smoke.md) passed after
merged PR #47. The subsequent [packaged combat recovery smoke](combat-packaged-recovery-smoke.md)
passed Execute, retry after actual app relaunch and Cancel, with journal/card/XP
integrity and process cleanup. These records supersede the original audit's absence
of evidence for those selected journeys. Cloud generation remains disabled.

The user selected reviewed encounter setup/selection as the next bounded change;
its scope and verification are recorded in [encounter setup](combat-encounter-setup.md).
Waived progression work, production XP migration, installer exercises, live
integrations and AI configuration are not implied follow-ups.

## Unselected broader directions

Batch card-art pipelines, gallery ingestion, annual/quarterly analytics, multiverse
decision tracking, broader creative-project matrices, live objective pinning,
ambient soundscapes/dynamic backgrounds and richer health/training visualizers remain
product directions, not confirmed active defects or newly authorized implementation.
Existing assets, entity reads, telemetry, trophy derivation and sector UIs do not
establish those entire workflows. Scope and evidence must precede a new story.
