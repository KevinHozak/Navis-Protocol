// Render real boards and execute their production hook/store and desktop API.
// Transport is synthetic; no Vault, HTTP server, or native installation is used.
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import React from 'react';
import TestRenderer, { act } from 'react-test-renderer';
import swc from 'next/dist/build/swc/index.js';
import { createTaskBoardStore } from '../src/lib/taskBoardStore.mjs';

if (!vm.SourceTextModule) {
  const result = spawnSync(process.execPath, ['--experimental-vm-modules', fileURLToPath(import.meta.url)], { stdio: 'inherit' });
  if (result.error) throw result.error;
  process.exit(result.status ?? 1);
}
await swc.loadBindings();
const task = { id: 'task 雪', text: 'Synthetic task', frequency: 'daily', next_due: '2026-10-02' };
const packet = (body, status = 200) => ({ status, body, text: JSON.stringify(body) });
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };

async function board(name, native) {
  const replies = [], calls = [];
  const transport = async (path, options = {}) => {
    calls.push({ path, method: options.method || 'GET', body: options.body });
    assert.ok(replies.length, `Unexpected request: ${path}`);
    const next = replies.shift();
    if (next instanceof Error) throw next;
    const result = await next;
    return native ? result : new Response(result.text, { status: result.status });
  };
  const context = vm.createContext({ process: { env: { NEXT_PUBLIC_API_URL: 'https://fixture.invalid' } },
    window: { __TAURI_INTERNALS__: native ? {} : undefined, location: { hostname: 'fixture.invalid' }, confirm: () => true, dispatchEvent: () => {} },
    navigator: { userAgent: 'Windows' }, fetch: (url, options) => transport(url.replace('https://fixture.invalid', ''), options),
    Headers, Response, Error, DOMException, Event, console, setInterval: () => 1, clearInterval: () => {} });
  const modules = new Map();
  const synthetic = async (key, values) => {
    if (modules.has(key)) return modules.get(key);
    const mod = new vm.SyntheticModule(Object.keys(values), function () { for (const [key, value] of Object.entries(values)) this.setExport(key, value); }, { context });
    modules.set(key, mod);
    await mod.link(() => {});
    return mod;
  };
  const load = async (path) => {
    if (modules.has(path)) return modules.get(path);
    let source = await readFile(new URL('../src/' + path, import.meta.url), 'utf8');
    if (path.startsWith('components/')) source = swc.transformSync(source, {
      filename: path, jsc: { parser: { syntax: 'ecmascript', jsx: true }, target: 'es2020', transform: { react: { runtime: 'classic' } } }, module: { type: 'es6' },
    }).code;
    const mod = new vm.SourceTextModule(source, { context, identifier: path,
      importModuleDynamically: async specifier => {
        if (specifier === '@tauri-apps/api/core') {
          const core = await synthetic('core', { invoke: (command, args) => { assert.equal(command, 'vault_request'); return transport(args.path, { method: args.method, body: args.body }); } });
          if (core.status !== 'evaluated') await core.evaluate();
          return core;
        }
        if (specifier === './MarkdownRenderer' || specifier === '@/components/MarkdownRenderer') {
          const md = await synthetic('md', { default: ({ content }) => React.createElement('div', null, content) });
          if (md.status !== 'evaluated') await md.evaluate();
          return md;
        }
        throw new Error(`Unexpected dynamic import: ${specifier}`);
      },
    });
    modules.set(path, mod);
    await mod.link(async specifier => {
      if (specifier === 'react') return synthetic('react', { default: React, useState: React.useState, useEffect: React.useEffect });
      if (specifier === 'framer-motion') return synthetic('motion', { motion: { div: 'div', form: 'form' }, AnimatePresence: ({ children }) => children });
      if (specifier === 'next/dynamic') return synthetic('next/dynamic', { default: () => ({ content }) => React.createElement('div', null, content) });
      if (specifier.startsWith('@/')) return load(specifier.slice(2) + '.js');
      if (specifier === './taskBoardStore.mjs') return load('lib/taskBoardStore.mjs');
      throw new Error(`Unexpected import: ${specifier}`);
    });
    return mod;
  };
  const mod = await load(`components/${name}.js`);
  await mod.evaluate();
  const Component = mod.namespace.default;
  let renderer;
  const render = async area => act(async () => { const element = React.createElement(Component, { area }); if (renderer) renderer.update(element); else renderer = TestRenderer.create(element); });
  const click = async button => act(async () => { await button.props.onClick(); });
  const text = () => JSON.stringify(renderer.toJSON());
  const button = label => renderer.root.findAllByType('button').find(node => node.props.title === label || node.children.join('') === label);
  const add = async () => {
    await click(button(name === 'TasksBoard' ? '+ New Directive' : '+ New Mandate'));
    await act(async () => renderer.root.findByType('input').props.onChange({ target: { value: 'New task' } }));
  };
  const submit = async () => act(async () => { await renderer.root.findByType('form').props.onSubmit({ preventDefault() {} }); });
  return { replies, calls, render, click, text, button, add, submit, get root() { return renderer.root; }, unmount: async () => act(async () => renderer.unmount()) };
}

let scenarios = 0;
for (const native of [false, true]) for (const name of ['TasksBoard', 'RecurringBoard']) {
  const endpoint = name === 'TasksBoard' ? '/api/active_tasks' : '/api/recurring';
  for (const failure of [packet({ detail: 'offline' }, 500), packet({ wrong: 'shape' }), packet([null]), packet([{ ...task, next_due: {} }]), new Error('disconnected'), { status: 200, text: '{', body: undefined }]) {
    const b = await board(name, native);
    b.replies.push(failure); await b.render('Home');
    assert.match(b.text(), /Retry loading/); assert.doesNotMatch(b.text(), /No active directives|No recurring mandates/);
    b.replies.push(packet([])); await b.click(b.button('Retry loading'));
    assert.match(b.text(), /No active directives|No recurring mandates/);
    await b.unmount(); scenarios++;
  }
  // Failed create preserves the draft; double-submit cannot duplicate the POST.
  const b = await board(name, native);
  b.replies.push(packet([task])); await b.render('Home'); await b.add();
  const saving = deferred(); b.replies.push(saving.promise);
  let first;
  await act(async () => { first = b.root.findByType('form').props.onSubmit({ preventDefault() {} }); });
  assert.equal(b.button('Deploy').props.disabled, true);
  await b.submit(); assert.equal(b.calls.filter(call => call.method === 'POST').length, 1);
  await act(async () => { saving.resolve(packet({ detail: 'persistence unavailable' }, 500)); await first; });
  assert.equal(b.root.findByType('input').props.value, 'New task'); assert.match(b.text(), /persistence unavailable/); assert.match(b.text(), /Synthetic task/);
  b.replies.push(packet([task]), packet({ saved: true }), packet([task, { ...task, id: 'created', text: 'New task' }]));
  await b.submit(); assert.equal(b.calls.filter(call => call.method === 'POST').length, 2); assert.equal(b.root.findAllByType('form').length, 0);
  await b.unmount(); scenarios++;

  // The POST committed, but its response was lost. Retry reconciles without POST.
  const lost = await board(name, native);
  lost.replies.push(packet([task])); await lost.render('Home'); await lost.add();
  lost.replies.push(new Error('response lost')); await lost.submit();
  lost.replies.push(packet([task, { ...task, id: 'committed', text: 'New task' }])); await lost.submit();
  assert.equal(lost.calls.filter(call => call.method === 'POST').length, 1); assert.equal(lost.root.findAllByType('form').length, 0);
  await lost.unmount(); scenarios++;

  // An unrelated successful mutation cannot forget an uncertain create.
  const mixed = await board(name, native);
  mixed.replies.push(packet([task])); await mixed.render('Home'); await mixed.add();
  mixed.replies.push(new Error('response lost')); await mixed.submit();
  const committed = { ...task, id: 'committed', text: 'New task' };
  mixed.replies.push(packet({ saved: true }), packet([task, committed]));
  await mixed.click(mixed.button(name === 'TasksBoard' ? 'Mark Done' : 'Mark Done Today'));
  mixed.replies.push(packet([task, committed])); await mixed.submit();
  assert.equal(mixed.calls.filter(call => call.path === endpoint && call.method === 'POST').length, 1);
  await mixed.unmount(); scenarios++;

  // Reconciliation failure blocks another create, keeping the draft retryable.
  const reconcile = await board(name, native);
  reconcile.replies.push(packet([task])); await reconcile.render('Home'); await reconcile.add();
  reconcile.replies.push(new Error('response lost')); await reconcile.submit();
  reconcile.replies.push(packet({ detail: 'read failed' }, 500)); await reconcile.submit();
  assert.equal(reconcile.calls.filter(call => call.method === 'POST').length, 1);
  assert.equal(reconcile.root.findByType('input').props.value, 'New task');
  reconcile.replies.push(packet([task]), packet({ saved: true }), packet([task, { ...task, id: 'new', text: 'New task' }]));
  await reconcile.submit(); assert.equal(reconcile.calls.filter(call => call.method === 'POST').length, 2);
  await reconcile.unmount(); scenarios++;

  for (const title of name === 'TasksBoard' ? ['Mark Done'] : ['Mark Done Today', 'Delete Mandate']) {
    for (const failure of [packet({ detail: 'write failed' }, 500), new Error('offline'), { status: 500, text: 'HTML error', body: null }]) {
      const m = await board(name, native);
      m.replies.push(packet([task])); await m.render('Home');
      m.replies.push(failure); await m.click(m.button(title));
      assert.match(m.text(), /Synthetic task/); assert.match(m.text(), /role.*alert/);
      m.replies.push(packet({ saved: true }), packet(title === 'Mark Done Today' ? [{ ...task, last_done: '2026-10-02' }] : []));
      await m.click(m.button(title));
      assert.equal(m.calls.at(-2).path, (title === 'Mark Done' || title === 'Mark Done Today') ? `${endpoint}/task%20%E9%9B%AA/complete` : `${endpoint}/task%20%E9%9B%AA`);
      await m.unmount(); scenarios++;
    }
  }
  // Successful write + failed refresh is a list error; the write is never resent.
  const refresh = await board(name, native);
  refresh.replies.push(packet([task])); await refresh.render('Home'); await refresh.add();
  refresh.replies.push(packet({ saved: true }), packet({ detail: 'offline' }, 500)); await refresh.submit();
  assert.equal(refresh.root.findAllByType('form').length, 0); assert.match(refresh.text(), /Showing last confirmed tasks/);
  refresh.replies.push(packet([])); await refresh.click(refresh.button('Retry loading'));
  assert.equal(refresh.calls.filter(call => call.method === 'POST').length, 1);
  await refresh.unmount(); scenarios++;

  // Area changes isolate both list responses and mutation follow-up requests.
  for (const mutation of [false, true]) {
    const stale = await board(name, native); const old = deferred();
    if (mutation) {
      stale.replies.push(packet([task])); await stale.render('Home');
      stale.replies.push(old.promise); await act(async () => { stale.button(name === 'TasksBoard' ? 'Mark Done' : 'Mark Done Today').props.onClick(); });
    } else { stale.replies.push(old.promise); await stale.render('Home'); }
    assert.match(stale.text(), mutation ? /Saving task/ : /Loading tasks/);
    stale.replies.push(packet([{ ...task, id: 'world', text: 'World task' }])); await stale.render('World');
    const before = stale.calls.length;
    await act(async () => { old.resolve(packet(mutation ? { saved: true } : [task])); });
    assert.match(stale.text(), /World task/); assert.doesNotMatch(stale.text(), /Synthetic task/);
    assert.equal(stale.calls.length, before, 'Disposed mutation must not issue another list request');
    await stale.unmount(); scenarios++;
  }
}
// Overlapping same-area refreshes: latest request wins on success and error.
for (const staleResult of [{ ok: true, json: async () => [task] }, { ok: false }]) {
  const old = deferred(); let calls = 0;
  const store = createTaskBoardStore(() => ++calls === 1 ? old.promise : Promise.resolve({ ok: true, json: async () => [] }), '/api/active_tasks', 'Home');
  const first = store.refresh(); await store.refresh(); old.resolve(staleResult); await first;
  assert.deepEqual(store.getState().tasks, []); assert.equal(store.getState().listError, ''); assert.equal(store.getState().loading, false);
  store.dispose(); scenarios++;
}
console.log(`Passed ${scenarios} task-board interaction and race scenarios through web/native adapters.`);
