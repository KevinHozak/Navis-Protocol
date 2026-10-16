import { spawnSync } from 'node:child_process';

const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const result = spawnSync(npmCommand, ['run', 'build'], {
  cwd: process.cwd(),
  env: { ...process.env, NAVIS_TAURI_BUILD: 'true' },
  stdio: 'inherit',
  shell: true,
});

if (result.error) {
  console.error(`Unable to start the desktop build: ${result.error.message}`);
  process.exit(1);
}

process.exit(result.status ?? 1);