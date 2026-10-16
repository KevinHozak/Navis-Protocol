# War Room runtime recovery (#224)

The desktop bundle must include `services/conversation_runtime.py`,
`conversation_service.py`, `reid_agent.py`, `ai_provider.py`, and `online_ai.py`.
The prior resource manifest omitted the conversation service and Reid module.
In a copied bundle without the source checkout, importing the service therefore
fails before it can emit JSON. This explains a reproducible packaging failure;
the screenshot's installed version and interpreter have not been verified.

Development uses the backend virtual environment when it starts successfully
and is Python 3.11+, falling back to PATH when it is missing, broken, or too old.
The repository desktop launcher validates its virtual environment before
selecting it. Release builds otherwise use Python 3.11+ from PATH or the
executable selected by `NAVIS_PYTHON`. An explicit `NAVIS_PYTHON` override remains
authoritative; an invalid override reports an error instead of falling back. Install
the backend requirements into that interpreter; `aiohttp` is required for local
generation. Restart Navis after changing its interpreter environment.

Start Ollama and install the model selected by `NAVIS_OLLAMA_MODEL` (default
`Kimiko-20B:latest`). Check `NAVIS_OLLAMA_URL` when using a different local
endpoint. An unavailable model now produces model installation guidance.
Retry repeats the failed history, initialization, or chat request. Failed
generation does not persist a user turn; frontend retry does not append another
copy or erase a newer draft. Each new frontend request has a stable request ID;
Retry reuses it. Completed replies retain the ID and a message fingerprint in the
existing 50-message history window, allowing a lost response to be replayed without
calling the provider or saving another turn. Reusing an ID for different input is
rejected. A file lock serializes generation across web requests and native Python
processes, and history is replaced atomically. Clearing history remains a separate
confirmed action and removes those retry receipts along with the conversation.

The native entrypoint emits one structured response and suppresses incidental
stdout/stderr. Missing imports, process failure, invalid/empty output, and invalid
envelopes receive fixed public diagnostics. Unexpected web generation errors also
use fixed copy. Raw stderr and unexpected exception text are never surfaced.
The existing local provider default and explicit online experiment guard remain.

Verification commands:

```powershell
python -m pytest backend/tests/test_conversation_service.py backend/tests/test_conversation_packaging.py backend/tests/test_ai_provider.py -k 'not forge' -q
cd frontend
npm run test:warroom
npm run test:unit
npm run build:desktop
cargo test --manifest-path src-tauri/Cargo.toml --offline p5::tests
```

Tests use synthetic Vaults, a copied resource bundle, missing site-packages,
mocked providers, and the real frontend desktop API with mocked transports.
Live installer recovery on the affected machine remains a manual verification
step; these checks do not certify its installed Python or Ollama configuration.
