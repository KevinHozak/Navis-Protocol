import { readFileSync, mkdtempSync, writeFileSync, rmSync, rmdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve, join } from 'node:path';

export const recoveryPaths = new Set([
  '.github/workflows/recovery-offline.yml', '.husky/pre-push',
  'scripts/test-packaged-recovery.ps1', 'scripts/packaged-recovery-policy.psm1',
  'scripts/test-packaged-recovery-policy.ps1', 'scripts/install-actionlint.ps1',
  'scripts/check-recovery-workflow.ps1', 'scripts/test-recovery-workflow-lint.ps1',
  'scripts/check-recovery-workflow-push.mjs', 'scripts/test-recovery-workflow-push.mjs',
  'docs/packaged-recovery-harness.md', 'docs/webview-process-investigation.md',
]);

export function requiresWorkflowLint(input, pathsForRange) {
  let needed = false;
  for (const line of input.trim().split(/\r?\n/).filter(Boolean)) {
    const fields = line.trim().split(/\s+/);
    if (fields.length !== 4 || !fields[1].match(/^[a-f0-9]{40,64}$/i) || !fields[3].match(/^[a-f0-9]{40,64}$/i)) {
      throw new Error('Invalid pre-push ref record; refusing to skip workflow validation.');
    }
    const [, local, , remote] = fields;
    if (/^0+$/.test(local)) continue; // Deleting a ref publishes no workflow content.
    if (pathsForRange(local, remote).some(path => recoveryPaths.has(path))) needed = true;
  }
  return needed;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  function git(args) {
    const result = spawnSync('git', args, { encoding: 'utf8' });
    if (result.error || result.status !== 0) throw result.error ?? new Error(result.stderr || 'Git range inspection failed');
    return result.stdout.trim().split(/\r?\n/).filter(Boolean);
  }
  const commits = new Set();
  const needed = requiresWorkflowLint(readFileSync(0, 'utf8'), (local, remote) => {
    let paths;
    if (!/^0+$/.test(remote) && spawnSync('git', ['cat-file', '-e', `${remote}^{commit}`]).status === 0) {
      paths = git(['diff', '--name-only', remote, local]);
    } else {
      // A new branch or unavailable remote object is checked conservatively.
      paths = git(['ls-tree', '-r', '--name-only', local]);
    }
    if (paths.some(path => recoveryPaths.has(path))) commits.add(local);
    return paths;
  });
  if (needed) {
    for (const commit of commits) {
      const directory = mkdtempSync(join(tmpdir(), 'navis-workflow-push-'));
      const workflow = join(directory, 'recovery-offline.yml');
      try {
        writeFileSync(workflow, git(['show', `${commit}:.github/workflows/recovery-offline.yml`]).join('\n') + '\n');
        console.log(`Validating recovery workflow from pushed commit ${commit}`);
        const result = spawnSync('pwsh', ['-NoProfile', '-NonInteractive', '-File', fileURLToPath(new URL('check-recovery-workflow.ps1', import.meta.url)), '-WorkflowPath', workflow], { stdio: 'inherit' });
        if (result.error) throw result.error;
        if (result.status !== 0) { process.exitCode = result.status || 1; break; }
      } finally {
        rmSync(workflow, { force: true });
        rmdirSync(directory);
      }
    }
  } else console.log('No recovery workflow changes to validate.');
}
