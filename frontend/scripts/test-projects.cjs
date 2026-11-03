const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const React = require('react');
const renderer = require('react-test-renderer');
const swc = require('next/dist/build/swc');
const moduleValue = {exports:{}};
let respond, calls = 0;
const apiFetch = () => { calls++; return new Promise(resolve => { respond = resolve; }); };
const code = swc.transformSync(fs.readFileSync('src/components/ProjectsView.js','utf8'), {
  filename:'ProjectsView.js', jsc:{parser:{syntax:'ecmascript',jsx:true},transform:{react:{runtime:'classic'}},target:'es2020'},module:{type:'commonjs'},
}).code;
vm.runInNewContext(code,{React,module:moduleValue,exports:moduleValue.exports,console,AbortSignal,
  require:id=>id==='react'?React:id==='framer-motion'?{motion:{section:'section'}}:{apiFetch}});
const act=renderer.act;
const payload={account:'fixture',refreshed_at:'2026-11-03T00:00:00Z',partial:true,limited:false,repositories:[{
  name:'fixture/repo',url:'https://github.com/fixture/repo',description:'Synthetic',visibility:'Private',issues:0,pull_requests:2,
  commit:{url:'https://github.com/fixture/repo/commit/abc',summary:'Fixture commit',date:'2026-11-03T00:00:00Z'},
}]};
const button=root=>root.root.findByType('button');
(async()=>{
  let root; await act(async()=>{root=renderer.create(React.createElement(moduleValue.exports.default));});
  assert.match(JSON.stringify(root.toJSON()),/Loading repositories/);
  await act(async()=>respond({ok:true,json:async()=>payload}));
  assert.equal(root.root.findAllByType('article').length,1);
  assert.match(JSON.stringify(root.toJSON()),/Some repository data is unavailable/);
  assert.equal(root.root.findAllByType('a').length,5);
  await act(async()=>{button(root).props.onClick();});
  assert.equal(root.root.findAllByType('article').length,0,'old private cards removed during refresh');
  await act(async()=>respond({ok:false,json:async()=>({detail:'Sign in again'})}));
  assert.match(JSON.stringify(root.toJSON()),/Sign in again/);
  assert.doesNotMatch(JSON.stringify(root.toJSON()),/fixture\/repo/);
  await act(async()=>{button(root).props.onClick();});
  await act(async()=>respond({ok:true,json:async()=>({...payload,repositories:[],partial:false})}));
  assert.match(JSON.stringify(root.toJSON()),/No accessible repositories/);
  let stale; await act(async()=>{button(root).props.onClick();stale=respond;root.unmount();});
  await act(async()=>stale({ok:true,json:async()=>payload}));
  assert.equal(calls,4); console.log('Projects loading, partial, links, empty, auth failure, privacy clearing and unmount race passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
