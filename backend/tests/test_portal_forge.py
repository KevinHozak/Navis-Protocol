"""Vault-free Portal feature/gate tests; all SDK work is fake and sockets are denied."""
import asyncio
import json
import threading

import pytest
from fastapi.testclient import TestClient
import main
from services import ai_provider, forge_service, online_ai, portal_bootstrap, portal_forge


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
    def invoke(profile,prompt,system,operation,cancel,vault_root):
        calls.append((prompt,operation))
        blueprint={field:"Generated guide" for field in forge_service.FIELDS}
        blueprint.update(name="Aster",voice_id="en-US-JennyNeural")
        return {"complete":True,"text":json.dumps(blueprint),"receipt":receipt()}
    monkeypatch.setattr(portal_bootstrap,"invoke",invoke)
    return TestClient(main.app),calls,fallback,root,proposals


def test_actual_fastapi_forge_path_returns_portal_receipt_without_vault_writes(feature):
    client,calls,fallback,root,_=feature
    result=client.post("/api/forge/submit",json=request())
    assert result.status_code==200,result.text
    value=result.json()
    assert value["blueprint"]["name"]=="Aster"
    assert value["portal_receipt"]["provider"]=="portal"
    assert value["portal_receipt"]["cost_usd"]=="0.00001"
    assert len(calls)==1 and fallback==[] and list(root.iterdir())==[]


def test_disabled_and_missing_request_privacy_opt_ins_never_dispatch(feature,monkeypatch):
    client,calls,fallback,_,_=feature
    for field in ("portal_opt_in","allow_external_text"):
        payload=request();payload[field]=False
        assert client.post("/api/forge/submit",json=payload).status_code==403
    monkeypatch.setenv("NAVIS_PORTAL_ENABLED","0")
    result=client.post("/api/forge/submit",json=request())
    assert result.status_code==503
    assert result.json()["detail"]["code"]=="PORTAL_APP_DISABLED"
    monkeypatch.setenv("NAVIS_PORTAL_ENABLED","1")
    monkeypatch.setattr(online_ai,"_read_config",lambda:{"enabled":True,"allow_vault_content":False})
    assert client.post("/api/forge/submit",json=request()).status_code==403
    assert calls==[] and fallback==[]


def test_unsupported_capabilities_and_missing_mode_operation_are_visible(feature):
    client,calls,fallback,_,_=feature
    for field in ("tools","stream","images","provider_key","budget"):
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
    client,calls,fallback,_,_=feature
    def denied(*args):
        calls.append(True)
        return {"complete":False,"receipt":receipt(code,state,None)}
    monkeypatch.setattr(portal_bootstrap,"invoke",denied)
    result=client.post("/api/forge/submit",json=request())
    assert result.status_code==status
    assert result.json()["detail"]["code"]==code
    assert result.json()["detail"]["cost_usd"] is None
    assert calls==[True] and fallback==[]


def test_health_checks_never_select_portal_even_when_feature_enabled(feature):
    client,calls,_,_,_=feature
    for _ in range(3):assert client.get("/").status_code==200
    assert calls==[]


def test_invalid_blueprint_keeps_settled_cost_visible_and_never_retries(feature,monkeypatch):
    client,calls,fallback,_,_=feature
    def invalid(*args):
        calls.append(True)
        return {"complete":True,"text":"invalid JSON","receipt":receipt()}
    monkeypatch.setattr(portal_bootstrap,"invoke",invalid)
    result=client.post("/api/forge/submit",json=request())
    assert result.status_code==502
    assert result.json()["detail"]["billing_state"]=="settled"
    assert result.json()["detail"]["cost_usd"]=="0.00001"
    assert calls==[True] and fallback==[]


def test_bounded_executor_refuses_busy_and_task_cancellation_signals_worker(feature,monkeypatch):
    client,calls,_,root,_=feature
    assert portal_forge._SLOTS.acquire(False)
    assert portal_forge._SLOTS.acquire(False)
    try:assert client.post("/api/forge/submit",json=request()).status_code==429
    finally:portal_forge._SLOTS.release();portal_forge._SLOTS.release()
    entered=threading.Event();finished=threading.Event()
    def blocked(profile,prompt,system,operation,cancel,vault_root):
        entered.set()
        try:
            assert cancel.wait(2)
            return {"complete":False,"receipt":receipt("PORTAL_CANCELLED","unresolved",None)}
        finally:finished.set()
    monkeypatch.setattr(portal_bootstrap,"invoke",blocked)
    async def scenario():
        task=asyncio.create_task(portal_forge.submit(root,request()))
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
