"""Stdlib-only native entrypoint: stdout is exactly one response envelope."""
import asyncio
import contextlib
import io
import json
import os
import sys


def run():
    public_errors = ()
    invalid_errors = (json.JSONDecodeError,)
    try:
        # Imports and legacy helpers may print. Discard that output so it cannot
        # corrupt the protocol or disclose a transcript/path in diagnostics.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            from services.conversation_service import dispatch, ConversationError
            from services.ai_provider import ProviderError
            from services.online_ai import OnlineAIError
            public_errors = (ProviderError, OnlineAIError, ConversationError)
            invalid_errors += (ConversationError,)
            raw = sys.stdin.read(65537)
            if len(raw) > 65536:
                raise ConversationError("Conversation request is too large.")
            request = json.loads(raw) if raw.strip() else {}
            if not isinstance(request, dict):
                raise ConversationError("Conversation request must be an object.")
            action = sys.argv[1] if len(sys.argv) > 1 else ""
            root = (os.environ.get("NAVIS_ROOT") or "").strip() or (os.environ.get("NAVIS_VAULT_ROOT") or "").strip()
            if not root:
                raise ConversationError("Configure NAVIS_ROOT or NAVIS_VAULT_ROOT before using conversations.")
            body = asyncio.run(dispatch(root, action, request))
            return {"http_status": 200, "body": body}
    except (ModuleNotFoundError, ImportError):
        return {"http_status": 503, "body": {
            "code": "native_dependency_unavailable",
            "detail": "Conversation Python dependencies or backend files are missing. Install backend requirements in the NAVIS_PYTHON interpreter and reinstall the current desktop build, then retry.",
            "status": "unavailable"}}
    except Exception as exc:
        # Only normalized public errors cross the process boundary.
        safe = isinstance(exc, public_errors)
        invalid = isinstance(exc, invalid_errors)
        return {"http_status": 400 if invalid else 503, "body": {
            "status": "error" if invalid else "unavailable",
            "code": "invalid_request" if invalid else "native_dependency_unavailable",
            "detail": str(exc) if safe else "Conversation runtime failed. Verify Python dependencies and the configured local model, then retry."}}


if __name__ == "__main__":
    print(json.dumps(run()))
