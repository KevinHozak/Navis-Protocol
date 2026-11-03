# Roadmap and acceptance reconciliation — 2026-11-03

Audit baseline: merged main `6f3f69ffd5f01ded1cae386e786742809f00dcb9`.
User authorization covers #246 closeout and documentation reconciliation, not new
feature implementation, reopened issues, personal-Vault operations or cloud setup.
Cloud generation remains disabled. No model/inference call was made.

## Method and status

Read the local runner inventory, GitHub open/closed issue bodies, selected legacy
closeout comments, current feature source and linked tracked acceptance records.
The GitHub snapshot contains 105 legacy/private issue records; selected #70/#71,
#75/#78, #82 and #84/#87 comment lists were empty. The absence of additional evidence
in these inspected sources is a verification-record gap, not proof of a product bug.
No application tests/build/UI exercises were rerun in this documentation audit.
Previously dated results retain their source/version/environment limits.

- Local backlog: all 32 records done (four complete epics, 28 stories).
- Public GitHub backlog: no open issues.
- Private GitHub backlog: no open issues after the authorized #246 closeout.
- #246: PR #44 merged at `7edf1ff`; 1.11.38 direct and launcher packaged UI,
  version metadata, frontend checks and 81 native tests provide its four criteria.
  Issue body was updated and closed; a separate readback confirmed closure.
- #245: PR #45 merged at `6f3f69f`; 1.11.39 HTTP, mounted, web and packaged-native
  acceptance is recorded in [Projects evidence](projects-overview.md). Issue closed.

## Corrected stale claims

| Previous statement | Verified reconciliation |
| --- | --- |
| Roadmap reconciled only at October 2; E001 still open | Current baseline and completed E001–E004, S027/S028, #245/#246 now appear in the roadmap. |
| Progression #71/#67 must stay open until manual packaged checks run | #71's explicit September 30 acceptance disposition waived those checks. Both issues are closed; the old hold instruction was removed from the P4 record. Waived remains unperformed, not passed. |
| All sync/rollover packaged close/cancel/resource checks are pending | S014 1.11.20 resource-directory fixtures and S015 selected web/native journeys passed. Installer/clean-machine and physical integration limits were explicitly accepted as untested. |
| Holocron/journal still await first packaged smoke | S010/S012, S006/S008 and S028 have scoped packaged/browser evidence. Broader physical/installer claims do not follow from it. |
| Talent tree and tactical mechanics are planned under #193/#183 | Both legacy epics are closed; source/docs implement allocation/perks, AP/shield/round rules, elements, squad passives and Bestiary analytics/trophies. Broad/full-game completion is not inferred. |
| Native squad deploy/bench/vanguard equivalents are absent | Routes and native tests exist in `vault.rs`. |
| File watcher/SSE/reactive invalidation is future #188 work | Backend watcher/event bus/stream, native watcher/events and client subscription/invalidation exist; #188 and its children are closed. |
| Native Forge/general conversation paths are absent; local Ollama is the current default | P5 delegates Forge and conversations to Python runtimes. S028 supersedes historical local defaults with explicitly configured, disabled OpenRouter routing. No live generation quality is certified. |
| Testing guide needs only built-in Node modules and has 11 regressions/30 unit cases | Mounted tests require React, react-test-renderer and Next/SWC. Lockfile dependency installation and current runner/output replace those historical counts. |
| September decorator registry is the complete current API | Registry is now explicitly historical; Projects uses `add_api_route` and later feature routes require current source/contracts. |

Historical test logs/counts and earlier blocked checkpoints were not rewritten into
new passing runs. The map/combat manual procedures remain visible and unperformed.
The [roadmap](roadmap.md) is the current status index; original records remain
evidence for their stated scope and dates.

## Confirmed remaining gaps and boundaries

| Kind | Finding and evidence | Disposition |
| --- | --- | --- |
| Verification gap — recommended next | [Map lifecycle smoke](map-telemetry.md): current/stale/future/malformed/missing/out-of-bounds telemetry, expiry without refresh, threat/squad/realm changes, keyboard navigation and small-view readability have an explicit unexecuted web/native procedure. No later runtime record or matching waiver was found in the inspected map sources. | Run fresh isolated fixtures; do not reopen #75–#78 merely because they are closed with this recorded boundary. |
| Verification gap | [Combat packaged UI recovery](combat-task-verification.md): automated durable completion/retry evidence does not establish real Execute/Retry/Cancel/relaunch behavior. No matching manual waiver was found in #84/#87 or their comments. | Separate bounded synthetic acceptance task after map smoke; retain exact task/card/XP and no-duplicate assertions. |
| Implementation integration gap | [Tactical rules](combat-tactical-rules.md) explicitly leave encounter creation/selection for later integration. Current battle API and UI read/resolve server-owned encounter state; no operator-facing setup route/control was found. | A separately scoped story could add reviewed encounter setup/selection. Existing round calculations are delivered; do not describe all combat as unimplemented. |
| Intentional integration boundary | Only a `map_telemetry` consumer was found in application source (`mapTelemetry.mjs`), not an authoritative measured-coordinate writer. The contract expressly refuses invented positions. | Decide whether a real producer is needed after renderer smoke. Never synthesize live positions from node indices or realm changes. |
| Evidence limit, not new failure | Talent records map source/automated acceptance; broader packaged/manual allocation UX is not independently established by those PASS labels. | Keep evidence classification explicit; no functional talent defect or reopened epic is asserted. |

Not automatic follow-ups: the #71 progression manual checks were explicitly waived;
S015 clean-machine/physical integration limits were explicitly accepted; personal
XP reconciliation is separately authorized operator work; MCP personal appends stay
disabled; model selection, budgets and live quality require separate authorization.
These boundaries are not silently converted into open implementation tasks.

## Recommended next bounded task

**Verify the map telemetry lifecycle on fresh web and packaged fixtures, with no
personal-Vault access and no generation.** Prepare synthetic current and invalid
telemetry, exercise threat/squad/realm changes and old-marker removal, wait through
the existing expiry threshold without a status update, and inspect keyboard and
small-view behavior. Record exact scenarios, original-file hashes and process cleanup.
Repair only a reproduced scoped defect; otherwise close the verification record
with its limits. This provides a useful observable result without repeating waived
progression work or inventing a coordinate producer.

No new stories were allocated by this audit. Broader roadmap ideas remain unselected
directions, not confirmed active defects. Documentation changes remain local until
the user requests commit/publication.
