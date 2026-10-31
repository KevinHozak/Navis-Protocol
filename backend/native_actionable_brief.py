"""Native brief adapter: no HTTP server or journal mutations."""
import json
import os
import sys
from urllib.parse import parse_qs
from fastapi import HTTPException
from services.ai_provider import ProviderError
from services.actionable_brief import generate, save

try:
    request = json.load(sys.stdin)
    raw_path, body = request.get("path"), request.get("body", {})
    path, _, query = raw_path.partition('?')
    if path == "/api/ai/text/status":
        from services.openrouter_provider import diagnostics
        result = diagnostics()
    elif path == "/api/journal/brief/generate":
        result = generate(body)
    elif path == "/api/journal/entry/polish":
        import asyncio
        from services.journal_polish import polish
        result = asyncio.run(polish(body.get("entry", ""), body.get("section", "sanctum")))
    elif path == "/api/neural/banter/generate":
        import contextlib
        import io
        from services.banter_generator import generate_squad_banter
        with contextlib.redirect_stdout(io.StringIO()):
            generated = generate_squad_banter(count=int(parse_qs(query).get('count', ['1'])[0]))
        if not generated:
            raise ProviderError("Banter was not generated. Review configured provider, budget and squad state before retrying.")
        result = {"status": "success", "message": "Generated requested squad banter."}
    elif path == "/api/journal/brief/save":
        result = save(os.environ["NAVIS_ROOT"], body)
    else:
        raise ValueError("Unsupported brief operation.")
    response = {"status": 200, "body": result}
except HTTPException as error:
    response = {"status": error.status_code, "body": {"detail": error.detail}}
except ProviderError as error:
    response = {"status": 503, "body": {"detail": str(error)}}
except ValueError as error:
    response = {"status": 422, "body": {"detail": str(error)}}
except Exception:
    response = {"status": 503, "body": {"detail": "Brief service unavailable. Original unchanged; retry the same save if needed."}}
json.dump(response, sys.stdout, ensure_ascii=True)
