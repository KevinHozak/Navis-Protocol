# Actionable briefs

S001 passed its revised five-note trial on 2026-10-28: five useful, no corrections, review time unknown. Scope is complex/tangled notes with dependencies, competing concerns or unresolved choices. Simple chores are excluded. No time savings have been measured.

S002 adds an explicit composer action with a four-field editable preview. Generation uses only local Ollama at loopback, with no external provider fallback. Hosted clients cannot generate or save briefs through the local-only feature. Discard writes nothing.

Save retains the exact draft snapshot and accepted fields in `Library/Actionable Briefs/<content-sha256>.json`. Date, section and the associated journal path are recorded as an **unsaved composer draft** reference; this does not claim the source already exists in the journal. Saving a brief does not append a journal item, create a task, alter checklist states or run XP. Journal Save Entry remains a separate explicit action.

HTTP `/api/journal/brief/generate` and `/save` and the native Python bridge use `backend/services/actionable_brief.py`. Saves publish flushed records atomically and identical retries verify and reuse the same record. Tauri packages the bridge alongside the shared backend services.

Verification: eight isolated backend tests, 52 frontend transport tests, journal-flow checks, Ruff and lint passed (existing lint warnings). Release 1.11.30 built and passed web/packaged UI generate, edit, save, discard and storage-failure/retry checks with synthetic Vaults. Three fresh source-grounding samples passed primary-agent review. Baseline journal/task/XP bytes stayed unchanged; fixture process trees were stopped. See [verification record](trials/s002-verification-2026-10-28.json).

## Grounded generation

The local qwen2.5-coder:7b model selects numbered source sentences for each field. The service validates the indices and renders the original source wording with fixed labels. Model-written prose, nonexistent indices and boolean values are rejected before preview. The next action is explicitly a suggestion to review the selected source detail before deciding. This trades free-form synthesis for traceable source selection; selection can still be incomplete or unhelpful, so editable review remains required. User edits are accepted intentionally and are not certified as source-grounded.
