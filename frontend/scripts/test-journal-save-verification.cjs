const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const React = require('react');
const renderer = require('react-test-renderer');
const swc = require('next/dist/build/swc');

const A = '2026-10-26', B = '2026-10-27';
const path = day => `Journal/2026/10/${day}.md`;
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const response = (body, status = 200) => ({ ok: status < 400, status, json: async () => body, text: async () => JSON.stringify(body) });
const receipt = (day, content, pending = false) => ({ saved: true, status: pending ? 'saved_xp_pending' : 'success',
  date: day, path: path(day), content, sha256: 'a'.repeat(64), request_id: 'fixture-request-identity-001', xp_status: pending ? 'pending' : 'complete' });
const compile = file => swc.transformSync(fs.readFileSync(file, 'utf8'), { filename: file,
  jsc: { parser: { syntax: 'ecmascript', jsx: true }, transform: { react: { runtime: 'classic' } }, target: 'es2020' }, module: { type: 'commonjs' },
}).code;

async function mount(transport) {
  const writes = [], failedReads = new Set(), files = { [path(A)]: '# A original', [path(B)]: '# B original' };
  const modules = {};
  const api = { supportsLocalOllama: () => false, apiUrl: value => value, vaultAssetUrl: value => value,
    subscribeVaultStream: () => () => {},
    apiFetch: async (url, options = {}) => {
      if (options.method === 'POST') { const pending = deferred(); writes.push({ url, request: JSON.parse(options.body), ...pending, transport }); return pending.promise; }
      if (url === '/api/status') return response({ last_updated: A, squad: [] });
      if (url === '/api/navigation/pillars') return response([{ id: 'COMMAND', sectors: [{ id: 'JOURNAL' }] }]);
      if (url.startsWith('/api/entities?')) return response([A, B].map(day => ({ id: path(day), name: day, type: 'file' })));
      if (url.startsWith('/api/vault/')) {
        const target = url.slice('/api/vault/'.length);
        return failedReads.has(target) ? response({ detail: 'synthetic read failure' }, 503) : response({ content: files[target] });
      }
      throw new Error(`Unexpected fixture request: ${url}`);
    },
  };
  const stub = () => null;
  const children = props => props.children;
  const components = {
    SovereignRibbon: stub, SectorRail: stub, DesktopDiagnostics: stub,
    SecurityGuard: children, AsyncJobModal: stub, HorizonRoadmap: stub,
    EntityRail: props => React.createElement('nav', null, props.entities.map(entity => React.createElement('button',
      { key: entity.id, 'data-day': entity.name, onClick: () => props.onSelect(entity) }, entity.name))),
    SectorView: props => React.createElement('article', { 'data-record': props.activeEntity?.id },
      props.activeEntity && React.createElement(modules.Composer, { key: props.activeEntity.id,
        date: props.activeEntity.name, onSaved: props.onJournalEntrySaved, onUnverified: props.onJournalEntryUnverified, initialDraft: props.journalEntryDraft }),
      React.createElement('pre', { 'data-content': true }, props.entityContent)),
  };
  const load = (file, name) => {
    const module = { exports: {} };
    const context = { React, module, exports: module.exports, console, AbortController, AbortSignal,
      process: { env: {} }, window: { confirm: () => false }, alert: () => {},
      setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {},
      require: id => id === 'react' ? React : id.includes('journalDay') ? { journalDay: () => A }
        : id.includes('desktopApi') ? api : id.includes('journalSave.mjs') ? modules.helper
          : id === 'framer-motion' ? { motion: new Proxy({}, { get: (_, key) => key }), AnimatePresence: children }
            : id.endsWith('JournalSaveNotice') ? { __esModule: true, default: modules.Notice }
              : { __esModule: true, default: components[id.split('/').at(-1)] || stub },
    };
    vm.runInNewContext(compile(file), context);
    modules[name] = module.exports.default || module.exports;
  };
  load('src/lib/journalSave.mjs', 'helper');
  load('src/components/JournalEntryComposer.js', 'Composer');
  load('src/components/JournalSaveNotice.js', 'Notice');
  load('src/app/page.js', 'Home');
  let tree;
  await renderer.act(async () => { tree = renderer.create(React.createElement(modules.Home)); });
  const text = () => JSON.stringify(tree.toJSON());
  const click = async label => renderer.act(async () => { tree.root.findAllByType('button').find(button => button.props.children === label).props.onClick(); });
  const select = async day => renderer.act(async () => tree.root.findByProps({ 'data-day': day }).props.onClick());
  const draft = async value => {
    if (!tree.root.findAllByType('textarea').length) await click('+ Add Entry');
    await renderer.act(async () => tree.root.findByType('textarea').props.onChange({ target: { value } }));
  };
  const submit = async () => renderer.act(async () => { tree.root.findByType('form').props.onSubmit({ preventDefault() {} }); });
  const resolve = async (value, index = writes.length - 1) => renderer.act(async () => writes[index].resolve(value));
  const content = () => tree.root.findByProps({ 'data-content': true }).props.children;
  return { tree, writes, files, failedReads, text, click, select, draft, submit, resolve, content,
    unmount: async () => renderer.act(async () => tree.unmount()) };
}

(async () => {
  for (const transport of ['web', 'native']) {
    const test = await mount(transport);
    assert.equal(test.content(), '# A original');
    assert(!test.text().includes('Task saved. XP pending.'));
    await test.draft('Saved to A'); await test.submit();
    assert.equal(test.writes.length, 1);
    await test.select(B); await test.draft('B draft survives');
    test.files[path(A)] = '# A saved';
    await test.resolve(response(receipt(A, '# A saved', true)));
    assert.equal(test.content(), '# B original', 'late A receipt cannot replace B');
    assert.equal(test.tree.root.findByType('textarea').props.value, 'B draft survives');
    assert(test.text().includes(`Entry saved to ${A}. XP sync pending.`));
    await test.click('Retry XP for saved entry');
    assert.deepEqual(test.writes[1].request, test.writes[0].request);
    await renderer.act(async () => test.writes[1].reject(new Error('synthetic lost XP response')));
    assert(test.text().includes('The entry remains saved'));
    assert.equal(test.content(), '# B original');
    await test.click('Open saved journal');
    assert.equal(test.content(), '# A saved');
    await test.click('Retry XP for saved entry');
    await test.resolve(response(receipt(A, '# A saved')));
    assert(!test.text().includes('Retry XP for saved entry'));
    // A mismatched receipt is not proof of a committed save to the selected path.
    await test.draft('Unverified entry'); await test.submit();
    await test.resolve(response(receipt(B, '# Wrong journal')));
    assert(test.text().includes('Save not verified'));
    assert.equal(test.content(), '# A saved');
    assert.equal(test.tree.root.findByType('textarea').props.value, 'Unverified entry');
    const before = test.writes.length;
    await test.click('Review journal');
    assert.equal(test.writes.length, before, 'review must only read');
    // Known pre-commit rejection retains the current draft without claiming success.
    await test.draft('Rejected entry'); await test.submit();
    await test.resolve(response({ detail: 'invalid_argument' }, 422));
    assert(test.text().includes('Entry was not saved'));
    assert.equal(test.tree.root.findByType('textarea').props.value, 'Rejected entry');
    // A lost response may follow committed bytes; there is no automatic replay.
    await test.draft('Ambiguous entry'); await test.submit();
    const lost = test.writes.at(-1), count = test.writes.length;
    await renderer.act(async () => lost.reject(new Error('synthetic connection loss')));
    assert.equal(test.writes.length, count);
    assert(test.text().includes('Save not verified'));
    assert.equal(test.tree.root.findByType('textarea').props.value, 'Ambiguous entry');
    await test.select(B); await test.draft('Another B draft');
    await test.click('Review journal');
    assert.equal(test.tree.root.findByType('textarea').props.value, 'Ambiguous entry', 'review restores the exact unresolved draft only to its source');
    await test.submit();
    assert.deepEqual(test.writes.at(-1).request, lost.request, 'manual reconciliation preserves identity');
    test.failedReads.add(path(A));
    test.files[path(A)] = '# A committed despite response loss';
    await test.resolve(response(receipt(A, '# Receipt snapshot')));
    assert(test.text().includes('Entry saved; view refresh not verified'));
    assert(!test.text().includes('Save not verified for'));
    assert.equal(test.content(), '# A saved');
    test.failedReads.clear();
    await test.click('Open saved journal');
    assert.equal(test.content(), '# A committed despite response loss');
    await test.draft('Next entry');
    const submit = test.tree.root.findByType('form').props.onSubmit;
    const prior = test.writes.length;
    await renderer.act(async () => { submit({ preventDefault() {} }); submit({ preventDefault() {} }); });
    assert.equal(test.writes.length, prior + 1, 'same-frame submit is serialized');
    test.files[path(A)] = '# Newer authoritative content';
    await test.resolve(response(receipt(A, '# Older receipt snapshot')));
    assert.equal(test.content(), '# Newer authoritative content');
    await test.draft('Recovery error'); await test.submit();
    await test.resolve(response({ detail: 'recovery_required' }, 409));
    assert(test.text().includes('Save not verified'));
    assert.equal(test.content(), '# Newer authoritative content');
    await test.unmount();
  }
  console.log('Passed mounted Home/composer late-save isolation, saved-source navigation, receipt mismatch, pre-commit failure and exact XP recovery across web/native doubles.');
})().catch(error => { console.error(error); process.exitCode = 1; });
