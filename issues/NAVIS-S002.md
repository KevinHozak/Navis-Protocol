---
depends_on: ["NAVIS-S001"]
id: "NAVIS-S002"
parent: ["NAVIS-E001"]
priority: "medium"
schema_version: 1
status: "done"
title: "Implement reviewed actionable briefs after a passing trial"
type: "enhancement"
---
## Outcome

Implement reviewed actionable briefs after a passing trial.

Parent: [NAVIS-E001](NAVIS-E001.md). Depends on [NAVIS-S001](NAVIS-S001.md).

## Target areas

frontend/src/components/JournalEntryComposer.js, backend/main.py and native/local AI adapters.

## Acceptance criteria

- [x] Before starting, link a passing five-sample trial and explicit keep decision; completion of the trial issue alone is insufficient.
- [x] Add a distinct Create actionable brief action beside polishing, returning Goal, Known facts, Uncertainties and One suggested next action.
- [x] Provide editable preview and save/discard; durably retain the original with accepted output and source reference rather than relying on component state.
- [x] Require a separate explicit action to create any task; preserve existing journals, dates and checklist states and existing local-first/provider safeguards.
- [x] Verify original retention, save/discard, failure handling and task separation with meaningful checks and web/desktop workflow smoke; review fresh samples after delivery.

## Evaluation, privacy and scope

Follow the parent epic's evaluation record, privacy requirements and trial gates. This issue records planned work only. Conditional implementation requires separately selected work after passing evidence; no trial results are claimed.

## Passing trial and selected scope

[Revised trial](../docs/trials/s001-complex-brief-rerun-2026-10-28.json): 5/5 useful, zero corrections, review time unknown. Explicit keep decision and S002 selection on 2026-10-28. Complex/tangled notes only; preserve original and source with accepted output. Saving a brief must not create tasks.

## Implementation progress

Local-only generation and editable save/discard preview added. Accepted records preserve original, edited brief and composer date/section reference in Library/Actionable Briefs; they do not append journal entries, create tasks or run XP. HTTP and Tauri use the shared service. Synthetic persistence/native tests, frontend transport tests, lint and Cargo check passed; HTTP regression and web/packaged smoke plus fresh-sample post-delivery review remain pending. Not ready for publication.

## Remaining acceptance (2026-10-28)

[Verification record](../docs/trials/s002-verification-2026-10-28.json): release 1.11.30 built and started, 44 packaged resources verified. Web generated an editable brief and saved a correction with exact original retention. Existing fixture journal/task bytes stayed unchanged on both surfaces. Native UI input remains blocked after accessibility and screenshot recovery; packaged save/discard/failure and remaining web flows are unverified. Local 20B generation timed out; installed local 7B returned three valid fresh briefs, but an additional web sample assumed a team meeting and needed correction. Fresh review is not a clean pass. Six scoped backend tests and Ruff passed after the model adjustment. Fixture process trees stopped. User conditioned commit/PR on passing checks, so no commit or PR was made.

## Final candidate acceptance

All requested isolated web and packaged desktop checks passed after grounding generation in source sentence indices and packaging the shared service. Eight backend tests, 52 frontend tests, lint, Ruff and release 1.11.30 packaging passed. Three fresh synthetic samples passed source-grounding review by the primary agent. Both fixtures retained journal/task/XP bytes; process trees cleaned up. See the final section of the linked verification record. Awaiting PR review/merge; earlier progress notes above describe superseded attempts.

## Closeout

PR #31 merged at 0e957dce73b79a66f718dbd8c058c64d189f36dd on 2026-10-28. Required secret scans passed on 53b59e0; merged state read back independently. Local main fast-forwarded to the merge. All acceptance criteria and isolated verification were recorded before merge.
