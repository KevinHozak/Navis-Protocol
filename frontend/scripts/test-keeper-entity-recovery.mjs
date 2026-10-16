import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const page = await readFile(new URL('../src/app/page.js', import.meta.url), 'utf8');
const rail = await readFile(new URL('../src/components/EntityRail.js', import.meta.url), 'utf8');
const view = await readFile(new URL('../src/components/SectorView.js', import.meta.url), 'utf8');
const backend = await readFile(new URL('../../backend/main.py', import.meta.url), 'utf8');
const native = await readFile(new URL('../src-tauri/src/vault.rs', import.meta.url), 'utf8');

assert.match(backend, /def _list_keeper_entities\(\):[\s\S]*?Configured Vault root is unavailable[\s\S]*?Keeper source directory is unavailable[\s\S]*?os\.listdir\(keeper_dir\)/);
assert.match(backend, /async def get_entities\(sectorId: str\):\s+if sectorId == "KEEPER":\s+return _list_keeper_entities\(\)/);
assert.match(native, /if sector == "KEEPER" \{[\s\S]*?resolve_relative_path\("Keeper"\)[\s\S]*?read_dir\(dir\)[\s\S]*?Some\("md"\)/);
assert.match(page, /setEntityLoadError\(\{[\s\S]*?kind:[\s\S]*?message:/);
assert.match(page, /\}, \[activeSector, entityRetryVersion\]\);/);
assert.match(rail, /filter \? 'No matching items' : activeSector === 'KEEPER' \? 'No Keeper records found'/);
assert.match(rail, /Retry Keeper load/);
assert.match(view, /sectorId === 'KEEPER' && loadingEntities/);
assert.match(view, /sectorId === 'KEEPER' && entityLoadError/);
assert.match(view, /sectorId === 'KEEPER' && !activeEntity && entities\.length === 0/);
assert.match(view, /Retry loading records/);
assert.match(view, /Select a Keeper record/);

console.log('Keeper entity recovery regression check passed.');
