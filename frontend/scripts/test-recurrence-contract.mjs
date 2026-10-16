import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { journalDay } from '../src/lib/journalDay.js';

process.env.TZ = 'America/Chicago';
const fixture = JSON.parse(readFileSync(new URL('../../tests/recurrence-contract.json', import.meta.url)));
for (const row of fixture.instants) {
  assert.equal(journalDay(new Date(row.local)), row.day, row.local);
}
console.log(`Passed ${fixture.instants.length} local-day cases, including UTC crossover and both DST transitions.`);
