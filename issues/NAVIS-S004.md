---
depends_on: ["NAVIS-S003"]
id: "NAVIS-S004"
parent: ["NAVIS-E001"]
priority: "medium"
schema_version: 1
status: "in_review"
title: "Implement reviewed knowledge notes after a passing reuse trial"
type: "enhancement"
---
## Outcome

Implement reviewed knowledge notes after a passing reuse trial.

Parent: [NAVIS-E001](NAVIS-E001.md). Depends on [NAVIS-S003](NAVIS-S003.md).

## Target areas

Existing Library/Vault search, selected-source handling and preview/save interfaces.

## Acceptance criteria

- [x] Before starting, link a passing three-note trial including later reuse evidence and an explicit keep decision.
- [x] Create notes only from explicitly selected sources; preserve question, findings, references, uncertainty and practical application.
- [x] Provide editable preview, destination selection and explicit save/discard using established Vault and Library capabilities where suitable.
- [x] Preserve source access and existing records; surface unavailable sources rather than fabricating support or silently broadening retrieval.
- [x] Verify provenance, save destination, discard and unavailable-source behavior with relevant checks and web/desktop smoke; conduct fresh-sample post-delivery review.

## Evaluation, privacy and scope

Follow the parent epic's evaluation record, privacy requirements and trial gates. This issue records planned work only. Conditional implementation requires separately selected work after passing evidence; no trial results are claimed.

## Selected implementation scope

Passing S003 evidence and explicit keep decision are published in PR #32 (commit 4c8ba32); 3/3 later-turn reuse checks passed, with same-day primary-agent limits and unknown human review time retained. User selected S004 on 2026-10-28. Implement explicit Markdown-source selection, bounded source previews, an editable question/findings/uncertainty/application note and constrained Library destination selection. Preserve source digests and revalidate before exclusive save; fail visibly if a selected source disappears or changes. No inferred retrieval expansion or task creation.

## Verified implementation candidate

Release 1.11.31, nine backend checks, 52 frontend transport checks, Ruff, frontend lint (existing warnings), Cargo check and fresh isolated web/packaged desktop workflows passed. Explicit selection, missing/changed-source errors, draft retention, destination/save/provenance and discard were verified. All 13 original fixture files per surface remained byte-identical after deliberate test edits were restored. Owned processes and browser tab cleaned up; no live Vault data used.

Three fresh synthetic notes passed primary-agent review with no unsupported findings or corrections. Human usefulness, review time and long-term reuse remain unmeasured. See [implementation notes](../docs/reviewed-knowledge-notes.md) and [sanitized verification](../docs/trials/s004-knowledge-notes-2026-10-28.json). Implementation awaits PR merge; this is not a story closeout.
