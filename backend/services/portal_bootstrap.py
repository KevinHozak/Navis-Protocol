"""Verified installed Portal package loader; invoked only after explicit feature gates."""
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
from services.portal_private_files import verify_private_path


def read_profile(path):
    with Path(path).open("rb") as source:
        raw=source.read(65537)
    if len(raw)>65536:raise ValueError()
    def unique(pairs):
        out={}
        for key,value in pairs:
            if key in out:raise ValueError()
            out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))


def _load_adapter(profile_path):
    verify_private_path(Path(profile_path).parent)
    verify_private_path(profile_path)
    profile=read_profile(profile_path)
    root=Path(profile["portal_release_root"])
    expected=profile["portal_release_id"]
    if not root.is_absolute() or not re.fullmatch(r"[0-9a-f]{64}",expected):raise ValueError()
    verify_private_path(root)
    verify_private_path(root/"manifest.json")
    manifest=read_profile(root/"manifest.json")
    if hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(",",":")).encode()).hexdigest()!=expected:raise ValueError()
    entries=manifest["files"]
    if not isinstance(entries,dict) or not 1<=len(entries)<=64:raise ValueError()
    total=0
    for name,sha in entries.items():
        if not re.fullmatch(r"(?:(?:portal_gateway|portal_client)/[a-z_]+\.py|qualification/deepseek-v41/[A-Za-z_.]+|bootstrap\.py)",name):raise ValueError()
        target=root/name
        verify_private_path(target)
        for parent in target.parents:
            if parent==root:break
            verify_private_path(parent)
        total+=target.stat().st_size
        if total>16*1024*1024:raise ValueError()
        if hashlib.sha256(target.read_bytes()).hexdigest()!=sha:raise ValueError()
    for name,module in list(sys.modules.items()):
        if name in {"portal_gateway","portal_client"} or name.startswith(("portal_gateway.","portal_client.")):
            path=getattr(module,"__file__",None)
            if path is None or not Path(path).resolve().is_relative_to(root.resolve()):raise ValueError()
    sys.path.insert(0,str(root))
    adapter=importlib.import_module("portal_gateway.protocol_client")
    return profile,root,adapter


def status_generation(profile_path):
    """Status-only attach for configured shared-host profiles; never starts a host."""
    profile,root,_=_load_adapter(profile_path)
    if profile.get("schema_version")==1:return None
    if profile.get("schema_version")!=2 or profile.get("host_mode")!="shared":raise ValueError()
    if Path(profile["portal_release_root"]).resolve()!=root.resolve():raise ValueError()
    host_profile=importlib.import_module("portal_gateway.host_profile")
    background_host=importlib.import_module("portal_gateway.background_host")
    with host_profile.reviewed() as host_doc:
        if (Path(host_doc["state"]).resolve()!=Path(profile["portal_state"]).resolve()
                or Path(host_doc["release"]).resolve()!=root.resolve()
                or host_doc["release_id"]!=profile["portal_release_id"]):raise ValueError()
    status=background_host.status(timeout_ms=3000)
    generation=status.get("generation") if status.get("state")=="running" else None
    if (status.get("release_id")!=profile["portal_release_id"] or not isinstance(generation,str)
            or not re.fullmatch(r"[0-9a-f]{32}",generation)):
        raise ValueError()
    return generation


def invoke(profile_path,prompt,system,operation_id,cancel,vault_root,expected_host_generation=None):
    profile,_,adapter=_load_adapter(profile_path)
    if profile.get("schema_version")==2 and expected_host_generation is None:
        return {"complete":False,"receipt":{"provider":"portal","feature":"forge","code":"PORTAL_HOST_MANUAL_START_REQUIRED","billing_state":"not_sent","cost_usd":None}}
    return adapter.generate(profile,prompt,system,operation_id,cancel,profile_path=profile_path,vault_root=vault_root,
                            shared_host=expected_host_generation is not None,
                            expected_host_generation=expected_host_generation)
