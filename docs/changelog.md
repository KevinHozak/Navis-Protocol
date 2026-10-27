# 📜 Navis-Protocol: Master History & Changelog

A chronological record of high-fidelity architectural shifts, multiversal milestones, and technical calibrations.

**Ordering:** Newest entries first (reverse chronological).

---

## Vault MCP read-only client trial — 2026-10-26

- NAVIS-S020: predefined rubric, reproducible model-free trial runner and sanitized
  results compare direct file/search retrieval with the installed desktop-bundled
  Codex MCP runtime. Five repetitions returned all ten required sources, rejected
  stale evidence and preserved fixture/XP bytes. The decision adopts a controlled
  read-only pilot on that runtime; desktop UI setup, human preference,
  personal-Vault performance and Claude Desktop remain unverified. No persistent
  MCP configuration or write tools were installed. See the
  [trial report](vault-mcp-trial-results.md).

## Vault MCP journal and mission retrieval — 2026-10-26

- NAVIS-S019: `get_journal_range` reads inclusive, canonical journal dates with
  explicit missing dates, configured timezone and bounded continuation.
  `get_mission` reads Main/Side mission definitions with duplicate-name
  disambiguation and bounded context from explicit internal links. Both reuse
  the shared read policy without an index, journal initialization, cache
  generation, sync or XP changes. Disposable fixtures cover boundaries, errors,
  links, budgets, junctions and real stdio calls. Internal Unicode paths retain
  character-count bounds without unnecessary URL expansion.

## Vault MCP search and freshness — 2026-10-26

- NAVIS-S018: source-linked `search_vault`, a separate private FTS5 generation
  store and an explicit local rebuild command. Searches distinguish current
  empty results from stale indexes, corrupt/missing indexes and unreadable or
  unavailable Vaults. Failed builds retain the last complete generation.
  Synthetic fixtures cover exclusions, source provenance, phrase/keyword
  queries, bounds and CLI/stdio behavior. Shared note reads now preserve C#
  heading names and fenced-code boundaries; plural credential/secret filenames
  and directories are excluded. See [operation and limits](vault-mcp.md).

## Standalone Vault MCP boundary — 2026-10-26

- NAVIS-S017: independent Python stdio adapter with a bounded, source-linked
  `read_note` tool, explicit Vault roots and exclusions, Windows path/link
  checks, safe errors and disposable-fixture process verification. Shared HTTP
  path containment is extracted without changing its contract. See the
  [operating guide](vault-mcp.md). Search, journal/mission retrieval, client
  adoption and write enablement remain NAVIS-S018–S021; no desktop installer
  or personal-data connection is certified by this change.

## Merged delivery — 2026-10-02

Verified from first-parent repository history through `fd3efb4`. PR links identify merged delivery, not manual release certification. Current application metadata is `1.7.1`.

- [#180](https://github.com/KevinHozak/Navis-Protocol-Private/pull/180): live Week-to-Date (WTD) telemetry aggregation, 7-day ISO cycle metrics, and local Ollama tactical debrief synthesis with deterministic rule-based fallback; cockpit `WeeklyHolocronView` with metrics cards, day rhythm charts, and standalone HTML/JSON export.
- [#181](https://github.com/KevinHozak/Navis-Protocol-Private/pull/181): Weekly Holocron exposed under `CHRONICLE` pillar (`HOLOCRON`) in desktop navigation and Tauri native bridge (`backend/native_holocron.py`, `vault::holocron_request`).
- [#182](https://github.com/KevinHozak/Navis-Protocol-Private/pull/182): desktop live backend repository path resolution in `operations.rs` and UTF-8 stream encoding configuration in `native_holocron.py`.

## Merged delivery — 2026-09-30

Verified from first-parent repository history through `85b3db6`; PR links identify merged delivery, not manual release certification. Dates use Git commit dates. Current application metadata is `1.6.2`; older headings below are historical project milestones, not the current installer version.

- [#140](https://github.com/KevinHozak/Navis-Protocol-Private/pull/140): bounded live synthetic local/online comparison and retained result reports; no production provider activation or verified billing is implied.
- [#125](https://github.com/KevinHozak/Navis-Protocol-Private/pull/125) and [#134](https://github.com/KevinHozak/Navis-Protocol-Private/pull/134): map realm navigation and validated telemetry rendering. Measured coordinates and manual web/native smoke remain separate.
- [#126](https://github.com/KevinHozak/Navis-Protocol-Private/pull/126), [#129](https://github.com/KevinHozak/Navis-Protocol-Private/pull/129) and [#138](https://github.com/KevinHozak/Navis-Protocol-Private/pull/138): local squad banter, approved local Forge proposals, and a bounded synthetic AI benchmark.
- [#127](https://github.com/KevinHozak/Navis-Protocol-Private/pull/127) and [#128](https://github.com/KevinHozak/Navis-Protocol-Private/pull/128): conservative historical XP reconciliation tooling and canonical progression dashboard. No production history migration is implied.
- [#130](https://github.com/KevinHozak/Navis-Protocol-Private/pull/130), [#133](https://github.com/KevinHozak/Navis-Protocol-Private/pull/133) and [#135](https://github.com/KevinHozak/Navis-Protocol-Private/pull/135): recoverable combat task completion, parity/restart evidence and duplicate-link protection.
- [#124](https://github.com/KevinHozak/Navis-Protocol-Private/pull/124): packaged-build evidence record; installed/clean-machine smoke remains unperformed.
- [#137](https://github.com/KevinHozak/Navis-Protocol-Private/pull/137) and [#139](https://github.com/KevinHozak/Navis-Protocol-Private/pull/139): isolated test/recovery coverage and prevention of pre-aborted request dispatch.

## Merged delivery — 2026-09-26 to 2026-09-29

- [#104](https://github.com/KevinHozak/Navis-Protocol-Private/pull/104), [#107](https://github.com/KevinHozak/Navis-Protocol-Private/pull/107), [#117](https://github.com/KevinHozak/Navis-Protocol-Private/pull/117), [#118](https://github.com/KevinHozak/Navis-Protocol-Private/pull/118) and [#119](https://github.com/KevinHozak/Navis-Protocol-Private/pull/119): Python discovery, subprocess lifecycle and default Vault-root fixes.
- [#120](https://github.com/KevinHozak/Navis-Protocol-Private/pull/120) and [#121](https://github.com/KevinHozak/Navis-Protocol-Private/pull/121): canonical entity XP writers/projections and native projection repair.
- [#122](https://github.com/KevinHozak/Navis-Protocol-Private/pull/122) and [#123](https://github.com/KevinHozak/Navis-Protocol-Private/pull/123): native sync/rollover verification scaffolding and isolated fixture runtime.
- [#103](https://github.com/KevinHozak/Navis-Protocol-Private/pull/103) and [#108](https://github.com/KevinHozak/Navis-Protocol-Private/pull/108): local-first AI provider interface and opt-in online guardrails.
- [#106](https://github.com/KevinHozak/Navis-Protocol-Private/pull/106), [#112](https://github.com/KevinHozak/Navis-Protocol-Private/pull/112), [#113](https://github.com/KevinHozak/Navis-Protocol-Private/pull/113), [#114](https://github.com/KevinHozak/Navis-Protocol-Private/pull/114) and [#115](https://github.com/KevinHozak/Navis-Protocol-Private/pull/115): map-node validation and realm selection/decoding/hop refresh fixes.

These entries summarize source delivery only. See the [roadmap](roadmap.md) and [release guide](desktop-release.md) for partial capabilities and outstanding runtime gates.

---

## [3.1.2] - 2026-06-24 (Roadmap Reorganization) 🗺️
### 📋 Roadmap Updates
- **Phase Reordering:** Moved `Banter Economics & Cost Controls` from `Phase 15` to `Phase 20` to reflect current backlog prioritization.
- **Documentation Canonicalization:** Established `Navis-Protocol/docs/changelog.md` as the single source of truth for project history, deprecating the prior `Navis-Vault/Documentation/Changelog.md`.

---

## [3.1.1] - 2026-06-23 (Neural War Room: Phase 10 Complete) 🧠
### 🏆 Strategic Milestones
- **API Model Migration:** Migrated the backend `warroom_chat` endpoint to leverage the configured Google Gemini API with standard models, removing the hard constraint on local Ollama.
- **Multi-Persona Chat Styling:** Optimized React parse and styling logic in `WarRoom.js` to correctly color-code dialogue prefixes for active squad members.
- **Live Context Syncing:** Synchronized live active-squad profiles, current realm situational metrics, and recent journal context seamlessly with the conversation prompt.
- **Companion Repair:** Diagnosed and restored silent companion `Rita Vrataski` by generating her missing `Persona.json` manifest, returning full tactical dialogue output. ✅

---

## [3.1.0] - 2026-06-20 (Immersive Sector Dashboards: Phase 9 Complete) 🖼️
### 🏆 Strategic Milestones
- **Library Zettelkasten HUD:** Built a dedicated interface to query the `Library_Intelligence.db`.
- **Prism Nexus Dashboard:** Engineered a glassmorphic dashboard for streaming rich media checklists.
- **Quest Boards Kanban:** Rendered Mission folders as interactive Kanban/Grid cards, retiring the left-rail.
- **Realm Hop Gateway:** Rebuilt the Moongate selector as a full-screen, visually stunning gateway.
- **The Vault Wealth Dashboard:** Built a Wealth & Ledger UI to parse and visualize `Wealth_Performance_Dashboard_v2.md`, integrating live Beancount telemetry via Recharts. ✅

---

## [3.0.0] - 2026-04-18 (The Sovereign Ascension: Operational Re-Architecture)
### 🏆 Strategic Milestones
- **Operational Manifold Re-Architecture**: Reorganized the entire Missions/Operations hierarchy into a high-fidelity nested structure. Missions now reside within their respective Operation theaters (`/Operations/Op_Name/Main/`). 🏰🏠⚔️⚖️🧭✅
- **Sovereign Ribbon Expansion**: Uplinked individual Operations directly to the Level 1 Sovereign Ribbon, enabling rapid tactical deployment from the primary navigation tier (Sanctum, Domestic, Front, etc.). 🛰️🚩✅
- **Engine Modularization (Phase 3)**: Fully deconstructed the `/Engine` root into logical sub-manifolds (`forge/`, `neural/`, `rendering/`, `rpg/`, `sync/`, `utility/`) for enhanced stability and high-fidelity orchestration. ⚙️📦✅
- **Temporal Control Integration**: Engineered a dedicated "New Day" tactical control within the Journal interface, enabling manual temporal rollovers and automated manifold refreshes. 🌅🔘✨✅
- **Legacy Zero-Entropy Purge**: Purged 15+ obsolete/temporary scripts to reduce system entropy and stabilize the Logic Engine core. 🧹🛡️✅

### 🏗️ Architecture & Core Engine
- **Nesting-Aware Scanning**: Re-engineered `ArchivalEngine.scan_sectors` to traverse the new nested mission directory structure.
- **Dynamic Ribbon Injection**: Updated `NavigationEngine` and `SovereignRibbon` to handle the expanded operation pillars.
- **Signal Bridge Synchronization**: Refactored `SyncOrchestrator` with a centralized script-path resolution manifold to support the modular directory structure.
- **Path Resolution Calibration**: Synchronized `SettingsManager` and `OperationEngine` to reflect the new root-level `/Operations` directory.

### 🖥️ UI & Interface Standard
- **Automated Chrono-Focus**: Implemented silent "Go to Today" snapping on Journal sector entry, ensuring the current temporal anchor is visually highlighted.
- **Operational Occlusion**: Refined the `EntityRail` logic to automatically filter structural sub-folders (`Main`, `Side`, `Archive`) from the operation view.
- **Link Hijacking Resiliency**: Patched `load_any_file` to prevent the system from attempting to open non-file sector strings in external applications.

### ⚙️ Engine & Logic
- **Success-Chain Rollouts**: Integrated `scan_sectors` and `refresh` triggers into the `daily_rollover` success callback for immediate visual propagation.
- **Modular Import Matrix**: Updated all core engines (`navis_protocol.py`, `operation_engine.py`, etc.) to utilize the new modular import paths.

---

## [2.1.1] - 2026-04-16 (The Stability & Documentation Calibration)
### 🏆 Strategic Milestones
- **Modular Manifold Deconstruction**: Extracted `NavigationEngine`, `NeuralCoordinator`, `RPGDataEngine`, and `SystemCoordinator` from the monolithic `NavisQt`. ⚙️✅
- **God-Object Deduplication**: Surgically removed over 300 lines of redundant code from `navis_protocol.py`. 🧹✅
- **Documentation Master-History**: Consolidated all legacy milestones and granular logs into this unified, date-driven history. 📚✅
- **Roadmap Refinement**: Calibrated `Roadmap.md` with active initiatives (Companions GUI, Moongate Stress-Test). 🗺️✅
- **Persona Emulation Expansion**: Successfully rolled out `Persona.json` manifests for all 20 companions, establishing high-fidelity voice directives and context-injection rules for the Neural Link. 👥🧠✅

### 🏗️ Architecture & Core Engine
- **State Source-of-Truth Alignment**: Corrected inconsistent references to `current_world`, ensuring all modules pull from `self.rpg_engine.current_world`.
- **Settings Path Resolution**: Added the missing `path` attribute to `SettingsManager` to ensure correct document resolution.

### 🖥️ UI & Interface Standard
- **Lifecycle Integrity Fix**: Resolved critical `RuntimeError` in `BanterBubble` via `shiboken` validity checks and idempotent fade-out logic.
- **White-Screen Neutralization**: Standardized background transparency and dark base layers to eliminate white flashes.
- **Navigation Signal Restoration**: Re-connected `view_changed` and `area_changed` signals in the constructor.
- **Recursive Switching Guard**: Implemented state-change guards in `NavigationEngine` to prevent process crashes.

### ⚙️ Engine & Logic
- **Theming Integration**: Restored the `apply_theme` method to the `NavisQt` class for high-fidelity visual sync.
- **Neural Context Calibration**: Fixed spatial realm context passing in `trigger_neural_input`.

---

## [2.1.0] - 2026-04-16 (The Modular Manifold: Advanced Refactoring)
### 🏗️ Architecture & Core Engine
- **Surgical Modularity Phase 2**: Continued the deconstruction of the `NavisQt` "God Object" by extracting specialized engines:
    - **`navigation_engine.py`**: Centralized all routing logic, view switching, and sector-mapping.
    - **`neural_coordinator.py`**: Extracted neural query management, threading, and status signaling.
    - **`view_renderer.py`**: Centralized all HTML generation logic for rendering consistency.
    - **`markdown_renderer.py`**: Created a dedicated module for converting tactical Markdown into HTML.
- **Path Resolution Calibration**: Updated `generate_party.py` and `generate_battle.py` for cross-drive script execution.

### 🖥️ UI & Interface Standard
- **Emoji Rendering Calibration**: Swapped the "🛰️" (Satellite) emoji for the more reliable "📡" (Satellite Antenna) on command buttons.
- **UI Widget Subclassing**: Moved `JournalCalendar`, `CompanionCard`, and `BanterBubble` into specialized `/ui` modules.
- **Portrait Resolution Fix**: Corrected path error in `CompanionCard` for the Keeper's portrait.

### ⚙️ Engine & Logic
- **Dynamic Battle Manifolds**: Overhauled `generate_battle.py` to pull dynamic squad data and visual recipes.

---

## [2.0.0] - 2026-04-11 (The Qt Ascension: PySide6 Migration)
### 🏆 Strategic Milestones
- **PySide6 (Qt) Migration**: Fully transitioned the interface from Tkinter/customtkinter to **PySide6**. 🌐✅
- **The Great Reforging**: Successfully transitioned the entire Codex from a deep GTD structure to a flat, narrative-driven RPG hierarchy (Campaigns, Lore, Camp). 🏛️✅
- **Legacy Tkinter Archive**: Decommissioned the original `RPGTerminal` (Tkinter V1.0) and archived the source as `navis_1.py`. 💾✅
- **Internal Link Hijacking**: Engineered a custom `QWebEnginePage` to intercept tactical URL schemes. 🔗✅
- **Ollama Neural Link Integration**: Replaced cloud-based Gemini CLI with a local-first **Ollama** engine (`neural_engine.py`) for enhanced privacy and offline autonomy. 🧠✅
- **Installations Framework Deployment**: Re-anchored the "Vault" into the **INSTALLATIONS** manifold, transforming the Codex from a library into an active Base of Operations. 🏛️✅
- **Interactive Checklists**: Restored surgical on-disk Markdown modification via UI triggers. ✅✅
- **Tactical Command Ribbons**: Button-driven interface replacing the text terminal. 🛰️✅
- **Sidebar Dominance Architecture**: Implemented the permanent 3-column navigation system (Nav 1, Nav 2, Content) with a dedicated RPG Status Sidebar. 🏢✅
- **Global System Dropdown**: Centralized system actions for sync, backup, and maintenance. ⚙️⚙️
- **Operational Readiness System**: Automated 10-day consistency tracking for strategic sectors. 📊✅
- **Advanced Banter Engine**: Native Qt Banter Bubbles with context-aware, animated dialogue. 💬✅

### 🏗️ Architecture & Core Engine
- **Surgical Modularity Phase 1**: Deconstructed the monolithic `navis_protocol.py` into `settings_mgr`, `archival_engine`, `theming_engine`, `sync_orchestrator`, `media_manager`, `dialogue_engine`, `neural_engine`, `banter_engine`, and `operation_engine`. ⚙️✅
- **Multi-Context Neural Core**: Refactored `neural_engine.py` to handle context-switching and local persistence via `Persona.json` manifests. 🧠✅

### 🖥️ UI & Interface Standard
- **Calendar Calibration**: Overhauled the Journal calendar to support a Sunday-start week with selection highlighting.

---

## [1.9.2] - 2026-04-08 (Navis UI Streamlining)
### 🖥️ UI & Interface Standard
- **Navis Button Removal**: Surgically removed the NAVIS button to declutter the navigation ribbon.
- **Neural Backgrounding**: Transitioned the Neural Link from a dedicated UI tab to a high-fidelity background service.

---

## [1.9.1] - 2026-04-05 (Unified Entity Protocol)
### 🏗️ Archival Standard
- **Dossier Unification**: Renamed all `Quest.md` to `Mission.md` and all `World.md` to `Realm.md`.
- **Visual Asset Standard**: Codified `Landscape.png` and `Portrait.png` as the high-fidelity standard.

---

## [1.9.0] - 2026-04-05 (Sovereign Aesthetic & Interlink Manifold)
### 🏆 Strategic Milestones
- **XP Progress Bars**: High-fidelity reactive progress bars integrated into the TUI sidebar. 📊✅
- **Vitality Gauge**: Automated integration with health data via Fitbit/Health Connect sync. 🏋️✅

### 🎨 Sovereign Aesthetic (UI)
- **Standardized Casing**: Mandated ALL CAPS for all primary command buttons.
- **Functional Wikilinks**: Engineered `sync_bridge.py` to process Obsidian-style `[[label]]` wikilinks.

---

## [1.8.0] - 2026-04-01 (Codex Deployment)
- **Unified Archival Manifold**: Consolidated Personae, Obstacles, Realms, and Lore into a single CODEX view.

---

## [Legacy] - 2026-03-30 (The Great Biometric Shift)
- **Manual Biometrics Decommissioned**: Removed SUDs, Focus, and Vitality manual tracking in favor of automated alternatives. 💾✅

---

## [Legacy] - 2026-03-17 (The Great Reforging)
### 🏆 Strategic Milestones
- **RPG Hierarchy Blueprint**: Defined the high-level narrative structure (🏹 Quests, 📜 Lore, 🏕️ The Camp). 🏛️✅
- **Zero Entropy Purge**: Systematically transmuted all legacy `.gdoc`, `.gsheet`, and `.gslides` into localized Markdown/CSV. 🧹✅
- **Archive Consolidation**: Bridged 25 years of journal history (2001-2026) and consolidated legacy data into mandate-aligned ledgers. 🧬✅
- **Unified Ledger Forge**: Consolidated all intake streams and localized Google Keep history into the Codex. 🔗✅
- **Temporal Bridge**: Bridged "Missing Years" (2001, 2013-2018) to create a continuous high-fidelity timeline. 🌉✅

---
Historical entries above retain their original descriptions; they are not current runtime or data-integrity certification.
