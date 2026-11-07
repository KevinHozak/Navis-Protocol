---
depends_on: []
id: "NAVIS-S029"
parent: []
priority: "medium"
schema_version: 1
status: "open"
title: "Read-only Quarterly Holocron preview"
type: "enhancement"
---
## Outcome

As the Keeper, I want an explicitly requested quarterly summary showing recorded checklist activity, signed Keeper XP and source coverage, so I can review a longer period without mistaking missing data for inactivity.

## Context

Selected from the unselected annual/quarterly analytics direction in the [roadmap](../docs/roadmap.md). Existing weekly aggregation and the [Holocron evidence contract](../docs/holocron-evidence.md) provide a foundation; they do not establish a quarterly workflow. Read original journal and canonical ledger evidence rather than treating weekly caches as authoritative quarterly totals.

The user authorized local issue creation on 2026-11-07 only. Implementation, application launches, personal-Vault access and provider calls are not authorized by this issue-creation request. This is a standalone enhancement with no inferred epic or dependency.

## Target areas (proposed)

- `backend/services/holocron_engine.py`: existing journal parsing and canonical progression telemetry rules.
- `backend/services/holocron_evidence.py`: coverage, safe relative source references and unavailable-data semantics.
- One bounded local preview command and synthetic offline verification; final implementation structure is not prescribed here.

## Acceptance criteria

- [ ] One local command accepts an explicit root and `YYYY-Q1` through `YYYY-Q4`, returning a JSON preview without writing files. Do not default to the personal Vault.
- [ ] Output identifies inclusive calendar-quarter dates and readable, missing and unreadable journal-day counts.
- [ ] Checklist metrics count entries, not inferred unique tasks. Completion percentage is unavailable when there are no observed checklist entries.
- [ ] XP uses canonical signed Keeper ledger rows within the quarter. A readable empty ledger means zero; missing or unusable evidence means unavailable. Exclude other entities and out-of-quarter rows; do not sum overlapping weekly caches.
- [ ] Output includes aggregation rules and relative source references, without journal bodies or absolute personal paths.
- [ ] Synthetic offline fixtures cover quarter boundaries, leap years, partial coverage, XP corrections and unavailable inputs. Original fixture bytes remain unchanged, with no artifacts or caches created and no provider/network calls. Verification does not launch Navis or access the personal Vault.

## Explicit exclusions

- No UI integration, annual summaries or quarter-to-quarter comparisons.
- No AI narrative or inferred readiness, focus hours or combat outcomes.
- No exports, caching, scheduling or background generation.
- No task creation, journal edits, XP migration, sync or rollover.
- No personal-Vault qualification, production-data migration, provider configuration, credentials or paid/live calls.

## Verification boundary

This issue is open planning scope, not evidence of a current product defect or implementation completion. Existing weekly evidence retains its own dates and runtime limits. A future implementation request must preserve read-only behavior and validate solely against explicitly supplied synthetic roots.

## Proposed contract and verification plan

The [JSON contract and synthetic verification matrix](../docs/quarterly-holocron-preview-contract.md) records the proposed schema, calendar-quarter boundaries, unavailable-data rules and zero-write proof obligations. It is a documentation-only draft, not implemented or tested feature behavior. All acceptance criteria remain unchecked.
