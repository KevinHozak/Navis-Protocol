---
depends_on: []
id: "NAVIS-E001"
parent: []
priority: "medium"
schema_version: 1
status: "done"
title: "Evaluate and deliver evidence-backed Navis AI workflows"
type: "epic"
---
## Outcome

Improve capture, reusable knowledge and weekly decisions through measured trials before bounded product changes.

## Context and scope

Source: [DHH Interview - Practical AI Experiments](https://drive.google.com/file/d/1kDhUU5Olrc_1ygv8JnllrqVhZh1DZmH0/view) and the phased Navis-Protocol plan agreed in this chat on 2026-10-18.
Prior source inspection identified journal polishing, Library search, Forge proposal approval and Weekly Holocron foundations. Live quality and usability remain unverified. Reinspect current code before implementation.

Trials use existing tools, with no new subscriptions or scheduled generation. Keep personal samples and raw records outside the repository; retain only sanitized evidence and authorized source references. Do not alter personal records or execute suggested actions during trials. Record model/runtime/settings when available, preparation and review minutes, elapsed time including waiting, corrections, errors (including corrected inventions), usefulness, unknown usage and comparable manual baseline or its absence. Claim time savings only with a comparable baseline.

For every trial record keep/revise/drop with evidence. A failed brief trial permits one prompt revision and fresh samples, then narrow or drop persistent failures. Other failed trials require a recorded revision/retest or drop decision. A trial may finish with a negative result; that never opens its implementation gate. Conditional stories remain unstarted unless their pass criteria and a keep decision are documented. Issue creation authorizes no implementation or trial execution.

## Acceptance criteria

- [x] Complete and record the four trial decisions in order, beginning with five actionable briefs.
- [x] Deliver only implementations with passing evidence and an explicit keep decision; explicitly disposition failed or dropped branches and reconcile this epic's scope without claiming undelivered features.
- [x] For each delivered feature retain acceptance evidence, relevant checks, web and desktop workflow verification, and a fresh-sample post-delivery review.

## Stories

- [NAVIS-S001](NAVIS-S001.md): Trial actionable briefs on five rough notes
- [NAVIS-S002](NAVIS-S002.md): Implement reviewed actionable briefs after a passing trial
- [NAVIS-S003](NAVIS-S003.md): Trial three source-linked reusable knowledge notes
- [NAVIS-S004](NAVIS-S004.md): Implement reviewed knowledge notes after a passing reuse trial
- [NAVIS-S005](NAVIS-S005.md): Compare decision-focused Holocrons across three weekly cycles
- [NAVIS-S006](NAVIS-S006.md): Implement a decision-focused Holocron section after a passing trial
- [NAVIS-S007](NAVIS-S007.md): Measure and simplify three capture-to-decision journeys
- [NAVIS-S008](NAVIS-S008.md): Implement only demonstrated workflow simplifications


## Closeout - 2026-11-03

All eight children are done. The trial decisions are retained in S001, S003, S005
and S007; the latter uses the explicit human-rehearsal waiver, not a human pass.
S002/S004/S006 and S008 deliver only the accepted bounded controls. S008's final
packaged mock-backed brief save and fresh-sample evidence resolves the last child
gate; see [verification and limits](../docs/s008-workflow-simplifications.md).

No human time savings, long-term reuse, clean-machine installation or live model
quality is claimed. Cloud generation remains disabled; enabling it is separate
explicitly configured work. This closeout does not authorize additional generation,
personal-data writes or a broader product redesign.
