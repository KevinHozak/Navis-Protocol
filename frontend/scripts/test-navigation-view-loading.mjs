import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const pageSource = await readFile(new URL('../src/app/page.js', import.meta.url), 'utf8');
const backendSource = await readFile(new URL('../../backend/main.py', import.meta.url), 'utf8');

const operationPillars = ['SANCTUM', 'DOMESTIC', 'FRONT', 'GAUNTLET', 'OUTLAND'];

for (const pillarId of operationPillars) {
  const primarySectorPattern = new RegExp(
    `"${pillarId}":\\s*\\[\\s*\\{\\s*"id":\\s*"${pillarId}"`,
  );
  assert.match(
    backendSource,
    primarySectorPattern,
    `${pillarId} must have a unique primary sector ID so navigation triggers a new data load.`,
  );
}

assert.match(
  pageSource,
  /setActiveSector\(firstSector\);/,
  'Selecting a pillar must activate its primary sector.',
);
assert.match(
  pageSource,
  /apiFetch\(`\/api\/entities\?sectorId=\$\{encodeURIComponent\(activeSector\)\}`(?:,\s*\{[\s\S]*?\})?\)/,
  'Active sectors must load their entities through the configured API client.',
);
assert.match(
  pageSource,
  /setEntities\(\[\]\);\s*setActiveEntity\(null\);\s*setEntityLoadError\(null\);\s*setEntityContent\(''\);\s*setContentLoadError\(null\);/,
  'Changing sectors must clear stale content before the next response arrives.',
);

console.log('Navigation view-loading regression check passed.');
