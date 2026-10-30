const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const React = require('react');
const renderer = require('react-test-renderer');
const swc = require('next/dist/build/swc');

function component(name, apiFetch) {
  const module = { exports: {} };
  const code = swc.transformSync(fs.readFileSync(`src/components/${name}.js`, 'utf8'), {
    filename: `${name}.js`, jsc: { parser: { syntax: 'ecmascript', jsx: true },
      transform: { react: { runtime: 'classic' } }, target: 'es2020' }, module: { type: 'commonjs' },
  }).code;
  vm.runInNewContext(code, { React, module, exports: module.exports, console,
    require: id => id === 'react' ? React : id === 'framer-motion' ? { motion: { div: 'div' } } : { apiFetch },
  });
  return module.exports.default;
}
const act = renderer.act;
const button = (root, text) => root.root.findAllByType('button').find(b => b.props.children === text);
const label = (root, text, type) => root.root.findAllByType('label').find(l => l.props.children[0] === text).findByType(type);

(async () => {
  const requests = [];
  const api = async (path, options) => {
    const body = options?.body && JSON.parse(options.body);
    requests.push({ path, body });
    const value = path.endsWith('/generate') ? { brief: Object.fromEntries(['Goal', 'Known facts', 'Uncertainties', 'One suggested next action'].map(k => [k, 'Synthetic reviewed text'])) }
      : path.endsWith('/sources') ? { sources: [{ path: 'Library/Source.md', content: 'Synthetic source unchanged.', sha256: 'fixture-digest' }] }
      : { saved: true, path: 'Library/Notes/fixture.md' };
    return { ok: true, json: async () => value };
  };
  let root;
  const Brief = component('ActionableBrief', api);
  await act(async () => { root = renderer.create(React.createElement(Brief, { entry: 'Synthetic tangled original.', date: '2026-10-30', section: 'Sanctum', available: true })); });
  await act(async () => button(root, 'Create actionable brief').props.onClick());
  assert.equal(root.root.findByType('details').props.open, true);
  assert.equal(root.root.findByType('pre').props.children, 'Synthetic tangled original.');
  assert.equal(requests.filter(r => r.path.endsWith('/save')).length, 0);
  await act(async () => root.root.findAllByType('textarea')[0].props.onChange({ target: { value: 'Edited goal' } }));
  await act(async () => button(root, 'Save brief').props.onClick());
  assert.equal(requests.at(-1).body.original, 'Synthetic tangled original.');
  assert.equal(requests.at(-1).body.brief.Goal, 'Edited goal');
  await act(async () => root.unmount());

  const Knowledge = component('KnowledgeNoteComposer', api);
  await act(async () => { root = renderer.create(React.createElement(Knowledge)); });
  await act(async () => button(root, 'Create knowledge note').props.onClick());
  const before = requests.length;
  await act(async () => root.root.findByType('textarea').props.onChange({ target: { value: 'Library/Source.md' } }));
  assert.equal(requests.length, before, 'selection must not fetch or save');
  await act(async () => button(root, 'Load selected sources').props.onClick());
  assert.equal(root.root.findByType('details').props.open, true);
  assert.equal(root.root.findByType('pre').props.children, 'Synthetic source unchanged.');
  const question = () => label(root, 'Question', 'textarea');
  await act(async () => question().props.onChange({ target: { value: 'Compare café exports?' } }));
  assert.equal(root.root.findByType('input').props.value, 'Compare-cafe-exports');
  assert.equal(requests.at(-1).path, '/api/knowledge-notes/sources', 'typing must not save');
  await act(async () => root.root.findByType('input').props.onChange({ target: { value: 'my-own-name' } }));
  await act(async () => question().props.onChange({ target: { value: 'Changed question' } }));
  assert.equal(root.root.findByType('input').props.value, 'my-own-name', 'suggestion must not overwrite a manual edit');
  for (const text of ['Findings (cite source numbers)', 'Uncertainty and disagreements', 'One practical application']) {
    await act(async () => label(root, text, 'textarea').props.onChange({ target: { value: `Reviewed ${text}` } }));
  }
  await act(async () => button(root, 'Save knowledge note').props.onClick());
  assert.equal(requests.at(-1).body.filename, 'my-own-name');
  assert.equal(requests.at(-1).body.sources[0].sha256, 'fixture-digest');
  assert.equal(requests.at(-1).body.destination, 'Library/Notes');
  await act(async () => button(root, 'Discard note').props.onClick());
  await act(async () => button(root, 'Load selected sources').props.onClick());
  await act(async () => question().props.onChange({ target: { value: 'CON' } }));
  assert.equal(root.root.findByType('input').props.value, 'knowledge-note');
  await act(async () => question().props.onChange({ target: { value: '中文' } }));
  assert.equal(root.root.findByType('input').props.value, 'knowledge-note');
  await act(async () => question().props.onChange({ target: { value: 'x'.repeat(200) } }));
  assert.equal(root.root.findByType('input').props.value.length, 80);
  await act(async () => root.unmount());

  const Evidence = component('HolocronEvidence', api);
  const evidence = { sources: [{ id: 'journal', date: '2026-10-30' }], metrics: {
    decision_review: { rule: 'Checkbox observations only.', status: 'partial', source_ids: ['journal'] },
    precision_rate: { rule: 'Other metric', status: 'partial', source_ids: [] },
  } };
  const prior = requests.length;
  await act(async () => { root = renderer.create(React.createElement(Evidence, { weekId: '2026-W44', evidence, decisionOnly: true })); });
  assert.equal(root.root.findByType('details').props.open, true);
  assert.match(JSON.stringify(root.toJSON()), /Checkbox observations only/);
  assert.doesNotMatch(JSON.stringify(root.toJSON()), /Other metric/);
  assert.equal(root.root.findAllByType('button').length, 1, 'explicit inspection retained');
  assert.equal(requests.length, prior, 'inline evidence must not automatically fetch or write');
  await act(async () => root.unmount());
  console.log('Passed mounted S008 journeys: expanded previews, editable safe filename, explicit loads/saves, source digests and inline decision references.');
})().catch(error => { console.error(error); process.exitCode = 1; });
