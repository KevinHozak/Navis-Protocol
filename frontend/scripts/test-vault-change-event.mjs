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

console.log('Testing native Tauri vault-change event bridge and payload integrity...');

const root = resolve(process.cwd(), 'src');
const [desktopApiSrc, rustVaultSrc, libRsSrc] = await Promise.all([
  readFile(resolve(root, 'lib/desktopApi.js'), 'utf8'),
  readFile(resolve(process.cwd(), 'src-tauri/src/vault.rs'), 'utf8'),
  readFile(resolve(process.cwd(), 'src-tauri/src/lib.rs'), 'utf8'),
]);

// 1. Rust and Desktop API Contract Alignment
assert.match(
  rustVaultSrc,
  /pub\s+const\s+VAULT_CHANGE_EVENT:\s+&str\s+=\s+"navis:\/\/vault-change";/,
  'vault.rs must define canonical VAULT_CHANGE_EVENT as "navis://vault-change"',
);

assert.match(
  desktopApiSrc,
  /export\s+const\s+VAULT_CHANGE_EVENT\s*=\s*['"]navis:\/\/vault-change['"];/,
  'desktopApi.js must export canonical VAULT_CHANGE_EVENT as "navis://vault-change"',
);

assert.match(
  rustVaultSrc,
  /pub\s+struct\s+VaultChangeEvent/,
  'vault.rs must define typed VaultChangeEvent struct',
);

assert.match(
  libRsSrc,
  /vault::emit_vault_change_event/,
  'lib.rs must register emit_vault_change_event in invoke handler',
);

assert.match(
  libRsSrc,
  /vault::VaultWatcherState::default\(\)/,
  'lib.rs must manage VaultWatcherState in Tauri builder',
);

// 2. VM Simulation of desktopApi in Desktop and Web Runtimes
async function setupDesktopApi(isNative = true) {
  const calls = [];
  const listeners = [];
  const window = {
    location: { hostname: 'localhost' },
    __TAURI_INTERNALS__: isNative ? {} : undefined,
    dispatchEvent: () => {},
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
            calls.push({ command, args: JSON.parse(JSON.stringify(args)) });
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
  return { api: module.namespace, calls, listeners };
}

// 3. Test Event Listening and Payload Integrity
const { api: nativeApi, listeners: nativeListeners } = await setupDesktopApi(true);

const observedEvents = [];
const unlisten = await nativeApi.listenVaultChange((payload) => {
  observedEvents.push(payload);
});

assert.equal(nativeListeners.length, 1, 'Event listener must be registered in Tauri runtime');
assert.equal(nativeListeners[0].eventName, 'navis://vault-change');

// Simulate incoming structured filesystem event from Tauri native event emitter
const samplePayload = {
  type: 'journal',
  path: 'Journal/2026/10/2026-10-02.md',
  timestamp: 1759461234.789,
  action: 'modified',
  full_path: 'G:/My Drive/Navis-Vault/Journal/2026/10/2026-10-02.md',
};

// Dispatch via Tauri event callback wrapper ({ payload })
nativeListeners[0].callback({ payload: samplePayload });

assert.equal(observedEvents.length, 1, 'Should receive dispatched event');
const received = observedEvents[0];
assert.equal(received.type, 'journal');
assert.equal(received.path, 'Journal/2026/10/2026-10-02.md');
assert.equal(received.action, 'modified');
assert.equal(received.timestamp, 1759461234.789);
assert.equal(received.full_path, 'G:/My Drive/Navis-Vault/Journal/2026/10/2026-10-02.md');

// 4. Test Unlisten Lifecycle
unlisten();
assert.equal(nativeListeners.length, 0, 'Unlisten must detach event listener');

// 5. Test Web Runtime Fallback (No Crash, Clean No-Op)
const { api: webApi, listeners: webListeners } = await setupDesktopApi(false);
let webCalled = false;
const webUnlisten = await webApi.listenVaultChange(() => {
  webCalled = true;
});
assert.equal(typeof webUnlisten, 'function', 'Web unlisten must return a safe callable');
assert.equal(webListeners.length, 0, 'Web mode must not register native event listener');
webUnlisten();
assert.equal(webCalled, false);

// 6. Test Native Event Emission Invocation
const { api: emitApi, calls: emitCalls } = await setupDesktopApi(true);
const dispatchEvent = {
  type: 'bridge',
  path: 'Bridge/status.json',
  timestamp: Date.now() / 1000,
  action: 'modified',
};
await emitApi.emitNativeVaultChangeEvent(dispatchEvent);

assert.equal(emitCalls.length, 1);
assert.equal(emitCalls[0].command, 'emit_vault_change_event');
assert.deepEqual(emitCalls[0].args, { event: dispatchEvent });

console.log('✅ All Tauri vault-change native event bridge and payload integrity checks passed.');
