import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { webcrypto } from 'node:crypto';
import vm from 'node:vm';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

if (!vm.SourceTextModule) {
  const result = spawnSync(process.execPath, ['--experimental-vm-modules', fileURLToPath(import.meta.url)], { stdio: 'inherit' });
  if (result.error) throw result.error;
  process.exit(result.status ?? 1);
}

const require = createRequire(process.env.NAVIS_TEST_MODULE_ROOT || new URL('../package.json', import.meta.url));
const React = require('react');
const TestRenderer = require('react-test-renderer');
const { act } = TestRenderer;
const swc = require('next/dist/build/swc');
await swc.loadBindings();
const source = await readFile(new URL('../src/components/WarRoom.js', import.meta.url), 'utf8');
const desktop = await readFile(new URL('../src/lib/desktopApi.js', import.meta.url), 'utf8');
const errors = await readFile(new URL('../src/lib/conversationError.js', import.meta.url), 'utf8');
const transformed = swc.transformSync(source, { filename: 'WarRoom.js', jsc: { parser: { syntax: 'ecmascript', jsx: true }, transform: { react: { runtime: 'classic' } } }, module: { type: 'es6' } }).code;

for (const native of [false, true]) {
  const queue = [], calls = [];
  const transport = async (path, options = {}) => {
    calls.push({ path, body: typeof options.body === 'object' ? JSON.stringify(options.body) : options.body });
    assert.ok(queue.length, `Unexpected request ${path}`);
    const result = queue.shift();
    if (!native) return result;
    const text = await result.text();
    let body; try { body = JSON.parse(text); } catch { body = { response: text }; }
    return { status: result.status, text, body };
  };
  const context = vm.createContext({ console, crypto: webcrypto, AbortController, TextDecoder, Error, DOMException, Event, Headers,
    process: { env: { NEXT_PUBLIC_API_URL: 'https://fixture.invalid' } }, navigator: { userAgent: 'Windows' },
    window: { confirm: () => true, location: { hostname: 'fixture.invalid' }, __TAURI_INTERNALS__: native ? {} : undefined, dispatchEvent: () => {} },
    fetch: (url, options) => transport(url.replace('https://fixture.invalid', ''), options) });
  const errorModule = new vm.SourceTextModule(errors, { context });
  await errorModule.link(() => {}); await errorModule.evaluate();
  const synthetic = async values => {
    const mod = new vm.SyntheticModule(Object.keys(values), function () { for (const [key, value] of Object.entries(values)) this.setExport(key, value); }, { context });
    await mod.link(() => {}); return mod;
  };
  const desktopModule = new vm.SourceTextModule(desktop, { context, importModuleDynamically: async name => {
    assert.equal(name, '@tauri-apps/api/core');
    const core = await synthetic({ invoke: (command, args) => {
      assert.equal(command, 'p5_request');
      return transport(args.path, { body: args.body });
    } });
    await core.evaluate(); return core;
  } });
  await desktopModule.link(() => {}); await desktopModule.evaluate();
  const module = new vm.SourceTextModule(transformed, { context });
  await module.link(async name => {
    if (name === 'react') return synthetic({ default: React, useState: React.useState, useEffect: React.useEffect, useRef: React.useRef });
    if (name.includes('conversationError')) return errorModule;
    if (name.includes('desktopApi')) return desktopModule;
    return synthetic({ default: ({ children }) => React.createElement('div', null, children) });
  });
  await module.evaluate();
  const response = (body, status = 200) => new Response(typeof body === 'string' ? body : JSON.stringify(body), { status });
  const fail = () => response({ code: 'native_dependency_unavailable', message: 'Start Ollama and verify the configured model.' }, 503);
  queue.push(fail());
  let renderer;
  await act(async () => { renderer = TestRenderer.create(React.createElement(module.namespace.default)); });
  const buttons = () => renderer.root.findAllByType('button');
  const retry = () => buttons().find(b => b.children.includes('Retry'));
  const text = () => JSON.stringify(renderer.toJSON());
  assert.ok(text().includes('Start Ollama'));
  assert.ok(!text().includes('native_dependency_unavailable'));
  const input = () => renderer.root.findByType('input');
  await act(async () => input().props.onChange({ target: { value: 'Unsent draft' } }));
  queue.push(response([]), fail());
  await act(async () => retry().props.onClick());
  assert.equal(calls.at(-2).path, '/api/neural/warroom/history');
  assert.equal(JSON.parse(calls.at(-1).body).message, '/init');
  assert.equal(input().props.value, 'Unsent draft');
  const initId = JSON.parse(calls.at(-1).body).request_id;
  queue.push(response('*Ahri*: Ready.'));
  await act(async () => retry().props.onClick());
  assert.equal(JSON.parse(calls.at(-1).body).message, '/init');
  assert.equal(JSON.parse(calls.at(-1).body).request_id, initId);
  assert.ok(!retry());
  queue.push(fail());
  await act(async () => renderer.root.findByType('form').props.onSubmit({ preventDefault() {} }));
  const chatId = JSON.parse(calls.at(-1).body).request_id;
  assert.equal(input().props.value, 'Unsent draft');
  await act(async () => input().props.onChange({ target: { value: 'Newer draft' } }));
  queue.push(response('*Ahri*: Recovered.'));
  await act(async () => retry().props.onClick());
  assert.equal(JSON.parse(calls.at(-1).body).request_id, chatId);
  assert.equal(input().props.value, 'Newer draft');
  assert.equal((text().match(/Unsent draft/g) || []).length, 1);
  assert.ok(text().includes('Recovered.'));
  await act(async () => renderer.unmount());
}
console.log('War Room history/init/chat recovery passed for web and native responses.');
