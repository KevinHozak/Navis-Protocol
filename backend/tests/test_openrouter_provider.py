import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from services import openrouter_provider as cloud
from services.ai_provider import ProviderError, get_provider


@pytest.fixture
def setup_cloud(tmp_path, monkeypatch):
    path = tmp_path / 'cloud.json'
    route = {'enabled': True, 'model': 'fixture/model-v1', 'provider': 'fixture/endpoint',
             'reviewed_model': 'fixture/model-v1', 'reviewed_provider': 'fixture/endpoint',
             'pricing_reviewed': datetime.now(timezone.utc).date().isoformat(),
             'input_usd_per_million': 1, 'output_usd_per_million': 2,
             'request_budget_usd': .1, 'daily_budget_usd': 1,
             'max_input_chars': 12000, 'max_output_tokens': 512, 'timeout_seconds': 2}
    config = {'enabled': True, 'allow_vault_content': True, 'allow_background': False,
              'daily_budget_usd': 1, 'features': {'forge': route}}
    path.write_text(json.dumps(config))
    monkeypatch.setenv('NAVIS_OPENROUTER_CONFIG', str(path))
    monkeypatch.setenv('OPENROUTER_API_KEY', 'synthetic-placeholder')
    monkeypatch.delenv('NAVIS_AI_PROVIDER', raising=False)
    calls = []
    state = {'status': 200, 'body': {'model': 'fixture/model-v1', 'choices': [
        {'finish_reason': 'stop', 'message': {'content': 'Synthetic result'}}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'cost': .00003}}}

    class Response:
        @property
        def status(self): return state['status']
        @property
        def content(self): return self
        async def read(self, limit):
            if state.get('timeout'): raise asyncio.TimeoutError()
            return json.dumps(state['body']).encode()[:limit]
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass

    class Session:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return Response()

    monkeypatch.setattr(cloud.aiohttp, 'ClientSession', Session)
    return path, config, state, calls


def run(): return asyncio.run(get_provider().generate('Synthetic input', feature='forge'))


def test_disabled_default_makes_no_calls(monkeypatch):
    monkeypatch.delenv('NAVIS_AI_PROVIDER', raising=False)
    monkeypatch.delenv('NAVIS_OPENROUTER_CONFIG', raising=False)
    sender = Mock(side_effect=AssertionError('network forbidden'))
    monkeypatch.setattr(cloud.aiohttp, 'ClientSession', sender)
    with pytest.raises(ProviderError, match='disabled'):
        run()
    sender.assert_not_called()
    assert asyncio.run(get_provider().check()) is False


def test_success_pins_route_and_settles_usage(setup_cloud):
    path, _, _, calls = setup_cloud
    assert run() == 'Synthetic result'
    assert calls[0][0] == cloud.ENDPOINT
    payload = calls[0][1]['json']
    assert payload['model'] == 'fixture/model-v1'
    assert payload['provider']['only'] == ['fixture/endpoint']
    assert payload['provider']['allow_fallbacks'] is False
    assert calls[0][1]['allow_redirects'] is False
    conn = cloud._db(path)
    assert conn.execute('SELECT cost,state FROM requests').fetchone() == (.00003, 'settled')
    conn.close()


@pytest.mark.parametrize('case', ['key', 'model', 'provider', 'price', 'disabled', 'feature', 'budget', 'background', 'input'])
def test_preflight_denials_do_not_contact_provider(setup_cloud, monkeypatch, case):
    path, config, _, calls = setup_cloud
    route = config['features']['forge']
    if case == 'key': monkeypatch.delenv('OPENROUTER_API_KEY')
    if case == 'model': route['model'] = ''
    if case == 'provider': route['provider'] = 'changed-endpoint'
    if case == 'price': route['pricing_reviewed'] = '2000-01-01'
    if case == 'disabled': config['enabled'] = False
    if case == 'feature': route['enabled'] = False
    if case == 'budget': route['request_budget_usd'] = .000001
    if case == 'input': route['max_input_chars'] = 1
    path.write_text(json.dumps(config))
    with pytest.raises(ProviderError):
        asyncio.run(get_provider().generate('Synthetic input', feature='forge', background=case == 'background'))
    assert not calls


@pytest.mark.parametrize('case', ['auth', 'rate', 'timeout', 'empty', 'usage', 'malformed', 'model', 'truncated', 'tools', 'overrun'])
def test_ambiguous_attempt_retains_reservation_and_blocks_retry(setup_cloud, case):
    path, _, state, calls = setup_cloud
    if case == 'auth': state['status'] = 401
    if case == 'rate': state['status'] = 429
    if case == 'timeout': state['timeout'] = True
    if case == 'empty': state['body']['choices'][0]['message']['content'] = ''
    if case == 'usage': state['body']['usage'] = {}
    if case == 'malformed': state['body'] = []
    if case == 'model': state['body']['model'] = 'different/model'
    if case == 'truncated': state['body']['choices'][0]['finish_reason'] = 'length'
    if case == 'tools': state['body']['choices'][0]['message']['tool_calls'] = [{}]
    if case == 'overrun': state['body']['usage']['cost'] = 1
    with pytest.raises(ProviderError): run()
    with pytest.raises(ProviderError, match='pending|unknown'): run()
    assert len(calls) == 1
    conn = cloud._db(path)
    reserve, cost, state_name = conn.execute('SELECT reserved,cost,state FROM requests').fetchone()
    assert reserve > 0 and state_name in ('unknown', 'reserved')
    if case == 'overrun': assert cost == 1
    conn.close()


def test_daily_budget_exhaustion_is_shared(setup_cloud):
    path, config, _, calls = setup_cloud
    assert run() == 'Synthetic result'
    config['daily_budget_usd'] = .00003
    path.write_text(json.dumps(config))
    with pytest.raises(ProviderError, match='daily budget'): run()
    assert len(calls) == 1
