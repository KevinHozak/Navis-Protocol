---
depends_on: []
id: "NAVIS-E002"
parent: []
priority: "medium"
schema_version: 1
status: "in_progress"
title: "Make Navis trustworthy at a glance"
type: "epic"
---
## Outcome

Make Navis trustworthy at a glance: in representative web and desktop journeys, the user can identify stale or unavailable data, verify a saved change, inspect supporting evidence and understand partial failures without reading logs.

## Context and scope

This is an audit-first proposal, not a claim that safeguards are absent. Existing diagnostics, asynchronous progress, ledger provenance, journal writing and Holocron foundations must be inspected before selecting repairs. Scope covers frontend, FastAPI, Tauri/native adapters, affected views and relevant launcher/runtime boundaries. Source checks do not establish packaged-app behavior.

The first story inventories confirmed gaps. Each candidate repair story depends on that audit and must link a reproducible finding before implementation. If already satisfied or duplicated, record evidence and reconcile the story's scope rather than adding redundant controls. Do not mark unimplemented acceptance as passed; explicitly disposition unnecessary branches before reconciling epic completion.

Companion work: [AI workflow experiments](NAVIS-E001.md), especially [Holocron evidence presentation](NAVIS-S006.md). That epic is not a prerequisite. Reuse or narrow overlapping work rather than building a second provenance interface.

Use disposable fixtures and sanitized evidence. Do not mutate personal Vault records for audit reproduction, expose private content in repository evidence, introduce hosted generation or background schedules, or claim runtime verification that was not performed. Follow existing glassmorphism, accent and transition conventions in UI changes.

## Acceptance criteria

- [x] Audit identifies existing coverage, confirmed defects, proposals and unverified runtime gaps separately, with prioritized evidence and affected journeys.
- [ ] Only confirmed gaps receive repairs, with disposition of already-satisfied or overlapping candidates.
- [ ] Relevant checks and representative web and packaged-desktop journeys establish trustworthy freshness, data states, persistence, evidence navigation and partial-failure recovery without logs; any unavailable runtime checks remain explicit blockers.
- [ ] All retained child acceptance and verification evidence is reconciled before completion; creating records does not complete the epic.

## Stories

- [NAVIS-S009](NAVIS-S009.md): Audit trust signals and identify confirmed gaps
- [NAVIS-S010](NAVIS-S010.md): Expose freshness and failed-refresh state for confirmed gaps
- [NAVIS-S011](NAVIS-S011.md): Distinguish unavailable data from valid empty and zero results
- [NAVIS-S012](NAVIS-S012.md): Verify saved journal and task changes against authoritative state
- [NAVIS-S013](NAVIS-S013.md): Make Holocron metrics and interpretations traceable to evidence
- [NAVIS-S014](NAVIS-S014.md): Explain partial sync failures and offer safe recovery
- [NAVIS-S015](NAVIS-S015.md): Verify trust journeys across web and packaged desktop

## Audit checkpoint - 2026-10-27

S009 completed a source/fixture audit with seven confirmed findings and existing safeguards mapped. [Report and web/native matrix](../docs/trust-signals-audit.md). S010-S015 are narrowed to the recorded findings and runtime verification gates. Start repairs with S014 partial-operation truthfulness, then S013 evidence/metric labels; S011/S012 are also high priority. No application fixes were made. Existing Python checks have three recorded failures (two manifest assumptions, missing watchdog); packaged checks remain unrun. The epic remains in progress.
