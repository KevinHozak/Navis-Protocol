---
depends_on: ["NAVIS-S001"]
id: "NAVIS-S002"
parent: ["NAVIS-E001"]
priority: "medium"
schema_version: 1
status: "open"
title: "Implement reviewed actionable briefs after a passing trial"
type: "enhancement"
---
## Outcome

Implement reviewed actionable briefs after a passing trial.

Parent: [NAVIS-E001](NAVIS-E001.md). Depends on [NAVIS-S001](NAVIS-S001.md).

## Target areas

frontend/src/components/JournalEntryComposer.js, backend/main.py and native/local AI adapters.

## Acceptance criteria

- [ ] Before starting, link a passing five-sample trial and explicit keep decision; completion of the trial issue alone is insufficient.
- [ ] Add a distinct Create actionable brief action beside polishing, returning Goal, Known facts, Uncertainties and One suggested next action.
- [ ] Provide editable preview and save/discard; durably retain the original with accepted output and source reference rather than relying on component state.
- [ ] Require a separate explicit action to create any task; preserve existing journals, dates and checklist states and existing local-first/provider safeguards.
- [ ] Verify original retention, save/discard, failure handling and task separation with meaningful checks and web/desktop workflow smoke; review fresh samples after delivery.

## Evaluation, privacy and scope

Follow the parent epic's evaluation record, privacy requirements and trial gates. This issue records planned work only. Conditional implementation requires separately selected work after passing evidence; no trial results are claimed.
