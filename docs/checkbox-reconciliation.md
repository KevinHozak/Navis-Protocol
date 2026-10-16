# Journal checkbox reconciliation (#223)

The reported refresh reversion remains unverified against personal records.
Controlled client execution narrowed two defects: a busy mutation returned
undefined while the renderer retained a successful-looking optimistic check,
and an already-running watcher read could replace a later save response.

The renderer now exposes pending/saved/retry feedback, prevents further input
while saving, retains its pending override across content updates, and removes
the override on every completion. Document changes remount the renderer.
Rejected mutations return an explicit failure.

Reads carry a document revision and request sequence. Navigation and mutations
invalidate older reads; only responses newer than the last successful read apply. A failed newer read
does not discard a successful pending initial load. Watcher
reads suppressed during a write are replayed afterward. Reads bypass HTTP
caching. Saves time out after 20 seconds and recovery reads after 10 seconds
through the shared web/native abort boundary. A timeout does not cancel an
already-dispatched native operation: read back and review before retrying.
Native task completion events carry the affected document path so writes that
finish after timeout readback still refresh the open journal.
Recovery never blindly inverts a task. Expected-content checks remain the
server authority, and canonical XP reconciliation remains unchanged.

Verification uses disposable journals only:

- `cd frontend; npm test` executes controlled refresh/save interleavings and
  the actual React Markdown renderer, plus shared web/native adapter tests.
- `python -m pytest backend/tests/test_checkbox_contract.py backend/tests/test_task_toggle_safety.py -q`
  covers conflicts, failed writes, BOM/CRLF/body preservation, canonical XP
  replay, HTTP/native parity and fresh-process readback of checked state.
- `cd frontend; npm run lint` checks the affected frontend integration.

These checks establish synthetic persistence and race behavior. They do not
constitute a live packaged desktop restart or a production Vault reproduction.
