# Weekly Holocron Synthesis & Display (Issue 132 Exploration)

> [!IMPORTANT]
> **Exploration & Design Specification**: This document establishes the architectural blueprint, data source contracts, generation trade-offs, scheduling resiliency, and UI integration surfaces for the **Weekly Holocron** (weekly infographic and telemetry synthesis) in Navis Protocol. Per the issue boundary, no automated recurring generation is activated during this exploration phase.

---

## 1. Executive Summary & Core Proposal

Navis Protocol tracks daily combat, task execution, and personal progression across multiple operational Manors. While daily logs (`Journal/YYYY/MM/YYYY-MM-DD.md`) and yearly retrospectives (`generate_infographic.py`) exist, the system currently lacks a regular weekly synthesis. 

This proposal recommends the **Weekly Holocron**—a **deterministic, local-first hybrid architecture**:
1. **Telemetry Engine**: An idempotent aggregator in `backend/services/holocron_engine.py` that parses the 7 daily journals of an ISO operating week (`YYYY-Www`), cross-references `Keeper/navis_progression.db`, and outputs an immutable, machine-readable `weekly_holocron_<week_id>.json`.
2. **Deterministic UI & Vector Graphics**: React-based glassmorphic HUD dashboards in both Web and Tauri cockpits with zero cloud dependencies, instant rendering, and high accessibility.
3. **Optional Local-AI Tactical Debrief**: A structured 2-3 sentence strategic debrief generated via local Ollama (`Kimiko-20B:latest` or `gemma3`) fed with aggregated counts (no raw diary text), with an automatic fallback to rule-based template summaries if Ollama is unavailable.
4. **Resilient Rollover Hook**: Generation triggered during Sunday midnight / Monday 03:00 rollover or on-demand, with automatic startup backfilling for missed runs and idempotent cache checks.

---

## 2. Content Inventory & Available Data Sources

### 2.1 Candidate Content & Metrics Matrix

| Metric Dimension | Candidate Signals | Value & Cognitive Impact |
| :--- | :--- | :--- |
| **Precision & Rhythm** | Total tasks, completed tasks, pending tasks, precision rate (`completed / total * 100`), 7-day daily velocity curve. | Identifies peak productivity days and mid-week friction/drop-offs without guilt. |
| **Manor / Sector Balance** | Task allocation across the 5 Manors: *High-Velocity Front* (work), *The Sanctum* (habits/health), *Domestic Breach* (home), *Bureaucratic Gauntlet* (finances/admin), *Kinetic Outland* (fitness). | Prevents systemic burnout by highlighting over-allocation in one sector at the expense of others. |
| **Progression & XP** | Weekly XP delta, XP distribution by source (tasks, combat, directives, missions), progress to next Sovereign level, achievements unlocked. | Reinforces the RPG progression loop; gives tangible sense of leveling up week over week. |
| **Combat & Nemesis Registry** | Battles initiated, victories, tactical retreats, Prime Beasts neutralized, top encountered adversary. | Visualizes overcoming friction and resistance as vanquished threats. |
| **Party & Squad Activity** | Companion deployment frequency, Vanguard MVP of the week. | Deepens squad connection and companion utility. |
| **Readiness & Focus** | Average readiness score, logged deep-focus hours. | Correlates physiological/mental recovery with task precision. |

### 2.2 Data Source Mapping & Gap Analysis

| Data Source | Location / Interface | Extracted Fields | Gaps & Edge Cases |
| :--- | :--- | :--- | :--- |
| **Daily Journals** | `Navis-Vault/Journal/YYYY/MM/YYYY-MM-DD.md` | Task checkboxes (`- [x]`, `- [ ]`), Manor headers (`## The ...`), `🌀 Realm:`, `👾 Prime Beast:`, `🛡️ Active Squad:`. | **Missing Days**: User may skip logging a day or miss a journal. System must treat missing days as 0-activity days rather than aborting. **Uncategorized Tasks**: Tasks outside recognized Manor headers map to `General / Unassigned`. |
| **Progression Ledger** | `Navis-Vault/Keeper/navis_progression.db` (`xp_ledger`, `achievements`) | Canonical XP awards filtered by `local_date` between week start and end dates; newly unlocked achievements. | Complete and authoritative; guarded by SQLite foreign keys and monotonic award IDs. |
| **Status State** | `Navis-Vault/Bridge/status.json` | Active missions, current companion assignments, Sovereign level. | Point-in-time snapshot; historical mission completions must be verified against journal or XP ledger provenance. |
| **Readiness Manifold** | `Navis-Vault/Bridge/readiness.json` & `/api/readiness` | Category readiness scores (sleep, mental, physical). | Voluntary user logging; partial or null entries must default gracefully to "Telemetry unlogged". |

---

## 3. Evaluation of Generation Approaches

| Evaluation Criteria | Approach A: Deterministic SVG / Component-Driven (Recommended) | Approach B: Local Ollama + Template Hybrid (Recommended Extension) | Approach C: Guarded Cloud AI (Gemini 2.5 Flash) | Approach D: Generative Raster Poster (Diffusion) |
| :--- | :--- | :--- | :--- | :--- |
| **Accuracy** | 100% mathematical precision. Zero hallucinations. | Numbers 100% deterministic; narrative grounded in pre-aggregated counts. | Risk of metric drift or hallucinated completions. | Poor; text rendering in diffusion images is illegible or distorted. |
| **Readability & Accessibility** | High. Scalable vector graphics, semantic DOM, screen-reader support. | High. Clear text debrief + SVG charts. | Moderate. Depends on generated HTML structure. | Poor. Raster pixel array without selectable text or alt-text. |
| **Privacy & Trust** | 100% local. Zero egress. Conforms strictly to local-first rules. | 100% local via loopback Ollama. Zero network requests. | Requires explicit opt-in and budget reservation per `local-first-ai.md`. | Requires online API calls; image generation is explicitly blocked under current text budget. |
| **Maintenance** | Low. Standard Python unit tests and React components. | Moderate. Requires Ollama service check; simple fallback logic. | High. Model version churn, quota limits, pricing audits, network checks. | Very High. Diffusion prompt drift, inconsistent art styles. |
| **Cost** | **$0.00** | **$0.00** | $0.002–$0.005 / week (held against monthly quota). | $0.03–$0.05 / week (exceeds standard AI budget). |
| **Latency** | <50 ms | 3–10 seconds | 2–5 seconds | 15–30 seconds |

**Decision**: **Approach A paired with Approach B**. All numeric metrics, charts, and layout structures are rendered deterministically. If local Ollama is active, it receives an anonymized JSON payload containing only counts (e.g., `{"completed": 41, "top_manor": "High-Velocity Front"}`) to generate the 2-sentence tactical debrief. If Ollama is offline, a deterministic template string is formatted.

---

## 4. Week Boundary, Scheduling, and Resilience

### 4.1 Boundary Definition
- **Journal Day Anchor**: Consistent with `docs/recurrence-contract.md`, each journal day starts at **03:00 local wall-clock time** (America/Chicago).
- **ISO-8601 Operating Cycle**: A week encompasses **Monday 03:00 to the subsequent Monday 02:59:59**.
- **Canonical Identifier**: ISO week notation `YYYY-Www` (e.g., `2026-W40`, spanning Monday `2026-09-28` through Sunday `2026-10-04`).

### 4.2 Lifecycle & Trigger Mechanisms
1. **Primary Trigger**: During the Monday 03:00 midnight rollover routine (`run_midnight_rollover` in `sync_engine.py`). When the rollover advances the active date into a new ISO week, it dispatches the week closure for `previous_iso_week`.
2. **Startup & Missed Run Catch-up**: On backend startup, `sync_engine.py` compares the current date with the latest generated week in `Bridge/Infographics/Weekly/`. If the previous completed week has no corresponding JSON artifact, it schedules a background generation task.
3. **Idempotency & Re-entrancy**:
   - The file is saved as `Bridge/Infographics/Weekly/2026-Www.json`.
   - Before running, the engine checks for the file. If present and the week is in the past, generation is skipped.
   - A `--force` flag or an explicit UI `POST /api/infographics/weekly/{week_id}/regenerate` endpoint allows manual re-synthesis without corrupting historical files.

---

## 5. Storage, History, and UI Cockpit Integration

### 5.1 Storage Hierarchy
All artifacts are maintained within the local Vault manifold:
```text
Navis-Vault/
├── Bridge/
│   └── Holocron/
│       ├── weekly_manifest.json          # Index of all generated weeks, metadata, and stats
│       └── Weekly/
│           ├── 2026-W38.json             # Structured telemetry fixture
│           ├── 2026-W38.html             # Portable, standalone dashboard
│           ├── 2026-W39.json
│           ├── 2026-W39.html
│           ├── 2026-W40.json
│           └── 2026-W40.html
```

### 5.2 UI Presentation Surfaces
1. **Executive Status Card (Command Hub 🛰️ ➔ Status 📡)**:
   - Located on the primary Command landing screen ([`BridgeHome.js`](file:///c:/Projects/Navis-Protocol/frontend/src/components/BridgeHome.js)), an executive summary card appears alongside System Readiness and Active Missions.
   - Displays the latest week's headline metrics (Precision Clearance %, Total XP Yield, Threats Neutralized) and a 2-sentence tactical briefing.
2. **Dedicated Infographics Cockpit (Chronicle 📜 ➔ Weekly Holocron 💠)**:
   - Accessed directly via the top **Chronicle** button (`ScrollText` icon) on the Sovereign Ribbon.
   - Appears as a new item in the **left-rail sector list** alongside *Daily Journal* and *Keeper Ledger*:
     ```text
     CHRONICLE
     ├── 📓 Daily Journal
     ├── ⚖️ Keeper Ledger
     └── 💠 Weekly Holocron  <-- New left list item
     ```
   - Selecting **Weekly Holocron** loads the full interactive cockpit view with:
     - **Week Selector Dropdown**: Historical cycle selection (`2026-W40`, `2026-W39`, ...).
     - **7-Day Rhythm Histogram**: Daily completed vs. pending tasks against the 80% precision threshold.
     - **Manor Labor Distribution**: Visual balance bars across the 5 Manors.
     - **Threat Registry & Honors**: Vanquished Prime Beasts and unlocked achievements.
     - **Export Controls**: Standalone HTML export and Markdown summary copy.
3. **Tauri Native vs. Web Parity**:
   - Both Web and Tauri consume the exact same Next.js component.
   - Tauri adds native file-save dialog integration via `@tauri-apps/api/dialog` for exporting standalone reports directly to user-selected folders.

---

## 6. Synthetic Mockup & Reference Fixtures

To ensure strict zero-vault isolation and repeatable testing:
- **Synthetic Data Fixture**: [`docs/fixtures/weekly-infographic-synthetic.json`](file:///c:/Projects/Navis-Protocol/docs/fixtures/weekly-infographic-synthetic.json)
- **Glassmorphic Interactive Mockup**: [`docs/fixtures/weekly-infographic-mockup.html`](file:///c:/Projects/Navis-Protocol/docs/fixtures/weekly-infographic-mockup.html)

The mockup demonstrates:
- Glassmorphic dark styling (`rgba(15, 23, 42, 0.75)` backdrop blur, `border: rgba(255, 255, 255, 0.08)`).
- Sovereign color codes: Cyan `#00d4ff` (Command/Sanctum), Crimson `#ff4d4d` (Combat), Amber `#f59e0b` (Threat XP), Emerald `#10b981` (Readiness/High Clearance).
- High visual readability on both desktop monitors and laptop screens.

---

## 7. Unresolved Decisions & Follow-up Implementation Plan

### 7.1 Open Design Decisions
1. **Handling Mid-Week In-Flight Weeks**: Should the UI allow viewing a "Week-to-Date" live preview of the current unfinished week, or only closed past weeks?
   - *Recommendation*: Support a "Live Cycle (WIP)" view that compiles Monday to current day, marking it with an `IN_PROGRESS` badge.
2. **Poster Image Diffusion**: Should we provide an optional button to generate a diffusion art poster (e.g., via Antigravity `generate_image` or local ComfyUI/SD) for users who want visual wallpaper art?
   - *Recommendation*: Keep this as a disconnected, manual action to protect AI budgets and prevent unwanted background network calls.

### 7.2 Bounded Implementation Phases

- **Phase 1: Backend Aggregator & Telemetry API**
  - Implement `backend/services/holocron_engine.py` to aggregate 7 days of journals and SQLite XP records.
  - Implement endpoints: `GET /api/holocron/weekly/latest`, `GET /api/holocron/weekly/{week_id}`, `GET /api/holocron/weekly/manifest`.
  - Add pytest suite using synthetic test vectors in `backend/tests/test_weekly_holocron.py`.
- **Phase 2: Frontend Cockpit View**
  - Implement `WeeklyHolocronView.jsx` in `frontend/src/components/`.
  - Wire sector route in `frontend/src/components/SectorView.js` under `CHRONICLE`.
- **Phase 3: Rollover Integration & Standalone HTML Exporter**
  - Connect generation trigger into `sync_engine.py` during Monday rollover.
  - Add single-file HTML generator script for zero-dependency archival.
