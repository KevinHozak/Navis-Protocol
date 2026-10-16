# Navis-Protocol roadmap

Reconciled against merged `origin/main` at `fd3efb4` on 2026-10-02. **Implemented** means source is merged. **Partial** means a bounded feature exists with remaining scope. **Planned** means the broader capability is not established by the inspected implementation. **Awaiting runtime verification** is independent of implementation: no status here certifies a personal Vault migration, live provider/device connection or clean-machine installation.

## Delivered work and remaining verification

| Workstream | Implementation state | Evidence and remaining work |
| --- | --- | --- |
| Native Windows runtime | Implemented, partial route coverage | Tauri static export, IPC modules and installed resources; [desktop guide](../frontend/README-DESKTOP.md), [endpoint registry](api_endpoints.md). Unsupported HTTP routes remain explicit. |
| Desktop sync hardening (#79, #80–82) | Implemented; awaiting packaged verification | Shared Python resolver, bounded subprocess lifecycle and disposable-fixture sync/rollover. Build evidence exists; installed resource resolution, clean-machine launch and close/cancel smoke remain open in [release guide](desktop-release.md). |
| Weekly Holocron & telemetry synthesis (#179–182) | Implemented; native bridge delivered | 7-day ISO cycle aggregation, live Week-to-Date (WTD) telemetry, local Ollama tactical debrief with rule-based fallback, standalone HTML export, desktop Tauri IPC adapter (`backend/native_holocron.py`, `vault::holocron_request`). Packaged runtime smoke remains open. |
| XP authority (#67, #68–69) | Implemented | Entity-scoped append-only ledger, idempotent writers and projections; [architecture](architecture.md). Legacy totals are retained separately. |
| Historical XP reconciliation (#70) | Implemented tooling; awaiting operator/runtime verification | Conservative inventory, reviewed mappings, backups, apply/recovery and rollback; [reconciliation](xp-reconciliation.md). Tool delivery does not establish production migration. |
| Canonical progression dashboard (#71) | Implemented; awaiting packaged verification | Ledger totals/history and API-derived thresholds; [acceptance record](progression-p4-verification.md). Broad health/task analytics remain planned. |
| Interactive map (#75, #76–78) | Implemented rendering/navigation; partial telemetry | Validated node selection and realm hop; measured-coordinate overlays and stale/mismatch omission. Coordinate production is not supplied by navigation. See [telemetry contract and pending web/native smoke](map-telemetry.md). |
| Combat hand and linked tasks (#85–88) | Implemented; awaiting packaged verification | Battle state UI, exact task binding, durable recovery, duplicate-link rejection and native/web parity fixtures; [verification](combat-task-verification.md), [link constraint](combat-link-constraint.md). Full tactical buffs and turn rules remain partial. |
| Local-first AI (#91–95) | Implemented provider boundary and bounded workflows; partial native coverage | Guarded opt-in online generation, local banter, Forge proposal approval and synthetic benchmark; [AI guide](local-first-ai.md), [Forge](forge-local-generation.md), [benchmarks](benchmarks/README.md). Native general chat/War Room and hosted accounting remain unavailable. Bounded live synthetic comparison results are recorded; they do not establish companion/creative quality or general reliability. |
| Journal entry composer | Implemented | Checked-item append and local optional polishing; no missing-journal creation. See [API contracts](api_endpoints.md). Native general toggle still lacks web XP synchronization. |
| Regression/test infrastructure (#131, #136) | Implemented | Isolated state/recovery tests and pre-aborted transport guard; [test audit](testing-audit.md). Source tests do not replace release smoke. |

## Broader product backlog

These retain the original product direction without treating an existing component as completion of its entire initiative.

| Initiative | State | Current boundary / next work |
| --- | --- | --- |
| Batch card-art generation | Planned | Existing card assets and battle UI do not establish a verified batch pipeline. |
| Analytics manifold / intelligence dashboard | Partial | Canonical XP dashboard and Weekly Holocron telemetry HUD exist; annual/quarterly rollups, health trends and long-term task-history charts remain broader work. |
| Beast bestiary | Partial | Entity reads/profiles exist; weakness matrices and historical combat analytics planned in Epic [#183](https://github.com/KevinHozak/Navis-Protocol-Private/issues/183) ([#185](https://github.com/KevinHozak/Navis-Protocol-Private/issues/185), [#187](https://github.com/KevinHozak/Navis-Protocol-Private/issues/187)). |
| Gallery integrations | Planned | General Vault asset access does not establish a gallery ingestion/scraping workflow. |
| Synthesis Lab HUD | Partial | Synthesis interface exists; full creative-project/multiverse matrices remain planned. |
| Companion Forge | Implemented bounded generation | Local proposal and explicit approval exist; full blueprint coverage and live quality validation remain follow-up work. |
| Multiverse decision tracking | Planned | A dedicated decision-tree analysis workflow remains broader scope. |
| AI spend audit and banter | Partial | Provider logging/guards and local banter are merged; automatic sync/rollover generation policy and native hosted accounting must be verified separately. |
| Squad management and dossier cards | Partial | Reserve/profile UI and status reads exist; native deploy/bench/vanguard HTTP equivalents are absent. |
| Stats dashboard | Partial | Attributes and entity UI exist; complete analytical visualization remains broader work. |
| Talent tree | Planned | Graphical progression and perk ledger tracked in Epic [#193](https://github.com/KevinHozak/Navis-Protocol-Private/issues/193) ([#194](https://github.com/KevinHozak/Navis-Protocol-Private/issues/194)–[#196](https://github.com/KevinHozak/Navis-Protocol-Private/issues/196)). |
| Achievement Hall | Partial | Achievement reads exist; full trophy/gallery workflow remains planned. |
| Combat engagement protocol | Partial | Hand, link, resolve and rest exist; full turn-based tactical mechanics tracked in Epic [#183](https://github.com/KevinHozak/Navis-Protocol-Private/issues/183) ([#184](https://github.com/KevinHozak/Navis-Protocol-Private/issues/184)–[#186](https://github.com/KevinHozak/Navis-Protocol-Private/issues/186)). |
| Live objective HUD | Partial | Active-mission selection exists; full objective pinning remains broader scope. |
| Ambient soundscapes | Planned | Realm-specific audio workflow remains planned. |
| System alerts | Partial | Diagnostics/errors and operation progress exist; real-time file watcher & SSE push tracked in Epic [#188](https://github.com/KevinHozak/Navis-Protocol-Private/issues/188) ([#189](https://github.com/KevinHozak/Navis-Protocol-Private/issues/189)–[#192](https://github.com/KevinHozak/Navis-Protocol-Private/issues/192)). |
| Dynamic backgrounds | Planned | Realm assets do not establish full animated atmosphere support. |
| Exercise tracker / biometric uplink | Partial | Vitals/history/exercise reads exist; live Fitbit/device linkage and training visualizer require separate validation. Edge cases in [#197](https://github.com/KevinHozak/Navis-Protocol-Private/issues/197). |
| HP / MP / AP gauges | Partial | Readiness/status telemetry exists; complete metric-to-gauge rules and live validation remain broader work. |
| Automated backups | Partial | Sync/backup jobs exist; universal automatic uplink scheduling is not established. |
| Bidirectional synchronization | Partial | Journal edits and combat completion write back; real-time push synchronization tracked in Epic [#188](https://github.com/KevinHozak/Navis-Protocol-Private/issues/188). |

Use issue acceptance criteria and the linked evidence records to select follow-up work. Recheck issue state before starting: merged implementation and unfinished manual verification can coexist.
