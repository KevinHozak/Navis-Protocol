# Local Forge generation
Web and Tauri share services.forge_service. Ollama is the default;
configure NAVIS_OLLAMA_URL, NAVIS_OLLAMA_MODEL and NAVIS_OLLAMA_TIMEOUT.
Native requires packaged backend resources and Python with backend dependencies.
Missing runtimes/models return a dependency error. No cloud fallback occurs.
Explicit Gemini selection uses the existing experiment opt-in, content permission
and budget guard. Renderer requests never receive API keys.

Generation returns a validated preview and opaque proposal ID. Proposals live
outside the Vault in the OS temporary directory, expire after one hour and contain
generated fields only. Discard revokes the proposal. Approve & Manifest sends
approved: true with its ID; the server uses stored reviewed fields.

Companion, Realm and Beast are supported. Strict names, fields, voice identifiers
and destinations are checked before approval and publication. Existing entities
are never overwritten. Controlled Forge scripts run with a sanitized environment
in isolated same-volume staging. Complete entity directories publish atomically.
Script output and private prompts are not forwarded to logs. Artwork generation
is separate and is not invoked implicitly.

Web jobs report staging and publication progress. Native shows manifestation in
progress and returns its final result. Closing the modal or disconnecting after
approval does not revoke approval. Retry the same proposal to confirm completion
without duplicates. OS locks serialize destinations and release on process exit.
Failed scripts remove staging data. Abrupt process termination can leave a hidden
.forge-* staging directory, but cannot publish partial entity files.
