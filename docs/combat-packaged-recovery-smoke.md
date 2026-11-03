# Packaged combat recovery smoke — 2026-11-03

**Result: PASS for Execute, retry after real app relaunch, and Cancel in isolated packaged fixtures.** No application source changed. This is agent-operated acceptance, not a human usability or production-Vault trial.

## Runtime and isolation

- Source baseline: main `1065053baec42bb1f53c5a79be2923e1f04f1654`.
- Packaged Windows release: **1.11.40**, executable SHA-256 `07a3b275a9e7ae95838a3630db068d4c6379437e55f401bcfddcd1cabc487889`. All 53 copied Python resources matched source with line-ending normalization.
- Fresh Vaults and WebView profiles under private `.tools/combat-smoke-20261103/`; accepted cases: `execute`, `retry2`, `cancel2`. Each had its own copied release/resources, BOM/CRLF journal, two synthetic cards and zero-XP Keeper.
- Links were seeded through the packaged `native_combat.py` adapter during setup. The accepted Execute, retry and Cancel outcomes were initiated through the actual desktop Tactical Cockpit.
- `NAVIS_ROOT` and `NAVIS_PYTHON` selected only the fixture and verified virtualenv. Cloud key/config variables were removed; generation remained disabled. No personal Vault, sync, rollover or production integration was used. No FastAPI listener was observed on port 8000, and no backend server was launched or personal service stopped.

## Observed journeys

| Journey | Packaged UI and durable read-back |
| --- | --- |
| Execute | Execute Sequence checked the exact linked task. Active link removed; card `a` appeared once in discard and burn card `b` once in lost. Resolution `combat-execute` reached `complete`. Canonical ledger had exactly one Keeper award of **12 XP**. |
| Retry after relaunch | Before Execute, the fixture's `Bridge/CompanionStats.json` was temporarily renamed to `.hold`, causing the real XP dependency check to fail. UI showed recovery pending and Retry completion. Durable phase was `xp_sync_pending`, task checked, cards committed, XP absent. The app was terminated, the original stats file restored and a different app process launched against the same fixture. Its cockpit loaded Retry completion from disk. Clicking it completed `combat-retry2`; read-only inspection confirmed one 12-XP ledger row **before** any CLI replay. Journal bytes were identical to the saved pending checkpoint and card counts stayed one each. |
| Cancel | The visible “Cancel link without completing task” control produced completed cancellation `combat-cancel2:cancel`. Journal remained byte-for-byte identical to its original unchecked state, stats unchanged, no XP rows and no progression database. Link removed and cards transitioned once to discard/lost. Cancellation does not return them to the hand. |

After completed UI outcomes, separate packaged-adapter replays for Execute and retry returned `idempotent_replay: true`, `xp_sync: not_repeated`. Journal, battle state, stats and ledger rows remained unchanged. These adapter replays supplement the UI journey; they are not described as extra UI clicks.

XP was verified from the canonical ledger and `ledger_xp` projection. Compatibility `xp` remained zero in CompanionStats; the sidebar's compatibility display was not used as proof of the new award. The synthetic `status.tasks` list was seeded for display, so its continued field-target entry is not evidence of an unchecked journal after completion.

## Integrity, cleanup and limits

For accepted cases, baseline hashes covered nine original fixture files. Only expected battle state/lock bookkeeping, completed journal and XP projections changed. Cancel changed only battle state and the completion lock. Original BOM/CRLF journal content outside the checkbox/completion metadata survived; pre-edit backups matched original bytes. Retry did not rewrite its already-completed journal. Added files were expected journal backups, XP ledger/projection and generated weekly Holocron caches.

All fixture app/Python/WebView process trees were stopped. Final read-back found **zero remaining combat fixture processes**. The temporary unavailable stats file was restored. Private harnesses, JSON read-backs and screenshots remain under `.tools/`; no synthetic fixture data is added to tracked application assets.

Two attempts were discarded rather than counted as passes:

- The first recovery attempt mixed an early read-back with a CLI replay before UI completion was established. That replay could finish recovery, so `retry` is excluded. Fresh `retry2` used read-only inspection until the UI-only operation reached complete.
- The first Cancel attempt reached a completion operation, with ambiguous native AX/input mapping. It is excluded. Fresh `cancel2` restored the window to one full-size screenshot region and used the observed Cancel control; its cancellation ID and untouched journal independently confirm the outcome.

Native helper geometry intermittently exposed a 16×16 icon region alongside the full window, and other foreground windows interrupted some inputs. Returned window selection, fresh capture and explicit full-window screenshot regions/restored window geometry resolved those automation issues. No product code was patched to obtain a pass.

This closes the selected packaged Execute/Retry/Cancel/relaunch evidence gap in [the original acceptance record](combat-task-verification.md). NSIS installation, clean-machine Python discovery, physical Drive interruption, other failure checkpoints, cohort changes and concurrent writers were not newly tested here; their separate limits and automated coverage remain as documented. No commit, PR, issue closure or deployment was requested by this smoke run.
