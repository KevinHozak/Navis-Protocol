import { existsSync, mkdtempSync, mkdirSync, copyFileSync, rmSync, lstatSync, readlinkSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { isPrivatePath } from './publication-policy.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const mode = process.argv[2] ?? '--history';
if (!['--history', '--staged', '--tree'].includes(mode)) {
  console.error('Usage: node scripts/scan-secrets.mjs [--history|--staged|--tree]');
  process.exit(2);
}

const gitArgs = mode === '--history'
  ? ['log', '--all', '--format=', '--name-only']
  : mode === '--staged'
    ? ['diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z']
    : ['ls-files', '-z'];
const listing = spawnSync('git', gitArgs, {
  cwd: root, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024,
});
if (listing.error || listing.status !== 0) {
  console.error('Cannot inspect Git files; secret scanning failed closed.');
  process.exit(2);
}
const names = [...new Set(listing.stdout.split(mode === '--history' ? '\n' : '\0').filter(Boolean))];
const forbidden = names.filter(isPrivatePath);
if (forbidden.length) {
  console.error(`Publication check blocked: ${forbidden.length} private/generated paths in ${mode.slice(2)}.`);
  forbidden.slice(0, 20).forEach((name) => console.error(`  ${name}`));
  console.error('Remove them from the index; historical paths require the cleaned publication repository.');
  process.exit(1);
}

const localBinary = path.join(root, '.tools', 'gitleaks', process.platform === 'win32' ? 'gitleaks.exe' : 'gitleaks');
const binary = existsSync(localBinary) ? localBinary : 'gitleaks';
const common = ['--redact=100', '--no-banner', '--ignore-gitleaks-allow'];
let snapshot;
if (mode === '--tree') {
  snapshot = mkdtempSync(path.join(tmpdir(), 'navis-tracked-scan-'));
  try {
    for (const name of names) {
      const source = path.resolve(root, name);
      if (!source.startsWith(path.resolve(root) + path.sep)) {
        throw new Error('Tracked path is outside the repository.');
      }
      if (!existsSync(source)) continue;
      const destination = path.join(snapshot, name);
      mkdirSync(path.dirname(destination), { recursive: true });
      if (lstatSync(source).isSymbolicLink()) {
        writeFileSync(destination, readlinkSync(source));
      } else {
        copyFileSync(source, destination);
      }
    }
  } catch {
    rmSync(snapshot, { recursive: true, force: true });
    console.error('Cannot prepare tracked-file scan; secret scanning failed closed.');
    process.exit(2);
  }
}
const args = mode === '--staged'
  ? ['git', '--pre-commit', '--staged', ...common, root]
  : mode === '--tree'
    ? ['dir', ...common, snapshot]
    : ['git', '--log-opts=--all', ...common, root];
const result = spawnSync(binary, args, { cwd: root, stdio: 'inherit' });
if (snapshot) rmSync(snapshot, { recursive: true, force: true });
if (result.error) {
  console.error('Gitleaks is required. Run scripts/install-gitleaks.ps1 on Windows, or install the pinned version documented in docs/public-repo-hygiene.md.');
  process.exit(2);
}
process.exit(result.status ?? 2);
