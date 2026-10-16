import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

// 1. Verify TasksCockpit Component Contracts
const cockpitSource = await readFile(new URL('../src/components/TasksCockpit.js', import.meta.url), 'utf8');

// Acceptance Criteria 1: Central Tasks Cockpit view renders and switches between Today and Upcoming
assert.match(cockpitSource, /id:\s*'today',\s*label:\s*'Today'/, 'TasksCockpit must contain Today view tab');
assert.match(cockpitSource, /id:\s*'upcoming',\s*label:\s*'Upcoming \(7-Day Agenda\)'/, 'TasksCockpit must contain Upcoming (7-Day Agenda) view tab');
assert.match(cockpitSource, /viewTab === 'today'/, 'TasksCockpit must conditionally render Today view section');
assert.match(cockpitSource, /viewTab === 'upcoming'/, 'TasksCockpit must conditionally render Upcoming agenda section');

// Acceptance Criteria 2: Priority-colored check rings (P1 Red, P2 Orange, P3 Blue, P4 Gray) & Due date status badges
assert.match(cockpitSource, /border-red-500/, 'TasksCockpit must style P1 ring with Red border');
assert.match(cockpitSource, /border-amber-500/, 'TasksCockpit must style P2 ring with Orange/Amber border');
assert.match(cockpitSource, /border-sky-500/, 'TasksCockpit must style P3 ring with Blue/Sky border');
assert.match(cockpitSource, /border-zinc-500/, 'TasksCockpit must style P4 ring with Gray/Zinc border');

assert.match(cockpitSource, /formatDateBadge/, 'TasksCockpit must format due date status badges');
assert.match(cockpitSource, /⚠️ Overdue/, 'TasksCockpit must render Overdue status badge');
assert.match(cockpitSource, /⚡ Today/, 'TasksCockpit must render Today status badge');
assert.match(cockpitSource, /🌅 Tomorrow/, 'TasksCockpit must render Tomorrow status badge');

// Acceptance Criteria 3: Expandable descriptions for markdown notes and clickable links
assert.match(cockpitSource, /toggleExpandNotes/, 'TasksCockpit must support expanding/collapsing task notes');
assert.match(cockpitSource, /<MarkdownRenderer\s+content=\{task\.description\}/, 'TasksCockpit must render markdown notes via MarkdownRenderer');

// Acceptance Criteria 4: Filter bar slicing by Manor and active labels
const manors = ['Sanctum', 'Domestic', 'Front', 'Gauntlet', 'Outland'];
for (const manor of manors) {
  assert.ok(cockpitSource.includes(manor), `TasksCockpit filter bar must include Manor ${manor}`);
}
assert.match(cockpitSource, /selectedLabel/, 'TasksCockpit must support filtering by active label chips');
assert.match(cockpitSource, /availableLabels/, 'TasksCockpit must extract active labels across tasks');

// 2. Verify TaskModal Component Contracts
const modalSource = await readFile(new URL('../src/components/TaskModal.js', import.meta.url), 'utf8');

// Acceptance Criteria 5: Task creation modal allows submitting tasks with due dates, priority, labels, and notes
assert.match(modalSource, /Directive Title/, 'TaskModal must include title field');
assert.match(modalSource, /Target Due Date/, 'TaskModal must include due date picker');
assert.match(modalSource, /Priority Tier/, 'TaskModal must include priority tier selector (P1-P4)');
assert.match(modalSource, /Directive Labels/, 'TaskModal must include label tag input');
assert.match(modalSource, /Dossier Notes & Markdown Details/, 'TaskModal must include description notes textarea');
assert.match(modalSource, /apiFetch\('\/api\/active_tasks'/, 'TaskModal must submit active tasks to /api/active_tasks');
assert.match(modalSource, /apiFetch\('\/api\/recurring'/, 'TaskModal must submit recurring tasks to /api/recurring');

// 3. Verify Top Navigation Registration
const backendSource = await readFile(new URL('../../backend/main.py', import.meta.url), 'utf8');
const pageSource = await readFile(new URL('../src/app/page.js', import.meta.url), 'utf8');
const sectorViewSource = await readFile(new URL('../src/components/SectorView.js', import.meta.url), 'utf8');
const vaultSource = await readFile(new URL('../src-tauri/src/vault.rs', import.meta.url), 'utf8');

// Check backend SECTOR_MAP and get_entities
assert.match(backendSource, /"COMMAND":\s*\[[\s\S]*?\{"id":\s*"DIRECTIVES",\s*"label":\s*"Directives",\s*"icon":\s*"📋"\}/, 'backend SECTOR_MAP must register DIRECTIVES under COMMAND');
assert.match(backendSource, /elif sectorId in \("DIRECTIVES", "TASKS"\):\s*entities = \[\s*\{"id": "TASKS_COCKPIT", "name": "Directives Cockpit", "type": "virtual"\}\s*\]/, 'backend get_entities must return TASKS_COCKPIT for DIRECTIVES');

// Check frontend page.js and SectorView.js
assert.match(pageSource, /'DIRECTIVES'/, 'page.js must register DIRECTIVES sector in dashboardSectors and hide EntityRail');
assert.match(sectorViewSource, /import TasksCockpit from '\.\/TasksCockpit'/, 'SectorView must import TasksCockpit');
assert.match(sectorViewSource, /sectorId === 'DIRECTIVES' \|\| activeEntity\?\.id === 'TASKS_COCKPIT'/, 'SectorView must render TasksCockpit for DIRECTIVES sector');

// Check Tauri desktop vault.rs parity
assert.match(vaultSource, /"COMMAND"\s*=>\s*json!\(\[[\s\S]*?\{"id":"DIRECTIVES","label":"Directives","icon":"📋"\}/, 'vault.rs navigation must register DIRECTIVES under COMMAND');
assert.match(vaultSource, /"DIRECTIVES" \| "TASKS"\s*=>\s*Some\(json!\(\[\s*\{"id":\s*"TASKS_COCKPIT"/, 'vault.rs list_entities must register TASKS_COCKPIT');

console.log('Central Tasks Cockpit, Agenda filtering, Priority rings, TaskModal, and Navigation checks passed.');
