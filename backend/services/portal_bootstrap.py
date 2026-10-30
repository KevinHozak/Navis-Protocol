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


def invoke(profile_path,prompt,system,operation_id,cancel,vault_root):
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
    return adapter.generate(profile,prompt,system,operation_id,cancel,profile_path=profile_path,vault_root=vault_root)
