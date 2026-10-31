// Execute the complete production module with mocked browser/native transports.
// No copied functions, source regexes, Tauri installation, or live HTTP service.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import vm from 'node:vm';

const source = await readFile(new URL('../src/lib/desktopApi.js', import.meta.url), 'utf8');

async function runtime({ native = false, hostname = 'example.invalid', invoke, fetch, eventSource } = {}) {
  const calls = [], events = [], listeners = [];
  const window = {
    location: { hostname },
    __TAURI_INTERNALS__: native ? {} : undefined,
    dispatchEvent(event) { events.push(event.type); },
    EventSource: eventSource,
  };
  const context = vm.createContext({
    process: { env: { NEXT_PUBLIC_API_URL: 'https://fixture.invalid' } },
    window, navigator: { userAgent: 'Windows' }, Error, DOMException, Event, Headers, URLSearchParams,
    fetch: fetch || ((...args) => { throw new Error(`Unexpected HTTP call: ${args[0]}`); }),
  });
  const module = new vm.SourceTextModule(source, {
    context,
    importModuleDynamically: async (specifier) => {
      if (specifier === '@tauri-apps/api/core') {
        const fake = new vm.SyntheticModule(['invoke'], function () {
          this.setExport('invoke', async (command, args) => {
            calls.push({ command, args: JSON.parse(JSON.stringify(args)) });
            return invoke ? invoke(command, args) : { status: 200, body: { saved: true }, text: 'saved' };
          });
        }, { context });
        await fake.link(() => { throw new Error('Unexpected dependency'); });
        await fake.evaluate();
        return fake;
      }
      if (specifier === '@tauri-apps/api/event') {
        const fake = new vm.SyntheticModule(['listen'], function () {
          this.setExport('listen', async (eventName, callback) => {
            listeners.push({ eventName, callback });
            return () => {
              const idx = listeners.findIndex((item) => item.eventName === eventName && item.callback === callback);
              if (idx >= 0) listeners.splice(idx, 1);
            };
          });
        }, { context });
        await fake.link(() => { throw new Error('Unexpected dependency'); });
        await fake.evaluate();
        return fake;
      }
      throw new Error(`Unexpected dynamic import: ${specifier}`);
    },
  });
  await module.link(() => { throw new Error('Unexpected static dependency'); });
  await module.evaluate();
  return { api: module.namespace, calls, events, listeners };
}

test('web forwards the exact HTTP options and configured API URL', async () => {
  const response = { ok: true, status: 200 };
  const observed = [];
  const { api, events } = await runtime({ fetch: async (...args) => { observed.push(args); return response; } });
  const options = { method: 'POST', body: '{"entry":"Synthetic"}', headers: { Accept: 'application/json' } };
  assert.equal(await api.apiFetch('/api/journal/entry', options), response);
  assert.deepEqual(observed, [['https://fixture.invalid/api/journal/entry', options]]);
  assert.deepEqual(events, ['navis:progression-changed']);
});

for (const [path, command] of [
  ['/api/tasks/toggle', 'vault_request'],
  ['/api/journal/month?year=2026&month=10', 'vault_request'],
  ['/api/status', 'vault_request'], ['/api/v1/progression/xp', 'progression_request'],
  ['/api/v1/lounge/media?type=books', 'lounge_request'], ['/api/v1/library/search?q=test', 'lounge_request'],
  ['/api/battle/resolve', 'p3_request'], ['/api/missions/list', 'p3_request'],
  ['/api/battle/bestiary', 'p3_request'],
  ['/api/cache/sector', 'p3_request'], ['/api/forge/submit', 'p5_request'],
  ['/api/v1/biometrics/vitals/latest', 'p5_request'],
  ['/api/squad/deploy', 'vault_request'], ['/api/squad/bench', 'vault_request'],
  ['/api/squad/vanguard', 'vault_request'], ['/api/combat/target', 'vault_request'],
  ['/api/combat/log', 'vault_request'], ['/api/bio/adjust', 'vault_request'],
  ['/api/holocron/weekly/latest', 'vault_request'], ['/api/holocron/weekly/manifest', 'vault_request'],
  ['/api/holocron/weekly/current', 'vault_request'],
  ['/api/holocron/weekly/2026-W40/evidence/journal-2026-09-28', 'vault_request'],
]) {
  test(`native route ${path} uses ${command} without HTTP`, async () => {
    const { api, calls } = await runtime({ native: true });
    const response = await api.apiFetch(path, { method: 'POST', body: '{"fixture":true}' });
    assert.equal(response.ok, true);
    assert.equal(response.status, 200);
    assert.equal((await response.json()).saved, true);
    assert.equal(await response.text(), 'saved');
    assert.deepEqual(calls, [{ command, args: { path, method: 'POST', body: { fixture: true } } }]);
  });
}

test('native malformed body uses null and read defaults to GET', async () => {
  const { api, calls, events } = await runtime({ native: true });
  await api.apiFetch('/api/status', { body: '{broken' });
  assert.deepEqual(calls[0].args, { path: '/api/status', method: 'GET', body: null });
  assert.deepEqual(events, []);
});

test('native HTTP-like error status emits no successful-write event', async () => {
  const { api, events } = await runtime({ native: true, invoke: () => ({ status: 409, body: { detail: 'conflict' }, text: 'conflict' }) });
  const response = await api.apiFetch('/api/battle/resolve', { method: 'POST' });
  assert.equal(response.ok, false);
  assert.equal(response.status, 409);
  assert.equal((await response.json()).detail, 'conflict');
  assert.deepEqual(events, []);
});

test('native rejection becomes an Error and explicit retry succeeds once', async () => {
  let attempts = 0;
  const { api, calls, events } = await runtime({ native: true, invoke: () => {
    if (++attempts === 1) throw 'synthetic write failure';
    return { status: 200, body: {}, text: '{}' };
  } });
  await assert.rejects(api.apiFetch('/api/journal/entry', { method: 'POST' }), /synthetic write failure/);
  assert.equal(calls.length, 1, 'no automatic replay of a state-changing request');
  assert.deepEqual(events, []);
  assert.equal((await api.apiFetch('/api/journal/entry', { method: 'POST' })).ok, true);
  assert.equal(calls.length, 2);
  assert.deepEqual(events, ['navis:progression-changed']);
});

test('abort rejects pending native request and removes listener after completion', async () => {
  let finish, added = 0, removed = 0;
  const controller = new AbortController();
  const { signal } = controller;
  const add = signal.addEventListener.bind(signal), remove = signal.removeEventListener.bind(signal);
  signal.addEventListener = (...args) => { added++; add(...args); };
  signal.removeEventListener = (...args) => { removed++; remove(...args); };
  const { api, events } = await runtime({ native: true, invoke: () => new Promise(resolve => { finish = resolve; }) });
  const pending = api.apiFetch('/api/journal/entry', { method: 'POST', signal });
  while (!finish) await new Promise(resolve => setImmediate(resolve));
  controller.abort();
  await assert.rejects(pending, { name: 'AbortError' });
  finish({ status: 200, body: {}, text: '{}' });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(added, 1);
  assert.equal(removed, 1);
  assert.deepEqual(events, []);
});

for (const path of [
  '/api/journal/entry', '/api/v1/progression/xp', '/api/v1/lounge/media',
  '/api/v1/library/item', '/api/battle/resolve', '/api/forge/submit',
  '/api/sync', '/api/journal/rollover', '/api/journal/entry/polish',
  '/api/holocron/weekly/2026-W40/regenerate', '/api/holocron/weekly/2026-W40/debrief/ai',
]) {
  test(`pre-aborted native write ${path} never invokes transport or emits a write event`, async () => {
    const controller = new AbortController();
    controller.abort();
    const { api, calls, events } = await runtime({ native: true });
    await assert.rejects(api.apiFetch(path, {
      method: 'POST', signal: controller.signal,
      body: JSON.stringify({ entry: 'Synthetic fixture' }),
    }), { name: 'AbortError' });
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(calls, []);
    assert.deepEqual(events, []);
    // A fresh signal explicitly retries exactly once, using the normal route.
    const response = await api.apiFetch(path, { method: 'POST', signal: new AbortController().signal });
    assert.equal(response.ok, true);
    assert.equal(calls.length, 1);
  });
}

test('pre-aborted web requests fail before HTTP or hosted-polish capability checks', async () => {
  let calls = 0;
  const { api, events } = await runtime({ fetch: async () => { calls++; return { ok: true }; } });
  const controller = new AbortController();
  controller.abort();
  for (const path of ['/api/journal/entry', '/api/journal/entry/polish']) {
    await assert.rejects(api.apiFetch(path, { method: 'POST', signal: controller.signal }), { name: 'AbortError' });
  }
  assert.equal(calls, 0);
  assert.deepEqual(events, []);
});

for (const path of ['/api/sync', '/api/journal/rollover', '/api/journal/entry/polish']) {
  test(`abort after dispatch of ${path} stops waiting without native job cancellation`, async () => {
    let finish;
    const controller = new AbortController();
    const { api, calls, events } = await runtime({ native: true,
      invoke: () => new Promise(resolve => { finish = resolve; }),
    });
    const pending = api.apiFetch(path, { method: 'POST', signal: controller.signal });
    while (!finish) await new Promise(resolve => setImmediate(resolve));
    controller.abort();
    await assert.rejects(pending, { name: 'AbortError' });
    finish({ status: 200, body: {}, text: '{}' });
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(calls.length, 1, 'no implicit cancellation or replay');
    assert.deepEqual(events, []);
  });
}

test('sync and rollover return native job envelopes and publish progression refresh', async () => {
  const { api, calls, events } = await runtime({ native: true, invoke: () => ({ job_id: 'fixture-job' }) });
  for (const path of ['/api/sync', '/api/journal/rollover']) {
    const response = await api.apiFetch(path, { method: 'POST' });
    assert.equal(response.status, 200);
    assert.equal((await response.json()).job_id, 'fixture-job');
  }
  assert.deepEqual(calls, [
    { command: 'start_sync_operation', args: { operation: 'sync' } },
    { command: 'start_sync_operation', args: { operation: 'rollover' } },
  ]);
  assert.equal(events.length, 2);
});

test('native sync preserves request identity on retry and status/review remain separate', async () => {
  const { api, calls } = await runtime({ native: true, invoke: () => ({ job_id: 'same-request' }) });
  await api.apiFetch('/api/sync?run_async=true&request_id=same-request', { method: 'POST' });
  await api.apiFetch('/api/sync?run_async=true&request_id=same-request', { method: 'POST' });
  await api.apiFetch('/api/ops/jobs/same-request');
  await api.apiFetch('/api/ops/jobs/same-request/review', { method: 'POST' });
  assert.deepEqual(calls.slice(0, 2), [
    { command: 'start_sync_operation', args: { operation: 'sync', requestId: 'same-request' } },
    { command: 'start_sync_operation', args: { operation: 'sync', requestId: 'same-request' } },
  ]);
  assert.deepEqual(calls.slice(2).map(call => [call.command, call.args.path, call.args.method]), [
    ['vault_request', '/api/ops/jobs/same-request', 'GET'],
    ['vault_request', '/api/ops/jobs/same-request/review', 'POST'],
  ]);
});

test('hosted polish fails before transport; desktop polish preserves entry and section', async () => {
  const hosted = await runtime();
  await assert.rejects(hosted.api.apiFetch('/api/journal/entry/polish'), /available in the desktop app/);
  assert.equal(hosted.calls.length, 0);
  const desktop = await runtime({ native: true });
  await desktop.api.apiFetch('/api/journal/entry/polish', { method: 'POST', body: JSON.stringify({ entry: '- [ ] Synthetic draft', section: 'outland' }) });
  assert.deepEqual(desktop.calls, [{ command: 'vault_request', args: { path: '/api/journal/entry/polish', method: 'POST', body: { entry: '- [ ] Synthetic draft', section: 'outland' } } }]);
});

test('native banter query uses the shared provider route', async () => {
  const desktop = await runtime({ native: true });
  await desktop.api.apiFetch('/api/neural/banter/generate?count=1', { method: 'POST' });
  assert.equal(desktop.calls[0].command, 'vault_request');
  assert.equal(desktop.calls[0].args.path, '/api/neural/banter/generate?count=1');
});

test('local web polish uses HTTP and native asset paths encode each segment', async () => {
  let requested;
  const local = await runtime({ hostname: 'localhost', fetch: async (url) => { requested = url; return { ok: true }; } });
  await local.api.apiFetch('/api/journal/entry/polish');
  assert.equal(requested, 'https://fixture.invalid/api/journal/entry/polish');
  const desktop = await runtime({ native: true });
  assert.equal(desktop.api.vaultAssetUrl('Companions/Ava & Echo/Portrait.png', { cacheBust: false }),
    'http://vault.localhost/Companions/Ava%20%26%20Echo/Portrait.png');
});

test('listenNativeEvent and listenVaultChange receive events and unsubscribe in native runtime', async () => {
  const { api, listeners } = await runtime({ native: true });
  assert.equal(api.VAULT_CHANGE_EVENT, 'navis://vault-change');

  const received = [];
  const unlisten = await api.listenVaultChange((payload) => {
    received.push(payload);
  });

  assert.equal(listeners.length, 1);
  assert.equal(listeners[0].eventName, 'navis://vault-change');

  // Trigger event dispatch from native bridge
  const eventPayload = {
    type: 'journal',
    path: 'Journal/2026/10/2026-10-02.md',
    timestamp: 1759461234.56,
    action: 'modified',
    full_path: 'G:/My Drive/Navis-Vault/Journal/2026/10/2026-10-02.md',
  };
  listeners[0].callback({ payload: eventPayload });

  assert.equal(received.length, 1);
  assert.deepEqual(received[0], eventPayload);

  // Unlisten removes registration
  unlisten();
  assert.equal(listeners.length, 0);
});

test('listenNativeEvent returns no-op in web mode without dynamic import', async () => {
  const { api, listeners } = await runtime({ native: false });
  const received = [];
  const unlisten = await api.listenVaultChange((payload) => {
    received.push(payload);
  });
  assert.equal(typeof unlisten, 'function');
  assert.equal(listeners.length, 0);
});

test('emitNativeVaultChangeEvent dispatches emit_vault_change_event natively', async () => {
  const { api, calls } = await runtime({ native: true });
  const changeEvent = {
    type: 'bridge',
    path: 'Bridge/status.json',
    timestamp: 1759461234.0,
    action: 'modified',
  };
  await api.emitNativeVaultChangeEvent(changeEvent);
  assert.deepEqual(calls, [
    { command: 'emit_vault_change_event', args: { event: changeEvent } },
  ]);
});

test('subscribeVaultStream connects to native listener and unlistens in desktop runtime', async () => {
  const { api, listeners } = await runtime({ native: true });
  const received = [];
  const states = [];
  const unlisten = api.subscribeVaultStream({
    onEvent: (payload) => received.push(payload),
    onConnectionChange: (connected, status) => states.push({ connected, status }),
  });

  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(listeners.length, 1);
  assert.deepEqual(states, [{ connected: true, status: 'connected' }]);

  const eventPayload = {
    type: 'journal',
    path: 'Journal/2026/10/2026-10-02.md',
    action: 'modified',
    timestamp: 12345,
  };
  listeners[0].callback({ payload: eventPayload });
  assert.deepEqual(received, [eventPayload]);

  unlisten();
  assert.equal(listeners.length, 0);
  assert.deepEqual(states, [
    { connected: true, status: 'connected' },
    { connected: false, status: 'disconnected' },
  ]);
});

test('subscribeVaultStream connects to EventSource in web runtime, handles vault_change and manages lifecycle', async () => {
  let createdUrl = null;
  const esInstances = [];
  class FakeEventSource {
    constructor(url) {
      createdUrl = url;
      this.listeners = {};
      esInstances.push(this);
    }
    addEventListener(event, fn) {
      this.listeners[event] = this.listeners[event] || [];
      this.listeners[event].push(fn);
    }
    removeEventListener(event, fn) {
      if (!this.listeners[event]) return;
      this.listeners[event] = this.listeners[event].filter(h => h !== fn);
    }
    close() {
      this.closed = true;
    }
  }

  const { api } = await runtime({ native: false, eventSource: FakeEventSource });
  const received = [];
  const states = [];
  const unlisten = api.subscribeVaultStream({
    onEvent: (payload) => received.push(payload),
    onConnectionChange: (connected, status) => states.push({ connected, status }),
  });

  assert.equal(createdUrl, 'https://fixture.invalid/api/events/stream');
  assert.equal(esInstances.length, 1);
  const es = esInstances[0];

  // Simulating connection open
  es.onopen();
  assert.deepEqual(states, [{ connected: true, status: 'connected' }]);

  // Dispatch SSE vault_change event
  const payload = {
    type: 'journal',
    path: 'Journal/2026/10/2026-10-02.md',
    action: 'modified',
  };
  es.listeners['vault_change']?.[0]?.({ data: JSON.stringify(payload) });
  assert.deepEqual(JSON.parse(JSON.stringify(received)), [payload]);

  // Dispatch connection drop
  es.onerror();
  assert.deepEqual(states, [
    { connected: true, status: 'connected' },
    { connected: false, status: 'disconnected' },
  ]);

  // Clean-up unlisten
  unlisten();
  assert.equal(es.closed, true);
});



test('completed-today uses a native GET with no write event or HTTP request', async () => {
  const {api,calls,events}=await runtime({native:true});
  const response=await api.apiFetch('/api/tasks/completed-today');
  assert.equal(response.ok,true);
  assert.deepEqual(calls,[{command:'vault_request',args:{path:'/api/tasks/completed-today',method:'GET',body:null}}]);
  assert.deepEqual(events,[]);
});
