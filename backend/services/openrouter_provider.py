"""Explicitly configured, disabled-by-default text generation. Never retries."""
from __future__ import annotations

import asyncio
import json
import math
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'
FEATURES = {'forge', 'banter', 'holocron', 'brief', 'polish', 'reid', 'neural_chat', 'warroom', 'general'}


def diagnostics():
    try:
        _, config = _config()
        enabled = []
        for name in FEATURES:
            try:
                _route(config, name, False)
                enabled.append(name)
            except OpenRouterError:
                pass
        return {'provider': 'openrouter', 'configured_features': sorted(enabled),
                'key_available': bool(os.environ.get('OPENROUTER_API_KEY')),
                'background_enabled': config.get('allow_background') is True,
                'enabled': bool(enabled) and bool(os.environ.get('OPENROUTER_API_KEY'))}
    except OpenRouterError:
        return {'provider': 'openrouter', 'enabled': False, 'configured_features': [],
                'key_available': bool(os.environ.get('OPENROUTER_API_KEY')), 'background_enabled': False}


class OpenRouterError(RuntimeError):
    """Contains only safe, local diagnostics, never provider response bodies."""


def _config():
    raw = os.environ.get('NAVIS_OPENROUTER_CONFIG')
    if not raw:
        raise OpenRouterError('Cloud generation is disabled until OpenRouter is configured.')
    path = Path(raw)
    if not path.is_absolute():
        raise OpenRouterError('OpenRouter configuration must use an absolute private file path.')
    try:
        if path.stat().st_size > 32768:
            raise ValueError()
        config = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(config, dict) or config.get('enabled') is not True:
            raise ValueError()
    except Exception:
        raise OpenRouterError('Cloud generation is disabled or its configuration is unreadable.') from None
    return path, config


def _number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
        raise OpenRouterError('OpenRouter limits or reviewed prices are invalid.')
    return value


def _route(config, feature, background):
    if feature not in FEATURES:
        raise OpenRouterError('Unsupported text-generation feature.')
    if config.get('allow_vault_content') is not True:
        raise OpenRouterError('Cloud transmission of selected text/context is not enabled.')
    if background and config.get('allow_background') is not True:
        raise OpenRouterError('Cloud background/rollover generation is disabled.')
    features = config.get('features')
    route = features.get(feature) if isinstance(features, dict) else None
    if not isinstance(route, dict) or route.get('enabled') is not True:
        raise OpenRouterError('Cloud generation is disabled for this feature.')
    model, provider = route.get('model'), route.get('provider')
    if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+', model) or model.endswith('/auto'):
        raise OpenRouterError('An explicit OpenRouter model ID is required.')
    if not isinstance(provider, str) or not re.fullmatch(r'[A-Za-z0-9_./-]{1,100}', provider):
        raise OpenRouterError('An explicit OpenRouter provider endpoint is required.')
    if route.get('reviewed_model') != model or route.get('reviewed_provider') != provider:
        raise OpenRouterError('Model/provider changed; review routing, privacy and pricing before enabling it.')
    try:
        age = (datetime.now(timezone.utc).date() - datetime.strptime(route['pricing_reviewed'], '%Y-%m-%d').date()).days
        if not 0 <= age <= 30:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise OpenRouterError('OpenRouter pricing review is missing or stale.') from None
    for key in ('input_usd_per_million', 'output_usd_per_million'):
        _number(route.get(key), 0, 10000)
    for source, name in ((config, 'daily_budget_usd'), (route, 'daily_budget_usd'), (route, 'request_budget_usd')):
        _number(source.get(name), 0.000001, 100)
    for name, low, high in (('max_input_chars', 1, 12000), ('max_output_tokens', 1, 2048), ('timeout_seconds', 1, 90)):
        _number(route.get(name), low, high)
    if not isinstance(route['max_input_chars'], int) or not isinstance(route['max_output_tokens'], int):
        raise OpenRouterError('Text/token limits must be integers.')
    return route


def _db(path):
    conn = sqlite3.connect(path.with_suffix('.usage.sqlite3'), isolation_level=None, timeout=10)
    conn.execute('PRAGMA busy_timeout=10000')
    conn.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, day TEXT, feature TEXT, model TEXT, reserved REAL, cost REAL, state TEXT)')
    return conn


def _reserve(path, config, route, feature, chars):
    # Four tokens per UTF-8 byte bounds text plus fixed message framing allowance.
    reserve = ((chars * 4 + 256) * route['input_usd_per_million'] + route['max_output_tokens'] * route['output_usd_per_million']) / 1_000_000
    reserve += _number(route.get('request_overhead_usd', 0), 0, 100)
    if reserve > route['request_budget_usd']:
        raise OpenRouterError('Cloud request exceeds its configured cost cap.')
    day = datetime.now(timezone.utc).date().isoformat()
    request_id = uuid.uuid4().hex
    conn = _db(path)
    try:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute("SELECT 1 FROM requests WHERE state IN ('reserved','unknown') LIMIT 1").fetchone():
            raise OpenRouterError('A cloud request is pending or has unknown cost; reconcile it before retrying.')
        global_cost = conn.execute('SELECT COALESCE(SUM(COALESCE(cost,reserved)),0) FROM requests WHERE day=?', (day,)).fetchone()[0]
        feature_cost = conn.execute('SELECT COALESCE(SUM(COALESCE(cost,reserved)),0) FROM requests WHERE day=? AND feature=?', (day, feature)).fetchone()[0]
        if global_cost + reserve > config['daily_budget_usd'] or feature_cost + reserve > route['daily_budget_usd']:
            raise OpenRouterError('Cloud daily budget is exhausted.')
        conn.execute('INSERT INTO requests VALUES (?,?,?,?,?,?,?)', (request_id, day, feature, route['model'], reserve, None, 'reserved'))
        conn.commit()
    finally:
        conn.close()
    return request_id, reserve


def _finish(path, request_id, *, cost=None, state='unknown'):
    conn = _db(path)
    try:
        conn.execute('UPDATE requests SET cost=?,state=? WHERE id=?', (cost, state, request_id))
    finally:
        conn.close()


class OpenRouterProvider:
    async def check(self):
        # Read-only configuration check: no remote probe, ledger mutation or paid call.
        try:
            _, config = _config()
            return config.get('allow_vault_content') is True and bool(os.environ.get('OPENROUTER_API_KEY'))
        except OpenRouterError:
            return False

    async def generate(self, prompt, *, system=None, feature='general', background=False, **kwargs):
        path, config = _config()
        route = _route(config, feature, background)
        key = os.environ.get('OPENROUTER_API_KEY')
        if not key:
            raise OpenRouterError('OpenRouter API key is unavailable in the server/native environment.')
        if not isinstance(prompt, str) or not prompt.strip() or not isinstance(system or '', str):
            raise OpenRouterError('Cloud text input is invalid.')
        chars = len(prompt.encode('utf-8')) + len((system or '').encode('utf-8'))
        if chars > route['max_input_chars']:
            raise OpenRouterError('Cloud text input exceeds the configured limit.')
        messages = ([{'role': 'system', 'content': system}] if system else []) + [{'role': 'user', 'content': prompt}]
        payload = {'model': route['model'], 'messages': messages, 'max_tokens': route['max_output_tokens'], 'stream': False,
                   'provider': {'only': [route['provider']], 'allow_fallbacks': False, 'require_parameters': True, 'data_collection': 'deny'},
                   'plugins': []}
        request_id, reserve = _reserve(path, config, route, feature, chars)
        try:
            timeout = aiohttp.ClientTimeout(total=route['timeout_seconds'])
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(ENDPOINT, json=payload, headers={'Authorization': f'Bearer {key}'}, allow_redirects=False) as response:
                    # Any attempted send retains its reservation unless a valid cost arrives.
                    if response.status != 200:
                        raise OpenRouterError(f'OpenRouter returned HTTP {response.status}; cost requires review before retrying.')
                    raw = await response.content.read(262145)
                    if len(raw) > 262144:
                        raise ValueError()
                    data = json.loads(raw)
            usage = data.get('usage', {})
            cost = usage.get('cost')
            _number(cost, 0, 100000)
            if any(isinstance(usage.get(n), bool) or not isinstance(usage.get(n), int) or usage[n] < 0 for n in ('prompt_tokens', 'completion_tokens')):
                raise ValueError()
            if usage['completion_tokens'] > route['max_output_tokens']:
                raise ValueError()
            if cost > reserve:
                _finish(path, request_id, cost=cost)
                raise OpenRouterError('Provider cost exceeded its reservation; cloud generation is locked pending review.')
            if data.get('model') != route['model']:
                raise OpenRouterError('Provider returned a different model; review the request before retrying.')
            choice = data['choices'][0]
            text = choice['message']['content']
            if choice.get('finish_reason') != 'stop' or not isinstance(text, str) or not text.strip() or key in text or choice['message'].get('tool_calls'):
                raise ValueError()
            _finish(path, request_id, cost=cost, state='settled')
            return text.strip()
        except OpenRouterError:
            _mark_unknown(path, request_id)
            raise
        except (Exception, asyncio.CancelledError):
            _mark_unknown(path, request_id)
            raise OpenRouterError('Cloud response was unavailable, incomplete or had unknown usage. Reconcile the reservation before retrying.') from None


def _mark_unknown(path, request_id):
    conn = _db(path)
    try:
        conn.execute("UPDATE requests SET state='unknown' WHERE id=? AND state='reserved'", (request_id,))
    finally:
        conn.close()
