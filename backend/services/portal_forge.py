"""Explicit foreground-only Portal Forge preview; no import-time inference or Vault read."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import re
import threading

from services import forge_service

_POOL=ThreadPoolExecutor(max_workers=2,thread_name_prefix="navis-portal-forge")
_SLOTS=threading.BoundedSemaphore(2)


class PortalFeatureError(RuntimeError):
    def __init__(self,code,status=503,*,receipt=None):
        self.status=status
        self.receipt=receipt or {"provider":"portal","feature":"forge","code":code,"billing_state":"not_sent","cost_usd":None}
        super().__init__(code)


async def submit(root,request):
    if request.get("portal_opt_in") is not True or request.get("allow_external_text") is not True:
        raise PortalFeatureError("PORTAL_PRIVACY_OPT_IN_REQUIRED",403)
    if os.environ.get("NAVIS_PORTAL_ENABLED")!="1":
        raise PortalFeatureError("PORTAL_APP_DISABLED")
    operation=request.get("operation_id")
    if not isinstance(operation,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}",operation):
        raise PortalFeatureError("PORTAL_OPERATION_REQUIRED",400)
    profile_path=os.environ.get("NAVIS_PORTAL_PROFILE")
    if not profile_path:
        raise PortalFeatureError("PORTAL_PROFILE_UNAVAILABLE")
    # Preserve the existing Forge online/privacy opt-ins, but never reserve or
    # write Google's usage ledger or inherit its provider key/pricing/grants.
    from services.online_ai import _read_config
    try:config=_read_config()
    except Exception:raise PortalFeatureError("PORTAL_APP_POLICY_UNAVAILABLE") from None
    if config.get("enabled") is not True or config.get("allow_vault_content") is not True:
        raise PortalFeatureError("PORTAL_APP_POLICY_OPT_IN_REQUIRED",403)

    class Provider:
        receipt=None
        async def generate(self,prompt,*,system=None):
            if not _SLOTS.acquire(blocking=False):raise PortalFeatureError("PORTAL_FEATURE_BUSY",429)
            cancel=threading.Event()
            def call():
                try:
                    from services.portal_bootstrap import invoke
                    return invoke(profile_path,prompt,system or "",operation,cancel,str(root))
                except Exception:
                    return {"complete":False,"receipt":{"provider":"portal","feature":"forge","code":"PORTAL_UNAVAILABLE_OR_INVALID_PROFILE","billing_state":"unknown","cost_usd":None}}
                finally:_SLOTS.release()
            try:result=await asyncio.shield(asyncio.get_running_loop().run_in_executor(_POOL,call))
            except asyncio.CancelledError:
                cancel.set()
                raise
            self.receipt=result["receipt"]
            if not result["complete"]:
                code=self.receipt["code"]
                status=409 if self.receipt["billing_state"]=="duplicate_unknown" else 429 if "BUDGET" in code or "CEILING" in code else 403 if any(word in code for word in ("PRIVACY","DATA_CLASS","AUTH")) else 503
                raise PortalFeatureError(code,status,receipt=self.receipt)
            return result["text"]

    provider=Provider()
    try:
        result=await forge_service.submit(root,request,provider=provider)
    except PortalFeatureError:raise
    except forge_service.ForgeError:
        if provider.receipt:
            raise PortalFeatureError("PORTAL_BLUEPRINT_INVALID",502,receipt={**provider.receipt,"code":"PORTAL_BLUEPRINT_INVALID"}) from None
        raise PortalFeatureError("PORTAL_FORGE_INPUT_INVALID",400) from None
    except Exception:
        raise PortalFeatureError("PORTAL_PREVIEW_STORE_FAILED",503,receipt=provider.receipt) from None
    return {**result,"portal_receipt":provider.receipt}
