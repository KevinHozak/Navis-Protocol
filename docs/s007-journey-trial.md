# S007 journey comparison

S006 merged in PR #34; S005 and earlier trial keep decisions are recorded. S007 compares review/finalization of preserved synthetic brief, knowledge-note and Holocron outputs. It does not modify production app components or implement S008.

[Open the standalone rehearsal](trials/s007-journey-rehearsal.html). Six runs alternate baseline/candidate order. Task instructions are inside the rehearsal. It records interaction events and completion time through explicit save/choice, then asks about factual corrections, correction effort and confusion/help. Originals are retained in trial receipts. Human results stay in browser storage until explicitly downloaded; no network requests, model calls, real saves or task commitments occur.

The tested changes are inline source/original previews and an editable suggested knowledge-note filename. Baselines model current review controls, with already prepared drafts for both versions. This is a narrowed rehearsal, not an end-to-end deployed app benchmark. Human completion is required; no coaching or agent substitution counts. A passing result needs fewer interactions or lower completion time in at least two journeys, no increased factual errors/correction effort, all three candidates completed without extra explanation, and an explicit keep decision. Failure requires revise/retest or drop. S008 stays gated.

Agent smoke completed all six prototype runs; observed interaction counts were brief 2→1, knowledge 4→2 and Holocron 2→1. These are functional observations only. Human results, confusion, correction effort and keep/revise/drop remain pending; no time savings are claimed. See [sanitized record](trials/s007-journey-rehearsal-2026-10-28.json).


## Rehearsal revision

The first human attempt did not complete all six recorded runs and required clarification. The item-save receipt was mistaken for completion; source loading versus opening its preview and Record run versus Start next run were confusing. This is evidence to revise the rehearsal, not a passing unassisted usability result.

At the user's request, an agent completed all six v1 runs in separate storage. [Agent record](trials/s007-agent-run-2026-10-28.json): interaction counts remained 2→1, 4→2 and 2→1; all originals retained, explicit saves used, and zero factual corrections in primary-agent review. Timings include tool waits and cannot establish human or production time savings. The agent decision was Revise, not a human keep decision. The [v1 prototype](trials/s007-journey-rehearsal-v1.html) is retained for reproducibility; its rerun storage prefix differs only to isolate agent results.

Version 2 shows run/phase status, directs source review clearly, scrolls to feedback after item save, and records feedback plus opens the next run with one button. Help-needed is explicit; optional confusion text need not contain “None.” Final completion and download are clearly labelled, and JSON results are also visible on-page. The measured work controls and synthetic samples remain unchanged. Old human data is preserved under its v1 storage key; the fresh v2 human run starts at 0/6.

All six v2 agent smoke runs passed progression and final-results checks. S007 remains in progress pending a fresh unassisted human run; S008 remains open and gated by explicit user instruction. No production app changes, Vault writes, task creation or model calls were made. The loopback server is intentionally retained for the human handoff.

## Accepted agent evidence and human waiver

On 2026-10-30 the user explicitly waived the human rehearsal, accepted the agent
evidence for the narrow controls, and requested S007 closure and S008 implementation.
The preserved six-run record reports brief 2→1, knowledge 4→2 and Holocron 2→1
work interactions, zero factual corrections and zero correction minutes in agent
review. Originals, source review, editing and explicit save/choice remained present.
The historical Revise decision and initial human confusion are retained unchanged.
This user acceptance supersedes the previous human retest gate; it does not turn
agent observations into human acceptance or erase the rehearsal's limitations.

Keep inline originals/loaded sources/supporting decision references and an editable
filename suggestion only. No human completion or time savings, production latency,
general usability or independent factual validation is established. The production
Holocron keeps explicit source inspection for freshness and its existing editable
view/export behavior; a rehearsal choice receipt does not authorize task creation.
S007 is done under this waiver. S008 owns final implementation regression and
web/desktop verification and remains in progress until those checks are complete.
