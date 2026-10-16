import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const pageSource = await readFile(new URL('../src/app/page.js', import.meta.url), 'utf8');
const sectorSource = await readFile(new URL('../src/components/SectorView.js', import.meta.url), 'utf8');
const backendSource = await readFile(new URL('../../backend/main.py', import.meta.url), 'utf8');

assert.match(pageSource, /loadingEntities=\{loadingEntities\}/);
assert.match(pageSource, /entityLoadError=\{entityLoadError\}/);
assert.match(pageSource, /onRetryEntityLoad=\{retryEntityLoad\}/);
assert.match(sectorSource, /sectorId === 'SYNTHESIS_LAB'/);
assert.match(sectorSource, /Calibrating synthesis archive/);
assert.match(sectorSource, /Archive request failed/);
assert.match(sectorSource, /\(entityLoadError \|\| contentLoadError\) && !activeEntity/);
assert.match(sectorSource, /entityLoadError\?\.message \|\| contentLoadError/);
assert.match(sectorSource, /Retry archive load/);
assert.match(sectorSource, /No archived entries yet/);
assert.match(sectorSource, /<ForgePanel initialType="Companion" \/>/);
assert.match(backendSource, /sectorId == "SYNTHESIS_LAB"/);
assert.match(backendSource, /SYNTHESIS_LAB.*?Archival/s);

console.log('Synthesis Lab regression check passed.');
