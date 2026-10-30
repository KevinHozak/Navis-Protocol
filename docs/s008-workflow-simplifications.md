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
