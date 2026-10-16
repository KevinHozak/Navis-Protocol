import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const sourceRoot = resolve(process.cwd(), 'src');
const bridgeHomeSource = await readFile(resolve(sourceRoot, 'components/BridgeHome.js'), 'utf8');
const sectorViewSource = await readFile(resolve(sourceRoot, 'components/SectorView.js'), 'utf8');
const backendMainSource = await readFile(resolve(process.cwd(), '../backend/main.py'), 'utf8');

// ============================================================================
// 1. Static Contract Checks
// ============================================================================

// Check that hardcoded fixed values are removed from BridgeHome
assert.doesNotMatch(
  bridgeHomeSource,
  />2026-05-19</,
  'BridgeHome must not contain the hardcoded Chrono Marker date 2026-05-19.',
);
assert.doesNotMatch(
  bridgeHomeSource,
  />88%</,
  'BridgeHome must not contain the hardcoded System Integrity value 88%.',
);
assert.doesNotMatch(
  bridgeHomeSource,
  /w-\[40%\]/,
  'BridgeHome must not hardcode fixed widths for readiness integrity bars.',
);
assert.doesNotMatch(
  bridgeHomeSource,
  /status\?\.current_realm\s*\|\|\s*['"]Canaan House['"]/,
  'BridgeHome must not fall back to hardcoded Canaan House when realm is unavailable.',
);

// Check authoritative telemetry and explicit unavailable states
assert.match(
  bridgeHomeSource,
  /isChronoAvailable\s*\?\s*chronoMarker\s*:\s*['"]UNAVAILABLE['"]/,
  'BridgeHome must display explicit UNAVAILABLE state when Chrono Marker is missing.',
);
assert.match(
  bridgeHomeSource,
  /isRealmAvailable\s*\?\s*currentRealm\s*:\s*['"]UNAVAILABLE['"]/,
  'BridgeHome must display explicit UNAVAILABLE state when Spatial Anchor realm is missing.',
);
assert.match(
  bridgeHomeSource,
  /isIntegrityAvailable\s*\?\s*`\$\{systemIntegrity\}%`\s*:\s*['"]UNAVAILABLE['"]/,
  'BridgeHome must display explicit UNAVAILABLE state when System Integrity is missing.',
);
assert.match(
  bridgeHomeSource,
  /bar\.available\s*\?\s*`\$\{bar\.value\}%`\s*:\s*['"]UNAVAILABLE['"]/,
  'BridgeHome must display explicit UNAVAILABLE state for individual missing manor bars.',
);

// Check prop synchronization without remounting
assert.match(
  bridgeHomeSource,
  /useEffect\(\(\)\s*=>\s*\{[\s\S]*?setStatus\(initialStatus\)[\s\S]*?setActiveMissions[\s\S]*?\},\s*\[initialStatus\]\)/,
  'BridgeHome must sync status and active missions when parent status prop changes.',
);

// Check mission save verification, error handling and optimistic rollback
assert.match(
  bridgeHomeSource,
  /if\s*\(!res\.ok\)\s*\{[\s\S]*?throw new Error/,
  'handleMissionSelect must check response status and throw on failure.',
);
assert.match(
  bridgeHomeSource,
  /setActiveMissions\(previousMissions\)/,
  'handleMissionSelect must roll back optimistic mission updates on save failure.',
);
assert.match(
  bridgeHomeSource,
  /setSaveError\(/,
  'handleMissionSelect must set visible error state on save failure.',
);
assert.match(
  bridgeHomeSource,
  /data-testid=["']mission-save-error["']/,
  'BridgeHome must render a visible error alert when mission save fails.',
);

// Check SectorView wiring
assert.match(
  sectorViewSource,
  /<BridgeHome[\s\S]*?onRefreshStatus=\{onRefreshStatus\}/,
  'SectorView must pass onRefreshStatus callback down to BridgeHome.',
);

// Check backend slot range validation
assert.match(
  backendMainSource,
  /if 0 <= req\.slot_index < len\(status\["active_missions"\]\):[\s\S]*?else:[\s\S]*?raise HTTPException\(\s*status_code=400/,
  'backend set_active_mission must validate slot_index and return 400 for out-of-range requests.',
);

// ============================================================================
// 2. Telemetry and Readiness Metric Resolution Logic
// ============================================================================

const {
  resolveMetric,
  resolveChronoMarker,
  resolveSpatialAnchor,
  resolveResolvedBars,
  resolveSystemIntegrity,
  READINESS_CATEGORIES,
} = await import(
  new URL('../src/lib/commandTelemetry.mjs', import.meta.url)
);

// Case A: Full readiness object with manor keys
const fullReadiness = {
  readiness: {
    'The Sanctum': { label: 'Sanctum Integrity', value: 95, color: '#00d4ff' },
    'The Domestic Breach': { label: 'Domestic Readiness', value: 80, color: '#00d4ff' },
    'The High-Velocity Front': { label: 'Frontline Status', value: 45, color: '#eab308' },
    'The Bureaucratic Gauntlet': { label: 'Gauntlet Flow', value: 20, color: '#ef4444' },
    'The Kinetic Outland': { label: 'Outland Mastery', value: 100, color: '#00d4ff' },
  },
};

const sanctumMetric = resolveMetric(fullReadiness, 'The Sanctum', 'Sanctum Integrity');
assert.equal(sanctumMetric.value, 95);
assert.equal(sanctumMetric.color, '#00d4ff');

const frontMetric = resolveMetric(fullReadiness, 'The High-Velocity Front', 'Frontline Status');
assert.equal(frontMetric.value, 45);
assert.equal(frontMetric.color, '#eab308');

// Case B: Readiness with flat object keyed by label
const flatLabelReadiness = {
  'Sanctum Integrity': 75,
  'Domestic Readiness': 60,
};
assert.equal(resolveMetric(flatLabelReadiness, 'The Sanctum', 'Sanctum Integrity').value, 75);
assert.equal(resolveMetric(flatLabelReadiness, 'The Domestic Breach', 'Domestic Readiness').value, 60);

// Case C: Missing / null telemetry returns null
assert.equal(resolveMetric(null, 'The Sanctum', 'Sanctum Integrity'), null);
assert.equal(resolveMetric({}, 'The Sanctum', 'Sanctum Integrity'), null);
assert.equal(resolveMetric({ readiness: {} }, 'The Sanctum', 'Sanctum Integrity'), null);

// Case D: Array format support
const arrayReadiness = [
  { manor: 'The Sanctum', value: 88, color: '#00d4ff' },
  { label: 'Domestic Readiness', value: 72 },
];
assert.equal(resolveMetric(arrayReadiness, 'The Sanctum', 'Sanctum Integrity').value, 88);
assert.equal(resolveMetric(arrayReadiness, 'The Domestic Breach', 'Domestic Readiness').value, 72);

// ============================================================================
// 3. Behavioral Simulation: Telemetry Transitions & Save Reconciliations
// ============================================================================

// Verify state transitions during telemetry update without remounting
function simulateHudState({ status, readiness }) {
  const chronoMarker = status?.last_updated || status?.date || status?.chrono_marker || null;
  const isChronoAvailable = Boolean(chronoMarker);
  const currentRealm = status?.current_realm || null;
  const isRealmAvailable = Boolean(currentRealm);

  const resolvedBars = READINESS_CATEGORIES.map((cat) => {
    const metric = resolveMetric(readiness, cat.key, cat.label);
    if (!metric) return { ...cat, available: false, value: null };
    return { ...cat, available: true, value: Math.max(0, Math.min(100, metric.value)) };
  });

  let systemIntegrity = null;
  let isIntegrityAvailable = false;
  if (typeof status?.system_integrity === 'number' && !isNaN(status.system_integrity)) {
    systemIntegrity = Math.max(0, Math.min(100, Math.round(status.system_integrity)));
    isIntegrityAvailable = true;
  } else {
    const availableValues = resolvedBars.filter((b) => b.available).map((b) => b.value);
    if (availableValues.length > 0) {
      const sum = availableValues.reduce((acc, curr) => acc + curr, 0);
      systemIntegrity = Math.round(sum / availableValues.length);
      isIntegrityAvailable = true;
    }
  }

  const activeMissions = Array.isArray(status?.active_missions) ? status.active_missions : [];

  return {
    chronoMarker: isChronoAvailable ? chronoMarker : 'UNAVAILABLE',
    currentRealm: isRealmAvailable ? currentRealm : 'UNAVAILABLE',
    systemIntegrity: isIntegrityAvailable ? `${systemIntegrity}%` : 'UNAVAILABLE',
    bars: Object.fromEntries(resolvedBars.map((b) => [b.key, b.available ? `${b.value}%` : 'UNAVAILABLE'])),
    activeMissions,
  };
}

// 1. Initial payload
const hudPayloadA = {
  status: {
    last_updated: '2026-09-28',
    current_realm: 'Earth',
    active_missions: ['Midnight Restoration', 'Cognitive Offload'],
  },
  readiness: {
    'The Sanctum': 50,
    'The Domestic Breach': 50,
  },
};
const stateA = simulateHudState(hudPayloadA);
assert.equal(stateA.chronoMarker, '2026-09-28');
assert.equal(stateA.currentRealm, 'Earth');
assert.equal(stateA.systemIntegrity, '50%');
assert.equal(stateA.bars['The Sanctum'], '50%');
assert.equal(stateA.bars['The High-Velocity Front'], 'UNAVAILABLE');
assert.deepEqual(stateA.activeMissions, ['Midnight Restoration', 'Cognitive Offload']);

// 2. Updated payload (simulating realm-hop and sync telemetry update without remounting)
const hudPayloadB = {
  status: {
    last_updated: '2026-10-01',
    current_realm: 'Emerald Sea',
    system_integrity: 92,
    active_missions: ['Texas Expedition', 'Deep Play'],
  },
  readiness: {
    'The Sanctum': 90,
    'The Domestic Breach': 95,
    'The High-Velocity Front': 90,
    'The Bureaucratic Gauntlet': 90,
    'The Kinetic Outland': 95,
  },
};
const stateB = simulateHudState(hudPayloadB);
assert.equal(stateB.chronoMarker, '2026-10-01');
assert.equal(stateB.currentRealm, 'Emerald Sea');
assert.equal(stateB.systemIntegrity, '92%');
assert.equal(stateB.bars['The Sanctum'], '90%');
assert.equal(stateB.bars['The Kinetic Outland'], '95%');
assert.deepEqual(stateB.activeMissions, ['Texas Expedition', 'Deep Play']);

// 3. Completely missing telemetry payload displays explicit UNAVAILABLE states
const emptyPayload = { status: {}, readiness: {} };
const emptyState = simulateHudState(emptyPayload);
assert.equal(emptyState.chronoMarker, 'UNAVAILABLE');
assert.equal(emptyState.currentRealm, 'UNAVAILABLE');
assert.equal(emptyState.systemIntegrity, 'UNAVAILABLE');
assert.equal(emptyState.bars['The Sanctum'], 'UNAVAILABLE');
assert.equal(emptyState.bars['The Domestic Breach'], 'UNAVAILABLE');
assert.deepEqual(emptyState.activeMissions, []);

// 4. Mission save failure reconciliation simulation
async function simulateMissionAssignment({ initialMissions, slotIndex, missionName, mockResponse }) {
  let activeMissions = [...initialMissions];
  let visibleError = null;

  const previousMissions = [...activeMissions];
  // Optimistic update
  activeMissions[slotIndex] = missionName;

  try {
    const res = await mockResponse();
    if (!res.ok) {
      throw new Error(`Save failed (${res.status})`);
    }
    const data = await res.json();
    if (Array.isArray(data?.active_missions)) {
      activeMissions = data.active_missions;
    }
  } catch (err) {
    // Reconcile: rollback optimistic assignment
    activeMissions = previousMissions;
    visibleError = err.message;
  }

  return { activeMissions, visibleError };
}

// Successful save: persists authoritative response
const successRun = await simulateMissionAssignment({
  initialMissions: ['Old Mission', 'Restoration'],
  slotIndex: 0,
  missionName: 'New Operation',
  mockResponse: async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      status: 'success',
      active_missions: ['New Operation', 'Restoration'],
    }),
  }),
});
assert.deepEqual(successRun.activeMissions, ['New Operation', 'Restoration']);
assert.equal(successRun.visibleError, null);

// Failed save (HTTP 500): rolls back optimistic state and sets visible error
const failedRun = await simulateMissionAssignment({
  initialMissions: ['Old Mission', 'Restoration'],
  slotIndex: 0,
  missionName: 'Broken Save Mission',
  mockResponse: async () => ({
    ok: false,
    status: 500,
    json: async () => ({ detail: 'Database error' }),
  }),
});
assert.deepEqual(
  failedRun.activeMissions,
  ['Old Mission', 'Restoration'],
  'Failed save must not retain optimistic mission values.',
);
assert.match(
  failedRun.visibleError,
  /Save failed \(500\)/,
  'Failed save must record an explicit visible error.',
);

console.log('Command telemetry and mission saves regression checks passed.');
