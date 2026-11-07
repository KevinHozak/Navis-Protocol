"""Vault-free Portal feature/gate tests; all SDK work is fake and sockets are denied."""
import asyncio
from contextlib import nullcontext
from io import StringIO
import json
import os
import tempfile
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
# Import service modules only after supplying a fresh generated Vault/config root.
_IMPORT_FIXTURE_ROOT=tempfile.TemporaryDirectory(prefix="navis-portal-s028-import-")
os.environ["NAVIS_ROOT"]=_IMPORT_FIXTURE_ROOT.name
os.environ["NAVIS_PORTAL_ENABLED"]="0"
os.environ["NAVIS_PORTAL_PROFILE"]=os.path.join(_IMPORT_FIXTURE_ROOT.name,"synthetic-profile.json")
import main
from services import ai_provider, forge_service, forge_volatile, online_ai, portal_bootstrap, portal_forge


def request():
    return {"entity_type":"companion","name":"Aster","prompt":"Generated synthetic guide",
            "provider":"portal","portal_opt_in":True,"allow_external_text":True,"operation_id":"synthetic-op-1"}


def receipt(code="OK",state="settled",cost="0.00001"):
    return {"provider":"portal","feature":"forge","code":code,"billing_state":state,"cost_usd":cost,
            "correlation":"a"*32,"accounting_role":"portal-cap-reference"}


@pytest.fixture
def feature(tmp_path,monkeypatch):
    root=tmp_path/"empty-vault";root.mkdir()
    proposals=tmp_path/"proposals";proposals.mkdir()
    monkeypatch.setattr(main,"NAVIS_ROOT",str(root))
    monkeypatch.setattr(forge_service,"store",lambda _:proposals)
    monkeypatch.setenv("NAVIS_PORTAL_ENABLED","1")
    monkeypatch.setenv("NAVIS_PORTAL_PROFILE",str(tmp_path/"unused-fake-profile.json"))
    monkeypatch.setattr(online_ai,"_read_config",lambda:{"enabled":True,"allow_vault_content":True})
    calls=[];fallback=[]
    def forbidden(*args,**kwargs):
        fallback.append(True)
        raise AssertionError("Direct provider fallback forbidden")
    monkeypatch.setattr(ai_provider,"get_provider",forbidden)
    monkeypatch.setattr(online_ai,"generate",forbidden)
    def invoke(profile,prompt,system,operation,cancel,vault_root,expected_host_generation):
        calls.append((prompt,operation,expected_host_generation))
        blueprint={field:"Generated guide" for field in forge_service.FIELDS}
        blueprint.update(name="Aster",voice_id="en-US-JennyNeural")
        return {"complete":True,"text":json.dumps(blueprint),"receipt":receipt()}
    monkeypatch.setattr(portal_bootstrap,"invoke",invoke)
    monkeypatch.setattr(portal_bootstrap,"status_generation",lambda _profile:None)
    return TestClient(main.app),calls,fallback,root,proposals


def test_actual_fastapi_forge_path_returns_portal_receipt_without_vault_writes(feature):
    client,calls,fallback,root,proposals=feature
    result=client.post("/api/forge/submit",json=request())
    assert result.status_code==200,result.text
    value=result.json()
    assert value["blueprint"]["name"]=="Aster"
    assert value["portal_receipt"]["provider"]=="portal"
    assert value["portal_receipt"]["cost_usd"]=="0.00001"
    assert len(calls)==1 and fallback==[] and list(root.iterdir())==[] and list(proposals.iterdir())==[]


def test_trusted_python_adapter_receives_native_generation_and_keeps_preview_volatile(feature):
    _,calls,fallback,root,proposals=feature
    value=asyncio.run(portal_forge.submit(root,request(),expected_host_generation="a"*32))
    assert value["blueprint"]["name"]=="Aster"
    assert value["portal_receipt"]["provider"]=="portal"
    assert len(calls)==1 and calls[0][1:]==("synthetic-op-1","a"*32)
    assert fallback==[] and list(root.iterdir())==[] and list(proposals.iterdir())==[]


def test_backend_adapter_preserves_explicit_manual_mode(feature):
    _,calls,fallback,root,proposals=feature
    value=asyncio.run(portal_forge.submit(root,request()))
    assert value["blueprint"]["name"]=="Aster"
    assert len(calls)==1 and calls[0][2] is None
    assert fallback==[] and list(root.iterdir())==[] and list(proposals.iterdir())==[]


@pytest.mark.parametrize("state,release_matches,expected",[("running",True,"a"*32),("stopped",True,None),("running",False,None)])
def test_shared_backend_binding_is_status_only_and_never_acquires(tmp_path,monkeypatch,state,release_matches,expected):
    root=tmp_path/"release";root.mkdir();vault=tmp_path/"empty-vault";vault.mkdir()
    profile={"schema_version":2,"host_mode":"shared","portal_release_root":str(root),
             "portal_state":str(vault),"portal_release_id":"b"*64}
    host={"state":str(vault),"release":str(root),"release_id":"b"*64}
    calls=[]
    background=SimpleNamespace(status=lambda **kwargs:(calls.append("status") or {"state":state,"release_id":"b"*64 if release_matches else "c"*64,"generation":"a"*32}),
                               acquire=lambda **kwargs:(_ for _ in ()).throw(AssertionError("status-only mode must never acquire")))
    monkeypatch.setattr(portal_bootstrap,"_load_adapter",lambda _path:(profile,root,None))
    monkeypatch.setattr(portal_bootstrap.importlib,"import_module",lambda name:SimpleNamespace(reviewed=lambda:nullcontext(host)) if name.endswith("host_profile") else background)
    if expected is None:
        with pytest.raises(ValueError):portal_bootstrap.status_generation("synthetic-profile")
    else:
        assert portal_bootstrap.status_generation("synthetic-profile")==expected
    assert calls==["status"]


def test_shared_backend_generation_change_is_not_retried_or_fallen_back(feature,monkeypatch):
    _,calls,fallback,root,_=feature
    monkeypatch.setattr(portal_bootstrap,"status_generation",lambda _profile:"a"*32)
    def changed(*args):
        calls.append(args[-1])
        return {"complete":False,"receipt":receipt("PORTAL_HOST_GENERATION_CHANGED","not_sent",None)}
    monkeypatch.setattr(portal_bootstrap,"invoke",changed)
    with pytest.raises(portal_forge.PortalFeatureError) as error:
        asyncio.run(portal_forge.submit(root,request()))
    assert error.value.receipt["code"]=="PORTAL_HOST_GENERATION_CHANGED"
    assert calls==["a"*32] and fallback==[] and list(root.iterdir())==[]


def test_shared_backend_incompatible_host_requires_manual_resolution(feature,monkeypatch):
    _,calls,fallback,root,_=feature
    def incompatible(_profile):raise RuntimeError("synthetic incompatible host")
    monkeypatch.setattr(portal_bootstrap,"status_generation",incompatible)
    with pytest.raises(portal_forge.PortalFeatureError) as error:
        asyncio.run(portal_forge.submit(root,request()))
    assert error.value.receipt["code"]=="PORTAL_HOST_MANUAL_START_REQUIRED"
    assert error.value.receipt["billing_state"]=="not_sent"
    assert calls==[] and fallback==[] and list(root.iterdir())==[]


@pytest.mark.parametrize("code,state,cost,status",[
    ("PORTAL_BLUEPRINT_INVALID","settled","0.00001",502),
    ("MISSING_USAGE","unresolved",None,503),
    ("PORTAL_DUPLICATE_OPERATION","duplicate_unknown",None,409),
    ("PORTAL_FEATURE_BUDGET_DENIED","not_admitted",None,429),
])
def test_native_cli_envelope_dispatches_generation_and_preserves_billing_receipts(monkeypatch,code,state,cost,status):
    calls=[]
    receipt_value={"provider":"portal","feature":"forge","code":code,"billing_state":state,"cost_usd":cost}
    async def submit(_root,_request,*,expected_host_generation=None):
        calls.append(expected_host_generation)
        raise portal_forge.PortalFeatureError(code,status,receipt=receipt_value)
    monkeypatch.setattr(portal_forge,"submit",submit)
    envelope={"request":request(),"native_binding":{"expected_host_generation":"a"*32}}
    with pytest.raises(portal_forge.PortalFeatureError) as error:
        forge_service.dispatch_cli("synthetic-root","submit",envelope,native_portal=True)
    output=forge_service.cli_error(error.value)
    assert calls==["a"*32]
    assert output=={"http_status":status,"body":{"detail":receipt_value}}


@pytest.mark.parametrize("envelope,native",[
    ({"request":request()},True),
    ({"request":{**request(),"native_binding":{"expected_host_generation":"a"*32}},"native_binding":{"expected_host_generation":"a"*32}},True),
    ({"request":request(),"native_binding":{"expected_host_generation":"a"*32}},False),
])
def test_native_cli_rejects_missing_or_injected_bindings(envelope,native):
    with pytest.raises(forge_service.ForgeError):
        forge_service.dispatch_cli("synthetic-root","submit",envelope,native_portal=native)


def test_native_cli_rejects_duplicate_json_keys():
    with pytest.raises(ValueError):forge_service.parse_cli_request('{"request":{},"request":{}}')


@pytest.mark.parametrize("action",["approve","discard"])
def test_native_python_worker_keeps_proposal_volatile_through_explicit_decision(feature,monkeypatch,action):
    _,calls,fallback,root,proposals=feature
    blueprint={field:"Generated guide" for field in forge_service.FIELDS}
    blueprint.update(name="Aster",voice_id="en-US-JennyNeural")
    def fake_invoke(profile,prompt,system,operation,cancel,vault_root,expected_host_generation):
        calls.append((operation,expected_host_generation))
        return {"complete":True,"text":json.dumps(blueprint),"receipt":receipt()}
    monkeypatch.setattr(portal_bootstrap,"invoke",fake_invoke)
    proposal_id=forge_volatile.reserve(root)
    monkeypatch.setattr(forge_volatile,"reserve",lambda _root:proposal_id)
    first={"request":request(),"native_binding":{"expected_host_generation":"a"*32}}
    followup={"action":action,"request":{"proposal_id":proposal_id,"approved":True}} if action=="approve" else {"action":action,"request":{"proposal_id":proposal_id}}
    monkeypatch.setattr("sys.stdin",StringIO(json.dumps(first)+"\n"+json.dumps(followup)+"\n"))
    output=StringIO()
    with __import__("contextlib").redirect_stdout(output):forge_service.run_portal_worker(str(root))
    responses=[json.loads(line) for line in output.getvalue().splitlines()]
    assert [item["http_status"] for item in responses]==[200,200],responses
    assert responses[0]["body"]["proposal_id"]==proposal_id
    if action=="approve":
        assert (root/"Companions"/"Aster"/"Profile.md").is_file()
        assert not list(proposals.glob("portal-*.json"))
    else:
        assert list(root.iterdir())==[]
    assert calls==[("synthetic-op-1","a"*32)] and fallback==[]


def test_disabled_and_missing_request_privacy_opt_ins_never_dispatch(feature,monkeypatch):
    client,calls,fallback,_,_=feature
    for field in ("portal_opt_in","allow_external_text"):
        payload=request();payload[field]=False
        with pytest.raises(portal_forge.PortalFeatureError) as error:
            asyncio.run(portal_forge.submit("/unused",payload,expected_host_generation="a"*32))
        assert error.value.status==403
    monkeypatch.setenv("NAVIS_PORTAL_ENABLED","0")
    with pytest.raises(portal_forge.PortalFeatureError) as error:
        asyncio.run(portal_forge.submit("/unused",request(),expected_host_generation="a"*32))
    assert error.value.receipt["code"]=="PORTAL_APP_DISABLED"
    monkeypatch.setenv("NAVIS_PORTAL_ENABLED","1")
    monkeypatch.setattr(online_ai,"_read_config",lambda:{"enabled":True,"allow_vault_content":False})
    with pytest.raises(portal_forge.PortalFeatureError) as error:
        asyncio.run(portal_forge.submit("/unused",request(),expected_host_generation="a"*32))
    assert error.value.status==403
    assert calls==[] and fallback==[]


def test_unsupported_capabilities_and_missing_mode_operation_are_visible(feature):
    client,calls,fallback,_,_=feature
    for field in ("tools","stream","images","provider_key","budget","native_binding","native_portal_binding"):
        payload={**request(),field:[]}
        assert client.post("/api/forge/submit",json=payload).status_code==422
    payload=request();payload["operation_id"]=None
    assert client.post("/api/forge/submit",json=payload).status_code==400
    payload=request();payload["provider"]="default"
    assert client.post("/api/forge/submit",json=payload).status_code==400
    assert calls==[] and fallback==[]


@pytest.mark.parametrize("code,state,status",[("UPSTREAM_TIMEOUT","unresolved",503),
    ("PORTAL_FEATURE_BUDGET_DENIED","not_admitted",429),("ROUTE_DATA_CLASS_DENIED","unresolved",403),
    ("PORTAL_DUPLICATE_OPERATION","duplicate_unknown",409),("GATEWAY_UNAVAILABLE","unresolved",503)])
def test_errors_expose_billing_state_without_retry_or_provider_fallback(feature,monkeypatch,code,state,status):
    _,calls,fallback,_,_=feature
    def denied(*args):
        calls.append(True)
        return {"complete":False,"receipt":receipt(code,state,None)}
    monkeypatch.setattr(portal_bootstrap,"invoke",denied)
    with pytest.raises(portal_forge.PortalFeatureError) as error:
        asyncio.run(portal_forge.submit("/unused",request(),expected_host_generation="a"*32))
    assert error.value.status==status
    assert error.value.receipt["code"]==code
    assert error.value.receipt["cost_usd"] is None
    assert calls==[True] and fallback==[]


def test_health_checks_never_select_portal_even_when_feature_enabled(feature):
    client,calls,_,_,_=feature
    for _ in range(3):assert client.get("/").status_code==200
    assert calls==[]


def test_invalid_blueprint_keeps_settled_cost_visible_and_never_retries(feature,monkeypatch):
    _,calls,fallback,_,_=feature
    def invalid(*args):
        calls.append(True)
        return {"complete":True,"text":"invalid JSON","receipt":receipt()}
    monkeypatch.setattr(portal_bootstrap,"invoke",invalid)
    with pytest.raises(portal_forge.PortalFeatureError) as error:
        asyncio.run(portal_forge.submit("/unused",request(),expected_host_generation="a"*32))
    assert error.value.status==502
    assert error.value.receipt["billing_state"]=="settled"
    assert error.value.receipt["cost_usd"]=="0.00001"
    assert calls==[True] and fallback==[]


def test_bounded_executor_refuses_busy_and_task_cancellation_signals_worker(feature,monkeypatch):
    client,calls,_,root,_=feature
    assert portal_forge._SLOTS.acquire(False)
    assert portal_forge._SLOTS.acquire(False)
    try:assert client.post("/api/forge/submit",json=request()).status_code==429
    finally:portal_forge._SLOTS.release();portal_forge._SLOTS.release()
    entered=threading.Event();finished=threading.Event()
    def blocked(profile,prompt,system,operation,cancel,vault_root,expected_host_generation):
        entered.set()
        try:
            assert cancel.wait(2)
            return {"complete":False,"receipt":receipt("PORTAL_CANCELLED","unresolved",None)}
        finally:finished.set()
    monkeypatch.setattr(portal_bootstrap,"invoke",blocked)
    async def scenario():
        task=asyncio.create_task(portal_forge.submit(root,request(),expected_host_generation="a"*32))
        for _ in range(100):
            if entered.is_set():break
            await asyncio.sleep(.01)
        assert entered.is_set()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        for _ in range(100):
            if finished.is_set():break
            await asyncio.sleep(.01)
        assert finished.is_set()
    asyncio.run(scenario())
