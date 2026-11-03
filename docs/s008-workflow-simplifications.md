# S008 narrow workflow simplifications

## Authority and scope

On 2026-10-30 the user waived the fresh human rehearsal and accepted S007's
agent-operated evidence for the narrow controls. [S007's closeout](s007-journey-trial.md#accepted-agent-evidence-and-human-waiver)
records the exception. No human usability or production time savings are claimed.

- ActionableBrief opens the original preview by default; it remains collapsible
  and scroll-bounded. Editing and explicit original-preserving save are unchanged.
- KnowledgeNoteComposer opens explicitly loaded sources by default. The question
  supplies a bounded ASCII filename suggestion; reserved/sensitive names and
  non-ASCII-only questions use a neutral fallback. The filename remains editable;
  after a manual filename edit, question edits never replace it. Discard resets it.
- WeeklyHolocronView places decision-review rules and source references beside the
  adjustment, already expanded. Explicit Inspect remains for current source status;
  nothing fetches automatically. Existing source navigation, fingerprint mismatch
  handling, editable adjustment and explicit exports are retained. No task is created.

These eliminate one preview expansion in each journey and optional filename entry
for knowledge notes. The agent rehearsal counted 2→1, 4→2 and 2→1 work interactions;
production workflows include additional source loading, drafting and inspection.
Those rehearsal totals are not presented as production totals or elapsed savings.

## Verification on 2026-10-30

- `npm test`: passed, including the new mounted journey checks. The tests exercise
  explicit generation/load/save, default-open content, retained originals/digests,
  manual filename preservation, discard reset, accents, length and safe fallbacks.
- Existing evidence checks passed available/changed/deleted sources and navigation.
- Affected backend suites: 26 passed (brief, knowledge notes, decision review and
  Holocron evidence). Disposable Vaults and socket-denial guards were used.
- Release frontend export, native compile and NSIS packaging passed for 1.11.35.
  Executable FileVersion/ProductVersion are 1.11.35. All 49 packaged Python resource
  files matched source before running a copied app with a fresh Vault/profile.
- Web and packaged desktop knowledge-note smoke: explicit source load displayed
  the original inline; the question suggested a filename; explicit save produced
  verified files with source references/digests. Desktop manual filename stayed
  unchanged after a question edit. Fresh synthetic export-comparison notes retained
  uncertainty and preserved both original sources; no factual corrections were needed
  in agent review, with human review effort unknown.
- Web and packaged desktop Holocron smoke: supporting rule and source buttons were
  visible beside Suggested adjustment without expanding a preview. Partial coverage,
  unknown outcomes and proposal limits remained visible. No AI debrief was requested.

- Brief browser smoke passed using the actual component, a synthetic generation
  response and the real isolated save service: original visible by default, editable
  goal, explicit save receipt, original bytes and edited goal verified in one saved
  record. The first harness save used an invalid uppercase section identifier; the
  corrected lowercase fixture passed without application changes. Live provider
  generation and full packaged brief generation/save remain unrun. No personal Vault, clean-machine
installation, human usability or timing result is certified. Post-publication fresh
sample review remains part of S008 acceptance. S008 stays in progress until remaining
verification and delivery are reconciled; this record does not close E001.

Fixture browser/app and owned web process trees were closed after checks. Both
synthetic source files retained their original SHA-256 bytes. No personal Vault
records were modified. The user authorized a scoped codex branch and PR after
verification; S028 and unrelated work are excluded.

## Final verification and keep decision - 2026-11-03

S008's remaining packaged brief gate passed on local source `73508e9`, which adds
an unrelated biometrics UTF-8 fix to merged S028. That existing local commit was
preserved and was not published by this verification. The copied executable was
1.11.37, SHA-256 `a1be6052170b82550b8778466c1b09a3b88a9b92d8c940e718ae876ce7180df2`.
All 51 packaged Python resources matched source before fixture instrumentation.

The fresh isolated app used a synthetic-only loopback HTTP mock. Port 11434 was
unavailable, so only the copied provider's local URL was redirected to dedicated
port 18144; no repository application source changed. The mock returned fixed
sentence selections and rejected unmarked inputs. This exercised the real packaged
UI, IPC, provider parsing, brief validation and save service, not model quality.
Cloud key/config values were removed from the fixture environment. No real model,
paid request or personal-Vault access was used.

Three fresh tangled notes covered export comparison, release-contract uncertainty
and household measurements/bracket compatibility. Each generated brief showed its
entire original by default, retained source constraints/uncertainty, allowed an
intentional goal edit, and saved only after explicit Save brief. Native receipts
were checked against three JSON records: exact originals, edited goals and unsaved
composer provenance were retained. All six original fixture files stayed
byte-identical. Only those three brief records and deterministic Holocron caches
were added; the journal and tasks were unchanged. Three mock generation requests
were observed. App, mock and owned processes were closed after verification.

Fresh post-delivery knowledge-note review used two synthetic export sources,
explicit source loading, reviewed findings/uncertainty/application and a deliberate
filename. The saved record retained both source links and SHA-256 references, and
source bytes stayed unchanged. A fresh two-day Holocron sample distinguished
unchecked-to-checked state from outcome, retained the unresolved timestamp question,
and kept adjustment wording as a proposal. These were service-level fresh-sample
reviews, not additional live UI journeys. Prior web/native knowledge-note and
Holocron smoke remains applicable to S008's unchanged preview/filename/reference
controls; since `10f1639`, changes in these components are provider disclosure and
AI-source labels, not those controls. The current mounted journey regression passed.

The affected backend suite passed 26 tests. Its first sandboxed run stalled without
output and was interrupted; one elevated rerun passed in 9.08 seconds. The initial
test invocation also used two incorrect test paths; the corrected actual filenames
were used for the passing checks. These setup failures are not product failures.

**Keep the narrow controls; S008 is done.** Compared with the old collapsed state,
the final mounted journeys require no separate original/source/rule expansion and
retain editable filename control without repeated automatic replacement. The real
packaged brief checks confirm preview/edit/save behavior. There is no measured
human interaction baseline, elapsed saving, human review-time result or live model
quality result. The S007 human-rehearsal waiver remains a waiver. No broader UX
redesign, automatic task creation, cloud enablement or new model workflow is accepted.
