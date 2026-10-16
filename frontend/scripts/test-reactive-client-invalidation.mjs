import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import vm from 'node:vm';

if (!vm.SourceTextModule) {
  const result = spawnSync(process.execPath, ['--experimental-vm-modules', fileURLToPath(import.meta.url)], { stdio: 'inherit' });
  if (result.error) throw result.error;
  process.exit(result.status ?? 1);
}

console.log('Testing client optimistic invalidation & reactive UI stream orchestration (Reactive-P4)...');

const root = resolve(process.cwd(), 'src');
const [desktopApiSrc, pageSrc, bridgeHomeSrc] = await Promise.all([
  readFile(resolve(root, 'lib/desktopApi.js'), 'utf8'),
  readFile(resolve(root, 'app/page.js'), 'utf8'),
  readFile(resolve(root, 'components/BridgeHome.js'), 'utf8'),
]);

// ---------------------------------------------------------------------------
// 1. Contract Alignment & Source Checks
// ---------------------------------------------------------------------------
assert.match(
  desktopApiSrc,
  /export\s+function\s+subscribeVaultStream/,
  'desktopApi.js must export subscribeVaultStream function',
);

assert.match(
  pageSrc,
  /import\s+.*subscribeVaultStream.*from\s+['"]@\/lib\/desktopApi['"]/,
  'page.js must import subscribeVaultStream from desktopApi',
);

assert.match(
  bridgeHomeSrc,
  /import\s+.*subscribeVaultStream.*from\s+['"]\.\.\/lib\/desktopApi['"]/,
  'BridgeHome.js must import subscribeVaultStream from desktopApi',
);

assert.match(
  pageSrc,
  /subscribeVaultStream\(\{[\s\S]*?onEvent:[\s\S]*?onConnectionChange:/,
  'page.js must subscribe to vault stream with onEvent and onConnectionChange handlers',
);

assert.match(
  pageSrc,
  /if\s*\(\s*streamConnected\s*\)\s*\{\s*\/\/\s*Legacy 30s interval retired while active stream is connected\s*return;\s*\}/,
  'page.js must retire legacy 30s setInterval polling when active stream is connected',
);

assert.match(
  pageSrc,
  /const\s+interval\s*=\s*setInterval\(refreshStatus,\s*30000\);/,
  'page.js must retain 30s fallback setInterval polling when stream is not connected',
);

// ---------------------------------------------------------------------------
// 2. Acceptance Criteria 1: Web mode connects to SSE, Desktop mode connects to native
// ---------------------------------------------------------------------------
async function setupDesktopApi(isNative = true, options = {}) {
  const calls = [];
  const listeners = [];
  const esInstances = [];

  class FakeEventSource {
    constructor(url) {
      this.url = url;
      this.listeners = {};
      this.closed = false;
      esInstances.push(this);
    }
    addEventListener(name, fn) {
      this.listeners[name] = this.listeners[name] || [];
      this.listeners[name].push(fn);
    }
    removeEventListener(name, fn) {
      if (!this.listeners[name]) return;
      this.listeners[name] = this.listeners[name].filter(h => h !== fn);
    }
    close() {
      this.closed = true;
    }
  }

  const window = {
    location: { hostname: 'localhost' },
    __TAURI_INTERNALS__: isNative ? {} : undefined,
    dispatchEvent: () => {},
    EventSource: isNative ? undefined : FakeEventSource,
  };

  const context = vm.createContext({
    process: { env: { NEXT_PUBLIC_API_URL: 'http://127.0.0.1:8000' } },
    window,
    navigator: { userAgent: 'Windows' },
    Error,
    DOMException,
    Event,
    Headers,
    fetch: async () => ({ ok: true, status: 200 }),
  });

  const module = new vm.SourceTextModule(desktopApiSrc, {
    context,
    importModuleDynamically: async (specifier) => {
      if (specifier === '@tauri-apps/api/core') {
        const fake = new vm.SyntheticModule(['invoke'], function () {
          this.setExport('invoke', async (command, args) => {
            calls.push({ command, args });
            return { status: 200, body: { ok: true } };
          });
        }, { context });
        await fake.link(() => {});
        await fake.evaluate();
        return fake;
      }
      if (specifier === '@tauri-apps/api/event') {
        const fake = new vm.SyntheticModule(['listen'], function () {
          this.setExport('listen', async (eventName, callback) => {
            listeners.push({ eventName, callback });
            return () => {
              const idx = listeners.findIndex((l) => l.eventName === eventName && l.callback === callback);
              if (idx >= 0) listeners.splice(idx, 1);
            };
          });
        }, { context });
        await fake.link(() => {});
        await fake.evaluate();
        return fake;
      }
      throw new Error(`Unexpected dynamic import: ${specifier}`);
    },
  });

  await module.link(() => {});
  await module.evaluate();
  return { api: module.namespace, calls, listeners, esInstances };
}

// Test Native Desktop Stream
{
  const { api, listeners } = await setupDesktopApi(true);
  const events = [];
  const connectionStates = [];

  const unlisten = api.subscribeVaultStream({
    onEvent: (payload) => events.push(payload),
    onConnectionChange: (connected, status) => connectionStates.push({ connected, status }),
  });

  await new Promise((r) => setImmediate(r));
  assert.equal(listeners.length, 1, 'Desktop mode must register native event listener');
  assert.equal(listeners[0].eventName, 'navis://vault-change');
  assert.deepEqual(connectionStates, [{ connected: true, status: 'connected' }]);

  // Dispatch native change event
  const sampleEvent = { type: 'journal', path: 'Journal/2026/10/2026-10-02.md', action: 'modified' };
  listeners[0].callback({ payload: sampleEvent });
  assert.deepEqual(events, [sampleEvent]);

  // Cleanup
  unlisten();
  assert.equal(listeners.length, 0, 'Desktop mode unlisten must detach native listener');
  assert.deepEqual(connectionStates, [
    { connected: true, status: 'connected' },
    { connected: false, status: 'disconnected' },
  ]);
}

// Test Web SSE Stream
{
  const { api, esInstances } = await setupDesktopApi(false);
  const events = [];
  const connectionStates = [];

  const unlisten = api.subscribeVaultStream({
    onEvent: (payload) => events.push(payload),
    onConnectionChange: (connected, status) => connectionStates.push({ connected, status }),
  });

  assert.equal(esInstances.length, 1, 'Web mode must instantiate EventSource');
  const es = esInstances[0];
  assert.equal(es.url, 'http://127.0.0.1:8000/api/events/stream', 'Web mode must connect to /api/events/stream');

  // Simulate open
  es.onopen();
  assert.deepEqual(connectionStates, [{ connected: true, status: 'connected' }]);

  // Simulate incoming vault_change event
  const samplePayload = { type: 'journal', path: 'Journal/2026/10/2026-10-02.md', action: 'modified' };
  es.listeners['vault_change']?.[0]?.({ data: JSON.stringify(samplePayload) });
  assert.deepEqual(JSON.parse(JSON.stringify(events)), [samplePayload]);

  // Simulate connection drop
  es.onerror();
  assert.deepEqual(connectionStates, [
    { connected: true, status: 'connected' },
    { connected: false, status: 'disconnected' },
  ]);

  // Cleanup
  unlisten();
  assert.equal(es.closed, true, 'Web mode unlisten must close EventSource');
}

// ---------------------------------------------------------------------------
// 3. Acceptance Criteria 2: Checkbox edits outside webview reflect < 500ms
// ---------------------------------------------------------------------------
{
  let contentState = '- [ ] Morning Review\n- [ ] Physical Readiness\n- [ ] Deep Focus';
  let loadedContentId = 'Journal/2026/10/2026-10-02.md';
  let refreshStatusCalled = 0;

  const mockContext = {
    AbortSignal,
    contentRevision: { current: 0 },
    refreshSequence: { current: 0 },
    appliedReadSequence: { current: 0 },
    setLoadingContent: () => {},
    selectedEntityRef: { current: 'Journal/2026/10/2026-10-02.md' },
    sourceContentRef: { current: contentState },
    activeEntityRef: { current: { id: 'Journal/2026/10/2026-10-02.md', type: 'file' } },
    activeSectorRef: { current: 'JOURNAL' },
    selectedJournalDateRef: { current: '2026-10-02' },
    checkboxPending: { current: false },
    setEntityContent: (content) => { contentState = content; },
    setLoadedContentEntityId: (id) => { loadedContentId = id; },
    setContentLoadError: () => {},
    refreshStatus: async () => { refreshStatusCalled++; },
    refreshEntitiesForSector: async () => {},
    apiFetch: async (path) => {
      if (path === '/api/vault/Journal/2026/10/2026-10-02.md') {
        return {
          ok: true,
          json: async () => ({
            content: '- [x] Morning Review\n- [ ] Physical Readiness\n- [ ] Deep Focus',
            source_content: '- [x] Morning Review\n- [ ] Physical Readiness\n- [ ] Deep Focus',
          }),
        };
      }
      return { ok: false };
    },
  };

  // Extract refreshActiveEntityContent and handleVaultChangeEvent from page.js
  const refreshStart = pageSrc.indexOf('  const refreshActiveEntityContent = async');
  const refreshEnd = pageSrc.indexOf('  const refreshEntitiesForSector');
  const refreshCode = pageSrc.slice(refreshStart, refreshEnd);

  const eventStart = pageSrc.indexOf('      onEvent:');
  const eventEnd = pageSrc.indexOf('      onConnectionChange:');
  const eventHandler = pageSrc.slice(eventStart + '      onEvent:'.length, eventEnd).trim().replace(/,\s*$/, '');

  const runner = `
    ${refreshCode}
    globalThis.handleVaultChangeEvent = ${eventHandler};
  `;

  vm.createContext(mockContext);
  vm.runInContext(runner, mockContext);

  // Measure latency of external checkbox modification event processing
  const startTime = performance.now();
  await mockContext.handleVaultChangeEvent({
    type: 'journal',
    path: 'Journal/2026/10/2026-10-02.md',
    action: 'modified',
    timestamp: Date.now() / 1000,
  });
  const elapsedMs = performance.now() - startTime;

  assert.match(contentState, /- \[x\] Morning Review/, 'Active document checkbox must be updated');
  assert.equal(mockContext.sourceContentRef.current, contentState, 'Source content ref must be synchronized');
  assert.equal(refreshStatusCalled, 1, 'Status refresh must be called when journal task modified');
  assert.ok(elapsedMs < 500, `External edit reflection took ${elapsedMs.toFixed(2)}ms (must be < 500ms)`);

  // Irrelevant document event should NOT modify current entity content
  contentState = '- [x] Kept State';
  await mockContext.handleVaultChangeEvent({
    type: 'journal',
    path: 'Journal/2025/01/2025-01-01.md',
    action: 'modified',
    timestamp: Date.now() / 1000,
  });
  assert.equal(contentState, '- [x] Kept State', 'Non-active document edits must not clobber active content');
}

// ---------------------------------------------------------------------------
// 4. Acceptance Criteria 3 & 4: Polling Interval Retired on Stream, Retained on Drop
// ---------------------------------------------------------------------------
{
  // Simulate page.js streamConnected effect behavior
  function simulatePollingEffect(streamConnected, mockSetInterval, mockClearInterval) {
    if (streamConnected) {
      // Legacy 30s interval retired while active stream is connected
      return () => {};
    }
    // Fallback polling retained if stream connection fails or drops
    const interval = mockSetInterval(() => {}, 30000);
    return () => {
      mockClearInterval(interval);
    };
  }

  let activeIntervals = 0;
  let clearedIntervals = 0;
  const fakeSetInterval = () => { activeIntervals++; return 101; };
  const fakeClearInterval = () => { clearedIntervals++; activeIntervals--; };

  // 1. Initial disconnected state -> fallback interval scheduled
  let cleanup = simulatePollingEffect(false, fakeSetInterval, fakeClearInterval);
  assert.equal(activeIntervals, 1, 'Fallback polling interval must be active when stream is disconnected');

  // 2. Stream connects -> cleanup interval, no interval scheduled
  cleanup();
  assert.equal(activeIntervals, 0, 'Previous interval cleared');
  cleanup = simulatePollingEffect(true, fakeSetInterval, fakeClearInterval);
  assert.equal(activeIntervals, 0, 'Legacy polling interval MUST be retired when stream is connected');

  // 3. Stream drops -> fallback interval scheduled again
  cleanup();
  cleanup = simulatePollingEffect(false, fakeSetInterval, fakeClearInterval);
  assert.equal(activeIntervals, 1, 'Fallback polling interval MUST be retained when stream drops');
  cleanup();
  assert.equal(activeIntervals, 0);
}

// ---------------------------------------------------------------------------
// 5. BridgeHome Surgical Telemetry Invalidation
// ---------------------------------------------------------------------------
{
  const requestedUrls = [];
  let statusRefreshed = 0;

  const mockBridgeHomeContext = {
    onRefreshStatus: () => { statusRefreshed++; },
    setHolocron: (data) => { mockBridgeHomeContext.holocron = data; },
    setReadiness: (data) => { mockBridgeHomeContext.readiness = data; },
    setAvailableMissions: (data) => { mockBridgeHomeContext.missions = data; },
    apiFetch: async (url) => {
      requestedUrls.push(url);
      if (url.includes('holocron')) return { ok: true, json: async () => ({ week_id: '2026-W40', summary: { precision_rate: 98 } }) };
      if (url.includes('readiness')) return { ok: true, json: async () => ({ overall: 95 }) };
      if (url.includes('missions')) return { ok: true, json: async () => (['Mission Alpha']) };
      return { ok: false };
    },
  };

  // Extract the handler inside subscribeVaultStream
  const returnUnsub = bridgeHomeSrc.includes('return () => {\r\n      unsubscribe();')
    ? 'return () => {\r\n      unsubscribe();'
    : 'return () => {\n      unsubscribe();';
  const handlerEnd = bridgeHomeSrc.indexOf(returnUnsub);
  const handlerStart = bridgeHomeSrc.indexOf('subscribeVaultStream(') + 'subscribeVaultStream('.length;
  const handlerFn = bridgeHomeSrc.slice(handlerStart, handlerEnd).trim().replace(/\);\s*$/, '');

  const bhRunner = `
    globalThis.handleBridgeEvent = ${handlerFn};
  `;

  vm.createContext(mockBridgeHomeContext);
  vm.runInContext(bhRunner, mockBridgeHomeContext);

  // Dispatch Bridge status change
  await mockBridgeHomeContext.handleBridgeEvent({ type: 'bridge', path: 'Bridge/status.json', action: 'modified' });
  assert.equal(statusRefreshed, 1, 'BridgeHome must invoke onRefreshStatus when Bridge/status.json changes');
  assert.ok(requestedUrls.includes('/api/readiness'), 'Readiness must be invalidated on status change');

  // Dispatch Holocron change
  requestedUrls.length = 0;
  await mockBridgeHomeContext.handleBridgeEvent({ type: 'bridge', path: 'Bridge/Holocron/Weekly/2026-W40.json', action: 'modified' });
  assert.ok(requestedUrls.includes('/api/holocron/weekly/current'), 'Holocron must be invalidated on holocron change');

  // Dispatch Mission change
  requestedUrls.length = 0;
  await mockBridgeHomeContext.handleBridgeEvent({ type: 'bridge', path: 'Bridge/.navis_cache/sector_cache.json', action: 'modified' });
  assert.ok(requestedUrls.includes('/api/missions/all'), 'Missions must be invalidated on sector cache change');
}

console.log('✅ All Reactive-P4 client optimistic invalidation & UI cache refresh checks passed.');
