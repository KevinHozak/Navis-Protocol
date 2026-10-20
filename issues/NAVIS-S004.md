---
depends_on: ["NAVIS-S003"]
id: "NAVIS-S004"
parent: ["NAVIS-E001"]
priority: "medium"
schema_version: 1
status: "open"
title: "Implement reviewed knowledge notes after a passing reuse trial"
type: "enhancement"
---
## Outcome

Implement reviewed knowledge notes after a passing reuse trial.

Parent: [NAVIS-E001](NAVIS-E001.md). Depends on [NAVIS-S003](NAVIS-S003.md).

## Target areas

Existing Library/Vault search, selected-source handling and preview/save interfaces.

## Acceptance criteria

- [ ] Before starting, link a passing three-note trial including later reuse evidence and an explicit keep decision.
- [ ] Create notes only from explicitly selected sources; preserve question, findings, references, uncertainty and practical application.
- [ ] Provide editable preview, destination selection and explicit save/discard using established Vault and Library capabilities where suitable.
- [ ] Preserve source access and existing records; surface unavailable sources rather than fabricating support or silently broadening retrieval.
- [ ] Verify provenance, save destination, discard and unavailable-source behavior with relevant checks and web/desktop smoke; conduct fresh-sample post-delivery review.

## Evaluation, privacy and scope

Follow the parent epic's evaluation record, privacy requirements and trial gates. This issue records planned work only. Conditional implementation requires separately selected work after passing evidence; no trial results are claimed.
