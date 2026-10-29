const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const React = require('react');
const renderer = require('react-test-renderer');
const swc = require('next/dist/build/swc');

const source = fs.readFileSync('src/components/AsyncJobModal.js', 'utf8');
const code = swc.transformSync(source, {
  filename: 'AsyncJobModal.js',
  jsc: { parser: { syntax: 'ecmascript', jsx: true }, transform: { react: { runtime: 'classic' } }, target: 'es2020' },
  module: { type: 'commonjs' },
}).code;

async function mount(report, { native = false, previous = null, operation = 'sync', portal = false } = {}) {
  const requests = [], events = [], cancel = [], writes = [];
  const portalTargets = [], body = { fixtureBody: true };
  const module = { exports: {} };
  vm.runInNewContext(code, {
    React, module, exports: module.exports, console, Event,
    ...(portal ? { document: { body } } : {}),
    window: { dispatchEvent: () => {}, confirm: () => true }, setTimeout: () => 0, clearTimeout: () => {},
    require: id => id === 'react' ? React : id === 'react-dom' ? {
      createPortal: (element, target) => { portalTargets.push(target); return element; },
    } : {
      apiFetch: async (path, options) => {
        requests.push(path);
        const value = previous && (path === '/api/ops/latest' || path.includes(previous.job_id)) ? previous : { job_id: 'random-request-id', ...report };
        if (options?.method === 'POST') writes.push(path);
        return { ok: true, json: async () => options?.method === 'POST' ? { ...value, reviewed: true } : value };
      },
      isTauriRuntime: () => native,
      listenNativeEvent: async (_, callback) => { events.push(callback); return () => {}; },
      cancelSyncOperation: async id => cancel.push(id),
    },
  });
  let completed = 0, root;
  const props = { operation, jobId: 'random-request-id', onClose: () => {}, onComplete: () => completed++ };
  await renderer.act(async () => { root = renderer.create(React.createElement(module.exports.default, props)); });
  return { root, requests, events, cancel, writes, portalTargets, body, completed: () => completed,
    text: () => JSON.stringify(root.toJSON()),
    async reconnect() {
      const button = root.root.findAllByType('button').find(b => b.props.children === 'Reconnect status');
      await renderer.act(async () => button.props.onClick());
    },
    async unmount() { await renderer.act(async () => root.unmount()); },
  };
}

async function main() {
  for (const native of [false, true]) {
    const report = { status: 'partial', recovery: 'review_saved_changes', steps: [
      { id: 'work', label: 'Work journal', status: 'completed', persistence: 'confirmed' },
      { id: 'xp', label: 'XP reconciliation', status: 'failed', persistence: 'may_have_committed' },
      { id: 'cache', label: 'View cache', status: 'not_run' },
    ] };
    const test = await mount(report, { native });
    assert.match(test.text(), /Partially completed/);
    assert.match(test.text(), /saved/);
    assert.match(test.text(), /not run/);
    assert.equal(test.completed(), 0);
    const before = test.requests.length;
    await test.reconnect();
    assert.equal(test.requests.length, before + 1);
    assert.ok(test.requests.every(path => path === '/api/ops/jobs/random-request-id'));
    assert.equal(test.completed(), 0);
    const review = test.root.root.findAllByType('button').find(b => b.props.children === 'Confirm review');
    await renderer.act(async () => review.props.onClick());
    assert.deepEqual(test.writes, ['/api/ops/jobs/random-request-id/review']);
    assert.match(test.text(), /Review recorded/);
    if (native) {
      await renderer.act(async () => test.events[0]({ status: 'failed', message: 'coarse process exit' }));
      assert.match(test.text(), /Partially completed/);
    }
    await test.unmount();
    const portalled = await mount(report, { native, portal: true });
    assert(portalled.portalTargets.length > 0);
    assert(portalled.portalTargets.every(target => target === portalled.body));
    assert.equal(portalled.root.root.findByProps({ role: 'dialog' }).props['aria-modal'], 'true');
    await portalled.unmount();
  }
  const interrupted = await mount({ status: 'interrupted', steps: [{ id: 'work', label: 'Work journal', status: 'unknown' }], recovery: 'review_saved_changes' });
  assert.match(interrupted.text(), /Interrupted/);
  assert.match(interrupted.text(), /unknown/);
  assert.equal(interrupted.completed(), 0);
  await interrupted.unmount();
  const completed = await mount({ status: 'completed', steps: [] });
  assert.equal(completed.completed(), 1);
  await completed.unmount();
  const running = await mount({ status: 'running', steps: [] }, { native: true });
  const button = running.root.root.findAllByType('button').find(b => b.props.children === 'Cancel operation');
  await renderer.act(async () => button.props.onClick());
  assert.deepEqual(running.cancel, ['random-request-id']);
  await running.unmount();
  const prior = await mount({ status: 'failed' }, { native: true, previous: { job_id: 'prior', operation: 'sync', status: 'completed', steps: [] } });
  assert.match(prior.text(), /This request did not start/);
  assert.equal(prior.completed(), 0);
  assert.equal(prior.writes.length, 0);
  await prior.unmount();
  const generic = await mount({ status: 'completed' }, { native: true, operation: null });
  assert.equal(generic.completed(), 1);
  await generic.unmount();
  console.log('Passed 7 mounted operation-outcome scenarios across web/native doubles; reconnect performs reads only.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
