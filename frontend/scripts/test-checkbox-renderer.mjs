import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import React from 'react';
import TestRenderer, { act } from 'react-test-renderer';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import swc from 'next/dist/build/swc/index.js';
if (!vm.SourceTextModule) {
  const run = spawnSync(process.execPath, ['--experimental-vm-modules', fileURLToPath(import.meta.url)], {stdio: 'inherit'});
  process.exit(run.status ?? 1);
}
await swc.loadBindings();
const context = vm.createContext({console});
const source = await readFile(new URL('../src/components/MarkdownRenderer.js', import.meta.url), 'utf8');
const code = swc.transformSync(source, {filename: 'MarkdownRenderer.js', jsc: {parser: {syntax: 'ecmascript', jsx: true}, transform: {react: {runtime: 'classic'}}}, module: {type: 'es6'}}).code;
const mod = new vm.SourceTextModule(code, {context});
const pickerModule = { exports: {} };
const pickerCode = swc.transformSync(await readFile(new URL('../src/components/TaskStatusPicker.js', import.meta.url), 'utf8'), {filename:'TaskStatusPicker.js', jsc:{parser:{syntax:'ecmascript',jsx:true},transform:{react:{runtime:'classic'}}},module:{type:'commonjs'}}).code;
vm.runInNewContext(pickerCode, {module: pickerModule, exports: pickerModule.exports, require: () => React});
await mod.link(async name => {
  const values = name === 'react' ? {default: React, useState: React.useState, useRef: React.useRef, useEffect: React.useEffect}
    : name === './TaskStatusPicker' ? {default: pickerModule.exports.default}
    : name === 'react-markdown' ? {default: ReactMarkdown}
    : name === 'remark-gfm' ? {default: remarkGfm}
    : name === 'rehype-raw' ? {default: rehypeRaw} : {apiUrl: path => path};
  const dependency = new vm.SyntheticModule(Object.keys(values), function () {
    for (const [key, value] of Object.entries(values)) this.setExport(key, value);
  }, {context});
  await dependency.link(() => {});
  return dependency;
});
await mod.evaluate();
const Renderer = mod.namespace.default;
let resolve, calls = 0, tree;
const onToggleCheckbox = () => {calls++; return new Promise(r => {resolve = r;});};
const props = {content: '- [ ] First\n- [ ] Second', onToggleCheckbox};
await act(async () => {tree = TestRenderer.create(React.createElement(Renderer, props));});
let request;
await act(async () => {request = tree.root.findAllByType('input')[0].props.onChange();});
assert.equal(tree.root.findAllByType('input')[0].props.checked, true);
assert.ok(tree.root.findAllByType('input').every(input => input.props.disabled));
assert.equal(tree.root.findByProps({role: 'status'}).children[0], 'Saving task…');
await act(async () => {await tree.root.findAllByType('input')[1].props.onChange();});
assert.equal(calls, 1);
await act(async () => {tree.update(React.createElement(Renderer, {...props, content: props.content + '\n'}));});
assert.equal(tree.root.findAllByType('input')[0].props.checked, true);
await act(async () => {
  tree.update(React.createElement(Renderer, {...props, content: '- [x] First\n- [ ] Second'}));
  resolve({ok: true}); await request;
});
assert.equal(tree.root.findAllByType('input')[0].props.checked, true);
assert.ok(tree.root.findAllByType('input').every(input => !input.props.disabled));
await act(async () => {request = tree.root.findAllByType('input')[0].props.onChange();});
await act(async () => {resolve({ok: false}); await request;});
assert.equal(tree.root.findAllByType('input')[0].props.checked, true);
assert.match(tree.root.findByProps({role: 'status'}).children[0], /retry/);
await act(async () => tree.unmount());
console.log('Checkbox renderer pending feedback, rapid input, refresh, confirmation and failure reconciliation passed.');
