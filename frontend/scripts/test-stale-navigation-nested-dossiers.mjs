import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const pageSource = await readFile(new URL('../src/app/page.js', import.meta.url), 'utf8');
const sectorViewSource = await readFile(new URL('../src/components/SectorView.js', import.meta.url), 'utf8');
const entityProfileSource = await readFile(new URL('../src/components/EntityProfile.js', import.meta.url), 'utf8');

// ============================================================================
// 1. Static Contract Checks
// ============================================================================

// Sector navigation abort controller & signal
assert.match(
  pageSource,
  /const controller = new AbortController\(\);[\s\S]*?apiFetch\(`\/api\/entities\?sectorId=\$\{encodeURIComponent\(activeSector\)\}`,\s*\{\s*signal:\s*controller\.signal\s*\}\)/,
  'Sector navigation must initiate an AbortController and pass its signal to apiFetch.',
);
assert.match(
  pageSource,
  /if \(controller\.signal\.aborted\) return;/,
  'Sector navigation must discard results if the request was aborted before state commit.',
);

// Content fetch abort controller, signal & loadedContentEntityId tracking
assert.match(
  pageSource,
  /const \[loadedContentEntityId,\s*setLoadedContentEntityId\] = useState\(null\);/,
  'page.js must declare loadedContentEntityId state to track content/entity alignment.',
);
assert.match(
  pageSource,
  /const controller = new AbortController\(\);[\s\S]*?apiFetch\(`\/api\/vault\/\$\{targetEntityId\}`, \{\s*signal:\s*controller\.signal,\s*cache:\s*'no-store'\s*\}\)/,
  'File content fetch must use AbortController and pass its signal to apiFetch.',
);
assert.match(
  pageSource,
  /setLoadedContentEntityId\(targetEntityId\);/,
  'Successful file content fetch must record the active entity ID for alignment checks.',
);

// Checkbox mutation alignment guards
assert.match(
  pageSource,
  /if \(loadingContent \|\| loadedContentEntityId !== activeEntity\.id\) \{/,
  'handleToggleCheckbox must guard against mutations when content is loading or misaligned with activeEntity.',
);
assert.match(
  pageSource,
  /if \(activeSector === 'JOURNAL'\) \{[\s\S]*?if \(!entityDate \|\| entityDate !== selectedJournalDate\)/,
  'handleToggleCheckbox must guard against mutations when journal date is misaligned with activeEntity.',
);

// Calendar date selection alignment
assert.match(
  pageSource,
  /handleEntitySelect\(\{\s*id: `Journal\/\$\{yyyy\}\/\$\{mm\}\/\$\{dateStr\}\.md`,\s*name: dateStr,\s*type: 'file'/m,
  'handleJournalDateSelect must synthesize a matching journal entity when not present in the current entities rail.',
);

// SectorView entity profile dispatch vs nested subdocument routing
assert.match(
  sectorViewSource,
  /\['Companions', 'Residents', 'Realms'\]\.includes\(pathParts\[0\]\)/,
  'SectorView must inspect path parts for entity profile types.',
);
assert.match(
  sectorViewSource,
  /if \(pathParts\.length === 2\) \{[\s\S]*?isEntityProfile = true;[\s\S]*?\} else if \(pathParts\.length === 3\) \{[\s\S]*?isProfileFile[\s\S]*?isEntityProfile = true;/,
  'SectorView must only designate directory or root Profile/Realm file as EntityProfile, leaving subdocuments for standard rendering.',
);

// EntityProfile abort handling & universal subdocuments
assert.match(
  entityProfileSource,
  /const controller = new AbortController\(\);[\s\S]*?apiFetch\(`\/api\/entity\/[\s\S]*?\{\s*signal:\s*controller\.signal\s*\}[\s\S]*?return \(\) => \{\s*controller\.abort\(\);/,
  'EntityProfile must abort obsolete fetch requests on unmount or entity change.',
);
assert.match(
  entityProfileSource,
  /data\.sub_documents && data\.sub_documents\.length > 0[\s\S]*?Local Archives & Planning/,
  'EntityProfile must render Local Archives & Planning subdocuments for non-Realm entities as well.',
);

// ============================================================================
// 2. Dynamic Interaction Simulation: Deliberately Reversed Sector Responses
// ============================================================================

{
  let state = {
    entities: [],
    activeEntity: null,
    loadingEntities: false,
    contentLoadError: null,
  };

  // Helper simulating the page.js sector fetch effect with AbortController
  let activeCleanup = null;

  function changeSector(newSector, fetchEntitiesMock) {
    if (activeCleanup) {
      activeCleanup();
      activeCleanup = null;
    }

    state.entities = [];
    state.activeEntity = null;
    state.contentLoadError = null;
    state.loadingEntities = true;

    const controller = new AbortController();
    const currentSector = newSector;

    fetchEntitiesMock(currentSector, controller.signal)
      .then((list) => {
        if (controller.signal.aborted) return;
        state.entities = list;
        state.activeEntity = list[0] || null;
      })
      .catch((error) => {
        if (controller.signal.aborted || error?.name === 'AbortError') return;
        state.contentLoadError = `Unable to load ${currentSector}: ${error.message}`;
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          state.loadingEntities = false;
        }
      });

    activeCleanup = () => controller.abort();
    return controller;
  }

  // Set up deferred responses for Sector A (slow) and Sector B (fast)
  let resolveSectorA, rejectSectorA;
  const sectorAPromise = new Promise((res, rej) => { resolveSectorA = res; rejectSectorA = rej; });

  let resolveSectorB;
  const sectorBPromise = new Promise((res) => { resolveSectorB = res; });

  const mockSectorFetch = (sectorId, signal) => {
    if (sectorId === 'SECTOR_A') {
      return new Promise((res, rej) => {
        signal.addEventListener('abort', () => rej(new DOMException('Aborted', 'AbortError')));
        sectorAPromise.then(res).catch(rej);
      });
    }
    if (sectorId === 'SECTOR_B') {
      return new Promise((res, rej) => {
        signal.addEventListener('abort', () => rej(new DOMException('Aborted', 'AbortError')));
        sectorBPromise.then(res).catch(rej);
      });
    }
    return Promise.resolve([]);
  };

  // 1. Navigate to Sector A
  const controllerA = changeSector('SECTOR_A', mockSectorFetch);
  assert.equal(controllerA.signal.aborted, false);
  assert.equal(state.loadingEntities, true);

  // 2. Quickly navigate to Sector B before Sector A finishes
  const controllerB = changeSector('SECTOR_B', mockSectorFetch);
  assert.equal(controllerA.signal.aborted, true, 'Sector A controller must be aborted on sector switch');
  assert.equal(controllerB.signal.aborted, false);

  // 3. Sector B finishes first
  resolveSectorB([{ id: 'entity_b_1', name: 'Entity B1' }]);
  await new Promise(process.nextTick);

  assert.deepEqual(state.entities, [{ id: 'entity_b_1', name: 'Entity B1' }]);
  assert.equal(state.activeEntity.id, 'entity_b_1');
  assert.equal(state.loadingEntities, false);
  assert.equal(state.contentLoadError, null);

  // 4. Sector A finishes LATER (deliberately reversed order)
  resolveSectorA([{ id: 'entity_a_stale', name: 'Stale A' }]);
  await new Promise(process.nextTick);

  // Assert: Sector A did NOT overwrite Sector B state
  assert.deepEqual(state.entities, [{ id: 'entity_b_1', name: 'Entity B1' }],
    'Stale Sector A response must NOT overwrite active Sector B entities');
  assert.equal(state.activeEntity.id, 'entity_b_1',
    'Stale Sector A response must NOT overwrite active Sector B activeEntity');
  assert.equal(state.contentLoadError, null,
    'Stale Sector A completion must NOT contaminate error state');
}

// ============================================================================
// 3. Dynamic Interaction Simulation: Deliberately Reversed File Content Responses
// ============================================================================

{
  let state = {
    entityContent: '',
    loadedContentEntityId: null,
    loadingContent: false,
    contentLoadError: null,
  };

  let activeCleanup = null;

  function selectEntityFile(entity, fetchContentMock) {
    if (activeCleanup) {
      activeCleanup();
      activeCleanup = null;
    }

    state.entityContent = '';
    state.loadedContentEntityId = null;
    state.loadingContent = true;

    const controller = new AbortController();
    const targetEntityId = entity.id;

    fetchContentMock(targetEntityId, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        state.entityContent = data.content || '';
        state.loadedContentEntityId = targetEntityId;
        state.contentLoadError = null;
        state.loadingContent = false;
      })
      .catch((err) => {
        if (controller.signal.aborted || err?.name === 'AbortError') return;
        state.contentLoadError = `Unable to load: ${err.message}`;
        state.entityContent = `Error: ${err.message}`;
        state.loadedContentEntityId = null;
        state.loadingContent = false;
      });

    activeCleanup = () => controller.abort();
    return controller;
  }

  let resolveFile1;
  const file1Promise = new Promise((res) => { resolveFile1 = res; });
  let resolveFile2;
  const file2Promise = new Promise((res) => { resolveFile2 = res; });

  const mockContentFetch = (fileId, signal) => {
    const targetPromise = fileId === 'file_1' ? file1Promise : file2Promise;
    return new Promise((res, rej) => {
      signal.addEventListener('abort', () => rej(new DOMException('Aborted', 'AbortError')));
      targetPromise.then(res).catch(rej);
    });
  };

  // Select File 1
  const ctrl1 = selectEntityFile({ id: 'file_1', type: 'file' }, mockContentFetch);
  assert.equal(ctrl1.signal.aborted, false);
  assert.equal(state.loadingContent, true);

  // Switch to File 2
  const ctrl2 = selectEntityFile({ id: 'file_2', type: 'file' }, mockContentFetch);
  assert.equal(ctrl1.signal.aborted, true, 'File 1 must be aborted when switching to File 2');

  // File 2 resolves first
  resolveFile2({ content: '# Content of File 2' });
  await new Promise(process.nextTick);

  assert.equal(state.entityContent, '# Content of File 2');
  assert.equal(state.loadedContentEntityId, 'file_2');
  assert.equal(state.loadingContent, false);

  // File 1 resolves later (reversed arrival)
  resolveFile1({ content: '# Stale Content of File 1' });
  await new Promise(process.nextTick);

  // Verify File 1 did not overwrite File 2
  assert.equal(state.entityContent, '# Content of File 2', 'Stale file response must not overwrite newer content');
  assert.equal(state.loadedContentEntityId, 'file_2', 'loadedContentEntityId must remain aligned with newer selection');
}

// ============================================================================
// 4. Alignment Simulation: Checkbox Mutations
// ============================================================================

{
  function canPerformCheckboxMutation({
    activeEntity,
    loadingContent,
    loadedContentEntityId,
    activeSector,
    selectedJournalDate,
  }) {
    if (!activeEntity || (activeEntity.type !== 'file' && activeEntity.type !== 'directory')) {
      return false;
    }
    if (loadingContent || loadedContentEntityId !== activeEntity.id) {
      return false;
    }
    if (activeSector === 'JOURNAL') {
      const entityDate = activeEntity.name?.match(/\d{4}-\d{2}-\d{2}/)?.[0] || activeEntity.id?.match(/\d{4}-\d{2}-\d{2}/)?.[0];
      if (!entityDate || entityDate !== selectedJournalDate) {
        return false;
      }
    }
    return true;
  }

  // Test Case A: Content is currently loading
  assert.equal(canPerformCheckboxMutation({
    activeEntity: { id: 'file_1', type: 'file' },
    loadingContent: true,
    loadedContentEntityId: null,
    activeSector: 'COMMAND',
    selectedJournalDate: '2026-10-01',
  }), false, 'Must reject mutation while content is still loading');

  // Test Case B: Loaded content belongs to a previous file
  assert.equal(canPerformCheckboxMutation({
    activeEntity: { id: 'file_2', type: 'file' },
    loadingContent: false,
    loadedContentEntityId: 'file_1', // Misaligned!
    activeSector: 'COMMAND',
    selectedJournalDate: '2026-10-01',
  }), false, 'Must reject mutation when loaded content is misaligned with active entity');

  // Test Case C: Journal date desync with active entity
  assert.equal(canPerformCheckboxMutation({
    activeEntity: { id: 'Journal/2026/05/2026-05-19.md', name: '2026-05-19', type: 'file' },
    loadingContent: false,
    loadedContentEntityId: 'Journal/2026/05/2026-05-19.md',
    activeSector: 'JOURNAL',
    selectedJournalDate: '2026-05-20', // Misaligned!
  }), false, 'Must reject mutation when journal date is misaligned with active journal entity');

  // Test Case D: Fully aligned state
  assert.equal(canPerformCheckboxMutation({
    activeEntity: { id: 'Journal/2026/05/2026-05-20.md', name: '2026-05-20', type: 'file' },
    loadingContent: false,
    loadedContentEntityId: 'Journal/2026/05/2026-05-20.md',
    activeSector: 'JOURNAL',
    selectedJournalDate: '2026-05-20',
  }), true, 'Must permit mutation when date, entity, and loaded content are perfectly aligned');
}

// ============================================================================
// 5. Nested Dossier Dispatch Function Test (SectorView.js Logic)
// ============================================================================

{
  function dispatchEntitySelection(activeEntity) {
    if (activeEntity?.type === 'file' || activeEntity?.type === 'directory') {
      const entityPath = activeEntity.path || activeEntity.id || '';
      const pathParts = entityPath.split(/[\\/]/).filter(Boolean);

      let isEntityProfile = false;
      let profileType = '';
      let profileName = '';

      if (['Companions', 'Residents', 'Realms'].includes(pathParts[0])) {
        if (pathParts.length === 2) {
          isEntityProfile = true;
          profileType = pathParts[0];
          profileName = pathParts[1];
        } else if (pathParts.length === 3) {
          const fileName = pathParts[2].toLowerCase();
          const isProfileFile = pathParts[0] === 'Realms'
            ? (fileName === 'realm.md' || fileName === 'profile.md')
            : fileName === 'profile.md';
          if (isProfileFile) {
            isEntityProfile = true;
            profileType = pathParts[0];
            profileName = pathParts[1];
          }
        }
      } else if (pathParts.length >= 3 && pathParts[0] === 'Obstacles' && ['Antagonists', 'Beasts'].includes(pathParts[1])) {
        if (pathParts.length === 3) {
          isEntityProfile = true;
          profileType = pathParts[1];
          profileName = pathParts[2];
        } else if (pathParts.length === 4 && pathParts[3].toLowerCase() === 'profile.md') {
          isEntityProfile = true;
          profileType = pathParts[1];
          profileName = pathParts[2];
        }
      }

      if (isEntityProfile) {
        return { target: 'EntityProfile', type: profileType, name: profileName };
      }
      if (activeEntity?.type === 'directory') {
        return { target: 'DirectoryListing', path: entityPath };
      }
      return { target: 'MarkdownRenderer', path: entityPath };
    }
    return { target: 'Other' };
  }

  // --- Realms ---
  // Parent Realm directory -> EntityProfile
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Realms/The Silver Spire', type: 'directory' }),
    { target: 'EntityProfile', type: 'Realms', name: 'The Silver Spire' }
  );
  // Root Realm.md -> EntityProfile
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Realms/The Silver Spire/Realm.md', type: 'file' }),
    { target: 'EntityProfile', type: 'Realms', name: 'The Silver Spire' }
  );
  // Nested subdocument in Local Archives & Planning -> MarkdownRenderer (BUG #10 FIX)
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Realms/The Silver Spire/Local Archives & Planning/Strategy.md', type: 'file' }),
    { target: 'MarkdownRenderer', path: 'Realms/The Silver Spire/Local Archives & Planning/Strategy.md' }
  );
  // Direct subdocument in realm root -> MarkdownRenderer
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Realms/The Silver Spire/Notes.md', type: 'file' }),
    { target: 'MarkdownRenderer', path: 'Realms/The Silver Spire/Notes.md' }
  );
  // Nested directory under Realm -> DirectoryListing
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Realms/The Silver Spire/Local Archives & Planning', type: 'directory' }),
    { target: 'DirectoryListing', path: 'Realms/The Silver Spire/Local Archives & Planning' }
  );

  // --- Companions ---
  // Companion directory -> EntityProfile
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Companions/Garrick', type: 'directory' }),
    { target: 'EntityProfile', type: 'Companions', name: 'Garrick' }
  );
  // Companion Profile.md -> EntityProfile
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Companions/Garrick/Profile.md', type: 'file' }),
    { target: 'EntityProfile', type: 'Companions', name: 'Garrick' }
  );
  // Companion nested document -> MarkdownRenderer
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Companions/Garrick/Journal/Doc.md', type: 'file' }),
    { target: 'MarkdownRenderer', path: 'Companions/Garrick/Journal/Doc.md' }
  );
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Companions/Garrick/Quests.md', type: 'file' }),
    { target: 'MarkdownRenderer', path: 'Companions/Garrick/Quests.md' }
  );

  // --- Residents ---
  // Resident directory -> EntityProfile
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Residents/Old Man', type: 'directory' }),
    { target: 'EntityProfile', type: 'Residents', name: 'Old Man' }
  );
  // Resident Profile.md -> EntityProfile
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Residents/Old Man/Profile.md', type: 'file' }),
    { target: 'EntityProfile', type: 'Residents', name: 'Old Man' }
  );
  // Resident subdocument -> MarkdownRenderer
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Residents/Old Man/Dialogue.md', type: 'file' }),
    { target: 'MarkdownRenderer', path: 'Residents/Old Man/Dialogue.md' }
  );

  // --- Obstacles: Beasts & Antagonists ---
  // Beast directory -> EntityProfile
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Obstacles/Beasts/Shadow Wolf', type: 'directory' }),
    { target: 'EntityProfile', type: 'Beasts', name: 'Shadow Wolf' }
  );
  // Beast Profile.md -> EntityProfile
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Obstacles/Beasts/Shadow Wolf/Profile.md', type: 'file' }),
    { target: 'EntityProfile', type: 'Beasts', name: 'Shadow Wolf' }
  );
  // Beast subdocument -> MarkdownRenderer
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Obstacles/Beasts/Shadow Wolf/Weaknesses.md', type: 'file' }),
    { target: 'MarkdownRenderer', path: 'Obstacles/Beasts/Shadow Wolf/Weaknesses.md' }
  );
  // Antagonist directory -> EntityProfile
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Obstacles/Antagonists/Malakor', type: 'directory' }),
    { target: 'EntityProfile', type: 'Antagonists', name: 'Malakor' }
  );
  // Antagonist Profile.md -> EntityProfile
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Obstacles/Antagonists/Malakor/Profile.md', type: 'file' }),
    { target: 'EntityProfile', type: 'Antagonists', name: 'Malakor' }
  );
  // Antagonist nested subdocument -> MarkdownRenderer
  assert.deepEqual(
    dispatchEntitySelection({ id: 'Obstacles/Antagonists/Malakor/Tactics/Phase2.md', type: 'file' }),
    { target: 'MarkdownRenderer', path: 'Obstacles/Antagonists/Malakor/Tactics/Phase2.md' }
  );
}

console.log('Stale navigation and nested dossier checks passed.');
