import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

// Explicit list avoids discovering ad hoc scripts that may use live services.
const scripts = [
  'test-keeper-entity-recovery.mjs',
  'test-map-loading-recovery.mjs',
  'test-codex-roster.mjs',
  'test-bestiary.mjs',
  'test-warroom-recovery.mjs',
  'test-checkbox-contract.mjs', 'test-checkbox-renderer.mjs', 'test-horizon-roadmap.mjs',
  'test-top-navigation-icons.mjs', 'test-navigation-view-loading.mjs',
  'test-moongate-loading.mjs', 'test-map-node-validation.mjs',
  'test-map-realm-navigation.mjs', 'test-map-telemetry.mjs',
  'test-synthesis-lab.mjs', 'test-journal-entry-flow.mjs',
  'test-desktop-api-boundary.mjs', 'test-native-capabilities.mjs', 'test-banter-recovery.mjs',
  'test-task-board-failures.mjs', 'test-directive-completion.mjs', 'test-progression-flow.mjs', 'test-stale-navigation-nested-dossiers.mjs',
  'test-command-telemetry-mission-saves.mjs',
  'test-recurrence-contract.mjs',
  'test-native-squad-combat-routes.mjs',
  'test-combat-theater-assets.mjs',
  'test-combat-synergies.mjs',
  'test-vault-change-event.mjs',
  'test-reactive-client-invalidation.mjs',
  'test-operation-outcomes.cjs',
  'test-tasks-cockpit.mjs',
  'test-e2e-sector-boards.mjs',
  'test-constellation-talents.mjs',
];
for (const script of scripts) {
  const result = spawnSync(process.execPath, [fileURLToPath(new URL(script, import.meta.url))], {
    cwd: fileURLToPath(new URL('../', import.meta.url)), stdio: 'inherit',
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}
