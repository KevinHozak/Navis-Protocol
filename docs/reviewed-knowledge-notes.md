# Reviewed knowledge notes (S004)

Prerequisite: the S003 three-note reuse trial passed with a keep decision in closeout PR #32. It is same-day primary-agent reuse evidence with human usefulness ratings, zero corrections and unknown review time; it is not a long-term or time-savings result.

The Library composer loads one to five explicitly selected Markdown paths using the existing bounded application Vault reader. It does not search for additional sources, expand MCP permissions, or invoke an AI provider. Source previews are bounded to 20,000 characters each and 40,000 total. Unsupported or unavailable paths fail visibly.

Users curate question, findings, uncertainty/disagreements and one practical application in an editable preview. Source numbers and references remain available while editing. Saving rereads the selected files and rejects changed digests or unavailable sources. References retain relative Markdown links and original digests; a reference is provenance, not automatic certification of every user-written finding.

Destinations are Library/Notes and Library/Knowledge Notes. A validated filename creates a new Markdown file exclusively; identical retries verify the existing bytes, and conflicting content cannot overwrite an existing note. Discard performs no save. Journal/task/XP writes are not part of this flow.

HTTP and native IPC use the same import-safe service. Both native bridge and authority are declared packaged resources. Release 1.11.31 built successfully with executable metadata verified and all 47 declared resources matching source. Nine backend checks, 52 frontend transport checks, Ruff, frontend lint (existing warnings), Cargo check and release packaging passed.

Fresh isolated web and packaged desktop fixtures passed explicit source selection, editable fields, destination selection, missing-source errors, changed-source rejection with draft retention, verified save and discard. Each retained one intentional note; all 13 original files per fixture remained byte-identical after restoring the deliberate source/settings test changes. Owned fixture process trees were stopped and the browser tab closed. No live Vault data was used.

Three fresh synthetic notes (archive comparison, release planning and repair planning) passed primary-agent review: findings matched selected sources, uncertainty and application were distinct, references and source bytes were preserved, and no corrections were needed. This is manual curation with no AI generation; human usefulness, review time and long-term reuse were not measured. See [sanitized verification record](trials/s004-knowledge-notes-2026-10-28.json). S004 is done: PR #33 merged as f36cb52; local main synchronized.
